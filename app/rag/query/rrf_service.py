from app.process.query.agent.state import QueryGraphState
from app.shared.runtime.logger import step_log, logger

# RRF 融合默认配置
# 最终返回的融合结果数量
top = 5
# RRF 公式平滑系数，避免排名过低导致分数趋近于 0
k = 60

@step_log("validate_rrf_inputs")
def validate_rrf_inputs(state: dict) -> tuple[list[dict], list[dict]]:
    """
    校验 RRF 融合所需的两路本地检索结果是否合法
    允许单路有结果、另一路为空，但不允许两路都为空
    """
    # 获取普通向量检索结果、HyDE 增强检索结果
    embedding_chunks = state.get("embedding_chunks", [])
    hyde_chunks = state.get("hyde_embedding_chunks", [])

    # 核心校验：两路都为空则无法融合，直接抛出异常
    if not embedding_chunks and not hyde_chunks:
        logger.error("embedding_chunks 和 hyde_embedding_chunks 均为空，RRF 融合无有效数据！")
        raise ValueError("RRF 融合失败：本地两路检索结果均为空")

    return embedding_chunks, hyde_chunks

@step_log("reciprocal_rank_fusion")
def reciprocal_rank_fusion(
        param_list: list[tuple[list[dict], float]],
        *,
        k: int = 60,
        top: int = 5,
) -> list[dict]:
    score_dict: dict[str,float] = {}
    entity_dict: dict[str,dict] = {}

    for chunks_list,weight in param_list:
        for rank,chunk in enumerate(chunks_list,start=1):
            chunk_id = chunk.get("chunk_id")
            if not chunk_id:
                continue

            score_dict[chunk_id] = score_dict.get(chunk_id, 0.0) + (1.0/(k + rank))*weight
            entity_dict.setdefault(chunk_id, chunk)

    document_list = []
    for chunk_id,score in score_dict.items():
        document = entity_dict.get(chunk_id, {}).copy()
        document["score"] = score
        document_list.append(document)

    document_list.sort(key=lambda x: x.get("score",0.0), reverse=True)

    return document_list[:top]




@step_log("fuse_by_rrf")
def fuse_by_rrf(state: QueryGraphState) -> list[dict]:
    """
    RRF 融合节点入口
    负责将本地两路检索结果（普通向量 + HyDE）进行加权融合
    两路默认权重均为 1.0
    """
    # 1. 校验两路输入结果是否合法
    embedding_chunks, hyde_embedding_chunks = validate_rrf_inputs(state)

    # 2. 构造 RRF 入参：(结果列表, 权重)
    param_list = [
        (embedding_chunks, 1.0),  # 普通向量检索，权重1.0
        (hyde_embedding_chunks, 1.0),  # HyDE增强检索，权重1.0
    ]

    # 3. 执行 RRF 融合并返回最终结果
    return reciprocal_rank_fusion(param_list)