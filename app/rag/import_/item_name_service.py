import json
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from pymilvus import MilvusClient, DataType

from app.process.import_.agent.state import ImportGraphState
from app.rag.import_.config import ITEM_NAME_RECOGNITION_CHUNKS_TOP_K
from app.shared.runtime.logger import  logger
from app.infra.llm.providers import llm_provider
from app.shared.runtime.load_prompt import load_prompt
from app.infra.vectorstore.milvus_gateway import milvus_gateway


def validate_and_get_data(state: ImportGraphState) -> tuple[str,list[dict[str, Any]]]:
    file_title = state.get("file_title")
    chunks:list[dict[str, Any]] = state.get("chunks")
    md_path:str = state.get("md_path")
    if not chunks:
        if md_path or Path(md_path).is_file():
            json_file_obj:Path = Path(md_path) / "chunks.json"
            #数据备份
            #json_file_obj.write_text(json.dumps(chunks, indent=4, ensure_ascii=False),encoding="utf-8")
            #数据还原
            chunks = json.loads(json_file_obj.read_text(encoding="utf-8"))

            #with json_file_obj.open("r",encoding="utf-8") as f:
            #   chunks = json.load(f)
        if not chunks:
            logger.error(f"chunks没有内容,读取备份文件也没有读取到,业务提前终止!")
            raise ValueError(f"chunks没有内容,读取备份文件也没有读取到,业务提前终止!")
        state["chunks"] = chunks
    if not file_title:
        file_title = "default_title"

    return file_title, chunks

def call_llm_item_name_recognition(chunks:list[dict[str, Any]],file_title:str) -> str:
    llm_client = llm_provider.chat(json_model=False)
    context:str = ""
    for chunk in chunks[:ITEM_NAME_RECOGNITION_CHUNKS_TOP_K]:
        context = f"副标题:{chunk.get('parent_title')},第{chunk.get('part')}部分,内容为:{chunk.get('content')}\n"
    recognition_prompt:str = load_prompt("item_name_recognition", context=context,file_title=file_title)
    message = HumanMessage(content = recognition_prompt)
    chains = llm_client | StrOutputParser()
    item_name = chains.invoke([message])
    if not item_name:
        logger.warning(f"没有识别到item_title,给一个file_title对应的默认值:{file_title}")
        item_name = file_title
    return item_name

def item_name_embedding(item_name:str) -> tuple[list,dict]:
    #需要的是列表
    result = llm_provider.generate_infra_embeddings([item_name])
    #result 是一个大字典
    dense_vector = result.get("dense")[0]
    sparse_vector = result.get("sparse")[0]
    return dense_vector, sparse_vector

def prepared_item_name_collection():
    #检查集合是否存在
    milvus_client:MilvusClient = milvus_gateway.client
    has:bool = milvus_client.has_collection(collection_name=milvus_gateway.item_name_collection)
    if has:
        logger.info(f"{milvus_gateway.item_name_collection}已经存在,确保加载后返回!")
        milvus_client.load_collection(
            collection_name=milvus_gateway.item_name_collection,
        )
        return
    schema = milvus_client.create_schema(
        auto_id=True,#主键自增
        enable_dynamic_collection=True,#默认允许超列插入,增加容错
    )

    #往schema里面添加字段
    schema.add_field(field_name="pk",datatype=DataType.INT64,is_primary=True)
    schema.add_field(field_name="file_title",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="item_name",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="dense_vector",datatype=DataType.FLOAT_VECTOR,dim=1024)
    schema.add_field(field_name="sparse_vector",datatype=DataType.SPARSE_FLOAT_VECTOR)


    #创建索引
    index_param = milvus_client.prepare_index_params()
    index_param.add_index(
        field_name="dense_vector",
        index_type="HNSW",
        index_name="dense_vector_index",
        metric_type="COSINE",
        index_params={
            "M":64,#邻居数量
            "efConstruction":100,#从多少个点中选出邻居的数量
        },
    )

    index_param.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",#稀疏倒排索引 从数据->向量 每次查询时先定位坐标关联的数据集合
        index_name="sparse_dense_vector_index",
        metric_type="IP",
        index_params={
            "inverted_index_algo":"SINDI"#IP提高查询效率的方式
        },
    )

    #创建集合
    milvus_client.create_collection(
        collection_name=milvus_gateway.item_name_collection,
        schema=schema,
        index_params=index_param,
    )

    #把集合从磁盘加载到内存
    milvus_client.load_collection(
        collection_name=milvus_gateway.item_name_collection,
    )

def insert_item_name_collection(item_name:str,dense_vector,sparse_vector,file_title):
    milvus_client:MilvusClient = milvus_gateway.client
    result = milvus_client.delete(
        collection_name=milvus_gateway.item_name_collection,
        #milvus里面是两个=
        #== {file_title}会把后面的值当作列名
        filter=f"file_title == '{file_title}'",
    )
    logger.info(f"已经完成数据的删除,删除的数据条数为:{result.get('delete_count')}")
    data:dict = {
        "file_title":file_title,
        "item_name":item_name,
        "dense_vector":dense_vector,
        "sparse_vector":sparse_vector,
    }
    insert_result = milvus_client.insert(
        collection_name=milvus_gateway.item_name_collection,
        data=data,#支持批量和单挑插入 [{}] {}
    )
    logger.info(f"完成了{item_name}数据插入,影响条数为:{insert_result.get('insert_count')}")

def improve_chunks_item_name(chunks,item_name):
    for chunk in chunks:
        chunk["item_name"] = item_name


def recognize_and_index_item_name(state: ImportGraphState) -> ImportGraphState:
    file_title,chunks = validate_and_get_data(state)
    item_name:str = call_llm_item_name_recognition(chunks,file_title)
    dense_vector,sparse_vector = item_name_embedding(item_name)
    prepared_item_name_collection()
    insert_item_name_collection(item_name,dense_vector,sparse_vector,file_title)
    improve_chunks_item_name(chunks,item_name)
    state["item_name"] = item_name
    state["chunks"] = chunks
    return state