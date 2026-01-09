from typing import Any

import ccxt


class ExchangeManager:
    def __init__(self):
        self.exchanges: dict[str, dict[str, Any]] = {}

    def add_exchange(self, exchange: dict[str, Any], config: dict[str, Any]):
        exchange_config = config.get('exchange', {})
        name = exchange["name"]

        if not hasattr(ccxt, name):
            print(f"[WARN] ccxt 不支持交易所: {name}")
            return

        exchange_class = getattr(ccxt, name)
        ex = exchange_class(exchange_config)

        self.exchanges[name] = {
            "ex": ex,
            "config": exchange
        }

    def get_exchanges(self):
        return self.exchanges
    
    def get_exchange_ins(self, name: str) -> ccxt.Exchange:
        return self.exchanges[name]["ex"]
    
    def get_last_price(self, exchange_name: str, symbol: str) -> float:
        """
        获取指定交易所的指定symbol的最新价格
        :param exchange_name: 交易所名称
        :param symbol: 交易对
        :return: 最新价格
        """
        exchange = self.get_exchange_ins(exchange_name)
        ticker = exchange.fetch_ticker(symbol)
        return ticker["last"]
    
    def get_order_book(self, exchange_name: str, symbol: str, limit: int = 10) -> dict[str, Any]:
        """
        获取指定交易所的指定symbol的订单簿数据
        :param exchange_name: 交易所名称
        :param symbol: 交易对
        :param limit: 订单簿数据条数
        :return: 订单簿数据
        """
        exchange = self.get_exchange_ins(exchange_name)
        return exchange.fetch_order_book(symbol, limit=limit)

    def fetch_perp_markets(self, exchange: dict[str, Any]) -> list[dict[str, Any]]:
        """
        获取指定交易所的永续合约市场数据
        :param name: 交易所名称
        :return: market列表，每个market是字典，包含 symbol, base, quote, contract_size, min_qty, leverage_max
        """
        ex = exchange['ex']
        exchange_id = exchange['config']['id']

        markets = ex.load_markets()
        result = []

        for symbol, market in markets.items():
            if not market.get("swap") or not market.get("linear") or market.get("settle") != "USDT":
                continue

            base = market.get('base')
            quote = market.get('quote')
            contract_size = market.get('contractSize', 1)
            min_qty = market.get('limits', {}).get('amount', {}).get('min', 0)
            leverage_max = market.get('limits', {}).get('leverage', {}).get('max', 0)

            result.append({
                'exchange_id': exchange_id,
                'symbol': symbol,
                'base': base,
                'quote': quote,
                'contract_size': contract_size,
                'min_qty': min_qty,
                'leverage_max': leverage_max
            })

        return result

    def liquidity_score(self, exchange_name, symbol: str) -> float:
        """
        获取指定交易所的指定symbol的流动性分数
        :param exchange_name: 交易所名称
        :param symbol: 交易对
        :return: 流动性分数
        """
        exchange = self.get_exchange_ins(exchange_name)
        ticker = exchange.fetch_ticker(symbol)
        ob = exchange.fetch_order_book(symbol, limit=10)

        if not ob["asks"] or not ob["bids"]:
            print(f"{symbol} 订单簿数据不足，无法计算流动性评分")
            return 0.0
    
        spread = (ob["asks"][0][0] - ob["bids"][0][0]) / ob["bids"][0][0]
        volume = ticker["quoteVolume"]

        score = (
            min(volume / 2e7, 1) * 0.5 +            # 24h的成交量达2000万作为满分占比
            max(0, 1 - spread * 1000) * 0.5
        )
        print(f"{symbol} liquidity score: {score}, volume: {volume:.2f}, spread: {spread:.3%}")
        return round(score, 3)