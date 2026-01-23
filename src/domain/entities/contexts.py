from dataclasses import dataclass
from typing import Dict, Any
from decimal import Decimal
from .hedge_position import HedgePosition
from ..value_objects.pair import Pair


@dataclass
class StrategyContext:
    pair: Pair
    market_snapshot: Dict[str, Any]  # MarketSnapshot data
    active_positions: int
    config: Dict[str, Any]


@dataclass
class PositionContext:
    position: HedgePosition  # 使用正确的HedgePosition类型
    current_spread: Decimal
    config: Dict[str, Any]