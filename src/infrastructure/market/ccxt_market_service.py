import ccxt
import time
from typing import List, Dict
from decimal import Decimal

from src.domain.services.market_service import MarketService
from src.domain.value_objects.pair import Pair
from src.domain.models.market_snapshot import MarketSnapshot, MarketLegSnapshot


class CCXTMarketService(MarketService):
    """
    基于CCXT的市场服务，从交易所获取实时行情数据
    """
    
    def __init__(self, exchanges_config: Dict[str, Dict]):
        """
        初始化CCXT市场服务
        
        Args:
            exchanges_config: 交易所配置，格式为：
            {
                "exchange_name": {
                    "apiKey": "...",
                    "secret": "...",
                    "sandbox": true/false,
                    ...
                }
            }
        """
        self.exchanges = {}
        self._initialize_exchanges(exchanges_config)
    
    def _initialize_exchanges(self, exchanges_config: Dict[str, Dict]):
        """
        根据配置初始化交易所实例
        """
        for exchange_name, config in exchanges_config.items():
            exchange_class = getattr(ccxt, exchange_name.lower())(config)
            
            # # 设置API密钥
            # if 'apiKey' in config:
            #     exchange_class.apiKey = config['apiKey']
            # if 'secret' in config:
            #     exchange_class.secret = config['secret']
            
            # # 设置沙盒模式
            # if config.get('sandbox', False):
            #     exchange_class.setSandboxMode(True)
            
            # # 设置限频
            # if config.get('enableRateLimit', False):
            #     exchange_class.enableRateLimit = True

            # # 设置代理
            # if 'proxies' in config:
            #     exchange_class.proxies = config.get('proxies')
            
            # # 设置其他选项
            # options = config.get('options', {})
            # for key, value in options.items():
            #     if not hasattr(exchange_class, 'options'):
            #         exchange_class.options = {}
            #     exchange_class.options[key] = value
            
            self.exchanges[exchange_name] = exchange_class
    
    def get_snapshot(self, pairs: List[Pair]) -> Dict[str, MarketSnapshot]:
        """
        获取指定交易对的市场快照
        """
        snapshots = {}
        
        for pair in pairs:
            try:
                # 获取长仓交易所的市场数据
                long_leg = self._get_market_leg_snapshot(
                    pair.long_exchange, 
                    pair.logical_symbol
                )
                
                # 获取短仓交易所的市场数据
                short_leg = self._get_market_leg_snapshot(
                    pair.short_exchange, 
                    pair.logical_symbol
                )
                
                if long_leg and short_leg:
                    snapshot = MarketSnapshot(
                        pair=pair,
                        timestamp=time.time(),
                        long_leg=long_leg,
                        short_leg=short_leg
                    )
                    snapshots[pair.pair_id] = snapshot
                    
            except Exception as e:
                print(f"Error getting snapshot for {pair.pair_id}: {str(e)}")
                continue
        
        return snapshots
    
    def _get_market_leg_snapshot(
        self, 
        exchange_name: str, 
        symbol: str
    ) -> MarketLegSnapshot:
        """
        获取单个交易所的市场数据
        """
        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange {exchange_name} not initialized")
        
        exchange = self.exchanges[exchange_name]
        
        # 获取ticker数据
        ticker = exchange.fetch_ticker(symbol)
        
        # 获取订单簿数据
        orderbook = exchange.fetch_order_book(symbol, limit=5)
        
        # 提取价格和大小数据
        last_price = Decimal(str(ticker.get('last'))) if ticker.get('last') else None
        last_timestamp = ticker.get('timestamp')
        
        # 获取买单和卖单数据
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        best_bid_price = Decimal(str(bids[0][0])) if bids and len(bids) > 0 else None
        best_bid_size = Decimal(str(bids[0][1])) if bids and len(bids) > 0 and len(bids[0]) > 1 else None
        best_ask_price = Decimal(str(asks[0][0])) if asks and len(asks) > 0 else None
        best_ask_size = Decimal(str(asks[0][1])) if asks and len(asks) > 0 and len(asks[0]) > 1 else None
                
        return MarketLegSnapshot(
            exchange=exchange_name,
            symbol=symbol,
            last_price=last_price,
            last_size=None,  # CCXT ticker doesn't always provide last size
            last_timestamp=last_timestamp,
            best_bid_price=best_bid_price,
            best_bid_size=best_bid_size,
            best_ask_price=best_ask_price,
            best_ask_size=best_ask_size,
            orderbook_bids=[[Decimal(str(item[0])), Decimal(str(item[1]))] for item in bids[:5] if len(item) >= 2 and isinstance(item[0], (int, float)) and isinstance(item[1], (int, float))],
            orderbook_asks=[[Decimal(str(item[0])), Decimal(str(item[1]))] for item in asks[:5] if len(item) >= 2 and isinstance(item[0], (int, float)) and isinstance(item[1], (int, float))]
        )