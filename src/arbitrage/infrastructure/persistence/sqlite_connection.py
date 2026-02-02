import sqlite3
from pathlib import Path


class SqliteConnection:
    def __init__(self, db_path: str = "data/arb.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)  # 确保目录存在

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn