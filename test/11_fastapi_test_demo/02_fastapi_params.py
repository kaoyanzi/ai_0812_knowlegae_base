from fastapi import FastAPI , UploadFile , File
from pydantic import BaseModel
from app.shared.runtime.logger import PROJECT_ROOT
from pathlib import Path

app = FastAPI(description="练习参数接收")


# 1. 接收query参数  语法: 形参列表中声明对应的参数名称和类型即可! fastapi就会自动给我们赋值!

#  客户端 -> 服务器主机 -> 服务器软件uvicorn -> fastapi -> 简化接收 ->  接口函数

"""
  用户信息查询 根据关键字(keyword)和分页参数(page,size) 
  keyword关键字必须传递    keyword:str 没有默认值,必须传递
  page,size 也是可以传递的! 不传递默认 page = 1  size = 10
                         size:int = 10,page:str = 1 可以传递,不传递走默认值!
                         keyword:str | None = None 可以不传递 但是为空
  url:    /user
  method: get
  参数:   query  ? keyword=x & page = 1 & size = 10
  响应:   json
"""
@app.get("/user")
def search_user_list(keyword:str,size:int = 10,page:str = 1):
    print(f"{keyword}-{size}-{page}")
    return {
        "code":0
    }



# 2. 接收路径参数
# 需求: 删除用户id=动态值 的用户信息
# 步骤1: 设置动态路径  {key}  步骤2: 形参列表声明同名的参数即可
# https://docs.qq.com/[sheet]/[DTnVDenpKSnR6SFZv]?[tab=lq0twl]
# @app.get(/{type}/xxx/{doc_id}/xxxx)
"""
  url:   /user/1
  method: delete
  参数:   path 唯一标识
  响应:   json
"""
@app.delete("/user/{id}")
def delete_user(id:int):
    print(f"删除id={id}的用户信息")
    return "哈哈"


# 3. 接收json数据 [post/put]
"""
  需求: 保存用户信息 id name age sex 
  url:    /user
  method: post
  参数:   {id:1,name:x,age:x,sex:x}
  响应:   json
  
  前端 -> json(对象 美元) -> python -> json(美元) = 对象(人民币)
  
"""

# 1.定义接收json的类
# from pydantic import BaseModel
# 为啥这个类需要继承BaseModel是不是必须得呢?
# BaseModel 1.类和JSON互相转换 (接收/响应) 2. pydantic严格模式
# 必须的  继承BaseModel有符合JSON转化的协议(方法 dump)!!
class User(BaseModel):
    id:int
    name:str
    age:int
    sex:str

# 2.形参列表中添加 名称:类
@app.post("/user")
def save_user(user:User):
    print(f"接收的对象:{user}")
    return user


"""
   {"name":"",age:"",address:{city:"xx",detail:""}} == 我也嵌套 == python 
"""

class Address(BaseModel):
    city:str
    detail:str

class Student(BaseModel):
    name:str
    address:Address


# user = User()
# user.du
#
# class Student:
#     id:int
#     name:str
#
# student = Student()
# student.d


# 4. 接收文件

"""
  前端 -> 文件 -> 接口 1. 接收文件(内存对象) 2. 转存文件  3. 记录文件地址(后续操作)
  
  场景: 前端会传递一张image的图片,传递account=账号 到我们接口! (接收和转存输出存储的地址即可!)
  url:  upload
  method: post / put 
  参数: image = 文件   account = 字符串账号
  响应: 返回转存的地址
  注意: 转存的地址 output / images / 图片..
"""
@app.post("/upload")
async def upload_image(account:str,image:UploadFile):

    # 1. 接收 形参列表添加 UploadFile 类型的变量即可
    # 2. 转存  UploadFile包含上传文件的所有信息: 字节数据 / 文件的名字
    #    image.filename 上传的文件名字
    #    image.size  上传文件的字节大小
    #    image.content_type mimetype类
    #    image.file  上传文件的流引用 类似: Path.open(rb) as file  : 拿到了输入的文件流, 可以自己一点一点的读取,在进行一点一点的转存!
    #    data =  image.read()  一次读取所有上传文件内容  -> 立即占有所有内存空间 -> 转存
    # async def read(
    data = await image.read()
    file_name  = image.filename

    # Path对象
    file_path_obj:Path = PROJECT_ROOT / "output" / "images" / file_name
    file_path_obj.write_bytes(data)

    print(account)
    print(image.filename)
    return {
        "account":account,
        "filename":image.filename,
        "file_path": str(file_path_obj)
    }






if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)