import logging
from rich.logging import RichHandler


def setup_logger(log_file: str = "app.log"):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    console_log = RichHandler(log_time_format="%Y-%m-%d %H:%M:%S")
    file_log = logging.FileHandler(filename=log_file, encoding="utf-8")
    file_log.setFormatter(
        logging.Formatter(
            "%(asctime)s %(filename)s:%(lineno)s %(levelname)s %(message)s"
        )
    )

    logger.addHandler(console_log)
    logger.addHandler(file_log)

    return logger


logger = setup_logger()
