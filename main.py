import context
from arbitrage_db import ArbitrageDB
from exchange_manager import ExchangeManager
from market_util import sync_all_perp_markets_to_db
from pair_util import sync_arb_pairs
from utils import load_config


def init_config():
    context.config = load_config()

def init_db():
    """初始化数据库连接"""
    context.db = ArbitrageDB("arb.db")
    context.db.init_db()


def init_em(api_keys=None) -> ExchangeManager:
    context.em = ExchangeManager()
    rows = context.db.fetch_all("exchange", where="type = ?", params=("cex",))
    for row in rows:
        context.em.add_exchange(exchange=dict(row), config = context.config)

# ======================
# 循环监控
# ======================
if __name__ == "__main__":
    init_config()
    init_db()
    init_em()
    sync_all_perp_markets_to_db()
    sync_arb_pairs()
    context.db.close()
