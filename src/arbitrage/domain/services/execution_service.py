from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

from ..entities.enums import ExecutionState
from ..entities.hedge_position import HedgePosition
from ..entities.open_intent import OpenIntent
from ..models.market_snapshot import MarketSnapshot
from ..models.market_ticker_snapshot import MarketTickerSnapshot


@dataclass
class ExecutionResult:
    success: bool
    position: Optional[HedgePosition]

    state: ExecutionState

    error: Optional[str] = None


class ExecutionService(ABC):
    @abstractmethod
    def open_position(
        self,
        intent: OpenIntent,
        market: MarketSnapshot
    ) -> ExecutionResult:
        pass

    @abstractmethod
    def close_position(
        self,
        position: HedgePosition,
        market: MarketTickerSnapshot
    ) -> ExecutionResult:
        pass