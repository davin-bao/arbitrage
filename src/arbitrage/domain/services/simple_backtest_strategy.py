from typing import List, Tuple
from decimal import Decimal
from arbitrage.application.utils.types import safe_decimal
from arbitrage.domain.services.trading_pair_filter import TradingPairFilter, PairQualityMetrics
from .strategy import IStrategy
from ..entities.pair import Pair
from ..entities.open_intent import OpenIntent
from ..entities.enums import EntryType, TradeSide
from ..entities.contexts import StrategyContext, PositionContext
from ..models.market_snapshot import MarketSnapshot
from ..models.market_ticker_snapshot import MarketTickerSnapshot, MarketTickerLegSnapshot
from arbitrage.application.logging.file_logger import ILogger, FileLogger


class SimpleBacktestStrategy(IStrategy):
    """
    一个简单的回测策略实现，用于测试目的
    """
    def __init__(self, logger: ILogger):
        self.logger = logger or FileLogger()
        # 策略参数
        self.min_spread_threshold = Decimal('0.02')  # 最小价差阈值 2%
        self.max_spread_threshold = Decimal('0.1')
        self.close_spread_threshold = Decimal('0.3')  # 平仓阈值,即开仓价差的30%就平仓
        self.max_positions_per_pair = 1  # 每个交易对最大持仓数
        
        self.pair_filter = TradingPairFilter()

    def select_pairs(self, pairs_with_snapshots: List[Tuple[Pair, MarketTickerSnapshot]]) -> List[Pair]:
        """
        选择要交易的交易对
        """
        candidate_pairs: List[Pair] = self.pair_filter.filter_pairs(
            pairs_with_snapshots,
            require_volume=True,
            require_depth=False  # 深度数据需要额外 API 调用，可选启用
        )
        
        self.logger.info(
            f"筛选完成：保留 {len(candidate_pairs)} 个交易对"
        )
        # 返回全部交易对
        return candidate_pairs

    def should_fetch_depth(self, ctx: StrategyContext) -> bool:
        """
        判断是否需要拉取深度行情。
        """
        # 从市场快照中获取价差信息
        snapshot: MarketTickerSnapshot = ctx.market_ticker_snapshot
        long_snapshot: MarketTickerLegSnapshot = snapshot.long_leg
        short_snapshot: MarketTickerLegSnapshot = snapshot.short_leg
        # 修正：使用属性访问而不是字典访问
        long_price = long_snapshot.last_price
        short_price = short_snapshot.last_price
        long_maker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.long_exchange, {}).get("fees", '0').get("maker", '0'))
        short_maker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.short_exchange, {}).get("fees", '0').get("maker", '0'))
        long_taker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.long_exchange, {}).get("fees", '0').get("taker", '0'))
        short_taker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.short_exchange, {}).get("fees", '0').get("taker", '0'))
        long_price = snapshot.long_leg.last_price
        short_price = snapshot.short_leg.last_price
        gross = Decimal('0')
        if long_price is not None and short_price is not None and long_price > 0:
            gross = abs(long_price - short_price)
        fee = long_price * (long_maker_fee + long_taker_fee) + short_price * (short_maker_fee + short_taker_fee)
        net = (gross - fee) / long_price
        should: bool = net >= self.min_spread_threshold and net < self.max_spread_threshold
        if should:
            self.logger.info(f"粗开仓判断: {ctx.pair.symbol} {long_price:.6}({ctx.pair.long_exchange})<=>{short_price:.6}({ctx.pair.short_exchange}) {net:.4%} < {self.min_spread_threshold:.4%}")
        return should
    def should_open_position(self, ctx: StrategyContext) -> OpenIntent:
        """
        判断是否开仓
        """
        # 从市场快照中获取价差信息
        snapshot: MarketSnapshot = ctx.market_snapshot
        ohlcv_average: Decimal = ctx.ohlcv_average
        ohlcv_max: Decimal = ctx.ohlcv_max
        threshold: Decimal = (ohlcv_max + ohlcv_average) * Decimal('0.5')
        long_maker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.long_exchange, {}).get("fees", '0').get("maker", '0'))
        short_maker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.short_exchange, {}).get("fees", '0').get("maker", '0'))
        long_taker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.long_exchange, {}).get("fees", '0').get("taker", '0'))
        short_taker_fee = Decimal(ctx.config.get("exchanges", {}).get(ctx.pair.short_exchange, {}).get("fees", '0').get("taker", '0'))

        long_bast_ask_price = safe_decimal(snapshot.long_leg.best_ask_price)
        long_bast_bid_price =  safe_decimal(snapshot.long_leg.best_bid_price)
        short_bast_ask_price = safe_decimal(snapshot.short_leg.best_ask_price)
        short_bast_bid_price = safe_decimal(snapshot.short_leg.best_bid_price)

        buy_side_diff = short_bast_bid_price - long_bast_ask_price
        sell_side_diff = long_bast_bid_price - short_bast_ask_price
        gross_ratio = Decimal('0')

        if buy_side_diff > sell_side_diff and buy_side_diff > 0:
            gross = short_bast_bid_price - long_bast_ask_price
            gross_ratio = Decimal('0') if long_bast_ask_price == 0 else gross / long_bast_ask_price
            long_fee = long_bast_ask_price * (long_maker_fee + long_taker_fee)
            short_fee = short_bast_bid_price * (short_maker_fee + short_taker_fee)
        
        elif sell_side_diff > buy_side_diff and sell_side_diff > 0:
            gross = long_bast_bid_price - short_bast_ask_price
            gross_ratio = gross / short_bast_ask_price
            long_fee = long_bast_bid_price * (long_maker_fee + long_taker_fee)
            short_fee = short_bast_ask_price * (short_maker_fee + short_taker_fee)
            
        else:
            gross = Decimal('0')
            long_fee = Decimal('0')
            short_fee = Decimal('0')

        net = gross - ohlcv_average - long_fee - short_fee
        self.logger.info(f"开仓判断 ohvc_diff:{ohlcv_average:.6} ohvc_high:{ohlcv_max:.6} gross:{gross:.6}>threshold:{threshold:.6} net:{net:.6}>0 and gross_ratio:{gross_ratio:.6}<=0.1 fee:{(long_fee + short_fee):.6}")
        if gross > threshold and net > 0 and gross_ratio <= Decimal('0.1'):
            # 返回开仓意图
            return OpenIntent(
                pair=ctx.pair,
                notional_usd=Decimal('100'),  # 固定名义金额
                entry_type=EntryType.LIMIT,
                ohlcv_average=ohlcv_average,
                ohlcv_max=ohlcv_max,
                max_slippage=Decimal('0.005'),  # 最大滑点0.5%
                reason=f"Net {net} exceeds threshold 0"
            )
        return None

    def should_close_position(self, ctx: PositionContext) -> bool:
        """
        判断是否平仓
        """
        # 从市场快照中获取价差信息
        snapshot: MarketTickerSnapshot = ctx.market_ticker_snapshot
        long_price = snapshot.long_leg.last_price
        short_price = snapshot.short_leg.last_price
        ohlcv_average = ctx.position.ohlcv_average
        long_trade_side = ctx.position.long_leg.side
        price_diff = Decimal('0')
        if long_trade_side == TradeSide.SELL:
            price_diff = long_price - short_price
        else:
            price_diff = short_price - long_price

        should_close: bool = price_diff <= ohlcv_average

        # 简单逻辑：如果当前价差小于阈值，则平仓
        self.logger.info(f"平仓判断: {snapshot.pair.symbol} {long_price:.6}({snapshot.pair.long_exchange})<=>{short_price:.6}({snapshot.pair.short_exchange}) {price_diff:.4}<={ohlcv_average:.4}")
        return should_close

    def should_stop_loss(self, ctx: PositionContext) -> bool:
        """
        判断是否止损
        """
        # 从市场快照中获取价差信息
        snapshot: MarketTickerSnapshot = ctx.market_ticker_snapshot
        long_price = snapshot.long_leg.last_price
        short_price = snapshot.short_leg.last_price
        ohlcv_max = ctx.position.ohlcv_max
        long_trade_side = ctx.position.long_leg.side
        price_diff = Decimal('0')
        if long_trade_side == TradeSide.SELL:
            price_diff = long_price - short_price
        else:
            price_diff = short_price - long_price

        should_stop: bool = price_diff >= ohlcv_max

        # 简单逻辑：如果当前价差小于阈值，则平仓
        self.logger.info(f"强平判断: {snapshot.pair.symbol} {long_price:.6}({snapshot.pair.long_exchange})<=>{short_price:.6}({snapshot.pair.short_exchange}) {price_diff:.4}>={ohlcv_max:.4}")
        return should_stop