from fastapi import FastAPI,APIRouter

# 根据id查询用户信息的接口!
# http://localhost:8080/user?id=1   [get]

"""
fastapi的基本使用步骤:
  1. from fastapi import FastAPI
  2. 实例化FastAPI对象
  3. 给函数添加对应路径
    方案1: 直接使用fastapi对象设置地址
      @fastapi实例化对象.请求方式("/设置访问地址即可")
      函数()
      设置简单的只有单模块!!
    方案2: 使用APIRouter设置分区路由地址
      web: 三个模块  用户模块  支付模块  地址管理模块 
      用户模块  /user/add /user/remove /user/show  
      支付模块  /pay/add  /pay/remove  /pay/detail 
      地址管理模块  /address/info  /address/list
      
      每个模块 -> fastapi.APIRouter
                     ->  实例化APIRouter  对象名 = APIRouter(prefix="/address",tags=['标签名']) 
                                -> @路由对象名称.get / post()
                                       -> app中进行绑定   app.include_router(路由对象即可)
    注意: 使用APIRouter方式分模块实现 切记 prefix 必须使用/开头   @路由对象.请求方式("/开头区分多层路径") 
    注意: 不同函数不能拥有'相同的地址'  判定相同: 地址 + 请求方式相同
"""

app = FastAPI(description="练习给函数设置访问地址")

@app.get("/user")
def user_detail(id:int|None=None):
    print(f"查询{id}了用户信息!")
    return {
        "code":0
    }

# 删除用户id等于1的用户信息
# user?id=1  delete
@app.delete("/user/info")
def user_delete(id:int|None=None):
    print(f"删除{id}了用户信息!")
    return {
        "code": 0
    }


# 服务器主机 + 服务器软件 + web项目
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app=app,host="0.0.0.0",port=8080)
