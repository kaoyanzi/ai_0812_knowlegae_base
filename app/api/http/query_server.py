from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse,EventSourceResponse
from mimetypes import guess_type

from fastapi.requests import Request

from app.api.schema.query_schema import QueryRequest, QueryAsyncResponse, QueryResponse, HistoryDeleteResponse, \
    HistoryItemResponse, HistoryResponse
from app.process.query.agent.main_graph import query_graph_app
from app.process.query.agent.state import QueryGraphState, create_query_default_state
from app.shared.runtime.logger import logger,PROJECT_ROOT
from pathlib import Path
from app.shared.utils.sse_utils import sse_generator,push_to_session,SSEEvent,create_sse_queue
from app.shared.utils.task_utils import update_task_status, TASK_STATUS_PROCESSING, TASK_STATUS_FAILED, \
    TASK_STATUS_COMPLETED, clear_task, get_done_task_list
from app.infra.persistence.history_repository import history_repository

app = FastAPI(description="查询模块的接口")

@app.get("/html")
def return_chat_html():
    html_file_obj:Path = PROJECT_ROOT / "app" /  "resources" / "html" / "chat.html"
    return FileResponse(
        path=str(html_file_obj),
        media_type=guess_type(html_file_obj.name)[0],
        #filename下载图
    )

@app.get("/health")
def health():
    return {
        "code":0
    }


@app.get("/stream/{session_id}")
def stream(session_id: str,request: Request):
    return EventSourceResponse(
        sse_generator(session_id,request)
    )


def invoke_query_graph(session_id: str,original_query:str,is_stream:bool):
    # 1. 准备state数据 [session_id,original_query,history = 省略]
    state: QueryGraphState = create_query_default_state(session_id=session_id, original_query=original_query,is_stream=is_stream)
    # 2. 动态执行(动态执行)
    try:
        # 开始状态
        update_task_status(session_id,TASK_STATUS_PROCESSING,is_stream)
        result = query_graph_app.invoke(state)
        # 成功状态
        update_task_status(session_id, TASK_STATUS_COMPLETED, is_stream)
        if is_stream:
            push_to_session(
                session_id,
                SSEEvent.FINAL,
                {
                    "answer": result.get("answer"),
                    "status": "completed",
                    "image_urls": result.get("image_urls"),
                }
            )
        return result
    except Exception as e:
        # 失败状态
        update_task_status(session_id, TASK_STATUS_FAILED, is_stream)
        logger.exception(f"查询任务发生异常,异常信息为:{str(e)}")
        if is_stream:
            push_to_session(session_id,SSEEvent.ERROR,{"error":f"异常信息为:{str(e)}"})

@app.post("/query")
def query(tasks:BackgroundTasks,params: QueryRequest):
    session_id = params.session_id
    original_query = params.query
    is_stream = params.is_stream
    #清空task_utils数据
    clear_task(session_id)

    if is_stream:
        #解决问题1
        create_sse_queue(session_id)
        tasks.add_task(invoke_query_graph,session_id=session_id,original_query=original_query,is_stream=is_stream)
        return QueryAsyncResponse(
            message=f"{session_id}任务开始查询中...",
            session_id=session_id
        )
    else:
        result:QueryGraphState = invoke_query_graph(session_id=session_id,original_query=original_query,is_stream=is_stream)
        answer:str = result.get("answer")
        image_urls:list[str] = result.get("image_urls", [])
        done_list:list[str] = get_done_task_list(session_id)
        return QueryResponse(
            message=f"{session_id}已经处理完毕了!",
            session_id=session_id,
            answer=answer,
            done_list=done_list,
            image_urls=image_urls,
        )

@app.delete("/history/{session_id}")
def clear_history(session_id: str):
    deleted_count = history_repository.clear_session(session_id=session_id)
    logger.info(f"已经完成{session_id}历史记录的清空,共计删除:{deleted_count}条")
    return HistoryDeleteResponse(
        message=f"已经完成{session_id}历史记录的清空,共计删除:{deleted_count}条",
        deleted_count=deleted_count,
    )
@app.get("/history/{session_id}")
def list_history(session_id: str):
    history_message:list[dict] = history_repository.list_recent(session_id=session_id,limit=20)
    item_list:list[HistoryItemResponse] = [
        HistoryItemResponse(
            id=str(message_dict.get("id")),
            session_id=session_id,
            role=message_dict.get("role"),
            text=message_dict.get("text"),
            rewritten_query=message_dict.get("rewritten_query"),
            item_names=message_dict.get("item_names"),
            image_urls=message_dict.get("image_urls"),
            ts=message_dict.get("ts"),
        )
        for message_dict in history_message
    ]
    logger.info(f"已经查询{session_id}对应的聊天记录,共查询到:{len(item_list)}条!")
    return HistoryResponse(
        session_id=session_id,
        items=item_list,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)