import logging

from dotenv import load_dotenv

from ._main import main
from .s3 import S3Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(pathname)s | %(name)s | func: %(funcName)s:%(lineno)s | %(levelname)s | %(message)s",
)