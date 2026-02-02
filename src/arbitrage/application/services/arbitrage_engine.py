from typing import Dict, Optional, Any, List

from arbitrage.domain.services.strategy import IStrategy
from arbitrage.domain.services.market_service import MarketService
from arbitrage.domain.services.account_service import AccountService
from arbitrage.domain.services.execution_service import ExecutionService
from arbitrage.domain.services.time_service import TimeService

from arbitrage.domain.entities.hedge_position import HedgePosition, PositionState
from arbitrage.domain.entities.account_snapshot import AccountSnapshot
from arbitrage.domain.entities.pair import Pair
from arbitrage.domain.models.market_snapshot import MarketSnapshot

from arbitrage.domain.entities.open_intent import OpenIntent
from arbitrage.domain.entities.contexts import StrategyContext, PositionContext
from arbitrage.domain.entities.risk_state import RiskState
from arbitrage.domain.entities.enums import ExecutionState
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

        self.logger = logger or FileLogger()
        self.config = config or {}

        self.risk_state = RiskState()

        # 初始化候选交易对
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
            account_snapshot: AccountSnapshot = self.account_service.get_account_snapshot()
        except Exception as e:
            self.logger.error(f"Fatal data fetch error: {e}")
            self.risk_state.enter_fatal("MARKET_OR_ACCOUNT_FETCH_FAILED")
            return

        # ===== 1. 平仓逻辑（优先） =====
        for position in self.hedge_position_repository.get_open_positions():
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
            account=account_snapshot,
            market_snapshot=market,
            position=position,
            risk_state=self.risk_state,
            config=self.config
        )

        try:
            should_close = self.strategy.should_close_position(ctx)
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

        for pair in self.candidate_pairs:
            if len(self.hedge_position_repository.get_open_positions()) >= max_positions:
                break

            market = market_snapshots.get(pair.pair_id)
            if market is None:
                continue

            ctx = StrategyContext(
                account=account_snapshot,
                pair=pair,
                market_snapshot=market,
                risk_state=self.risk_state,
                config=self.config
            )
            intent: OpenIntent = initialize_arbitrage_engine_instance()
            # try:
            #     intent: OpenIntent = self.strategy.should_open_position(ctx)
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
            self.hedge_position_repository.update(position)
            self.logger.info(f"Position closed: {position.id}")

# 假设这是ArbitrageEngine类的构造函数调用
def initialize_arbitrage_engine_instance():
    from decimal import Decimal
    from arbitrage.domain.entities.enums import EntryType
    from arbitrage.domain.entities.pair import Pair, ContractInfo


    # 创建合约信息字典
    contracts = {
        'binance': ContractInfo(
            contract_size=1.0,
            min_qty=1.0,
            leverage_max=None
        ),
        'okx': ContractInfo(
            contract_size=10.0,
            min_qty=1.0,
            leverage_max=None
        )
    }
    
    # 创建交易对对象
    pair = Pair(
        symbol='FUN/USDT:USDT',
        base='FUN',
        quote='USDT',
        long_exchange='binance',
        short_exchange='okx',
        contracts=contracts
    )
    
    # 创建开仓意图对象
    open_intent = OpenIntent(
        pair=pair,
        notional_usd=Decimal('100'),
        entry_type=EntryType.LIMIT,
        max_slippage=Decimal('0.005'),
        reason='Spread 34.93724194880264244426094137 exceeds threshold 0.02'
    )
    
    return open_intent



