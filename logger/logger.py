import os
import logging

from logging.handlers import RotatingFileHandler


class SubtitleFilter(logging.Filter):
    def __init__(self, subtitle: str):
        super().__init__()
        self.subtitle = subtitle

    def filter(self, record):
        record.subtitle = self.subtitle
        return True
    
def reset_logging(log_path: str = "logs/logs.txt"):
    if os.path.exists(log_path):
        os.remove(log_path)
        print(f"File '{log_path}' deleted successfully.")
    else:
        print(f"File '{log_path}' not found.")

def get_logger(subtitle: str, log_path: str = "logs/logs.txt", level=logging.INFO) -> logging.Logger:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger(f"kasa_logger_{subtitle}")
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(subtitle)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        file_handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SubtitleFilter(subtitle))
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(SubtitleFilter(subtitle))
        logger.addHandler(stream_handler)

    return logger
