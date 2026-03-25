from decimal import Decimal
from typing import Dict, Optional, Any
import uuid
import random
from arbitrage.domain.services.account_service import AccountService
from arbitrage.domain.services.execution_service import ExecutionService, ExecutionResult
from arbitrage.domain.entities.open_intent import OpenIntent
from arbitrage.domain.models.market_snapshot import MarketSnapshot
from arbitrage.domain.models.market_ticker_snapshot import MarketTickerSnapshot
from arbitrage.domain.entities.hedge_position import HedgePosition
from arbitrage.domain.entities.trade_leg import TradeLeg
from arbitrage.domain.entities.enums import ExecutionState, OrderType, TradeSide, EntryType
from arbitrage.application.utils.types import safe_decimal


class SimulatedExecutionService(ExecutionService):
    """
    模拟执行服务，用于回测和模拟运行
    """
    def __init__(self, 
                 account_service: AccountService =None,
                 config: Optional[Dict[str, Any]] = {}):
        self.account_service = account_service
        # 模拟订单执行成功率
        self.success_rate = 0.95
        self.config = config 

    def open_position(
        self,
        intent: OpenIntent,
        snapshot: MarketSnapshot
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
        long_amount = self._calculate_amount(intent.notional_usd, snapshot.long_leg.last_price)
        short_amount = self._calculate_amount(intent.notional_usd, snapshot.short_leg.last_price)

        # 模拟执行结果
        is_successful = random.random() < self.success_rate

        if not is_successful:
            return ExecutionResult(
                success=False,
                position=None,
                state=ExecutionState.FAILED,
                error="Order failed due to simulated market conditions"
            )
        
        long_bast_ask_price = safe_decimal(snapshot.long_leg.best_ask_price)
        long_bast_bid_price = safe_decimal(snapshot.long_leg.best_bid_price)
        short_bast_ask_price = safe_decimal(snapshot.short_leg.best_ask_price)
        short_bast_bid_price = safe_decimal(snapshot.short_leg.best_bid_price)

        buy_side_diff = short_bast_bid_price - long_bast_ask_price
        sell_side_diff = long_bast_bid_price - short_bast_ask_price

        if buy_side_diff > sell_side_diff and buy_side_diff > 0:
            long_trade_side = TradeSide.BUY
            short_trade_side = TradeSide.SELL
            long_price = long_bast_ask_price
            short_price = short_bast_bid_price
        elif sell_side_diff > buy_side_diff and sell_side_diff > 0:
            long_trade_side = TradeSide.SELL
            short_trade_side = TradeSide.BUY
            long_price = long_bast_bid_price
            short_price = short_bast_ask_price

        # 创建多头腿
        long_leg = TradeLeg(
            exchange=snapshot.long_leg.exchange,
            symbol=snapshot.long_leg.symbol,
            side=long_trade_side,
            amount=long_amount,
            price=long_price,
            fee=self._calculate_fee(EntryType.LIMIT, snapshot.long_leg.exchange, long_amount, long_price),
            slippage_loss=abs((snapshot.long_leg.best_ask_price - snapshot.long_leg.best_bid_price) * long_amount / 2) if snapshot.long_leg.best_ask_price and snapshot.long_leg.best_bid_price else Decimal('0'),
            order_type=order_type,
            timestamp=snapshot.timestamp,
            close_price=None,
            close_timestamp=None
        )

        # 创建空头腿
        short_leg = TradeLeg(
            exchange=snapshot.short_leg.exchange,
            symbol=snapshot.short_leg.symbol,
            side=short_trade_side,
            amount=short_amount,
            price=short_price,
            fee=self._calculate_fee(EntryType.LIMIT, snapshot.short_leg.exchange, short_amount, short_price),
            slippage_loss=abs((snapshot.short_leg.best_ask_price - snapshot.short_leg.best_bid_price) * short_amount / 2) if snapshot.short_leg.best_ask_price and snapshot.short_leg.best_bid_price else Decimal('0'),
            order_type=order_type,
            timestamp=snapshot.timestamp,
            close_price=None,
            close_timestamp=None
        )

        # 创建对冲仓位
        position_id = f"sim_{uuid.uuid4().hex[:8]}"
        position = HedgePosition(
            id=position_id,
            pair=intent.pair,
            long_leg=long_leg,
            short_leg=short_leg,
            ohlcv_average=intent.ohlcv_average,
            ohlcv_max=intent.ohlcv_max,
            open_timestamp=snapshot.timestamp,
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
        snapshot: MarketTickerSnapshot
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
        # 更新仓位的平仓价格和时间
        long_close_price = safe_decimal(snapshot.long_leg.last_price)
        short_close_price = safe_decimal(snapshot.short_leg.last_price)
        amount = min(position.long_leg.amount, position.short_leg.amount)
        long_fee = self._calculate_fee(EntryType.MARKET, snapshot.long_leg.exchange, amount, long_close_price)
        short_fee = self._calculate_fee(EntryType.MARKET, snapshot.short_leg.exchange, amount, short_close_price)
        position.long_leg.close_price = long_close_price
        position.short_leg.close_price = short_close_price
        position.long_leg.fee += long_fee
        position.long_leg.close_timestamp = snapshot.timestamp
        position.short_leg.close_timestamp = snapshot.timestamp
        position.short_leg.fee += short_fee
        
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

    def _calculate_fee(self, entry_type: EntryType, exchange_name:str, amount: Decimal, price: Optional[Decimal]) -> Decimal:
        """
        计算手续费，这里使用固定费率0.1%
        """
        maker_fee = Decimal(self.config.get("exchanges", {}).get(exchange_name, {}).get("fees", '0').get("maker", '0'))
        taker_fee = Decimal(self.config.get("exchanges", {}).get(exchange_name, {}).get("fees", '0').get("taker", '0'))

        if not price:
            return Decimal('0')
        # 使用0.1%作为手续费率，这应该从配置中读取
        fee_rate = entry_type == EntryType.LIMIT and maker_fee or taker_fee
        notional = amount * price
        return notional * fee_rate