import time
from typing import Dict, Optional, Any

from src.domain.services.strategy import IStrategy
from src.domain.services.market_service import MarketService
from src.domain.services.account_service import AccountService
from src.domain.services.execution_service import ExecutionService
from src.domain.services.time_service import TimeService

from src.domain.entities.hedge_position import HedgePosition, PositionState
from src.domain.value_objects.pair import Pair
from src.domain.models.market_snapshot import MarketSnapshot

from src.domain.entities.contexts import StrategyContext, PositionContext
from src.domain.entities.risk_state import RiskState
from src.application.logging.file_logger import ILogger, FileLogger


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
        market_service: MarketService,
        account_service: AccountService,
        execution_service: ExecutionService,
        time_service: TimeService,
        logger: Optional[ILogger] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.strategy = strategy
        self.market_service = market_service
        self.account_service = account_service
        self.execution_service = execution_service
        self.time_service = time_service

        self.logger = logger or FileLogger()
        self.config = config or {}

        self.risk_state = RiskState()

        # 内存态（⚠️不是最终事实）
        self.positions: Dict[str, HedgePosition] = {}

        # 初始化候选交易对
        universe = self.config.get("pair_universe", [])
        self.candidate_pairs = self.strategy.select_pairs(universe)

        self.logger.info(
            f"Engine initialized with {len(self.candidate_pairs)} candidate pairs"
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
            market_snapshots = self._load_market_snapshots()
            account_snapshot = self.account_service.get_account_snapshot()
        except Exception as e:
            self.logger.error(f"Fatal data fetch error: {e}")
            self.risk_state.enter_fatal("MARKET_OR_ACCOUNT_FETCH_FAILED")
            return

        # ===== 1. 平仓逻辑（优先） =====
        for position in list(self.positions.values()):
            self._handle_close_logic(
                position,
                market_snapshots.get(position.pair.pair_id),
                account_snapshot,
                now,
            )

        # ===== 2. 开仓逻辑 =====
        self._handle_open_logic(
            market_snapshots,
            account_snapshot,
            now,
        )

    # ========================
    # 内部方法
    # ========================

    def _load_market_snapshots(self) -> Dict[str, MarketSnapshot]:
        """
        获取全量市场快照
        """
        snapshots = self.market_service.get_snapshot(self.candidate_pairs)

        if not snapshots:
            raise RuntimeError("Empty market snapshot")

        return snapshots

    # ---------- 平仓 ----------

    def _handle_close_logic(
        self,
        position: HedgePosition,
        market: Optional[MarketSnapshot],
        account_snapshot: Any,
        now: float,
    ) -> None:
        if market is None:
            self.logger.warning(
                f"Missing market snapshot for {position.pair.pair_id}"
            )
            return

        if position.state not in {PositionState.OPEN, PositionState.CLOSING}:
            return

        ctx = PositionContext(
            position=position,
            market=market,
            account=account_snapshot,
            now=now,
            risk_state=self.risk_state,
        )

        try:
            should_close = self.strategy.should_close(ctx)
        except Exception as e:
            self.logger.error(f"Strategy close decision error: {e}")
            return

        if not should_close:
            return

        self.logger.info(f"Closing position {position.id}")
        position.state = PositionState.CLOSING

        result = self.execution_service.close_position(position, market)
        self._handle_execution_result(result)

    # ---------- 开仓 ----------

    def _handle_open_logic(
        self,
        market_snapshots: Dict[str, MarketSnapshot],
        account_snapshot: Any,
        now: float,
    ) -> None:
        max_positions = self.config.get("max_total_positions", 10)

        if len(self.positions) >= max_positions:
            return

        for pair in self.candidate_pairs:
            if len(self.positions) >= max_positions:
                break

            market = market_snapshots.get(pair.pair_id)
            if market is None:
                continue

            ctx = StrategyContext(
                pair=pair,
                market=market,
                account=account_snapshot,
                now=now,
                risk_state=self.risk_state,
            )

            try:
                intent = self.strategy.open_intent(ctx)
            except Exception as e:
                self.logger.error(f"Strategy open decision error: {e}")
                continue

            if intent is None:
                continue

            self.logger.info(
                f"Opening intent: {pair.pair_id}, notional={intent.notional_usd}"
            )

            result = self.execution_service.open_position(intent, market)
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

        if result.state == "OPENED":
            position.state = PositionState.OPEN
            self.positions[position.id] = position
            self.logger.info(f"Position opened: {position.id}")

        elif result.state == "PARTIAL":
            position.state = PositionState.OPEN
            self.positions[position.id] = position
            self.logger.warning(f"Partial fill accepted: {position.id}")

        elif result.state == "CLOSED":
            self.positions.pop(position.id, None)
            self.logger.info(f"Position closed: {position.id}")