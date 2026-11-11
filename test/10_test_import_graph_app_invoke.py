from pathlib import Path

from app.process.import_.agent.state import create_default_state,ImportGraphState
from app.process.import_.agent.main_graph import import_graph_app
from app.shared.runtime.logger import logger,PROJECT_ROOT
import uuid
import json


local_file_path_obj:Path = PROJECT_ROOT / "doc" / "hak180_clean.pdf"
local_dir_obj:Path = PROJECT_ROOT / "output"
task_id:str = str(uuid.uuid4())
state:ImportGraphState = create_default_state(
    task_id = task_id,
    local_file_path = str(local_file_path_obj),
    local_dir = str(local_dir_obj),
)

logger.info(f"执行参数:\n{json.dumps(state,indent=4,ensure_ascii=False)}")

result:ImportGraphState = import_graph_app.invoke(state)

logger.info(f"最终结果:\n{json.dumps(result,indent=4,ensure_ascii=False)}")