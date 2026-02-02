from enum import Enum


class TradeSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    EMERGENCY = "emergency_market"


class EntryType(Enum):
    LIMIT = "limit"
    MARKET = "market"


class PositionState(Enum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class ExecutionState(Enum):
    OPENED = "opened"
    PARTIAL = "partial"
    FAILED = "failed"
    CLOSED = "closed"
    EMERGENCY_CLOSED = "emergency_closed"