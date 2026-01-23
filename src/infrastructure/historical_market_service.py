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
                
                # 解析交易对名称 (例如: BTCUSDT_binance_okx -> BTCUSDT, binance, okx)
                parts = pair_name.split('_')
                if len(parts) >= 3:
                    symbol = parts[0]
                    exchange1 = parts[1]
                    exchange2 = parts[2]
                    
                    # 确定哪个是long exchange，哪个是short exchange
                    exchanges = sorted([exchange1, exchange2])
                    long_exchange = exchanges[0]
                    short_exchange = exchanges[1]
                    
                    pair = Pair(
                        logical_symbol=symbol,
                        long_exchange=long_exchange,
                        short_exchange=short_exchange
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
                    exchange=exchange,
                    symbol=symbol,
                    last_price=Decimal(row['last_price']) if row.get('last_price') else None,
                    best_bid_price=Decimal(row['bid_price']) if row.get('bid_price') else None,
                    best_bid_size=Decimal(row['bid_size']) if row.get('bid_size') else None,
                    best_ask_price=Decimal(row['ask_price']) if row.get('ask_price') else None,
                    best_ask_size=Decimal(row['ask_size']) if row.get('ask_size') else None,
                )
                
                # 存储这个交易所的数据
                key = f"{pair.logical_symbol}_{exchange}"
                if key not in self._data_cache[timestamp]:
                    self._data_cache[timestamp][key] = leg_data
        
        # 记录所有时间戳并排序
        self._timestamps = sorted(self._data_cache.keys())
    
    def get_snapshot(self, pairs: List[Pair], target_timestamp: Optional[float] = None) -> Dict[str, MarketSnapshot]:
        """
        获取指定时间戳的市场快照
        如果target_timestamp为None，则使用下一个时间戳
        """
        if not self._timestamps:
            return {}
        
        # 如果没有指定时间戳，使用当前索引的时间戳
        if target_timestamp is None:
            if self._current_index >= len(self._timestamps):
                # 循环回到开始
                self._current_index = 0
                if not self._timestamps:
                    return {}
            
            timestamp = self._timestamps[self._current_index]
            self._current_index += 1
        else:
            # 查找最接近的时间戳
            timestamp = self._find_nearest_timestamp(target_timestamp)
        
        # 检查缓存中是否存在这个时间戳的数据
        if timestamp not in self._data_cache:
            return {}
        
        result = {}
        
        for pair in pairs:
            # 获取这个交易对的两条腿数据
            long_key = f"{pair.logical_symbol}_{pair.long_exchange}"
            short_key = f"{pair.logical_symbol}_{pair.short_exchange}"
            
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
    
    def _find_nearest_timestamp(self, target_timestamp: float) -> float:
        """
        查找最接近目标时间戳的时间戳
        """
        if not self._timestamps:
            return target_timestamp
        
        # 使用二分查找找到最接近的时间戳
        left, right = 0, len(self._timestamps) - 1
        
        while left < right:
            mid = (left + right) // 2
            if self._timestamps[mid] < target_timestamp:
                left = mid + 1
            else:
                right = mid
        
        # 检查left和left-1哪个更接近
        if left == 0:
            return self._timestamps[0]
        if left == len(self._timestamps):
            return self._timestamps[-1]
        
        # 返回更接近的一个
        diff_left = abs(self._timestamps[left] - target_timestamp)
        diff_prev = abs(self._timestamps[left - 1] - target_timestamp)
        
        if diff_left < diff_prev:
            return self._timestamps[left]
        else:
            return self._timestamps[left - 1]
    
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