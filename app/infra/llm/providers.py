from app.shared.model.embedding_utils import generate_embeddings
from app.shared.model.lm_utils import get_llm_client
from app.infra.config.providers import infra_config


class LLMProvider:

    #大语言模型
    def chat(self,model:str|None = None,json_model:bool=False):
        return get_llm_client(model=model,json_mode=json_model)
    #视觉模型
    def vision_chat(self,model:str|None = None):
        if not model:
            model = infra_config.lm_config.lv_model
        return get_llm_client(model=model,json_mode=False)
    #添加新的方法,进行嵌入式向量生成
    def generate_infra_embeddings(self,texts: list[str]) -> dict[str, list]:
        return generate_embeddings(texts)
    #-------------------以下暂时不封装,后面再修改-----------------------
    #嵌入式模型


    #重排序模型

llm_provider = LLMProvider()