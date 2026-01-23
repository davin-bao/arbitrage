import time
from dataclasses import dataclass, field
from .trade_leg import TradeLeg
from ..value_objects.pair import Pair
from ..value_objects.enums import PositionState


@dataclass
class HedgePosition:
    id: str
    pair: Pair
    long_leg: TradeLeg
    short_leg: TradeLeg
    open_timestamp: float = field(default_factory=lambda: time.time())
    state: PositionState = field(default=PositionState.OPEN)