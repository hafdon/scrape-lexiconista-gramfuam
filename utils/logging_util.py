from config.config import LOG_FILE

import logging

def create_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Set the root logger to the lowest level

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler = logging.FileHandler(LOG_FILE)
    stream_handler = logging.StreamHandler()

    # File handler for 'process.log' with level DEBUG
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Stream handler for stdout with level INFO
    stream_handler.setLevel(logging.CRITICAL)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger