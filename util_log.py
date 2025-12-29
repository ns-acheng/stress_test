import logging
import sys
import os
from datetime import datetime

class LogSetup:
    def __init__(self):
        self.timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.log_folder = os.path.join("log", self.timestamp)

    def get_timestamp(self):
        return self.timestamp
    
    def get_log_folder(self):
        return self.log_folder

    def setup_logging(self):
        if not os.path.exists(self.log_folder):
            os.makedirs(self.log_folder)
            
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        if logger.hasHandlers():
            logger.handlers.clear()

        log_filename = 'stress_test.log'
        log_path = os.path.join(self.log_folder, log_filename)

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