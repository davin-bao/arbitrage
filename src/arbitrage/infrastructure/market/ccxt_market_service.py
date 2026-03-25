import ccxt
import time
from typing import List, Dict
from decimal import Decimal
from arbitrage.domain.entities.ohlcv_diff_result import OHLCVDiffResult, CachedOHLCVResult

from arbitrage.domain.services.market_service import MarketService
from arbitrage.domain.entities.pair import Pair
from arbitrage.domain.models.market_snapshot import MarketSnapshot, MarketLegSnapshot
from arbitrage.domain.models.market_ticker_snapshot import MarketTickerSnapshot, MarketTickerLegSnapshot


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
        self.ohlcv_cache: Dict[str, CachedOHLCVResult] = {}  # OHLCV差值缓存 {cache_key: CachedOHLCVResult}
        self.cache_expiry_seconds = 60  # 缓存过期时间（秒）
        self._initialize_exchanges(exchanges_config)
    
    def _initialize_exchanges(self, exchanges_config: Dict[str, Dict]):
        """
        根据配置初始化交易所实例
        """
        for exchange_name, config in exchanges_config.items():
            if not config.get('enabled'):
                continue
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
        snapshots : Dict[str, MarketSnapshot] = {}
        if not pairs:
            return snapshots
        
        all_tickers = {}
        for exchange_name in self.exchanges:
            all_tickers[exchange_name] = self._fetch_tickers(exchange_name)
        
        for pair in pairs:
            try:
                long_ticker = all_tickers[pair.long_exchange][pair.symbol]
                # 获取长仓交易所的市场数据
                long_leg = self._get_market_leg_snapshot(
                    pair.long_exchange, 
                    pair.symbol,
                    ticker=long_ticker
                )
                
                # 获取短仓交易所的市场数据
                short_ticker = all_tickers[pair.long_exchange][pair.symbol]
                short_leg = self._get_market_leg_snapshot(
                    pair.short_exchange, 
                    pair.symbol,
                    ticker=short_ticker
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
    
    def fetch_tickers(self, pairs: List[Pair]) -> Dict[str, MarketTickerSnapshot]:
        snapshots : Dict[str, MarketTickerSnapshot] = {}
        all_tickers = {}
        for exchange_name in self.exchanges:
            all_tickers[exchange_name] = self._fetch_tickers(exchange_name)
        
        for pair in pairs:
            try:
                long_ticker = all_tickers[pair.long_exchange][pair.symbol]
                long_leg = MarketTickerLegSnapshot(
                    exchange=pair.long_exchange,
                    symbol=pair.symbol,
                    last_price=Decimal(long_ticker['last']) if 'last' in long_ticker else None,
                    last_size=Decimal(long_ticker['volume']) if 'volume' in long_ticker else None
                )
                # 获取短仓交易所的市场数据
                short_ticker = all_tickers[pair.short_exchange][pair.symbol]
                short_leg = MarketTickerLegSnapshot(
                    exchange=pair.short_exchange,
                    symbol=pair.symbol,
                    last_price=Decimal(short_ticker['last']) if 'last' in short_ticker else None,
                    last_size=Decimal(short_ticker['volume']) if 'volume' in short_ticker else None
                )
                
                if long_leg and short_leg:
                    snapshot = MarketTickerSnapshot(
                        pair=pair,
                        timestamp=time.time(),
                        long_leg=long_leg,
                        short_leg=short_leg
                    )
                    snapshots[pair.pair_id] = snapshot
                    
            except KeyError as e:
                print(f"Error getting snapshot for {str(e)}")
                continue
        
        return snapshots
        
    def _fetch_tickers(self, exchange_name: str) -> Dict[str, Dict]:
        """
        获取指定交易所的ticker数据
        """
        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange {exchange_name} not initialized")
        
        exchange = self.exchanges[exchange_name]
        return exchange.fetch_tickers()
    
    def _get_market_leg_snapshot(
        self, 
        exchange_name: str, 
        symbol: str,
        ticker: Dict
    ) -> MarketLegSnapshot:
        """
        获取单个交易所的市场数据
        """
        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange {exchange_name} not initialized")
        
        exchange = self.exchanges[exchange_name]
        
        # 获取ticker数据
        # ticker = exchange.fetch_ticker(symbol)
        
        # 获取订单簿数据
        orderbook = exchange.fetch_order_book(symbol, limit=5)
        
        # 提取价格和大小数据
        last_price = Decimal(str(ticker.get('last'))) if ticker.get('last') else None
        last_timestamp = ticker.get('timestamp')
        
        # 获取买单和卖单数据
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        quote_volume = Decimal(str(ticker.get('quoteVolume'))) if ticker.get('quoteVolume') else None
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
            quote_volume=quote_volume,
            best_bid_price=best_bid_price,
            best_bid_size=best_bid_size,
            best_ask_price=best_ask_price,
            best_ask_size=best_ask_size,
            orderbook_bids=[[Decimal(str(item[0])), Decimal(str(item[1]))] for item in bids[:5] if len(item) >= 2 and isinstance(item[0], (int, float)) and isinstance(item[1], (int, float))],
            orderbook_asks=[[Decimal(str(item[0])), Decimal(str(item[1]))] for item in asks[:5] if len(item) >= 2 and isinstance(item[0], (int, float)) and isinstance(item[1], (int, float))]
        )
    
    def get_ohlcv_diff(self, market_snapshot: MarketSnapshot) -> OHLCVDiffResult:
        """
        获取市场数据的OHLCV差值统计
        
        对两个交易所的OHLCV数据进行时间对齐，计算每个timeframe的插值，
        返回平均价差和最大价差。
        
        OHLCV格式: [timestamp, open, high, low, close, volume]
        插值计算: abs(price1 - price2)
        
        缓存机制：基于pair.symbol和当前时间进行缓存，有效期1分钟
        """
        # 生成缓存键：使用pair.symbol和当前分钟时间戳
        cache_key = f"{market_snapshot.pair.symbol}_{int(time.time() // 60)}"
        
        # 检查缓存是否存在且未过期
        current_time = time.time()
        if cache_key in self.ohlcv_cache:
            cached_result = self.ohlcv_cache[cache_key]
            # 检查是否过期（1分钟内）
            if current_time - cached_result.timestamp < self.cache_expiry_seconds:
                # 从缓存的平均值创建结果对象（缓存中只存储平均值）
                return cached_result.value
        
        try:
            # 获取两个交易所的OHLCV数据
            k1 = self._fetch_ohlcv(
                market_snapshot.long_leg.exchange, 
                market_snapshot.pair.symbol, 
                timeframe="1m", 
                limit=500
            )
            k2 = self._fetch_ohlcv(
                market_snapshot.short_leg.exchange, 
                market_snapshot.pair.symbol, 
                timeframe="1m", 
                limit=500
            )
            
            if not k1 or not k2:
                result = OHLCVDiffResult(
                    average=Decimal('0'),
                    max=Decimal('0')
                )
            else:
                # 将k2转换为字典以便快速查找 {timestamp: ohlcv_data}
                d2 = {candle[0]: candle for candle in k2 if len(candle) >= 6}
                
                diffs = []
                
                # 遍历k1中的每个时间点，寻找对应的时间点进行比较
                for candle1 in k1:
                    if len(candle1) < 6:
                        continue
                        
                    timestamp1 = candle1[0]
                    
                    # 查找k2中相同时间点的数据
                    if timestamp1 in d2:
                        candle2 = d2[timestamp1]
                        if len(candle2) >= 6:
                            # 使用收盘价进行比较（索引4）
                            close1 = Decimal(str(candle1[4]))
                            close2 = Decimal(str(candle2[4]))
                            
                            # 计算插值
                            if close1 != 0 and close2 != 0:
                                diff = abs(close1 - close2)
                                diffs.append(diff)
                    else:
                        # 如果找不到精确匹配的时间点，寻找最近的时间点进行插值
                        nearest_timestamp = None
                        min_time_diff = float('inf')
                        
                        for ts2 in d2.keys():
                            time_diff = abs(timestamp1 - ts2)
                            if time_diff < min_time_diff:
                                min_time_diff = time_diff
                                nearest_timestamp = ts2
                        
                        # 如果找到相近时间点且时间差在合理范围内（例如5分钟内）
                        if nearest_timestamp is not None and min_time_diff <= 300000:  # 5分钟 = 300000毫秒
                            candle2 = d2[nearest_timestamp]
                            if len(candle2) >= 6:
                                close1 = Decimal(str(candle1[4]))
                                close2 = Decimal(str(candle2[4]))
                                
                                if close1 != 0 and close2 != 0:
                                    diff = abs(close1 - close2)
                                    # 根据时间差加权调整
                                    time_weight = Decimal(str(1 - min_time_diff / 300000))  # 时间差越大权重越小
                                    weighted_diff = diff * time_weight
                                    diffs.append(weighted_diff)
                
                # 计算平均值和最大值
                if diffs:
                    average_diff = sum(diffs) / len(diffs)
                    max_diff = max(diffs)
                    result = OHLCVDiffResult(
                        average=average_diff,
                        max=max_diff
                    )
                else:
                    result = OHLCVDiffResult(
                        average=Decimal('0'),
                        max=Decimal('0')
                    )
            
            # 缓存平均值结果（为了向后兼容）
            self.ohlcv_cache[cache_key] = CachedOHLCVResult(
                value=result,
                timestamp=current_time
            )
            
            return result
                
        except Exception as e:
            # 记录错误但不中断程序
            print(f"Error calculating OHLCV diff: {str(e)}")
            return OHLCVDiffResult(
                average=Decimal('0'),
                max=Decimal('0')
            )
    
    def _fetch_ohlcv(self, exchange_name: str, symbol: str, timeframe: str="1m", limit:int=50) -> List[List[Decimal]]:
        """
        获取指定交易所的OHLCV数据
        """
        if exchange_name not in self.exchanges:
            raise ValueError(f"Exchange {exchange_name} not initialized")
        
        exchange = self.exchanges[exchange_name]
        
        # 获取OHLCV数据
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)