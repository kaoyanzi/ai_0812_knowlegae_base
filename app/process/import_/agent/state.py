from typing import TypedDict, List, Any
import copy


class ImportGraphState(TypedDict):

    #12个属性
    #任务标识 -> context_state - > task_id
    task_id:str

    #输入文件和输出文件夹
    local_file_path: str    #输入的文件地址 start ->  local_file_path  -> node_entry
    local_dir: str  #输出文件的文件夹地址 ouy=tput

    #标记文件类型
    is_md_read_enable: bool#是不是md
    is_pdf_read_enable: bool#是不是pdf

    #存储对应文件的文件地址
    md_path: str#专门存储md的文件地址
    pdf_path: str#专门存储pdf文件的地址

    #储存数据内容:
    md_content: str#md的文本内容,后续用于切割
    item_name: str#文件的唯一标识
    file_title: str#文件名 去掉后缀名

    #切片后的数据
    chunks:List[dict[str,Any]]#切片内容
    embeddings_content:List[dict[str,Any]]# 装生成向量的切片内容 稠密和稀疏

#定义了一个对象模板 赋予少量的默认值
graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enable": False,
    "is_md_read_enable": False,
    "local_dir": "",
    "local_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "md_content": "",
    "chunks": [],
    "item_name": "",
    "embeddings_content": [],
}
#提供两个快速创建对象的方法
def create_default_state(**kwargs) -> ImportGraphState:
    """快速创建一个指定属性的state对象,并返回新的对象"""
    #**kwargs -> 动态 -> key:value 传递参数 -> 要求key = 属性名 -> kwargs 本质上是字典
    new_state = copy.deepcopy(graph_default_state)
    #for k, v in kwargs.items():
    #   for k in kwargs:
    new_state.update(kwargs) #dict.update(dict) 相同字段自动更新
    return new_state

#create_default_state -> 指定赋值属性 -> state
def get_default_state() -> ImportGraphState:
    """快速返回模板对象,不修改属性,返回都是新的对象"""
    new_state: ImportGraphState = copy.deepcopy(graph_default_state)
    return new_state

#get_default_state -> state -> 模板state对象,其他的属性后续再修改

#copy
#import copy
#浅copy: 第一层属性  新的对象=copy.copy(模板对象)
#深copy: 嵌套属性    新的对象= copy.deepcopy(模板对象)

