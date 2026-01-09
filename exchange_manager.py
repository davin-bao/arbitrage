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

