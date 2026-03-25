from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from ..entities.pair import Pair


@dataclass(frozen=True)
class MarketTickerLegSnapshot:
    """
    单腿（单交易所）的市场快照。
    """
    exchange: str
    symbol: str
    
    # 最新成交
    last_price: Optional[Decimal] = None
    last_size: Optional[Decimal] = None

@dataclass(frozen=True)
class MarketTickerSnapshot:
    """
    套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
    """
    pair: Pair
    timestamp: float  # Unix 时间戳（秒，含小数）

    long_leg: MarketTickerLegSnapshot   # 做多腿（如 Binance BTC/USDT）
    short_leg: MarketTickerLegSnapshot  # 做空腿（如 Bybit BTC/USDT）