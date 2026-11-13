import datetime
import json
import shutil
import uuid

import uvicorn
from fastapi import FastAPI,BackgroundTasks,UploadFile
from fastapi.responses import FileResponse

from app.api.schema.import_schema import UploadResponse, StatusResponse
from app.process.import_.agent.main_graph import import_graph_app
from app.process.import_.agent.state import ImportGraphState, create_default_state
from app.shared.runtime.logger import logger,PROJECT_ROOT
from pathlib import Path
from mimetypes import guess_type
from datetime import datetime
from app.shared.utils.task_utils import get_done_task_list, get_running_task_list, get_task_status, update_task_status, \
    TASK_STATUS_PROCESSING, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED

app = FastAPI(description="导入模块的接口")

@app.get("/html")
def return_import():
    html_file_obj:Path = PROJECT_ROOT / "app" / "resources" / "html" / "import.html"
    return FileResponse(
        path=str(html_file_obj),
        media_type=guess_type(html_file_obj.name)[0],
        #filename
    )

def invoke_import_graph(task_id:str,local_file_path:str,local_dir:str):
    state: ImportGraphState = create_default_state(
        task_id=task_id,
        local_file_path=str(local_file_path),
        local_dir=str(local_dir),
    )

    logger.info(f"执行参数:\n{json.dumps(state, indent=4, ensure_ascii=False)}")

    try:
        #开始状态
        update_task_status(task_id,TASK_STATUS_PROCESSING)
        result: ImportGraphState = import_graph_app.invoke(state)
        #成功状态
        update_task_status(task_id, TASK_STATUS_COMPLETED)
    except Exception as e:
        logger.exception(f"导入流程发生了异常:{str(e)}")
        #失败状态
        update_task_status(task_id, TASK_STATUS_FAILED)


@app.post("/upload")
async def upload_file(tasks:BackgroundTasks,files:list[UploadFile]):
    #接收文件,固定前端只能传一个文件,但是用列表包装了
    current_file:UploadFile = files[0]
    #文件转存
    task_id = str(uuid.uuid4())
    local_dir_obj:Path = PROJECT_ROOT / "output" / datetime.now().strftime("%Y%m%d") / task_id
    local_dir_obj.mkdir(parents=True,exist_ok=True)
    local_file_path_obj:Path = local_dir_obj / current_file.filename
    #data = await current_file.read()
    #local_file_path_obj.write_bytes(data)
    with local_file_path_obj.open("wb") as output_file:
        shutil.copyfileobj(current_file.file, output_file)
    #异步调用图对象的执行
    tasks.add_task(invoke_import_graph,task_id=task_id,local_file_path=str(local_file_path_obj),local_dir=str(local_dir_obj))
    #返回结果
    return UploadResponse(
        code = 200,
        message=f"{current_file.filename}已经完成上传,正在解析中...",
        task_ids=[task_id],
    )



@app.get("/status/{task_id}")
def status_info(task_id:str):
    status  = get_task_status(task_id)
    running_list = get_running_task_list(task_id)
    done_list = get_done_task_list(task_id)

    return StatusResponse(
        code = 200,
        task_id=task_id,
        status=status,
        running_list=running_list,
        done_list = done_list,
    )
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)