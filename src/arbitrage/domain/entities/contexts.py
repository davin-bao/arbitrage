from dataclasses import dataclass
from typing import Dict, Any
from decimal import Decimal
from .hedge_position import HedgePosition
from ..entities.pair import Pair
from ..entities.account_snapshot import AccountSnapshot
from ..entities.risk_state import RiskState
from ..models.market_snapshot import MarketSnapshot
from ..models.market_ticker_snapshot import MarketTickerSnapshot


@dataclass
class StrategyContext:
    account: AccountSnapshot
    pair: Pair
    market_ticker_snapshot: MarketTickerSnapshot
    market_snapshot: MarketSnapshot  # MarketSnapshot data
    ohlcv_average: Decimal
    ohlcv_max: Decimal
    risk_state: RiskState
    config: Dict[str, Any]


@dataclass
class PositionContext:
    account: AccountSnapshot
    market_ticker_snapshot: MarketTickerSnapshot  # MarketTickerSnapshot data
    position: HedgePosition  # 使用正确的HedgePosition类型
    risk_state: RiskState
    config: Dict[str, Any]