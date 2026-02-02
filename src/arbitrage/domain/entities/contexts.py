from dataclasses import dataclass
from typing import Dict, Any
from decimal import Decimal
from .hedge_position import HedgePosition
from ..entities.pair import Pair
from ..entities.account_snapshot import AccountSnapshot
from ..entities.risk_state import RiskState
from ..models.market_snapshot import MarketSnapshot


@dataclass
class StrategyContext:
    account: AccountSnapshot
    pair: Pair
    market_snapshot: MarketSnapshot  # MarketSnapshot data
    risk_state: RiskState
    config: Dict[str, Any]


@dataclass
class PositionContext:
    account: AccountSnapshot
    market_snapshot: MarketSnapshot  # MarketSnapshot data
    position: HedgePosition  # 使用正确的HedgePosition类型
    risk_state: RiskState
    config: Dict[str, Any]