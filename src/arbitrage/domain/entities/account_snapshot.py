from dataclasses import dataclass
from decimal import Decimal
from typing import List
from arbitrage.domain.entities.hedge_position import HedgePosition


@dataclass(frozen=True)
class AccountSnapshot:
    total_balance: Decimal
    available_balance: Decimal
    positions: List[HedgePosition]
    initial_balance: Decimal