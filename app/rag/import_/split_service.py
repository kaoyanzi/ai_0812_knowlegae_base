from app.process.import_.agent.state import ImportGraphState
from pathlib import Path
from app.shared.runtime.logger import  logger
from typing import Any
import re

def validates_and_get_data(state: ImportGraphState) -> tuple[str,str,Path]:
    md_content = state.get('md_content')
    md_path = state.get('md_path')
    file_title = state.get('file_title')
    if not md_path:
        logger.error(f"md_path指向的md文件为空,业务无法继续提前终止")
        raise ValueError(f"md_path指向的md文件为空,业务无法继续提前终止")
    md_path_obj = Path(md_path)
    if not md_path_obj.is_file():
        logger.error(f"md_path指向的地址为{md_path},但是没有对应的文件,业务无法继续,提前终止")
        raise FileNotFoundError(f"md_path指向的地址为{md_path},但是没有对应的文件,业务无法继续,提前终止")
    if not md_content:
        md_path = md_path_obj.read_text(encoding='utf-8')
        if not md_content:
            logger.error(f"md_content为空,读取md_path依然为空,业务无法继续提前终止")
            raise ValueError(f"md_content为空,读取md_path依然为,业务无法继续提前终止")
        state['md_content'] = md_content
    if not file_title:
        file_title = md_path_obj.stem
        logger.warning(f"file_title为空,给默认值为{file_title}")

    return md_content, file_title,md_path_obj

def document_split_by_title(md_content:str) -> list[dict[str,Any]]:
    chunks_title:list[dict[str,Any]] = []
    current_title:str|None = None
    current_title_lines:list[str] = []
    is_code:bool = False
    md_all_lines:list[str] = md_content.split("\n")
    #定义正则匹配对应的标题:  前面可以有空格1-6#一个空格后续必须内容
    title_re = re.compile(r"^\s*#{1,6}\s.+")
    for line in md_all_lines:
        #问题3 空行处理:
        line = line.strip() #
        if not line:
            #去空行和去空格
            logger.debug(f"当前行为空行,跳过,进行下一行处理!")
            continue
        logger.debug(f"当前行为有内容的正常行,进行处理!")
        #问题4 md中可能存在##代码块注释
        if line.startswith("```") and line.startswith("~~~"):
            current_title_lines.append(line)
            is_code = not is_code #取反
            continue
        match = title_re.match(line)
        if not is_code and match:
            #问题1 第一行是标题,先不要结算
            #问题2 不要空标题
            if current_title and len(current_title_lines) > 1:
                chunks_title.append(
                    {
                        "title": current_title,
                        "content": "\n".join(current_title_lines),
                    }
                )
            #孤儿数据
            if not current_title and len(current_title_lines) > 0:
                current_title_lines.append(line)
                current_title = line
                continue
            current_title = line
            current_titile_lines = [line]
        else:
            current_title_lines.append(line)
    if current_title and len(current_title_lines) > 1:
        chunks_title.append(
            {
                "title": current_title,
                "content": "\n".join(current_title_lines),
            }
        )
    logger.info(f"将文档分割了{len(chunks_title)}块")
    return chunks_title



def split_document(state: ImportGraphState) -> ImportGraphState:
    #1. 参数校验和数据获取
    md_content, file_title, md_path_obj = validates_and_get_data(state)
    return state