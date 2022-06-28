import logging
import sys

LOG_FORMAT = "%(asctime)s.%(msecs)03d|%(levelname).1s|%(filename)s:%(lineno)d|%(message)s"

logger = logging.getLogger("raspinukibridge")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
logger.addHandler(handler)