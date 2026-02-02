from dataclasses import dataclass
from decimal import Decimal
from ..entities.pair import Pair
from ..entities.enums import EntryType


@dataclass(frozen=True)
class OpenIntent:
    pair: Pair
    notional_usd: Decimal

    entry_type: EntryType  # 使用EntryType枚举
    max_slippage: Decimal

    reason: str  # 用于日志 / 分析