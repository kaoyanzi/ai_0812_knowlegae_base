from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser

from app.process.import_.agent.state import ImportGraphState
from pathlib import Path

from app.rag.import_.config import IMAGE_CONTEXT_CHAR_LENGTH, SUPPORTED_IMAGE_EXTENSIONS
from app.shared.runtime.logger import logger
import re
from app.infra.llm.providers import llm_provider
from app.shared.runtime.load_prompt import load_prompt
from mimetypes import guess_type
import base64

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



def summary_image_info(images_info:list[tuple[str,Path,tuple[str,str]]],root_folder:str) -> dict[str, str]:
    images_summary:dict[str, str] = {}
    vision_model = llm_provider.vision_chat()
    for image_name,image_path_obj,image_context in images_info:

        image_des = load_prompt("image_summary",image_content = image_context,root_folder=root_folder)
        image_type:str = guess_type(image_name)[0]
        image_base64:str = base64.b64encode(image_path_obj.read_bytes()).decode("utf-8")
        message = HumanMessage(
            content=[
                {"type":"text","text":image_des},
                {"type":"image_url",
                 "image_url":{"url":f"data:{image_type};base64,{image_base64}"}
                 },
            ]
        )
        #langchain的调用链
        #chains = 提示词 | 模型 | 解析器
        chains = vision_model | StrOutputParser()

        summary:str = chains.invoke([message])
        #model.invoke([]) -> response -> response.content -> 字符串
        #chains = vision_model | JsonOutputParser()
        # model.invoke([]) -> response -> response.content -> 字符串 -> json.load(字符串) -> dict
        images_summary[image_name] = summary
        logger.debug(f"图片:{image_name},已经通过视觉模型,进行意图识别,结果为:{summary}")
    logger.info(f"已经完成{root_folder}文件夹中的所有图片内容总结,总结图片的内容对数为:{len(images_summary)}")
    return images_summary

def enrich_markdown_images(state: ImportGraphState) -> ImportGraphState:
    #1. 获取参数并校验
    md_content,md_path_obj,images_path_obj = validates_and_get_data(state)
    #md 没有图片,需要特殊校验和提前终止
    if not list(images_path_obj.iterdir()):
        logger.info(f"{md_path_obj}中没有引用任何图片,无需后续图片处理,直接跳转到下一个节点")
        return state
    #2. 调用方法进行图片信息识别
    images_info_list:list[tuple[str,Path,tuple[str,str]]] = scan_images_info(images_path_obj,md_content)
    #3. 调用模型进行图片内容总结
    images_summary:dict[str,str] = summary_image_info(images_info_list,md_path_obj.stem)
    return state