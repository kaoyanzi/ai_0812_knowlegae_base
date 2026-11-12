from pydantic import BaseModel

class UploadResponse(BaseModel):
    code: int
    message: str
    task_ids:list[str]#返回每个文件对应的task_id


class StatusResponse(BaseModel):
    code: int
    task_id:str
    status:str              #整个任务的状态
    done_list:list[str]
    running_list:list[str]