from typing import List
from decimal import Decimal
from .strategy import IStrategy
from ..entities.pair import Pair
from ..entities.open_intent import OpenIntent
from ..entities.enums import EntryType
from ..entities.contexts import StrategyContext, PositionContext
from ..models.market_snapshot import MarketSnapshot
from arbitrage.application.logging.file_logger import ILogger, FileLogger


class SimpleBacktestStrategy(IStrategy):
    """
    一个简单的回测策略实现，用于测试目的
    """
    def __init__(self, logger: ILogger):
        self.logger = logger or FileLogger()
        # 策略参数
        self.min_spread_threshold = Decimal('0.02')  # 最小价差阈值 2%
        self.min_spread_threshold_tmp = Decimal('100')  # 最小价差阈值 2%
        self.max_positions_per_pair = 1  # 每个交易对最大持仓数

    def select_pairs(self, universe: List[Pair]) -> List[Pair]:
        """
        选择要交易的交易对
        """
        # 返回全部交易对
        return universe

    def should_open_position(self, ctx: StrategyContext) -> OpenIntent:
        """
        判断是否开仓
        """
        # 从市场快照中获取价差信息
        snapshot: MarketSnapshot = ctx.market_snapshot

        spread: Decimal = self._get_spread(snapshot)
        
        # 修正：使用属性访问而不是字典访问
        long_price = snapshot.long_leg.last_price
        short_price = snapshot.short_leg.last_price

        if spread >= self.min_spread_threshold:
            # 返回开仓意图
            return OpenIntent(
                pair=ctx.pair,
                notional_usd=Decimal('100'),  # 固定名义金额
                entry_type=EntryType.LIMIT,
                max_slippage=Decimal('0.005'),  # 最大滑点0.5%
                reason=f"Spread {spread} exceeds threshold {self.min_spread_threshold}"
            )
        else:
            self.logger.info(f"{ctx.pair.symbol} {long_price}<=>{short_price} {spread} < {self.min_spread_threshold}")
        return None

    def should_close_position(self, ctx: PositionContext) -> bool:
        """
        判断是否平仓
        """
        # 从市场快照中获取价差信息
        snapshot: MarketSnapshot = ctx.market_snapshot
        spread: Decimal = self._get_spread(snapshot)
        # 简单逻辑：如果当前价差小于阈值，则平仓
        return spread < self.min_spread_threshold_tmp / 2
    
    def _get_spread(self, snapshot: MarketSnapshot) -> Decimal:
        """
        获取价差
        """
        # 修正：使用属性访问而不是字典访问
        long_price = snapshot.long_leg.last_price
        short_price = snapshot.short_leg.last_price
        if long_price is not None and short_price is not None and long_price > 0:
            return abs(long_price - short_price) / long_price
        else:
            return Decimal('0')