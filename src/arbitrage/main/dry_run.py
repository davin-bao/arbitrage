# dry_run.py

import time
import signal
import sys
from typing import Dict
import arbitrage.application.utils.debug_profiler as debug_profiler

from arbitrage.application.services.arbitrage_engine import ArbitrageEngine
from arbitrage.infrastructure.config.config_manager import ConfigManager

from arbitrage.infrastructure.market.ccxt_market_service import CCXTMarketService
from arbitrage.infrastructure.market.historical_market_service import HistoricalMarketService
from arbitrage.infrastructure.account.simulated_account_service import SimulatedAccountService
from arbitrage.infrastructure.execution.simulated_execution_service import SimulatedExecutionService
from arbitrage.infrastructure.time.real_time_service import RealTimeService
from arbitrage.infrastructure.persistence.sqlite_connection import SqliteConnection
from arbitrage.infrastructure.persistence.hedge_position_repository_sqlite import HedgePositionRepositorySqlite

from arbitrage.domain.services.strategy import IStrategy
from arbitrage.application.logging.file_logger import ILogger, FileLogger


RUN_INTERVAL_SECONDS = 2.0


def main():
    # debug_profiler.enable()
    logger = FileLogger(prefix="[DRY-RUN]")
    logger.info("Starting DRY-RUN trading engine")
    config = _load_config()

    # ===== 模拟基础设施 =====
    market_service = CCXTMarketService(config['exchanges'])
    account_service = SimulatedAccountService(initial_balance=100_000)
    execution_service = SimulatedExecutionService(account_service=account_service, config=config)
    time_service = RealTimeService()
    sqliteConnection = SqliteConnection(db_path=config['db_path'])
    hedge_position_repository = HedgePositionRepositorySqlite(conn=sqliteConnection)

    strategy: IStrategy = load_strategy(logger)

    engine = ArbitrageEngine(
        strategy=strategy,
        universe=load_pair_universe(),
        market_service=market_service,
        account_service=account_service,
        execution_service=execution_service,
        time_service=time_service,
        hedge_position_repository=hedge_position_repository,
        config=config,
    )

    def shutdown_handler(sig, frame):
        logger.warning("Shutdown signal received, exiting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    while True:
        engine.run_single_cycle()
        time.sleep(RUN_INTERVAL_SECONDS)


def _load_config(config_path: str = "config/dry_run.yml", global_config_path: str = "config/global.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    config_manager = ConfigManager()
    dry_config = config_manager.load_or_create_config(config_path, _get_sample_config())
    global_config = config_manager.load_or_create_config(global_config_path, {})
    return {
        'exchanges': global_config['exchanges'],
        'blacklist_pairs': global_config.get('blacklist_pairs', []),
        'db_path': dry_config.get('db_path', 'data/arb.db'),
        'initial_balance': dry_config.get('initial_balance', 100000),
        'locked_seconds': dry_config.get('locked_seconds', 300),
        'max_total_positions': 10
    }

def _get_sample_config():
    """
    创建示例配置文件
    """
    return {
        'initial_balance': 100000
    }


def load_strategy(logger: ILogger):
    from arbitrage.domain.services.simple_backtest_strategy import SimpleBacktestStrategy  # 新增导入
    # 返回简单回测策略的实例
    return SimpleBacktestStrategy(logger)


def load_pair_universe():
    from arbitrage.application.utils.pair_util import load_pairs
    return load_pairs()


if __name__ == "__main__":
    main()
