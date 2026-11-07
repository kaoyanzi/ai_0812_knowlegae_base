
from app.shared.runtime.logger import logger

#  from loguru import logger -> remove -> add / add -> logger

logger.debug("This is an info message")
logger.info("This is an info message")
logger.warning("This is an info message")
logger.error("This is an info message")

name="二狗子"
age=18

logger.info(f"姓名:{name},age:{age}")
logger.info("姓名:{},age:{}",name,age)


try:
    a = 1/0
except Exception as e:
    logger.exception(f"This is an info message {e}")
