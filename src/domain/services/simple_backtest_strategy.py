from typing import List
from decimal import Decimal
from .strategy import IStrategy
from ..value_objects.pair import Pair
from ..models.open_intent import OpenIntent
from ..value_objects.enums import EntryType
from ..entities.contexts import StrategyContext, PositionContext


class SimpleBacktestStrategy(IStrategy):
    """
    一个简单的回测策略实现，用于测试目的
    """
    def __init__(self):
        # 策略参数
        self.min_spread_threshold = Decimal('0.02')  # 最小价差阈值 2%
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
        # 简单逻辑：如果价差超过阈值且没有活跃持仓，则开仓
        if ctx.active_positions >= self.max_positions_per_pair:
            return None

        # 从市场快照中获取价差信息
        snapshot = ctx.market_snapshot
        if 'long_leg' in snapshot and 'short_leg' in snapshot:
            long_price = snapshot['long_leg'].get('last_price')
            short_price = snapshot['short_leg'].get('last_price')

            if long_price and short_price and long_price > 0:
                spread = abs(long_price - short_price) / long_price
                if spread >= self.min_spread_threshold:
                    # 返回开仓意图
                    return OpenIntent(
                        pair=ctx.pair,
                        notional_usd=Decimal('100'),  # 固定名义金额
                        entry_type=EntryType.LIMIT,
                        max_slippage=Decimal('0.005'),  # 最大滑点0.5%
                        reason=f"Spread {spread} exceeds threshold {self.min_spread_threshold}"
                    )

        return None

    def should_close_position(self, ctx: PositionContext) -> bool:
        """
        判断是否平仓
        """
        # 简单逻辑：如果当前价差小于阈值，则平仓
        return abs(ctx.current_spread) < self.min_spread_threshold / 2