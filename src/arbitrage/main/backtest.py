# backtest.py

import sys
import os
import json
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
from src.domain.entities.pair import Pair, ContractInfo


def _load_config(config_path: str = "config/backtest.yml", global_config_path: str = "config/global.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    config_manager = ConfigManager()
    backtest_config = config_manager.load_or_create_config(config_path, _get_sample_config())
    global_config = config_manager.load_or_create_config(global_config_path, {})
    return {
        'exchanges': global_config['exchanges'],
        'csv_directory': backtest_config['csv_directory'],
        'initial_balance': backtest_config.get('initial_balance', 100000)
    }


def _get_sample_config():
    """
    创建示例配置文件
    """
    return {
        'csv_directory': "data/historical",
        'initial_balance': 100000
    }


def _get_pairs():
    """从JSON文件加载交易对"""
    # 加载配置以获取交易所信息
    config = _load_config()
    exchanges = list(config['exchanges'].keys())
    
    if len(exchanges) < 2:
        raise ValueError("至少需要配置两个交易所才能进行套利回测")
    
    # 使用配置中的前两个交易所作为做多和做空交易所
    long_exchange_name = exchanges[0]
    short_exchange_name = exchanges[1]
    
    # 获取数据目录中的交易对文件，文件名按照字母顺序排列
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    
    # 按字母顺序排列交易所名称，构成文件名
    sorted_exchanges = sorted([long_exchange_name, short_exchange_name])
    pair_file = os.path.join(data_dir, f"{sorted_exchanges[0]}_{sorted_exchanges[1]}_pairs.json")
    
    if not os.path.exists(pair_file):
        raise FileNotFoundError(f"交易对文件不存在: {pair_file}")
    
    with open(pair_file, 'r', encoding='utf-8') as f:
        pairs_data = json.load(f)
    
    pairs = []
    for pair_data in pairs_data:
        # 使用 Pair 类的 from_dict 方法从字典创建对象
        pair = Pair.from_dict(pair_data)
        pairs.append(pair)
        
    return pairs

def load_strategy():
    # 返回简单回测策略的实例
    return SimpleBacktestStrategy()


def load_pair_universe() -> List[Pair]:
    """从JSON文件加载交易对"""
    return _get_pairs()

def export_results(account_service: SimulatedAccountService):
    # 输出回测结果
    print(f"Final Balance: {account_service.get_total_balance()}")
    print(f"Positions: {len(account_service.get_real_positions())}")
    print("Backtest completed successfully!")

def main():
    config = _load_config()
    initial_balance = config['initial_balance']
    csv_directory = config['csv_directory']
    
    # 初始化服务
    market_service = HistoricalMarketService(csv_directory=csv_directory)
    account_service = SimulatedAccountService(initial_balance=initial_balance)
    execution_service = SimulatedExecutionService(account_service)
    time_service = BacktestTimeService()
    logger = FileLogger("backtest")
    strategy = load_strategy()
    pairs = load_pair_universe()
    
    # 初始化套利引擎
    engine = ArbitrageEngine(
        market_service=market_service,
        account_service=account_service,
        execution_service=execution_service,
        time_service=time_service,
        strategy=strategy,
        logger=logger,
        pairs=pairs
    )
    
    # 运行回测
    while market_service.has_more_data():
        snapshots = market_service.get_snapshot(pairs)
        if snapshots:
            engine.process_market_snapshot(snapshots)
        else:
            break

    # 导出结果
    export_results(account_service)

if __name__ == "__main__":
    main()