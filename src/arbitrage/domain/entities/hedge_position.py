import time
from decimal import Decimal
from dataclasses import dataclass, field
from .trade_leg import TradeLeg
from ..entities.pair import Pair
from ..entities.enums import PositionState


@dataclass
class HedgePosition:
    id: str
    pair: Pair
    long_leg: TradeLeg
    short_leg: TradeLeg
    ohlcv_average: Decimal
    ohlcv_max: Decimal
    close_timestamp: float
    open_timestamp: float = field(default_factory=lambda: time.time())
    state: PositionState = field(default=PositionState.OPEN)