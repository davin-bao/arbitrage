from decimal import Decimal
from typing import Optional
import uuid
import random

from ...domain.services.execution_service import ExecutionService, ExecutionResult
from ...domain.entities.open_intent import OpenIntent
from ...domain.models.market_snapshot import MarketSnapshot
from ...domain.entities.hedge_position import HedgePosition
from ...domain.entities.trade_leg import TradeLeg
from ...domain.entities.enums import ExecutionState, OrderType, TradeSide


class SimulatedExecutionService(ExecutionService):
    """
    模拟执行服务，用于回测和模拟运行
    """
    def __init__(self, account_service=None):
        self.account_service = account_service
        # 模拟订单执行成功率
        self.success_rate = 0.95

    def open_position(
        self,
        intent: OpenIntent,
        market: MarketSnapshot
    ) -> ExecutionResult:
        """
        模拟开仓操作
        """
        # 检查是否有足够的资金
        if self.account_service:
            available_balance = self.account_service.get_available_balance()
            if available_balance < intent.notional_usd:
                return ExecutionResult(
                    success=False,
                    position=None,
                    state=ExecutionState.FAILED,
                    error=f"Insufficient balance. Available: {available_balance}, Required: {intent.notional_usd}"
                )

        # 根据意图类型确定订单类型
        order_type = OrderType.MARKET if intent.entry_type.value == 'market' else OrderType.LIMIT

        # 计算交易金额，考虑滑点
        long_amount = self._calculate_amount(intent.notional_usd, market.long_leg.last_price)
        short_amount = self._calculate_amount(intent.notional_usd, market.short_leg.last_price)

        # 模拟执行结果
        is_successful = random.random() < self.success_rate

        if not is_successful:
            return ExecutionResult(
                success=False,
                position=None,
                state=ExecutionState.FAILED,
                error="Order failed due to simulated market conditions"
            )

        # 创建多头腿
        long_leg = TradeLeg(
            exchange=market.long_leg.exchange,
            symbol=market.long_leg.symbol,
            side=TradeSide.BUY,
            amount=long_amount,
            price=market.long_leg.last_price or market.long_leg.best_ask_price or Decimal('0'),
            fee=self._calculate_fee(long_amount, market.long_leg.last_price),
            slippage_loss=abs((market.long_leg.best_ask_price - market.long_leg.best_bid_price) * long_amount / 2) if market.long_leg.best_ask_price and market.long_leg.best_bid_price else Decimal('0'),
            order_type=order_type,
            timestamp=market.timestamp
        )

        # 创建空头腿
        short_leg = TradeLeg(
            exchange=market.short_leg.exchange,
            symbol=market.short_leg.symbol,
            side=TradeSide.SELL,
            amount=short_amount,
            price=market.short_leg.last_price or market.short_leg.best_bid_price or Decimal('0'),
            fee=self._calculate_fee(short_amount, market.short_leg.last_price),
            slippage_loss=abs((market.short_leg.best_ask_price - market.short_leg.best_bid_price) * short_amount / 2) if market.short_leg.best_ask_price and market.short_leg.best_bid_price else Decimal('0'),
            order_type=order_type,
            timestamp=market.timestamp
        )

        # 创建对冲仓位
        position_id = f"sim_{uuid.uuid4().hex[:8]}"
        position = HedgePosition(
            id=position_id,
            pair=intent.pair,
            long_leg=long_leg,
            short_leg=short_leg,
            open_timestamp=market.timestamp,
            close_timestamp=None
        )

        # 如果有账户服务，更新账户状态
        if self.account_service:
            self.account_service.add_position(position)

        return ExecutionResult(
            success=True,
            position=position,
            state=ExecutionState.OPENED
        )

    def close_position(
        self,
        position: HedgePosition,
        market: MarketSnapshot
    ) -> ExecutionResult:
        """
        模拟平仓操作
        """
        # 模拟执行结果
        is_successful = random.random() < self.success_rate

        if not is_successful:
            return ExecutionResult(
                success=False,
                position=position,
                state=ExecutionState.FAILED,
                error="Close order failed due to simulated market conditions"
            )

        # 更新仓位状态为已关闭
        # 注意：在实际实现中，我们可能需要克隆position对象并更改状态
        # 但在这个模拟实现中，我们假设调用方会处理状态更新

        # 如果有账户服务，移除仓位
        if self.account_service:
            self.account_service.remove_position(position.id)

        return ExecutionResult(
            success=True,
            position=position,
            state=ExecutionState.CLOSED  # 实际应用中这里应该是CLOSING或CLOSED状态
        )

    def _calculate_amount(self, notional: Decimal, price: Optional[Decimal]) -> Decimal:
        """
        根据名义价值和价格计算交易数量
        """
        if not price or price <= 0:
            return Decimal('0')
        return abs(notional / price)

    def _calculate_fee(self, amount: Decimal, price: Optional[Decimal]) -> Decimal:
        """
        计算手续费，这里使用固定费率0.1%
        """
        if not price:
            return Decimal('0')
        # 使用0.1%作为手续费率，这应该从配置中读取
        fee_rate = Decimal('0.001')
        notional = amount * price
        return notional * fee_rate