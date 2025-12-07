# main.py
from smartmoney.db import init_db
from smartmoney.engine.runner import main_loop

if __name__ == "__main__":
    init_db()
    main_loop()
