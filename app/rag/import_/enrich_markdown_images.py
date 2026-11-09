from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from minio import Minio
from minio.deleteobjects import DeleteObject

from app.process.import_.agent.state import ImportGraphState
from pathlib import Path

from app.rag.import_.config import IMAGE_CONTEXT_CHAR_LENGTH, SUPPORTED_IMAGE_EXTENSIONS
from app.shared.runtime.logger import logger
import re
from app.infra.llm.providers import llm_provider
from app.shared.runtime.load_prompt import load_prompt
from mimetypes import guess_type
import base64
from app.infra.object_storage.minio_gateway import minio_gateway

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
        match = re.search(r"\!\[.*?\]\(.*?" + re.escape(image_name) + r".*?\)",md_content)
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

def upload_image_to_minio(images_info:list[tuple[str,Path,tuple[str,str]]],stem) -> dict[str, str]:
    images_url:dict[str, str] = {}
    minio_client:Minio = minio_gateway.client
    objects:list = minio_client.list_objects(
        bucket_name=minio_gateway.bucket_name,
        #minio_gateway.image_dir[1:] 不要MINIO_IMG_DIR=/upload-images前面的斜杠,会报错
        prefix=minio_gateway.image_dir[1:] + "/" + stem,
        recursive=True,
    )
    if objects:
        #查询到了之前文件有相应照片,进行删除
        """
        坑1:list_objects -> list -> list[object]  || list[DeleteObject] <- remove_objec这个方法需要的
        坑2:remove_object方法返回的是一个生成器,需要循环处理结果才会真的触发
            errors = x
            for error in errors:
                pass
        """
        delete_object_list = [ DeleteObject(obj.object_name) for obj in objects]
        errors = minio_client.remove_objects(bucket_name=minio_gateway.bucket_name,delete_object_list=delete_object_list)
        for error in errors:
            logger.warning(f"删除{stem}文件夹下的图片出现问题:{error}")

    for image_name,image_path_obj,_ in images_info:
        try:
            minio_client.fput_object(
                bucket_name=minio_gateway.bucket_name,
                object_name=minio_gateway.image_dir + "/" + stem + "/" + image_name,
                file_path=str(image_path_obj),
                content_type=guess_type(image_name)[0],
            )
            url:str = minio_gateway.build_image_url(stem, image_name)
            images_url[image_name] = url
            logger.debug(f"{image_name}已经传递到了minio服务器,访问地址为{url}")
        except Exception as e:
            logger.error(f"{image_name}上传失败,跳过本次,进行下一张图片的处理")
            continue
    logger.info(f"已经完成文件夹{stem}所有图片的上传,上传的数量为:{len(images_url)}")
    return images_url


def replace_old_md_content(md_content:str,images_url:dict[str,str],images_summary:dict[str,str]) -> str:
    for image_name,image_url in images_url.items():
        summary:str = images_summary[image_name]
        image_re = re.compile(r"\!\[.*?\]\(.*?" + re.escape(image_name) + ".*?\)")
        #累加替换
        #天然的一个问题: sub(" \ -> 反 / -> 正斜杠 替代中代表分组!!!匹配错误!")
        #解决分组替换的问题 lambda表达式,匿名函数
        #sub(1 (替换入的字符串 -> 会检查 / 分组替换的特殊符号 | 匿名函数,匿名函数的返回结果替换入 -> 不是检查返回结果),2)
        #记住以后所有的替换 第一个参数都不要直接写字符串,写lambda _:替换入的字符串
        md_content = image_re.sub(lambda _:f"![{summary}]({image_url})",md_content)

    return md_content

def backup_md_return_path(md_content:str,md_path_obj:Path) -> str:
    new_path_md_obj:Path = md_path_obj.with_name(f"{md_path_obj.stem}_new.md")
    new_path_md_obj.write_text(data=md_content,encoding="utf-8")
    return str(new_path_md_obj)

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
    #4. 调用图片上传,获取图片上传地址
    iamges_url:dict[str,str] = upload_image_to_minio(images_info_list,md_path_obj.stem)
    #5. 进行md的内容替换
    new_md_contetn:str = replace_old_md_content(md_content,iamges_url,images_summary)
    #6. 进行new_md_contetn数据备份
    new_md_path:str = backup_md_return_path(new_md_contetn,md_path_obj)
    #7. 更新state
    state['md_content'] = new_md_contetn
    state['md_path'] = new_md_path
    return state