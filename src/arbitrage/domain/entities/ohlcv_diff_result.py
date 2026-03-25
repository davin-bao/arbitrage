from decimal import Decimal
from dataclasses import dataclass

@dataclass
class OHLCVDiffResult:
    """OHLCV差值计算结果"""
    average: Decimal  # 平均价差
    max: Decimal      # 最大价差

@dataclass
class CachedOHLCVResult:
    """缓存的OHLCV差值结果"""
    value: OHLCVDiffResult
    timestamp: float  # 缓存时间戳
