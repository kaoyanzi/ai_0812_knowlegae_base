from typing import Any

from pymilvus import MilvusClient, DataType

from app.infra.vectorstore.milvus_gateway import milvus_gateway
from app.process.import_.agent.state import ImportGraphState
from app.shared.runtime.logger import logger, step_log


@step_log("validata_and_get_chunks")
def validata_and_get_chunks(state: ImportGraphState) -> list[dict[str,Any]]:
    embeddings_content = state.get("embeddings_content")
    if not embeddings_content:
        logger.error(f"embeddings_content内容为空,业务无法继续,提前终止!")
        raise ValueError(f"embeddings_content内容为空,业务无法继续,提前终止!")
    return embeddings_content

@step_log("repared_item_name_collection")
def prepared_item_name_collection():
    #检查集合是否存在
    milvus_client:MilvusClient = milvus_gateway.client
    has:bool = milvus_client.has_collection(collection_name=milvus_gateway.chunks_collection)
    if has:
        logger.info(f"{milvus_gateway.chunks_collection}已经存在,确保加载后返回!")
        milvus_client.load_collection(
            collection_name=milvus_gateway.chunks_collection,
        )
        return
    schema = milvus_client.create_schema(
        auto_id=True,#主键自增
        enable_dynamic_collection=True,#默认允许超列插入,增加容错
    )

    #往schema里面添加字段
    schema.add_field(field_name="chunk_id",datatype=DataType.INT64,is_primary=True)
    schema.add_field(field_name="file_title",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="item_name",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="parent_title",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="title",datatype=DataType.VARCHAR,max_length=600)
    schema.add_field(field_name="part",datatype=DataType.INT8)
    schema.add_field(field_name="content",datatype=DataType.VARCHAR,max_length=65535)
    schema.add_field(field_name="dense_vector",datatype=DataType.FLOAT_VECTOR,dim=1024)
    schema.add_field(field_name="sparse_vector",datatype=DataType.SPARSE_FLOAT_VECTOR)


    #创建索引
    index_param = milvus_client.prepare_index_params()
    index_param.add_index(
        field_name="dense_vector",
        index_type="HNSW",
        index_name="dense_vector_index",
        metric_type="COSINE",
        index_params={
            "M":64,#邻居数量
            "efConstruction":100,#从多少个点中选出邻居的数量
        },
    )

    index_param.add_index(
        field_name="sparse_vector",
        index_type="SPARSE_INVERTED_INDEX",#稀疏倒排索引 从数据->向量 每次查询时先定位坐标关联的数据集合
        index_name="sparse_dense_vector_index",
        metric_type="IP",
        index_params={
            "inverted_index_algo":"SINDI"#IP提高查询效率的方式
        },
    )

    #创建集合
    milvus_client.create_collection(
        collection_name=milvus_gateway.chunks_collection,
        schema=schema,
        index_params=index_param,
    )

    #把集合从磁盘加载到内存
    milvus_client.load_collection(
        collection_name=milvus_gateway.chunks_collection,
    )

@step_log("insert_or_update_chunks")
def insert_or_update_chunks(embeddings_content: list[dict[str,Any]]):
    file_title = embeddings_content[0].get("file_title")
    milvus_client:MilvusClient = milvus_gateway.client
    delete_result = milvus_client.delete(
        collection_name=milvus_gateway.chunks_collection,
        filter=f"file_title=='{file_title}'",
    )
    delete_count = delete_result.get("delete_count",0)
    logger.info(f"删除{file_title}下对应的{delete_count}条数据")

    insert_result = milvus_client.insert(
        collection_name=milvus_gateway.chunks_collection,
        data=embeddings_content,
    )
    insert_count = insert_result.get("insert_count",0)
    logger.info(f"已经完成数据插入,本次插入{insert_count}条数据")
    ids:list = insert_result.get("ids",[])
    for id,chunk in zip(ids,embeddings_content):
        chunk['chunk_id'] = id

@step_log("index_chunks")
def index_chunks(state: ImportGraphState) -> ImportGraphState:
    #1. 获取并校验数据
    embeddings_content:list[dict[str,Any]] = validata_and_get_chunks(state)
    #2. 提前准备chunk存储的集合
    prepared_item_name_collection()
    #3. 进行数据更新和插入
    insert_or_update_chunks(embeddings_content)
    #4. 修改和返回结果
    return state