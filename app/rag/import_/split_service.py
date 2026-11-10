import json

from app.process.import_.agent.state import ImportGraphState
from pathlib import Path

from app.rag.import_.config import CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_MAX_SIZE, CHUNK_MIN
from app.shared.runtime.logger import  logger
from typing import Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
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
        md_content = md_path_obj.read_text(encoding='utf-8')
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
        if line.startswith("```") or line.startswith("~~~"):
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
            current_title_lines = [line]
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
"""
合适大小和边界清晰
"""
def improve_chunk_size(chunks:list[dict[str,Any]]) -> list[dict[str,Any]]:
    logger.info(f"没有切割也没有合并的原始数据长度:{len(chunks)}")
    final_chunks:list[dict[str,Any]] = []
    for chunk in chunks:
        if len(chunk.get("content")) > 600:
            final_chunks.extend(_content_split(chunk))
        else:
            final_chunks.append(chunk)
    logger.info(f"按标题切割但是没有合并的数据长度:{len(final_chunks)}")
    #合并
    final_chunks = _content_merge(final_chunks)
    logger.info(f"按标题切割也进行了合并的数据长度:{len(final_chunks)}")
    return final_chunks


def _content_split(chunk:dict[str,Any]) -> list[dict[str,Any]]:
    """本质使用递归切割器进行切割
        1.数据前置处理
            chunk {"title":....,"content":....,}
            content -> 标题\n -> 扣除去
            准备公共前置 -> 标题\n
        2.数据切割
        content
        3.切割的数据组装为对应的chunk
        chunk + 标题\n
    """
    current_title_chunk:list[dict[str,Any]] = []
    #1.
    content:str = chunk.get("content")
    title:str = chunk.get("title")
    content   = content[len(title)+1:]
    pre_fix:str = title + "\n"

    #2.声明递归切割器
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n","\n","。","！","？","："],
        chunk_size=CHUNK_SIZE - len(pre_fix),
        chunk_overlap=CHUNK_OVERLAP,
    )
    #3. 递归切割器切割
    chunk_list:list[str] = text_splitter.split_text(content)
    for index,chunk_content in enumerate(chunk_list,start=1):
        sub_chunk = {
            "parent_title":title,
            "content":pre_fix + chunk_content,  #自己定义的规则 目标: 1.让模型知道我们是同一标题下的切块 2.后续展示的时候让我们自己知道这是同一个标题下面的切块
            "title":f"{title}_{index}",
            "part":index,
        }
        current_title_chunk.append(sub_chunk)
    logger.info(f"已经完成{title}的内容切割,切割的数量等于{len(current_title_chunk)}")
    return current_title_chunk


def _content_merge(final_chunks:list[dict[str,Any]]) -> list[dict[str,Any]]:
    """
        短了合并:   条件一:同一个parent_title下面 条件二: content<400 条件三:合并后不能>1000
    """
    logger.info(f"在合并之前的数据长度:{len(final_chunks)}")
    chunks:list[dict[str,Any]] = []
    base_chunk:dict[str,Any] = None#第一个值给base
    #伪双指针
    for next_chunk in final_chunks:
        if not base_chunk:
            base_chunk = next_chunk
            continue
        #第二次循环
        if len(base_chunk.get("content")) < CHUNK_MIN:
            if base_chunk.get("parent_title") and base_chunk.get("parent_title") == next_chunk.get("parent_title"):
                if (len(base_chunk.get("content")) + len(next_chunk.get("content"))) < CHUNK_MAX_SIZE:
                    #真的可以合并
                    base_chunk["content"] = base_chunk.get("content") + "\n" + next_chunk.get("content")
                else:
                    chunks.append(base_chunk)
                    base_chunk = next_chunk
            else:
                chunks.append(base_chunk)
                base_chunk = next_chunk
        else:
            chunks.append(base_chunk)
            base_chunk = next_chunk
    if base_chunk:
        #最后一个一定没有添加进来
        chunks.append(base_chunk)
    logger.info(f"在合并之后的数据长度:{len(chunks)}")
    return chunks


def append_chunk_meta_data(chunks:list[dict[str,Any]],file_title:str) -> list[dict[str,Any]]:
    for chunk in chunks:
        chunk["file_title"] = file_title
        if "part" not in chunk:
            chunk["part"] = 1
        if "parent_title" not in chunk:
            chunk["parent_title"] = chunk["title"]
    logger.info(f"已经完成chunk的所有元数据补充")

def backup_chunks_json(chunks,md_path_obj:Path):
    chunks_json_obj:Path = md_path_obj.parent / "chunks.json"
    chunks_json_obj.write_text(json.dumps(chunks, indent=4, ensure_ascii=False),encoding="utf-8")
    #with chunks_json_obj.open(mode="w",encoding="utf-8") as f:
    #    json.dump(chunks, f, indent=4, ensure_ascii=False)
    logger.info(f"已经完成{md_path_obj.name}对应切块内容的数据备份!")


def split_document(state: ImportGraphState) -> ImportGraphState:
    #1. 参数校验和数据获取
    md_content, file_title, md_path_obj = validates_and_get_data(state)
    #2. 根据语义初步切割
    title_chunks:list[dict[str,Any]] = document_split_by_title(md_content)
    #3. 同一个标题下的长度优化处理和添加
    chunks:list[dict[str,Any]] = improve_chunk_size(title_chunks)
    #4. 元数据的补充和完善
    append_chunk_meta_data(chunks, file_title)
    #5. 数据备份
    backup_chunks_json(chunks, md_path_obj)
    #6. 更新state
    state["chunks"] = chunks
    #7. 返回结果
    return state