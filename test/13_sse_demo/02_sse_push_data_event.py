import asyncio

from fastapi import FastAPI
from fastapi.responses import EventSourceResponse,StreamingResponse
from starlette.middleware.cors import CORSMiddleware

# 向前端推送数据

# 定义一个长连接的接口 = 前端一连接 == 持续推送内容

app = FastAPI(description="单纯向前端推送数据和事件类型!!")


# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有来源（生产环境建议指定具体域名） * 全部的html可以具体  localhost:6379
    allow_credentials=True,         # 允许携带凭证（如 Cookie）
    allow_methods=["*"],            # 允许所有 HTTP 方法（GET、POST、PUT、DELETE 等）
    allow_headers=["*"],            # 允许所有请求头
)


async def progress_generator():

    for i in range(1,101):
        await asyncio.sleep(0.1)
        yield f"event: progress\n"
        yield f"data: {i}\n\n"
    yield f"event: completed\n"
    yield f"data: <font color='green'>下载完成</font>\n\n"



@app.get("/download")
def download():
    return EventSourceResponse(progress_generator())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)

