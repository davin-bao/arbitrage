# dry_run.py

import time
import signal
import sys

from src.application.services.arbitrage_engine import ArbitrageEngine

from infrastructure.ccxt_market_service import CCXTMarketService
from infrastructure.account.simulated_account_service import SimulatedAccountService
from infrastructure.execution.simulated_execution_service import SimulatedExecutionService
from infrastructure.time.real_time_service import RealTimeService

from src.domain.services.strategy import IStrategy
from src.application.logging import ConsoleLogger


RUN_INTERVAL_SECONDS = 1.0


def main():
    logger = ConsoleLogger(prefix="[DRY-RUN]")

    logger.info("Starting DRY-RUN trading engine")

    # ===== 模拟基础设施 =====
    market_service = CCXTMarketService()
    account_service = SimulatedAccountService(initial_balance=100_000)
    execution_service = SimulatedExecutionService()
    time_service = RealTimeService()

    strategy: IStrategy = load_strategy()

    engine = ArbitrageEngine(
        strategy=strategy,
        market_service=market_service,
        account_service=account_service,
        execution_service=execution_service,
        time_service=time_service,
        logger=logger,
        config={
            "max_total_positions": 10,
            "pair_universe": load_pair_universe(),
        },
    )

    def shutdown_handler(sig, frame):
        logger.warning("Shutdown signal received, exiting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    while True:
        engine.run_single_cycle()
        time.sleep(RUN_INTERVAL_SECONDS)


def load_strategy() -> IStrategy:
    from strategies.my_dry_run_strategy import MyDryRunStrategy
    return MyDryRunStrategy()


def load_pair_universe():
    from config.pairs import PAIR_UNIVERSE
    return PAIR_UNIVERSE


if __name__ == "__main__":
    main()
