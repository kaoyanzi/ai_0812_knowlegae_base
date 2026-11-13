
from fastapi import FastAPI
from fastapi.responses import  FileResponse
from pydantic import BaseModel
from app.shared.runtime.logger import PROJECT_ROOT
from pathlib import Path
from mimetypes import guess_type

app = FastAPI(description="练习响应数据2种类型")

# 1. 返回json数据给前端
"""
  需求: 根据用户id查询信息! 返回用户的完整信息!  [id name age]
  url     /user/{id}
  method   get
  参数     path
  响应    json字符串
  
  
  请求方式只影响请求数据格式! get post -> 请求报文有没有请求体! 
  响应的json是利用响应报文返回! 响应报文一定四部分! 响应体
"""


# [ 前端 -> json(oop对象) -> fastapi -> 定义类(BaseModel) -> 接口  ] -> 定义类(BaseModel) -> fastapi ->  json -> 前端

class Address(BaseModel):
    city:str
    detail:str

class User(BaseModel):
    id:int
    name:str
    age:int
    address:Address

# {id,name,age,address:{city:,detail:}}

@app.get("/user/{id}")
def user_info(id:int):
    # id -> 用户信息
    address = Address(city="葫芦岛/东戴河",detail="高领镇赵孤家子屯")
    user = User(id=id,name="张三",age=18,address=address)
    return user



# 2. 向前端文件数据
# /http get 返回 import.http
# FileResponse
@app.get("/http")
def return_html():
    print(f"返回html文件")

    html_file_obj:Path = PROJECT_ROOT / "app" / "resources" / "http" / "xx.zip"

    # from fastapi.responses import  FileResponse
    # return "地址" -> "地址" -> 响应体 -> 前端
    # FileResponse(filepath="地址") -> 地址读取数据(字节数据) -> 响应体中 -> 前端
    return FileResponse(
        path=str(html_file_obj),  # 文件地址 (完整地址) str
        # filename=html_file_obj.name,  # 文件的名字 名字.后缀名
        # todo: filename -> 响应头 -> content-disposition:attachment;filename=文件名
        # todo: 1. 添加了filename就变成下载行为 2. 不想下载去掉filename
        # todo: 3. 就算没有添加filename(没有添加下载头!) 返回的文件mimetype是浏览器不支持的格式,也会变成下载!
        media_type=guess_type(html_file_obj.name)[0],  # 文件mimetype类型
    )


@app.get("/image")
def return_image():
    image_path_obj:Path = PROJECT_ROOT / "output" / "images" / "ai.png"
    return FileResponse(
        # filename=,
        path=str(image_path_obj),
        media_type=guess_type(image_path_obj.name)[0]
    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)