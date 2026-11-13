import time

from fastapi import FastAPI, BackgroundTasks
import threading

app = FastAPI(description="演示并行和串行,以及单次请求中如何开启异步动作")



"""
  
  并行和串行
    并行:  同一时刻可以有多个任务同时进行
    串行:  同一时刻只有一个任务在执行
  
  fastapi宏观并行/微观串行
    宏观: 站在整体/高处 看待所有用户的请求!    
        并发级别: 进程 > 线程 > 协程
        理解1: 没有添加async的接口方法也是异步也是并发的! [线程]
        
                                      线程1  非async描述接口方法
        客户端 -> fastapi -> 线程池 ->  线程2  非async描述接口方法
                                      线程3  非async描述接口方法
                                      
        理解2: 添加了async的方法也是异步也是并发的! [协程]         
                        线程            
                代码     线程   -> cpu 
                        线程             
                        
                        GIL: 全局线程锁
                        
                                            协程
                线程    event_loop           协程
                                            协程
        fastapi的并发模型: 
             默认线程: 协程 协程 协程 协程 async 
             新的线程: 没有async
             新的线程: 没有async
             新的线程: 没有async
             新的线程: 没有async
             新的线程: 没有async
             
    微观: 一次请求内是串行的
       一次请求内的代码是顺序执行的! 
       就算有休眠! 后续也是只能等待!
               
    微观异步:
       一次请求内, 有异步的动作行为! 
       例如: 上传pdf解析就是微观异步!
                                    1. 接收文件/转存
       前端   ---> 文件 ----> 接口    [异步] 2. 开启一个新的线程 ----> 调用导入图流程(7个节点) [超级耗时动作]  1 2 3 4 5 6 7  add_running_task / add_done_task(task_id,"节点")
         |                          3. 返回结果前端                                                                                  |
         |                                 |                                                                                       |
         |                                 |                                                                                       |
         <----------------------------------                                                                                       |
                                                                                                                                   |
                                                                                                                                   |
                                                                                                                                   |
                                                                                                                        running_dict{task_id:[节点名]}    
         ------------------------------------------ 接口 1s 2s task_id ----------------------------------------->
                                                                                                                        done_dict   {task_id:[节点名,....]}
                                                                                                                                   
         前端   --> 主动请求 3个接口 --->   后端
         前端   <-- sse | websocket | 前端轮询 1s  <---   后端
                                         
       
       fastapi提供了一个快速在一次请求中开启协程和线程的方法!!   
         
"""


@app.get("/a")
def a():
    print("a开始休眠")
    time.sleep(10)
    print("a休眠结束")
    return "a"


def long_time(session_id:str):
    print(f"耗时方法开始执行了 22")
    # 调用图流程
    time.sleep(100)
    print(f"耗时方法开始执行结束了 44")



@app.get("/b")
def b(tasks:BackgroundTasks):
    print("b执行了 11 ")
    # 方案1: 自己开线程或者协程
    # 方案2: 使用fastapi提供的技术快速开启线程或者协程
    """
      1. 形参变量 参数:类型必须是 BackgroundTasks
      2. 参数.add_task(函数,key调用函数需要的参数名=value...)
         add_task(函数) -> 线程         没有+async
                                 异步 -> 函数
                       -> 协程         有 async
    """
    tasks.add_task(long_time,session_id="007")
    # time.sleep(10)
    print("b执行结束了 33")
    return f"临时返回结果了"
"""
                         1
    fastapi -> 接口 ->    2 [异步]  函数 -> tasks []
                         3
                         |
                     fastapi  -> tasks -> 有要开启异步任务的函数 -> 开启线程/协程 -> 目标函数    
                     
                 
    fastapi 
            tasks
            b(tasks)
              1
              2
              tasks(1,2,3,4)
              1
              3     
            tasks有没有 
               有 -> 开启
               没有 -> 拉倒            
                     
                     
"""




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="0.0.0.0",port=8000)
