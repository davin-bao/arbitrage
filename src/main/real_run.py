# real_run.py

import time
import signal
import sys

from application.services.arbitrage_engine import ArbitrageEngine

from infrastructure.market.ccxt_market_service import CCXTMarketService
from infrastructure.account.ccxt_account_service import CCXTAccountService
from infrastructure.execution.ccxt_execution_service import CCXTExecutionService
from infrastructure.time.real_time_service import RealTimeService

from domain.services.strategy import IStrategy
from application.logging import ConsoleLogger


RUN_INTERVAL_SECONDS = 1.0


def main():
    logger = ConsoleLogger(prefix="[REAL]")

    logger.info("Starting REAL trading engine")

    # ===== 实盘基础设施 =====
    market_service = CCXTMarketService()
    account_service = CCXTAccountService()
    execution_service = CCXTExecutionService()
    time_service = RealTimeService()

    # ===== 策略 =====
    strategy: IStrategy = load_strategy()

    engine = ArbitrageEngine(
        strategy=strategy,
        market_service=market_service,
        account_service=account_service,
        execution_service=execution_service,
        time_service=time_service,
        logger=logger,
        config={
            "max_total_positions": 5,
            "pair_universe": load_pair_universe(),
        },
    )

    # ===== 优雅退出 =====
    def shutdown_handler(sig, frame):
        logger.warning("Shutdown signal received, exiting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # ===== 主循环 =====
    while True:
        engine.run_single_cycle()
        time.sleep(RUN_INTERVAL_SECONDS)


def load_strategy() -> IStrategy:
    """
    加载实盘策略（留给你自己实现）
    """
    from strategies.my_real_strategy import MyRealStrategy
    return MyRealStrategy()


def load_pair_universe():
    """
    返回 Pair 列表
    """
    from config.pairs import PAIR_UNIVERSE
    return PAIR_UNIVERSE


if __name__ == "__main__":
    main()
