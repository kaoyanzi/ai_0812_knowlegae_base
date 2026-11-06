from app.process.import_.agent.main_graph import import_graph_app
from app.process.import_.agent.state import create_default_state, ImportGraphState
from app.shared.runtime.logger import logger
import json
"""
json.dump /dumps[倾倒] python 数据转化为json相关的数据:{向外} dump 转到外部的文件[备份] dumps 转成json字符串[可视化转换]
            s 代表字符串
json.load /loads[加载] 把json的数据转成python的数据: {向内} load 将外部json文件[还原] loads 将json字符串转成python[json字符串 - > python数据[模型返回值处理]]
dumps(要转成json的python对象,indent=4:层次之间带有四个缩进,ensure_ascii=False:是否把中文转成ascii编码! )
"""
#动态测试[ graph stream | invoke]    我们没有设计业务,看图的设计结构  适合:完整的业务开发测试
#创建一个对应的state出来 task_id任务标识 local_file_path
state: ImportGraphState = create_default_state(task_id="007",local_file_path="xxx.md")
logger.info(f"开始进行动态执行测试,参数为:\n {json.dumps(state, indent=4,ensure_ascii=False)}")
result_state = import_graph_app.invoke(input=state)
logger.info(f"完成动态执行测试,测试结果为:\n {json.dumps(result_state, indent=4,ensure_ascii=False)}")


#静态测试 你写不写业务代码无所谓,根据图的节点和边就可以静态的测试出图的结构!!!
import_graph_app.get_graph().print_ascii()