from app.shared.runtime.logger import logger
from app.process.query.agent.state import create_query_default_state,QueryGraphState
from app.process.query.agent.main_graph import query_graph_app
import json

# 1. 准备state数据 [session_id,original_query,history = 省略]
state:QueryGraphState = create_query_default_state(session_id="9527",original_query="它还好么?",item_names=["驴蛋蛋"])
# 2. 动态执行(动态执行)
result = query_graph_app.invoke(state)

logger.info(f"完成动态测试\n {json.dumps(result,ensure_ascii=False,indent=4)}")
# 3. 静态执行
query_graph_app.get_graph().print_ascii()