import time
from typing import Any
from utils import is_lock, set_lock

import context


def sync_all_perp_markets_to_db():
    lock_name = "sync-all-perp-markets"
    if is_lock(lock_name):
        return
    for name, exchange in context.em.get_exchanges().items():
        sync_perp_markets_to_db(context.em.fetch_perp_markets(exchange))
        print(f"同步市场完成: {name}")
    set_lock(lock_name)

def sync_perp_markets_to_db(markets: list[dict[str, Any]]):
    """
    将market列表同步到数据库：
    1. 新的市场 -> 插入
    2. 已存在市场 -> 更新
    3. 已不存在的市场 -> 删除
    完全使用 db 封装方法
    """
    if not markets:
        return

    # 假设 markets 都是同一个交易所
    exchange_id = markets[0]['exchange_id']

    # 1. 查询数据库已有市场
    db_markets = context.db.fetch_all('perp_market', 'exchange_id=?', (exchange_id,))
    db_symbols = {m['symbol']: m['id'] for m in db_markets}

    # 2. 遍历最新市场数据
    new_symbols = set()
    for data in markets:
        symbol = data['symbol']
        new_symbols.add(symbol)

        if symbol in db_symbols:
            # 已存在 -> 更新
            context.db.update('perp_market', data, 'id=?', (db_symbols[symbol],))
            print(f"更新市场: {symbol}")
        else:
            # 新增 -> 插入
            context.db.insert('perp_market', data)
            print(f"新增市场: {symbol}")

    # 3. 删除已不存在的市场
    to_delete = set(db_symbols.keys()) - new_symbols
    for symbol in to_delete:
        context.db.delete('perp_market', 'exchange_id=? AND symbol=?', (exchange_id, symbol))
        print(f"删除市场: {symbol}")
