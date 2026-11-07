from Demos.FileSecurityTest import sd

from app.process.import_.agent.state import ImportGraphState
from pathlib import Path

from app.rag.import_.config import IMAGE_CONTEXT_CHAR_LENGTH, SUPPORTED_IMAGE_EXTENSIONS
from app.shared.runtime.logger import logger
import re

def validates_and_get_data(state: ImportGraphState) -> tuple[str,Path,Path]:
    md_path:str = state.get('md_path')
    if not md_path:
        logger.error(f"md_path内容为空,业务无法继续,提前终止")
        raise ValueError(f"md_path内容为空,业务无法继续,提前终止")
    md_path_obj:Path = Path(md_path)
    if not md_path_obj.is_file():
        logger.error(f"md_path地址有值:{md_path},但是没有对应的文件,业务无法继续,提前终止")
        raise FileNotFoundError(f"md_path地址有值:{md_path},但是没有对应的文件,业务无法继续,提前终止")
    md_content:str = md_path_obj.read_text(encoding='utf-8')
    state['md_content'] = md_content
    images_path_obj:Path = md_path_obj.parent / 'images'
    return md_content, md_path_obj, images_path_obj


def scan_images_info(images_path_obj:Path,md_content:str) -> list[tuple[str,Path,tuple[str,str]]]:
    #获取所以图片信息
    generator  = images_path_obj.iterdir()
    images_info_list:list[tuple[str,Path,tuple[str,str]]] = []
    for image_file_obj in generator:
        #是不是图片检查
        if image_file_obj.suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            logger.debug(f"{image_file_obj.name}不是图片,跳过,进行下一条处理!")
            continue

        image_name = image_file_obj.name
        match = re.search(r"\!\[.*?\]\(.*?" + re.escape(image_name) + ".*?\)",md_content)
        if not match:
            logger.debug(f"{image_name}没有在md_cont中被使用,跳过,进行下一条处理!")
            continue
        start = match.start()
        end = match.end()
        #IMAGE_CONTEXT_CHAR_LENGTH
        #str[] -> 字符串截取左闭右开
        pre_context:str = md_content[max(start-IMAGE_CONTEXT_CHAR_LENGTH,0):start]
        post_context:str = md_content[end+1:min(end+IMAGE_CONTEXT_CHAR_LENGTH,len(md_content))]
        images_info_list.append(
            (
                image_name,
                image_file_obj,
                (
                    pre_context,
                    post_context
                )
            )
        )
    logger.info(f"已经完成了{len(images_info_list)}张图片内容的匹配!")
    return images_info_list


def enrich_markdown_images(state: ImportGraphState) -> ImportGraphState:
    #1. 获取参数并校验
    md_content,md_path_obj,images_path_obj = validates_and_get_data(state)
    #2. 调用方法进行图片信息识别
    images_info_list:list[tuple[str,Path,tuple[str,str]]] = scan_images_info(images_path_obj,md_content)
    return state