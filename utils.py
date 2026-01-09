from config import Config

import time
import os


def load_config(config_path: str = "config.yml") -> Config:
    """加载配置文件并返回Config对象"""
    return Config.from_yaml(config_path)


def is_lock(name: str) -> bool:
    current_time = time.time()
    lock_file_path = f"{name}.lock"
    if not os.path.exists(lock_file_path):
        return False
    
    if os.path.exists(lock_file_path):
        with open(lock_file_path, 'r') as f:
            last_run_time = float(f.read().strip())
        
        # 计算时间差（小时）
        time_diff = (current_time - last_run_time) / 60 /60
        
        if time_diff < 24:  # 小于24小时，不执行
            print(f"[{name}] 距离上次执行不足24小时 ({time_diff:.2f}小时)，跳过本次执行")
            return True
        return False

def set_lock(name: str):
    current_time = time.time()
    lock_file_path = f"{name}.lock"
    with open(lock_file_path, 'w') as f:
        f.write(str(current_time))

def get_spread(ob: dict[str, object]) -> float:
    """
    计算点差
    :param ob: 订单簿数据
    :return: 点差
    """
    bids = ob["bids"]
    asks = ob["asks"]

    if not bids or not asks:
        raise ValueError("Orderbook is empty")

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    # 2️⃣ 计算点差
    return (best_ask - best_bid) / best_bid

def get_slippage(ob: dict[str, object], side: str, order_usdt: float) -> float:
    """
    计算滑点
    :param ob: 订单簿数据
    :param side: 买单/卖单
    :param order_usdt: 订单USDT数量
    :return: 滑点
    """
    bids = ob["bids"]
    asks = ob["asks"]

    if not bids or not asks:
        raise ValueError("Orderbook is empty")

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    # 3️⃣ 根据方向选择吃哪一边
    book = asks if side == "buy" else bids

    filled_usdt = 0
    filled_amount = 0

    for price, amount in book:
        level_value = price * amount

        if filled_usdt + level_value >= order_usdt:
            remaining = order_usdt - filled_usdt
            filled_amount += remaining / price
            filled_usdt += remaining
            break
        else:
            filled_amount += amount
            filled_usdt += level_value

    # 4️⃣ 成交均价
    avg_price = filled_usdt / filled_amount

    # 5️⃣ 滑点计算
    best_price = best_ask if side == "buy" else best_bid
    return abs(avg_price - best_price) / best_price