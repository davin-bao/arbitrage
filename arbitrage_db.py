import os
import sqlite3
from typing import Any, Optional


class ArbitrageDB:
    """
    跨交易所 / 永续合约套利系统的 SQLite 数据库封装
    """

    def __init__(self, db_path: str = "arb.db"):
        """
        :param db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    # =========================
    # 基础连接与初始化
    # =========================

    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # 必须的性能与并发配置（套利系统强烈建议）
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def init_db(self):
        """
        若数据库不存在则创建，并初始化所有表结构
        """
        first_create = not os.path.exists(self.db_path)

        self.connect()

        if first_create:
            self._create_tables()
            self._init_exchange()

    # =========================
    # 表结构定义
    # =========================

    def _create_tables(self):
        """
        创建所有表
        """

        cursor = self.conn.cursor()

        # -------------------------
        # 1. 交易所表
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,          -- 交易所名称，如 binance / okx
            type TEXT,                 -- 类型，如 cex
            timezone TEXT,             -- 时区
            fee_maker REAL,            -- maker 手续费
            fee_taker REAL,            -- taker 手续费
            last_sync_market_time INTEGER -- 上次更新market时间
        )
        """)

        # -------------------------
        # 2. 永续合约市场表
        # 一个交易所 + 一个永续合约 = 一条记录
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS perp_market (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exchange_id INTEGER,       -- 所属交易所（exchange.id）
            symbol TEXT,               -- BTC/USDT:USDT
            base TEXT,                 -- BTC
            quote TEXT,                -- USDT
            contract_size REAL,        -- 合约面值
            min_qty REAL,              -- 最小下单量
            leverage_max INTEGER,      -- 最大杠杆
            FOREIGN KEY(exchange_id) REFERENCES exchange(id)
        )
        """)

        # -------------------------
        # 3. 行情快照表
        # 高频数据，可重算
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshot (
            market_id INTEGER,         -- perp_market.id
            ts TEXT,                   -- 时间戳
            last_price REAL,           -- 最新成交价
            mark_price REAL,           -- 标记价格
            index_price REAL,          -- 指数价格
            volume_24h REAL,           -- 24h 成交量
            open_interest REAL,        -- 持仓量
            PRIMARY KEY (market_id, ts),
            FOREIGN KEY(market_id) REFERENCES perp_market(id)
        )
        """)

        # -------------------------
        # 4. Funding 快照
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS funding_snapshot (
            market_id INTEGER,         -- perp_market.id
            ts TEXT,                   -- 记录时间
            funding_rate REAL,         -- 当前资金费率
            funding_time TEXT,         -- 结算时间
            FOREIGN KEY(market_id) REFERENCES perp_market(id)
        )
        """)

        # -------------------------
        # 5. 订单簿摘要
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orderbook_snapshot (
            market_id INTEGER,
            ts TEXT,
            bid_price REAL,
            bid_size REAL,
            ask_price REAL,
            ask_size REAL,
            FOREIGN KEY(market_id) REFERENCES perp_market(id)
        )
        """)

        # -------------------------
        # 6. 套利组合表（跨市场）
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS arb_pair (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_long_id INTEGER,    -- 做多市场
            market_short_id INTEGER,   -- 做空市场
            strategy_type TEXT,        -- spread / funding / hybrid
            active INTEGER DEFAULT 1,
            FOREIGN KEY(market_long_id) REFERENCES perp_market(id),
            FOREIGN KEY(market_short_id) REFERENCES perp_market(id)
        )
        """)

        # -------------------------
        # 7. 价差快照（派生数据）
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS spread_snapshot (
            arb_pair_id INTEGER,
            ts TEXT,
            spread REAL,               -- (short - long) / long
            z_score REAL,
            FOREIGN KEY(arb_pair_id) REFERENCES arb_pair(id)
        )
        """)

        # -------------------------
        # 8. 套利边际评估
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS edge_metrics (
            arb_pair_id INTEGER,
            ts TEXT,
            net_edge REAL,             -- 最终套利边际
            fee_cost REAL,
            slippage_cost REAL,
            funding_edge REAL,
            risk_discount REAL,
            FOREIGN KEY(arb_pair_id) REFERENCES arb_pair(id)
        )
        """)

        # -------------------------
        # 9. 套利仓位（一对一）
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS arb_position (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arb_pair_id INTEGER,
            entry_ts TEXT,
            entry_spread REAL,
            size_usdt REAL,
            status TEXT,               -- open / closing / closed
            expected_edge REAL,
            FOREIGN KEY(arb_pair_id) REFERENCES arb_pair(id)
        )
        """)

        # -------------------------
        # 10. 子仓位（两条腿）
        # -------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leg_position (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arb_position_id INTEGER,
            market_id INTEGER,
            side TEXT,                 -- long / short
            entry_price REAL,
            qty REAL,
            funding_collected REAL,
            unrealized_pnl REAL,
            FOREIGN KEY(arb_position_id) REFERENCES arb_position(id),
            FOREIGN KEY(market_id) REFERENCES perp_market(id)
        )
        """)

        self.conn.commit()


    def _init_exchange(self):
        self.insert("exchange", {
            "name": "binance",
            "type": "cex",
            "timezone": "UTC",
            "fee_maker": 0.0002,
            "fee_taker": 0.0004,
            "last_sync_market_time": 0
        })
        self.insert("exchange", {
            "name": "gateio",
            "type": "cex",
            "timezone": "UTC",
            "fee_maker": 0.0002,
            "fee_taker": 0.0005,
            "last_sync_market_time": 0
        })

    # =========================
    # 通用 CRUD 方法
    # =========================

    def insert(self, table: str, data: dict[str, Any]):
        """
        通用插入
        """
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
        self.conn.execute(sql, tuple(data.values()))
        self.conn.commit()

    def update(self, table: str, data: dict[str, Any], where: str, params: tuple):
        """
        通用更新
        """
        sets = ", ".join([f"{k}=?" for k in data.keys()])
        sql = f"UPDATE {table} SET {sets} WHERE {where}"
        self.conn.execute(sql, tuple(data.values()) + params)
        self.conn.commit()

    def delete(self, table: str, where: str, params: tuple):
        """
        通用删除
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        self.conn.execute(sql, params)
        self.conn.commit()

    def fetch_all(self, table: str, where: Optional[str] = None, params: tuple = ()):
        """
        查询多条
        """
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, table: str, where: str, params: tuple):
        """
        查询单条
        """
        sql = f"SELECT * FROM {table} WHERE {where}"
        cursor = self.conn.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None
