import logging
import sys
import os
from datetime import datetime

class LogSetup:
    def __init__(self):
        self.timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    def get_timestamp(self):
        return self.timestamp

    def setup_logging(self):
        if not os.path.exists("log"):
            os.makedirs("log")
            
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        if logger.hasHandlers():
            logger.handlers.clear()

        log_filename = f'{self.timestamp}_stress_test.log'
        log_path = os.path.join("log", log_filename)

        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger