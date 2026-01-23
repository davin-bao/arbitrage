import csv
import os
from typing import List, Dict, Optional
from decimal import Decimal

from domain.services.market_service import MarketService
from domain.value_objects.pair import Pair
from domain.models.market_snapshot import MarketSnapshot, MarketLegSnapshot


class HistoricalMarketService(MarketService):
    """
    历史市场服务，从CSV文件读取历史市场数据
    """
    
    def __init__(self, csv_directory: str = "data/historical"):
        self.csv_directory = csv_directory
        self._data_cache = {}
        self._timestamps = []
        self._current_index = 0
        
        # 加载所有CSV文件数据
        self._load_data_from_csv()
    
    def _load_data_from_csv(self):
        """
        从CSV文件加载历史数据
        CSV文件应包含列：timestamp, exchange, symbol, last_price, bid_price, bid_size, ask_price, ask_size
        """
        if not os.path.exists(self.csv_directory):
            raise FileNotFoundError(f"Directory {self.csv_directory} does not exist")
        
        for filename in os.listdir(self.csv_directory):
            if filename.endswith('.csv'):
                pair_name = filename.replace('.csv', '')
                
                # 解析交易对名称 (例如: BTC_USDT_binance_okx -> BTC/USDT, binance, okx)
                parts = pair_name.split('_')
                if len(parts) >= 3:
                    symbol = '_'.join(parts[:-2])  # 处理可能包含下划线的符号，如BTC_USDT
                    exchange1 = parts[-2]
                    exchange2 = parts[-1]
                    
                    # 使用原始顺序作为long和short交易所
                    # 这样可以保持下载配置中定义的顺序
                    pair = Pair(
                        logical_symbol=symbol.replace('_', '/'),  # 将下划线转回斜杠
                        long_exchange=exchange1,
                        short_exchange=exchange2
                    )
                    
                    file_path = os.path.join(self.csv_directory, filename)
                    self._load_pair_data_from_csv(pair, file_path)
    
    def _load_pair_data_from_csv(self, pair: Pair, file_path: str):
        """
        从CSV文件加载特定交易对的历史数据
        """
        data_list = []
        
        with open(file_path, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                timestamp = float(row['timestamp'])
                
                # 为每个交易所创建腿数据
                legs = {}
                
                # 假设CSV中有exchange列标识交易所
                exchange = row['exchange']
                symbol = row['symbol']
                
                # 如果还没有这个时间戳的数据，创建一个
                if timestamp not in self._data_cache:
                    self._data_cache[timestamp] = {}
                
                # 创建腿数据
                leg_data = MarketLegSnapshot(
                    exchange=row['exchange'],
                    symbol=row['symbol'],
                    last_price=Decimal(row['last_price']) if row['last_price'] and row['last_price'] != '' else None,
                    last_size=None,  # 历史数据中通常没有last_size
                    last_timestamp=timestamp,
                    best_bid_price=Decimal(row['bid_price']) if row['bid_price'] and row['bid_price'] != '' else None,
                    best_bid_size=Decimal(row['bid_size']) if row['bid_size'] and row['bid_size'] != '' else None,
                    best_ask_price=Decimal(row['ask_price']) if row['ask_price'] and row['ask_price'] != '' else None,
                    best_ask_size=Decimal(row['ask_size']) if row['ask_size'] and row['ask_size'] != '' else None,
                    orderbook_bids=[],  # 历史数据中通常没有深度数据
                    orderbook_asks=[]   # 历史数据中通常没有深度数据
                )
                
                # 存储这个交易所的数据
                key = f"{pair.logical_symbol}_{exchange}"
                if key not in self._data_cache[timestamp]:
                    self._data_cache[timestamp][key] = leg_data
        
        # 记录所有时间戳并排序
        self._timestamps = sorted(self._data_cache.keys())
    
    def get_snapshot(self, pairs: List[Pair]) -> Dict[str, MarketSnapshot]:
        """
        获取下一个时间戳的市场快照
        """
        if not self._timestamps or self._current_index >= len(self._timestamps):
            # 循环回到开始
            self._current_index = 0
            if not self._timestamps:
                return {}
        
        timestamp = self._timestamps[self._current_index]
        self._current_index += 1
        
        # 检查缓存中是否存在这个时间戳的数据
        if timestamp not in self._data_cache:
            return {}
        
        result = {}
        
        for pair in pairs:
            # 获取这个交易对的两条腿数据
            long_key = f"{pair.logical_symbol.replace('/', '_')}_{pair.long_exchange}"
            short_key = f"{pair.logical_symbol.replace('/', '_')}_{pair.short_exchange}"
            
            long_leg = self._data_cache[timestamp].get(long_key)
            short_leg = self._data_cache[timestamp].get(short_key)
            
            if long_leg and short_leg:
                # 创建市场快照
                snapshot = MarketSnapshot(
                    pair=pair,
                    timestamp=timestamp,
                    long_leg=long_leg,
                    short_leg=short_leg
                )
                
                result[pair.pair_id] = snapshot
        
        return result
    
    def reset(self):
        """
        重置到初始状态
        """
        self._current_index = 0
    
    def has_more_data(self) -> bool:
        """
        检查是否还有更多数据
        """
        return self._current_index < len(self._timestamps)