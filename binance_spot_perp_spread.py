import time
from pathlib import Path

import ccxt
import pandas as pd


# ======================
# 参数区
# ======================
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
]

SPREAD_OPEN_THRESHOLD = 0.003   # 0.3% 以上认为有套利价值
SPREAD_CLOSE_THRESHOLD = 0.001  # 0.1% 回归可平仓
BINANCE_FEE = 0.0004
GATE_FEE = 0.0004
MAX_ORDER_SIZE = 5
orders = pd.DataFrame(columns=["symbol", "side", "price", "amount", "fee", "timestamp"])

# ======================
# 初始化交易所
# ======================
binance_spot = ccxt.binance({
    "enableRateLimit": True,
    'proxies': {
        'https': 'http://127.0.0.1:7897'
    }
})

binance_perp = ccxt.binance({
    "enableRateLimit": True,
    "options": {
        "defaultType": "future"   # USDT 永续
    },
    'proxies': {
        'https': 'http://127.0.0.1:7897'
    }
})

gate_spot = ccxt.gate({
    "enableRateLimit": True,
    'proxies': {
        'https': 'http://127.0.0.1:7897'
    }
})

gate_perp = ccxt.gate({
    "enableRateLimit": True,
    "options": {
        "defaultType": "future"   # USDT 永续
    },
    'proxies': {
        'https': 'http://127.0.0.1:7897'
    }
})

# 获取流动性评分阈值
LIQUIDITY_SCORE_THRESHOLD = 0.4

# ======================
# 获取流动性评分
# Score	含义
# > 0.8	非常适合套利
# 0.6~0.8	可做
# 0.4~0.6	小仓位
# < 0.4	放弃
# ======================
def liquidity_score(exchange, symbol):
    ticker = exchange.fetch_ticker(symbol)
    ob = exchange.fetch_order_book(symbol, limit=10)

    spread = (ob["asks"][0][0] - ob["bids"][0][0]) / ob["bids"][0][0]
    volume = ticker["quoteVolume"]

    score = (
        min(volume / 2e7, 1) * 0.5 +            # 24h的成交量达2000万作为满分占比
        max(0, 1 - spread * 1000) * 0.5
    )
    print(f"{symbol} liquidity score: {score}, volume: {volume:.2f}, spread: {spread:.3%}")
    return round(score, 3)

def get_enable_symbols():
    binance_spot_symbols = binance_spot.load_markets()
    gate_perp_symbols = gate_perp.load_markets()

    usdt_perp_symbols = []
    for symbol, m in binance_spot_symbols.items():
        # 检查是否为U本位永续合约
        if m.get("swap") and m.get("linear") and m.get("settle") == "USDT":
            usdt_perp_symbols.append(symbol)
    symbols = [symbol for symbol in gate_perp_symbols if symbol in usdt_perp_symbols]
    enable_symbols = [symbol for symbol in symbols if liquidity_score(gate_perp, symbol) > LIQUIDITY_SCORE_THRESHOLD]  # noqa: E501
    print("Liquidity filter symbols counts ", len(enable_symbols))
    return enable_symbols

def get_spread_and_slippage(exchange, symbol, side, order_usdt, depth_limit=20):
    """
    使用 ccxt 获取点差和滑点 USDT 计价
    """
    # 1️⃣ 获取订单簿
    ob = exchange.fetch_order_book(symbol, limit=depth_limit)

    bids = ob["bids"]
    asks = ob["asks"]

    if not bids or not asks:
        raise ValueError("Orderbook is empty")

    best_bid = bids[0][0]
    best_ask = asks[0][0]

    # 2️⃣ 计算点差
    spread = (best_ask - best_bid) / best_bid

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
    slippage = abs(avg_price - best_price) / best_price
    print(f"{symbol} spread: {spread:.3%} slippage: {slippage:.3%}")
    return spread + slippage


# ======================
# 主逻辑
# ======================
def check_spread(symbols):
    rows = []
    for symbol in symbols:
        try:
            binance_ticker = binance_perp.fetch_ticker(symbol)
            gate_ticker = gate_perp.fetch_ticker(symbol)

            binance_price = binance_ticker["last"]
            gate_price = gate_ticker["last"]

            if not binance_price or not gate_price:
                continue
            gross = (gate_price - binance_price) / binance_price

            binance_spread = get_spread_and_slippage(binance_spot, symbol, "buy" if (gross > 0) else "sell", binance_price * 1000, 20)   # noqa: E501
            gate_spread = get_spread_and_slippage(gate_spot, symbol, "buy" if (gross <= 0) else "sell", gate_price * 1000, 20)   # noqa: E501
            spread = binance_spread + gate_spread

            fee = BINANCE_FEE * 2 + GATE_FEE * 2
            net = gross - fee - spread

            # 套利方向判断
            if net > SPREAD_OPEN_THRESHOLD:
                signal = "Gate做多 + Binance做空"
            elif net < -SPREAD_OPEN_THRESHOLD:
                signal = "Binance做多 + Gate做空"
            else:
                signal = "无明显机会"

            rows.append({
                "symbol": symbol,
                "binance": round(binance_price, 4),
                "gate": round(gate_price, 4),
                "net_%": round(net * 100, 3),
                "signal": signal
            })

        except Exception as e:
            print(f"{symbol} error:", e)

    df = pd.DataFrame(rows)
    df = df.sort_values("net_%", ascending=False)
    print("\n", df.to_string(index=False))

    file_exists =Path.exists("spread.csv")
    df.to_csv("spread.csv", mode='a', index=False, header=not file_exists)


# ======================
# 循环监控
# ======================
if __name__ == "__main__":
    # symbols = get_enable_symbols()
    symbols = ["RIVER/USDT:USDT"]
    while True:
        check_spread(symbols)
        time.sleep(10)  # 每 10 秒刷新
