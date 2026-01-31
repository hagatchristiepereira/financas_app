import logging

def get_logger(name: str = "minha_renda"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler("app.log", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_logger()