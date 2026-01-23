from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Pair:
    logical_symbol: str
    long_exchange: str
    short_exchange: str

    @property
    def pair_id(self) -> str:
        return f"{self.logical_symbol}_{self.long_exchange}_{self.short_exchange}"