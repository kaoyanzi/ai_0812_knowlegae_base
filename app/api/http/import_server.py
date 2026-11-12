from fastapi import FastAPI,BackgroundTasks,UploadFile
from fastapi.responses import FileResponse

from app.api.schema.import_schema import UploadResponse, StatusResponse
from app.shared.runtime.logger import logger,PROJECT_ROOT
from pathlib import Path
from mimetypes import guess_type

app = FastAPI(description="导入模块的接口")

@app.get("/html")
def return_import():
    html_file_obj = PROJECT_ROOT / "app" / "resources" / "html" / "index.html"
    return FileResponse(
        path=str(html_file_obj),
        media_type=guess_type(html_file_obj.name)[0],
        #filename
    )

@app.post("/upload")
def upload_file(tasks:BackgroundTasks,files:list[UploadFile]):
    return UploadResponse(
        code = 200,
        message="",
        task_ids=[]
    )

@app.get("/status/{task_id}")
def status_info(task_id:str):
    return StatusResponse(
        code = 200,
        task_id=task_id,
        status="",
        done_list=[],
        running_list=[]
    )