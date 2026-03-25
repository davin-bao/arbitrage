import time
from typing import Dict, Optional, Any, List
from decimal import Decimal

from arbitrage.domain.services.strategy import IStrategy
from arbitrage.domain.services.market_service import MarketService
from arbitrage.domain.services.account_service import AccountService
from arbitrage.domain.services.execution_service import ExecutionService
from arbitrage.domain.services.time_service import TimeService

from arbitrage.domain.entities.hedge_position import HedgePosition, PositionState
from arbitrage.domain.entities.account_snapshot import AccountSnapshot
from arbitrage.domain.entities.pair import Pair
from arbitrage.domain.models.market_snapshot import MarketSnapshot
from arbitrage.domain.models.market_ticker_snapshot import MarketTickerSnapshot

from arbitrage.domain.entities.open_intent import OpenIntent
from arbitrage.domain.entities.contexts import StrategyContext, PositionContext
from arbitrage.domain.entities.risk_state import RiskState
from arbitrage.domain.entities.enums import ExecutionState
from arbitrage.domain.entities.ohlcv_diff_result import OHLCVDiffResult
from arbitrage.domain.repositories.hedge_position_repository import HedgePositionRepository
from arbitrage.application.logging.file_logger import ILogger, FileLogger


class ArbitrageEngine:
    """
    套利引擎（Application 层）
    - 唯一职责：编排策略 / 市场 / 执行 / 风控
    - 不做任何 IO、不算指标、不碰交易所
    """

    def __init__(
        self,
        *,
        strategy: IStrategy,
        universe: List[Pair],
        market_service: MarketService,
        account_service: AccountService,
        execution_service: ExecutionService,
        time_service: TimeService,
        hedge_position_repository: HedgePositionRepository,
        logger: Optional[ILogger] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.strategy = strategy
        self.market_service = market_service
        self.account_service = account_service
        self.execution_service = execution_service
        self.time_service = time_service
        self.hedge_position_repository = hedge_position_repository

        self.logger = logger or FileLogger(prefix="[Engine]")
        self.config = config or {}

        self.risk_state = RiskState()
        # 初始化候选交易对
        blacklist_pairs = self.config["blacklist_pairs"]
        ticker_snapshots : Dict[str, MarketTickerSnapshot] = self.market_service.fetch_tickers(universe)
         # 准备筛选输入数据
        pairs_with_snapshots = [
            (pair, snapshot) 
            for pair in universe
            if (snapshot := ticker_snapshots.get(pair.pair_id)) is not None
        ]

        all_candidate_pairs = self.strategy.select_pairs(pairs_with_snapshots)
        
        # 过滤掉黑名单中的交易对
        self.candidate_pairs = [
            pair for pair in all_candidate_pairs 
            if pair.symbol not in blacklist_pairs
        ]
        
        # 记录过滤信息
        filtered_count = len(all_candidate_pairs) - len(self.candidate_pairs)
        if filtered_count > 0:
            self.logger.info(
                f"从 {len(all_candidate_pairs)} 个候选交易对中过滤掉 {filtered_count} "
                f"个黑名单交易对，剩余 {len(self.candidate_pairs)} 个"
            )
            self.logger.debug(f"黑名单交易对: {blacklist_pairs}")
        else:
            self.logger.info(
                f"Engine initialized with {len(self.candidate_pairs)} candidate pairs (无黑名单过滤)"
            )

    # ========================
    # 主循环
    # ========================

    def run_single_cycle(self) -> None:
        """
        单次调度周期：
        - 拉取市场快照
        - 风控判断
        - 平仓 → 开仓
        """
        if self.risk_state.is_halted():
            self.logger.error(
                f"Engine halted due to risk: {self.risk_state.reason}"
            )
            return

        now = self.time_service.now()

        try:
            account_snapshot: AccountSnapshot = self.account_service.get_account_snapshot()
        except Exception as e:
            self.logger.error(f"Fatal data fetch error: {e}")
            self.risk_state.enter_fatal("ACCOUNT_FETCH_FAILED")
            return

        try:
            market_ticker_snapshots = self._load_market_ticker_snapshots()
        except Exception as e:
            self.logger.error(f"Fatal market fetch error: {e}")
            self.risk_state.enter_fatal("MARKET_TICKER_FETCH_FAILED")
            return

        
        open_positions: List[HedgePosition] = self.hedge_position_repository.get_open_positions()

        # ===== 1. 平仓逻辑（优先） =====
        self._handle_close_logic(
            open_positions,
            market_ticker_snapshots,
            account_snapshot,
            now,
        )

        should_check_open_pairs: List[Pair] = self._select_should_check_open_pairs(
            open_positions,
            market_ticker_snapshots,
            account_snapshot
        )

        try:
            market_snapshots = self._load_market_snapshots(should_check_open_pairs)
        except Exception as e:
            self.logger.error(f"Fatal data fetch error: {e}")
            self.risk_state.enter_fatal("MARKET_FETCH_FAILED")
            return

        # ===== 2. 开仓逻辑 =====
        self._handle_open_logic(
            open_positions,
            market_snapshots,
            account_snapshot,
            now,
        )
        self.logger.info("------------------------------------------------------------------------------")

    # ========================
    # 内部方法
    # ========================

    def _load_market_snapshots(self, should_check_open_pairs: List[Pair]) -> Dict[str, MarketSnapshot]:
        """
        获取全量市场快照
        """
        return self.market_service.get_snapshot(should_check_open_pairs)

    # ========================
    # 内部方法
    # ========================

    def _load_market_ticker_snapshots(self) -> Dict[str, MarketTickerSnapshot]:
        """
        获取全量市场快照
        """
        snapshots = self.market_service.fetch_tickers(self.candidate_pairs)

        if not snapshots:
            raise RuntimeError("Empty market snapshot")

        return snapshots

    # ---------- 平仓 ----------

    def _handle_close_logic(
        self,
        open_positions: Optional[List[HedgePosition]],
        market_ticker_snapshots: Dict[str, MarketTickerSnapshot],
        account_snapshot: Any,
        now: float,
    ) -> None:
        
        if open_positions is None or len(open_positions) == 0:
            self.logger.debug("No open positions")
            return
        
        for position in open_positions:
            market_ticker_snapshot: Optional[MarketTickerSnapshot] =  market_ticker_snapshots.get(position.pair.pair_id)

            if market_ticker_snapshot is None:
                self.logger.warning(
                    f"Missing market snapshot for {position.pair.pair_id}"
                )
                continue

            if position.state not in {PositionState.OPEN, PositionState.CLOSING}:
                continue

            ctx = PositionContext(
                account=account_snapshot,
                market_ticker_snapshot=market_ticker_snapshot,
                position=position,
                risk_state=self.risk_state,
                config=self.config
            )

            try:
                should_close = self.strategy.should_close_position(ctx)
            except Exception as e:
                self.logger.error(f"Strategy close decision error: {e}")
                continue

            should_stop_loss = False
            if not should_close:
                # try:
                should_stop_loss = self.strategy.should_stop_loss(ctx)
                # except Exception as e:
                #     self.logger.error(f"Strategy close decision error: {e}")

            if not should_close and not should_stop_loss:
                continue

            if should_stop_loss:
                self.logger.info(f"Stopping loss for position {position.id}")
                self._lock_pairs(position.pair)

            self.logger.info(f"Closing position {position.id}")
            position.state = PositionState.CLOSING
            position.close_timestamp = now

            result = self.execution_service.close_position(position, market_ticker_snapshot)
            self._handle_execution_result(result)

    def _select_should_check_open_pairs(
            self,
            open_positions,
            market_ticker_snapshots,
            account_snapshot
    ) -> List[Pair]:
        should_check_open_pairs : List[Pair] = []
        max_positions = self.config.get("max_total_positions", 10)
        for pair in self.candidate_pairs:
            if len(open_positions) >= max_positions:
                break

            market = market_ticker_snapshots.get(pair.pair_id)
            if market is None:
                continue
            # 检查当前货币对是否已有开仓记录
            existing_positions = [pos for pos in open_positions if pos.pair.symbol == pair.symbol]
 
            if existing_positions:
                self.logger.info(f"跳过 {pair.symbol}，因为已有开仓记录")
                continue

            ctx = StrategyContext(
                account=account_snapshot,
                pair=pair,
                market_ticker_snapshot=market,
                market_snapshot=None,
                ohlcv_average=Decimal('0.0'),
                ohlcv_max=Decimal('0.0'),
                risk_state=self.risk_state,
                config=self.config
            )
            # try:
            should_fetch_depth: bool = self.strategy.should_fetch_depth(ctx)
            if should_fetch_depth:
                should_check_open_pairs.append(pair)
            # except Exception as e:
            #     self.logger.error(f"Strategy open decision error: {e}")
            #     continue
        return should_check_open_pairs
    
    # ---------- 开仓 ----------
    def _handle_open_logic(
        self,
        open_positions: Optional[List[HedgePosition]],
        market_snapshots: Dict[str, MarketSnapshot],
        account_snapshot: Any,
        now: float,
    ) -> None:
        max_positions = self.config.get("max_total_positions", 10)

        for pair in self.candidate_pairs:
            if time.time() < pair.locked_timestamp:
                self.logger.info(f"Pair {pair.pair_id} is still locked, skipping open operation.")
                continue
            if len(open_positions) >= max_positions:
                break
            market = market_snapshots.get(pair.pair_id)
            if market is None:
                continue

            # 检查当前货币对是否已有开仓记录
            existing_positions = [pos for pos in open_positions if pos.pair.symbol == pair.symbol]
 
            if existing_positions:
                self.logger.info(f"跳过 {pair.symbol}，因为已有开仓记录")
                continue

            ohlcv_diff_result: OHLCVDiffResult = self.market_service.get_ohlcv_diff(market)

            ctx = StrategyContext(
                account=account_snapshot,
                pair=pair,
                market_ticker_snapshot=None,
                market_snapshot=market,
                ohlcv_average=ohlcv_diff_result.average,
                ohlcv_max=ohlcv_diff_result.max,
                risk_state=self.risk_state,
                config=self.config
            )
            # intent: OpenIntent = initialize_arbitrage_engine_instance()
            # try:
            intent: OpenIntent = self.strategy.should_open_position(ctx)
            # except Exception as e:
            #     self.logger.error(f"Strategy open decision error: {e}")
            #     continue

            if intent is None:
                continue

            self.logger.info(
                f"Opening intent: {pair.pair_id}, notional={intent.notional_usd}"
            )

            result = self.execution_service.open_position(intent, market)

            self.logger.info(f"Execution result: {result}")
            self._handle_execution_result(result)

    # ---------- 执行结果统一处理 ----------

    def _handle_execution_result(self, result) -> None:
        """
        所有 ExecutionService 返回都必须经过这里
        """
        if result is None:
            return

        if not result.success:
            self.logger.warning(
                f"Execution failed: state={result.state}, error={result.error}"
            )

            if result.state == "EMERGENCY_CLOSED":
                self.risk_state.enter_fatal("EMERGENCY_CLOSE_TRIGGERED")
            return

        position = result.position
        if position is None:
            return

        if result.state == ExecutionState.OPENED:
            position.state = PositionState.OPEN
            self.hedge_position_repository.save(position)
            self.logger.info(f"Position opened: {position.id}")

        elif result.state == ExecutionState.PARTIAL:
            position.state = PositionState.OPEN
            self.hedge_position_repository.update(position)
            self.logger.warning(f"Partial fill accepted: {position.id}")

        elif result.state == ExecutionState.CLOSED:
            position.state = PositionState.CLOSED
            self.hedge_position_repository.update(position)
            self.logger.info(f"Position closed: {position.id}")

    def _lock_pairs(self, lock_pair: Pair):
        """
        冻结所有候选交易对（self.candidate_pairs），直到五分钟后解冻。
        可通过 pair.locked_timestamp 判断是否仍在冻结期内。
        """
        current_time = time.time()
        lock_duration = self.config.get('locked_seconds', 300)  # 5分钟 = 300秒

        for pair in self.candidate_pairs:
            if pair.pair_id == lock_pair.pair_id:  # 匹配目标交易对
                # 设置锁定时间为当前时间 + 5分钟
                pair.locked_timestamp = current_time + lock_duration
                self.logger.info(f"Pair {pair.pair_id} has been locked until {pair.locked_timestamp}")
            pass


