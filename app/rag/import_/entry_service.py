import os.path

from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger, step_log
from pathlib import Path

@step_log("resolve_input_file")
def resolve_input_file(state: ImportGraphState) -> ImportGraphState:

    #入口识别服务：
    local_file_path:str = state.get("local_file_path")
    #1. 校验 local_file_path
    if not local_file_path:
        #为空 local_file_path error + raise
        #前因 后果 关键参数
        logger.error(f"local_file_path 为空,业务无法继续进行,提前终止")
        raise ValueError(f"local_file_path 为空,业务无法继续进行,提前终止")
    #2. 识别文件类型（PDF / Markdown）
    #xx.MD xx.PDF
    if local_file_path.lower().endswith(".md"):
        # 3. 回写 is_pdf_read_enabled / is_md_read_enabled
        state['is_md_read_enable'] = True
        state['is_pdf_read_enable'] = False
        state['md_path'] = local_file_path

    elif local_file_path.lower().endswith(".pdf"):
        # 4. 回写 pdf_path / md_path
        state['is_pdf_read_enable'] = True
        state['is_md_read_enable'] = False
        state['pdf_path'] = local_file_path
    else:
        return state

    #5.回写file_title
    #3.4之前os.path字符串操作哦
    #os.path.basename(local_file_path)
    #os.path.splitext(local_file_path)[0]
    #3.4之后pathlib利用面向对象的思路进行操作
    local_file_obj:Path = Path(local_file_path)
    file_title:str = local_file_obj.stem
    """
    Path的使用分三步
        1.创建对应的Path对象
            x:Path = Path(字符串地址)    获取地址对应的Path对象
            x:Path = Path(Path对象)     暂时用处不大
            x:Path = Path()            获取当前文件所在的文件夹 linux pwd
            x:Path = Path(__file__)    获取当前文件的Path地址
            x:Path = Path对象 / "字符串地址" / "字符串地址" ROOT_PATH / "output"
        2. .属性      文件名
            .name   获取文件的完整文件名 info.pdf
            .stem   获取文件名部分 info
            .suffix 获取后缀名部分 .pdf
            .parent 获取父Path对象   Path(__file__).parent.parent
            .parents    获取所以的文件夹    Path(__file__).parent[1] = [import_,rag,app,项目根地址...]
        3. .方法()    创建一个文件夹  查询文件是否存在
    """
    state['file_title'] = file_title
    return state