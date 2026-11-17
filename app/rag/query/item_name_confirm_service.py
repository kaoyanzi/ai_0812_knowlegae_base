from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pymilvus import AnnSearchRequest

from app.infra.llm.providers import llm_provider
from app.infra.vectorstore.milvus_gateway import milvus_gateway
from app.process.query.agent.state import QueryGraphState
from app.infra.persistence.history_repository import history_repository
from app.rag.query.config import ITEM_NAME_CONFIRM_THRESHOLD, ITEM_NAME_CANDIDATE_THRESHOLD, ITEM_NAME_OPTIONS_TOPK
from app.shared.runtime.load_prompt import load_prompt
from app.shared.runtime.logger import logger, step_log



def validate_and_get_data(state:QueryGraphState) -> tuple[str,str]:
    session_id = state.get("session_id")
    original_query = state.get("original_query")

    if not session_id or not original_query:
        logger.error(f"session_id or original_query为空,业务无法继续,提前终止!!!")
        raise ValueError(f"session_id or original_query为空,业务无法继续,提前终止!!!")
    return session_id, original_query

def valid_chat_message(session_id:str) -> list[dict]:
    recent_message_list:list[dict]=history_repository.list_recent(session_id=session_id,limit=20)
    valid_message_list:list[dict]=[
        item
        for item in recent_message_list if item.get("item_names") and item.get("role")=="user"
    ]
    logger.info(f"查询近期聊天数据共计:{len(recent_message_list)}条,过滤筛选后有效数据为:{len(valid_message_list)}条")
    return valid_message_list

def call_llm_confirm_item_name_and_rewritten_query(message_list:list[dict],original_query:str) -> dict[str,str]:
    llm_client = llm_provider.chat(json_model = True)
    query = original_query
    history_text:str = ""
    if message_list:
        for index,message in enumerate(message_list,start=1):
            history_text += f"{index},原始问题:{message.get('text')},重写后的问题:{message.get('rewritten_query')},关联的item_name:{message.get('item_names')}\n"
    else:
        history_text = "没有有效的聊天记录"
    prompt_text:str = load_prompt("rewritten_query_and_itemnames",history_text= history_text,query=query)
    messages = [HumanMessage(content=prompt_text)]
    chains = llm_client | JsonOutputParser()
    result:dict = chains.invoke(messages)
    if "rewritten_query" not in result:
        logger.warning(f"模型重写问题失败,给rewritten_query赋予原始问题:{original_query}")
        result["rewritten_query"] = original_query
    if "item_names" not in result:
        logger.warning(f"模型识别商品失败,给item_names赋予空列表")
        result["item_names"] = []
    logger.info(f"完成本次主题识别和任务重写,结果为:{result}")
    return result

def milvus_hybrid_search(item_names:list[str]) -> dict[str,list[dict[str,Any]]]:
    milvus_client = milvus_gateway.client
    milvus_search_result:dict[str,list[dict[str,Any]]] = {}

    for item_name_llm in item_names:
        result = llm_provider.generate_infra_embeddings([item_name_llm])
        dense_vector = result["dense"][0]
        sparse_vector = result["sparse"][0]
        reqs:list[AnnSearchRequest] = milvus_gateway.create_requests(dense_vector=dense_vector,sparse_vector=sparse_vector,limit=5*2)
        milvus_result = milvus_gateway.hybrid_search(
            collection_name=milvus_gateway.chunks_collection,
            reqs=reqs,
            ranker_weights=(0.5,0.5),
            norm_score=True,
            limit=5
        )
        if milvus_result and milvus_result[0]:
            milvus_item_name_list:list[dict[str,Any]]=[
                {"item_name": item.get("entity",{}).get("item_name"),"score":item.get("distance",0.0)}
                for item in milvus_result[0]
            ]
            logger.debug(f"大模型识别item_name:{item_name_llm},查询出相关数据:{milvus_item_name_list}")
            milvus_search_result[item_name_llm] = milvus_item_name_list
        else:
            logger.warning(f"大模型识别item_name:{item_name_llm},没有查询到任何相关数据!!!")

    return milvus_search_result

def select_item_names(milvus_result:dict[str,list[dict[str,Any]]]) -> dict[str,list[str]]:
    confirmed_item_name_list:list[str] = []
    optional_item_name_list:list[str] = []
    for _,milvus_item_list in milvus_result.items():
        confirmed_list:list[dict] = [
            item
            for item in milvus_item_list if item.get("score",0.0)> ITEM_NAME_CONFIRM_THRESHOLD
        ]
        if confirmed_list:
            confirmed_item_name_list.append(confirmed_list[0].get("item_name"))
            continue
        optional_list: list[dict] = [
            item
            for item in milvus_item_list if ITEM_NAME_CANDIDATE_THRESHOLD< item.get("score", 0.0) < ITEM_NAME_CONFIRM_THRESHOLD
        ]
        if optional_list:
            optional_item_name_list.extend([item.get("item_name") for item in optional_list[:ITEM_NAME_OPTIONS_TOPK]])
            continue
    return {
        "confirmed_item_name_list":confirmed_item_name_list,
        "optional_item_name_list":optional_item_name_list
    }

def update_query_state(item_list:dict[str,list[str]],rewritten_query:str,state:QueryGraphState):
    confirmed_item_name_list:list[str] = item_list.get("confirmed_item_name_list")
    optional_item_name_list: list[str] = item_list.get("optional_item_name_list")
    if confirmed_item_name_list:
        state['item_names'] = confirmed_item_name_list
        state['rewritten_query'] = rewritten_query
        return
    if optional_item_name_list:
        state['answer'] = f"没有明确的主题名,但是有相似的:{','.join(optional_item_name_list)}请您确定后返回"
        return
    state['answer'] = f"没有任何的匹配名,请确认后,再次提问!"

def save_user_chat_message(session_id:str,original_query:str,rewritten_query:str,item_names):
    history_repository.save_message(
        session_id=session_id,
        role="user",
        text = original_query,
        rewritten_query=rewritten_query,
        item_names=item_names,
        image_urls=[]
    )
    logger.info(f"完成{ '有效' if item_names else '无效'}")
def confirm_item_name(state: QueryGraphState) -> QueryGraphState:
    #1. 检验和参数获取
    session_id,original_query = validate_and_get_data(state)
    #2. 获取有效聊天记录
    valid_message_list:list[dict] = valid_chat_message(session_id=session_id)
    #3. 调用模型进行主题识别和问题重写
    result  = call_llm_confirm_item_name_and_rewritten_query(valid_message_list,original_query)
    #4. 进行向量数据库查询
    milvus_search_result:dict[str,list[dict[str,Any]]] = milvus_hybrid_search(item_names=result.get("item_names"))
    #5. 获取确认和可选的数据列表
    item_name_dict:dict[str,list[str]] = select_item_names(milvus_search_result)
    #6. 修改state对应的数据
    update_query_state(item_name_dict,result.get("rewritten_query"),state)
    #7. 保存聊天记录
    save_user_chat_message(session_id,original_query,result.get("rewritten_query"),state.get("item_names",[]))
    #8. 返回state
    return state