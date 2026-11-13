import asyncio

from fastapi import FastAPI
from fastapi.responses import EventSourceResponse,StreamingResponse
from starlette.middleware.cors import CORSMiddleware

# 向前端推送数据

# 定义一个长连接的接口 = 前端一连接 == 持续推送内容

app = FastAPI(description="单纯向前端推送数据,不区分事件类型!!")


# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # 允许所有来源（生产环境建议指定具体域名） * 全部的html可以具体  localhost:6379
    allow_credentials=True,         # 允许携带凭证（如 Cookie）
    allow_methods=["*"],            # 允许所有 HTTP 方法（GET、POST、PUT、DELETE 等）
    allow_headers=["*"],            # 允许所有请求头
)


async def generator():
    for i in range(10):
        await asyncio.sleep(1)
        yield f"data: 你好么{i}\n\n"

@app.get("/stream/sse")
def return_sse():

    print(f"前端和我们创建长连接!!!!!")
    """
    参数1: 生成器
    参数2: media_type = 流式数据类型
    """
    return EventSourceResponse(generator())
    # return StreamingResponse(
    #     generator()
    #     ,media_type = "text/event-stream"
    # )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)

