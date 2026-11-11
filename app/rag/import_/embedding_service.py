from typing import Any

from app.process.import_.agent.state import ImportGraphState
from app.rag.import_.config import EMBEDDING_BATCH_SIZE
from app.shared.runtime.logger import logger, step_log
from app.infra.llm.providers import llm_provider

@step_log("validata_and_get_chunks")
def validata_and_get_chunks(state: ImportGraphState) -> list[dict[str,Any]]:
    chunks = state.get("chunks")
    if not chunks:
        logger.error(f"chunks内容为空,业务无法继续,提前终止!")
        raise ValueError(f"chunks内容为空,业务无法继续,提前终止!")
    return chunks

@step_log("batch_chunks_embedding")
def batch_chunks_embedding(state: ImportGraphState):
     chunks: list[dict[str,Any]] = validata_and_get_chunks(state)
     total = len(chunks)
     for index in range(0,total,EMBEDDING_BATCH_SIZE):
         logger.debug(f"进行{index}-{index+EMBEDDING_BATCH_SIZE}批次的chunks向量化处理!")
         sub_chunks: list[dict[str,Any]] = chunks[index:index+EMBEDDING_BATCH_SIZE]
         item_name_and_content: list[str] = []
         for sub_chunk in sub_chunks:
             item_name_and_content.append(sub_chunk["item_name"]+ ":" + sub_chunk["content"])
         result = llm_provider.generate_infra_embeddings(item_name_and_content)
         for sub_index in range(len(sub_chunks)):
             dense_vector = result["dense"][sub_index]
             sparse_vector = result["sparse"][sub_index]
             sub_chunks[sub_index]["dense_vector"] = dense_vector
             sub_chunks[sub_index]["sparse_vector"] = sparse_vector
     logger.info(f"已经完成所有切片的内容向量化了!,打印示例:{chunks[0]}")

@step_log("generate_chunk_embeddings")
def generate_chunk_embeddings(state: ImportGraphState) -> ImportGraphState:
    #1. 参数校验和获取
    chunks: list[dict[str,Any]] = validata_and_get_chunks(state)
    #2. 批量向量化处理
    batch_chunks_embedding(state)
    #3. 更新state
    state["embeddings_content"] = chunks
    #4. 返回state
    return state