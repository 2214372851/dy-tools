import time
import logging

logger = logging.getLogger(__name__)


def retry(retry_num=5):
    def wrapper(func):
        def inner(*args, **kwargs):
            for i in range(retry_num):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f'第{i + 1}次重试:{e}')

        return inner

    return wrapper
