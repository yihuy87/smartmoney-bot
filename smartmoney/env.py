# smartmoney/env.py
from dotenv import load_dotenv
import os

# load .env di root project
load_dotenv()

def env(key: str, default=None):
    return os.getenv(key, default)
