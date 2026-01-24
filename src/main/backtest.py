# backtest.py

import sys
import os
from typing import Dict
# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from application.services.arbitrage_engine import ArbitrageEngine
from infrastructure.config.config_manager import ConfigManager

from src.infrastructure.market.historical_market_service import HistoricalMarketService
from infrastructure.account.simulated_account_service import SimulatedAccountService
from infrastructure.execution.simulated_execution_service import SimulatedExecutionService
from infrastructure.time.backtest_time_service import BacktestTimeService

from domain.services.strategy import IStrategy
from application.logging.file_logger import FileLogger



def _load_config(config_path: str = "config/backtest.yml", global_config_path: str = "config/global.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    configManager = ConfigManager()
    backtestConfig = configManager.load_or_create_config(config_path, _get_sample_config())
    globalConfig = ConfigManager.load_or_create_config(global_config_path, {})
    return {
        'exchanges': globalConfig['exchanges'],
        'pairs': backtestConfig['pairs'],
        'csv_directory': backtestConfig['csv_directory']
    }


def _get_sample_config():
    """
    创建示例配置文件
    """
    return {
        'pairs': [
            {
                'logical_symbol': 'BTC/USDT',
                'long_exchange': 'binance',
                'short_exchange': 'gateio'
            }
        ],
        'csv_directory': "data/historical",
        'initial_balance': 100_000
    }


def main():
    logger = FileLogger(prefix="[BACKTEST]")

    logger.info("Starting BACKTEST engine")
    
    # 加载配置
    config = _load_config()
    if not config:
        return

    csv_directory = config.get('csv_directory', "data/historical")
    initial_balance = config.get('initial_balance', 100_000)

    # ===== 回测时间 =====
    time_service = BacktestTimeService(
        start_ts=1700000000.0,
        end_ts=1700086400.0,
        step_seconds=1.0,
    )

    # ===== 回测基础设施 =====
    market_service = HistoricalMarketService(csv_directory)
    account_service = SimulatedAccountService(initial_balance)
    execution_service = SimulatedExecutionService()
    
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

    # ===== 回测主循环 =====
    while time_service.has_next():
        engine.run_single_cycle()
        time_service.step()

    logger.info("Backtest finished")
    export_results(account_service)


def load_strategy() -> IStrategy:
    from strategies.my_backtest_strategy import MyBacktestStrategy
    return MyBacktestStrategy()


def load_pair_universe():
    from config.pairs import PAIR_UNIVERSE
    return PAIR_UNIVERSE


def export_results(account_service):
    """
    导出回测结果（PnL / 曲线等）
    """
    summary = account_service.get_summary()
    print("Final PnL:", summary.total_pnl)


if __name__ == "__main__":
    main()