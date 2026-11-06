from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from app.process.import_.agent.state import ImportGraphState
from app.process.import_.agent.nodes.node_entry import node_entry
from app.process.import_.agent.nodes.node_pdf_to_md import node_pdf_to_md
from app.process.import_.agent.nodes.node_md_img import node_md_img
from app.process.import_.agent.nodes.node_document_split import node_document_split
from app.process.import_.agent.nodes.node_item_name_recognition import node_item_name_recognition
from app.process.import_.agent.nodes.node_bge_embedding import node_bge_embedding
from app.process.import_.agent.nodes.node_import_milvus import node_import_milvus
from app.shared.runtime.logger import logger

#创建图的构建对象
import_builder = StateGraph(state_schema=ImportGraphState)

#添加节点
import_builder.add_node("node_entry",node_entry)
import_builder.add_node("node_pdf_to_md",node_pdf_to_md)
import_builder.add_node("node_md_img",node_md_img)
import_builder.add_node("node_document_split",node_document_split)
import_builder.add_node("node_item_name_recognition",node_item_name_recognition)
import_builder.add_node("node_bge_embedding",node_bge_embedding)
import_builder.add_node("node_import_milvus",node_import_milvus)

#添加边 静态边和条件边
#import_builder.add_edge(START,"node_entry")
import_builder.set_entry_point("node_entry")


def after_entry_node(state:ImportGraphState) -> str:
    """"
        start -> 值 -> 返回目标节点名
        :return: 字符串 目标节点的名字 node_pdf_to_md | node_md_img | END
    """
    if state.get("is_md_read_enabled"):
        #不为空 且为 TRUE
        #文件就是md
        #日志: 前因 后果 核心参数(佐证)
        logger.info(f"传入的文件是md,md_path:{state.get('md_path')},后续跳转到node_md_img节点")
        return "node_md_img"

    elif state.get("is_pdf_read_enabled"):
        # 不为空 且为 TRUE
        #文件是pdf
        logger.info(f"传入的文件是pdf,pdf_path:{state.get('pdf_path')},后续跳转到node_pdf_to_md节点")
        return "node_pdf_to_md"
    else:
        logger.warning(f"当前项目只支持md和pdf,跳转到END节点")
        return END

"""
    langgraph 静态 add_edge("1","2") 一定会执行
    langgraph 动态 add_conditional_edges("起始节点",路由函数 return 目标节点
    ,path_map : dict = {key:value...})其中path_map是给静态测试看的
    条件边的第三个参数 :1.静态测试,必须显示的写path_map 2.不是静态测试,但是路由函数返回的值不等于目标节点

"""
import_builder.add_conditional_edges("node_entry",after_entry_node,{
    "node_md_img":"node_md_img",
    "node_pdf_to_md":"node_pdf_to_md",
    END:END
})

import_builder.add_edge("node_pdf_to_md","node_md_img")
import_builder.add_edge("node_md_img","node_document_split")
import_builder.add_edge("node_document_split","node_item_name_recognition")
import_builder.add_edge("node_item_name_recognition","node_bge_embedding")
import_builder.add_edge("node_bge_embedding","node_import_milvus")
import_builder.add_edge("node_import_milvus",END)

import_graph_app = import_builder.compile()
