# backtest.py

import sys
import os
from typing import Dict, List
# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.application.services.arbitrage_engine import ArbitrageEngine
from src.infrastructure.config.config_manager import ConfigManager

from src.infrastructure.market.historical_market_service import HistoricalMarketService
from src.infrastructure.account.simulated_account_service import SimulatedAccountService  # 修正导入路径
from src.infrastructure.execution.simulated_execution_service import SimulatedExecutionService
from src.infrastructure.time.backtest_time_service import BacktestTimeService

from src.domain.services.simple_backtest_strategy import SimpleBacktestStrategy  # 新增导入
from src.application.logging.file_logger import FileLogger
from src.domain.value_objects.pair import Pair


def _load_config(config_path: str = "config/backtest.yml", global_config_path: str = "config/global.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    config_manager = ConfigManager()
    backtest_config = config_manager.load_or_create_config(config_path, _get_sample_config())
    global_config = config_manager.load_or_create_config(global_config_path, {})
    return {
        'exchanges': global_config['exchanges'],
        'pairs': backtest_config['pairs'],
        'csv_directory': backtest_config['csv_directory'],
        'initial_balance': backtest_config.get('initial_balance', 100000)
    }


def _get_sample_config():
    """
    创建示例配置文件
    """
    return {
        'pairs': [
            {
                'logical_symbol': 'BTC_USDT',
                'long_exchange': 'binance',
                'short_exchange': 'gateio'
            }
        ],
        'csv_directory': "data/historical",
        'initial_balance': 100000
    }

def load_strategy():
    # 返回简单回测策略的实例
    return SimpleBacktestStrategy()


def load_pair_universe() -> List[Pair]:
    # 从配置或数据加载交易对
    # 为了演示，我们简单返回一个示例交易对
    config = _load_config()
    pairs_config = config.get('pairs', [])
    pairs = []
    for pair_config in pairs_config:
        pair = Pair(
            logical_symbol=pair_config['logical_symbol'],
            long_exchange=pair_config['long_exchange'],
            short_exchange=pair_config['short_exchange']
        )
        pairs.append(pair)
    return pairs

def export_results(account_service: SimulatedAccountService):
    # 输出回测结果
    print(f"Final Balance: {account_service.get_total_balance()}")
    print(f"Positions: {len(account_service.get_real_positions())}")
    print("Backtest completed successfully!")

def main():
    logger = FileLogger(prefix="[BACKTEST]")

    logger.info("Starting BACKTEST engine")
    
    # 加载配置
    config = _load_config()
    if not config:
        logger.error("Failed to load configuration")
        return

    csv_directory = config.get('csv_directory', "data/historical")
    initial_balance = config.get('initial_balance', 100000)

    # ===== 回测基础设施 =====
    market_service = HistoricalMarketService(csv_directory)
    account_service = SimulatedAccountService(initial_balance)
    execution_service = SimulatedExecutionService(account_service=account_service)
    
    strategy = load_strategy()

    # 初始化时间服务，从市场数据中获取时间范围
    time_service = BacktestTimeService()
    if market_service._timestamps:
        time_service.set_time(market_service._timestamps[0])

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
    cycle_count = 0
    while market_service.has_more_data():
        engine.run_single_cycle()
        market_service._current_index += 1  # 移动到下一个时间点
        if market_service._current_index < len(market_service._timestamps):
            time_service.set_time(market_service._timestamps[market_service._current_index])
        cycle_count += 1
        
        # 每处理1000个周期打印一次进度
        if cycle_count % 1000 == 0:
            logger.info(f"Processed {cycle_count} cycles")

    logger.info("Backtest finished")
    export_results(account_service)


if __name__ == "__main__":
    main()