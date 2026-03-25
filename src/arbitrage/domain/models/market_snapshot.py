from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from ..entities.pair import Pair


@dataclass(frozen=True)
class MarketLegSnapshot:
    """
    单腿（单交易所）的市场快照。
    """
    exchange: str
    symbol: str
    
    # 最新成交
    last_price: Optional[Decimal] = None
    last_size: Optional[Decimal] = None
    last_timestamp: Optional[float] = None

    # 订单簿顶部（Top of Book）
    quote_volume: Optional[Decimal] = None
    best_bid_price: Optional[Decimal] = None
    best_bid_size: Optional[Decimal] = None
    best_ask_price: Optional[Decimal] = None
    best_ask_size: Optional[Decimal] = None

    # 深度快照（可选，用于滑点模拟）
    orderbook_bids: List[List[Decimal]] = field(default_factory=list)  # [[price, size], ...]
    orderbook_asks: List[List[Decimal]] = field(default_factory=list)  # [[price, size], ...]


@dataclass(frozen=True)
class MarketSnapshot:
    """
    套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
    """
    pair: Pair
    timestamp: float  # Unix 时间戳（秒，含小数）

    long_leg: MarketLegSnapshot   # 做多腿（如 Binance BTC/USDT）
    short_leg: MarketLegSnapshot  # 做空腿（如 Bybit BTC/USDT）