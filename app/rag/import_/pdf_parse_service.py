import time
from pathlib import Path

import requests

from app.process.import_.agent.state import ImportGraphState
from app.rag.import_.config import MINERU_MODEL_VERSION, MINERU_DOWNLOAD_TIMEOUT_SECONDS, MINERU_POLL_TIMEOUT_SECONDS, \
    MINERU_POLL_INTERVAL_SECONDS
from app.shared.runtime.logger import logger,PROJECT_ROOT
from app.infra.config.providers import infra_config
import requests


def validates_pdf_paths(state: ImportGraphState) -> tuple[Path, Path]:
    pdf_path:str = state.get('pdf_path')
    local_dir:str = state.get('local_dir')
    if not pdf_path:
        #前因 后果 关键参数
        logger.error(f"pdf_path为空!业务无法继续,提前终止")
        raise ValueError(f"pdf_path为空!业务无法继续,提前终止")
    if not local_dir:
        local_dir = PROJECT_ROOT / "output"
        logger.warning(f"local_dir没有赋予默认值,配置默认输出地址为:{local_dir}")
        state['local_dir'] = str[local_dir] #state标准 类型就是字符串

    pdf_path_obj:Path = Path(pdf_path)
    local_dir_obj:Path = Path(local_dir)
    #is_file()存在文件  exists()存在
    if not pdf_path_obj.is_file():
        logger.error(f"虽然pdf_path的路径地址为:{pdf_path},但是检查没有真实对应到文件!业务无法继续,提前终止!!")
        raise FileNotFoundError(f"虽然pdf_path的路径地址为:{pdf_path},但是检查没有真实对应到文件!业务无法继续,提前终止!!")

    if not local_dir_obj.is_dir():
        #parents=True 可以创建多级文件夹 linux mkdir -P a/b/c/d
        #exist_ok=True 存在也不报错!防御性编程
        logger.warning(f"local_dir的地址路径为{local_dir},但是没有具体的文件夹,直接创建对应的文件夹,程序业务继续进行")
        local_dir_obj.mkdir(parents=True,exist_ok=True)
    return pdf_path_obj,local_dir_obj

def apply_mineru_get_upload_url(pdf_file_name:str) -> tuple[str, str]:
    #https://mineru.net/apiManage/docs
    #4.1 组装对应的请求头 {token}
    token = infra_config.mineru_config.api_key
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"  #千万有空格
    }
    #4.2 组装对应的请求体json数据(请求参数)
    data = {
        #dict -> requests(json=dict -> json字符串)
        #请求参数 == 对方服务器决定
        "files":[
            {"name":pdf_file_name},
        ],
        "model_version": MINERU_MODEL_VERSION,
        "extra_formats":["html"]
        #"callback":
    }
    url = f"{infra_config.mineru_config.base_url}/file-urls/batch"
    response = requests.post(
        url = url,
        headers=header,
        json = data,
        timeout = MINERU_DOWNLOAD_TIMEOUT_SECONDS
    )

    status_code = response.status_code
    if status_code != 200:
        logger.error(f"向minerU服务器申请解析地址,但是网络状态码为:{status_code},业务无法继续,提前终止!!")
        raise RuntimeError(f"向minerU服务器申请解析地址,但是网络状态码为:{status_code},业务无法继续,提前终止!!")
    #response.text
    #response.content
    response_json = response.json()
    code = response_json.get("code",-1)
    if code != 0:
        logger.error(f"向minerU服务器申请解析地址,但是业务状态码为:{code},业务无法继续,提前终止!!")
        raise RuntimeError(f"向minerU服务器申请解析地址,但是业务状态码为:{code},业务无法继续,提前终止!!")
    json_data = response_json.get("data",{})
    batch_id:str = json_data.get("batch_id")
    upload_file_url:str = json_data.get("file_urls")[0]

    return batch_id,upload_file_url


def upload_file_to_url(upload_file_url:str,pdf_path_obj:Path) -> None:
    """"
    Path 是一个路径的对象 | 对象的属性 | 路径对象的一些简单方法 数据读取 判断 校验...
    .name .stew .suffix .parent .parents
    .isfile() .isdir() .exists() .read_text()读路径文件的字符串数据 .read_bytes()读路径对应的字节数据 .write_text() .write_bytes()
    .iterdir() .glob() .rglob()
    """
    data = pdf_path_obj.read_bytes()
    #response = requests.put(url=upload_file_url,data=data,timeout=MINERU_DOWNLOAD_TIMEOUT_SECONDS)
    #这里面的upload_file_url是一个预签名地址,相当于地址后面带了检验信息,所以不需要请求头里面的token做验证,但正是因为这个后门导致,服务器会对
    #这部分进行严格的检查,比如平时用代理都会访问不了,所以访问请求的失败概率太大了

    #下面是对预签名地址的常见处理方案
    #session  -> requests.put一次请求       1.复用请求 2.session.trust_env = False 不要给我额外添加任何请求头,我本次设置了什么,就传递什么
    with requests.Session() as session:
        session.trust_env = False
        response = session.put(url=upload_file_url,data=data,timeout=MINERU_DOWNLOAD_TIMEOUT_SECONDS)



    status_code = response.status_code
    if status_code != 200:
        logger.error(f"向:{upload_file_url}地址上传文件,网络状态失败:{status_code},业务无法继续,提前终止!!")
        raise ValueError(f"向:{upload_file_url}地址上传文件,网络状态失败:{status_code},业务无法继续,提前终止!!")



def poll_mineru_zip_url(batch_id:str) -> str:
    max_timeout = MINERU_POLL_TIMEOUT_SECONDS
    interval_time = MINERU_POLL_INTERVAL_SECONDS
    start_time = time.time()    #当前时间秒
    url = f"{infra_config.mineru_config.base_url}/extract-results/batch/{batch_id}"
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {infra_config.mineru_config.api_key}"
    }
    while(True):
        if time.time() - start_time > max_timeout:
            logger.error(f"轮询获取解析结果连接超时!等待时间为:{time.time() - start_time},最大等待时间为:{max_timeout},业务无法继续,提前终止!")
            raise TimeoutError(f"轮询获取解析结果连接超时!等待时间为:{time.time() - start_time},最大等待时间为:{max_timeout},业务无法继续,提前终止!")
        response = requests.get(url=url,headers=header,timeout=MINERU_DOWNLOAD_TIMEOUT_SECONDS)
        status_code = response.status_code
        if status_code != 200:
            #错误可以尝试 5xx [程序是客户端,mineru是服务端]
            if 500 <= status_code <= 599:
                logger.warning(f"轮询获取解析结果,出现服务器异常,状态码为:{status_code},稍后重试")
                time.sleep(interval_time)   #线程休眠!
                continue
            #错误不可以重试
            logger.error(f"轮询获取解析结果,出现异常,异常状态码:{status_code},异常是不可修复和重试的,业务无法继续,提前终止!")
            raise RuntimeError(f"轮询获取解析结果,出现异常,异常状态码:{status_code},异常是不可修复和重试的,业务无法继续,提前终止!")

        json_data = response.json()
        code = json_data.get("code",-1)
        if code != 0:
            logger.error(
                f"轮询获取解析结果,业务状态出现异常,异常状态码:{code},异常是不可修复和重试的,业务无法继续,提前终止!")
            raise RuntimeError(
                f"轮询获取解析结果,业务状态出现异常,异常状态码:{code},异常是不可修复和重试的,业务无法继续,提前终止!")

        #判断文件的解析状态state
        result = json_data.get("data",{}).get("extract_result",[])[0]
        state = result.get("state")

        if state == "done":
            #解析完成
            full_zip_url:str = result.get("full_zip_url")
            logger.info(f"完成文件内容的解析,获取的下载地址为:{full_zip_url}")
            return full_zip_url
        elif state == "failed":
            #解析失败
            logger.error(f"文件解析失败,业务无法继续,提前终止!")
            raise RuntimeError(f"文件解析失败,业务无法继续,提前终止!")
        else:
            #解析进行中
            logger.info(f"文件正在解析中,当前状态为:{state},稍后重试")
            time.sleep(interval_time)  # 线程休眠!
            continue

    """
        我申请文件上传地址 -> minerU -> 上传文件的地址
        我向上传文件的地址 -> 上传文件的地址 -> put(data=文件数据)
        轮询等待minerU的解析状态 ->[ 轮询 ] 查询解析状态  batch_id-> zip_url下载解析结果的地址
        
        minerU获取解析结果的两种方案:
        方案1:轮询 batch_id -> 根据batch_id 轮询查询即可
        
        
        方案2:接口回调 申请-> 配置回调接口 -> minerU解析完毕 -> 他主动调用接口 -> 传递解析结果
            问题1:
            接口地址必须是公网地址
            问题2:
            异步动作
    """


def parse_pdf_to_markdown(state: ImportGraphState) -> ImportGraphState:
    #1. 类型参数合理性校验
    pdf_path_obj,local_dir_obj = validates_pdf_paths(state)
    #2. 向minerU申请文件上传地址和batch_id
    batch_id,upload_file_url = apply_mineru_get_upload_url(pdf_path_obj.name)
    #3. 向指定的文件地址(预签名地址)上传文件数据
    upload_file_to_url(upload_file_url,pdf_path_obj)
    #4. 轮询获取解析结果
    full_zip_url:str = poll_mineru_zip_url(batch_id)
    return state