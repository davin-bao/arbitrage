from dataclasses import dataclass
from decimal import Decimal
from typing import List
from ..entities.enums import OrderType, TradeSide


@dataclass(frozen=True)
class TradeLeg:
    exchange: str
    symbol: str
    side: TradeSide
    amount: Decimal
    price: Decimal
    fee: Decimal            # 手续费（USD）
    slippage_loss: Decimal  # 滑点损失（USD）
    order_type: OrderType   # 'limit', 'market', 'emergency_market'
    timestamp: float