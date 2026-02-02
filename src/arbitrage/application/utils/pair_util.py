"""
交易对加载工具模块
"""
import json
import os
from typing import List
from arbitrage.infrastructure.config.config_manager import ConfigManager
from arbitrage.domain.entities.pair import Pair
from arbitrage.application.utils.paths import DATA_DIR



def load_pairs(
    config_path: str = "config/global.yml", 
    csv_directory: str = "data/historical"
) -> List[Pair]:
    """
    从配置文件和交易对文件加载交易对列表
    
    Args:
        config_path: 配置文件路径
        csv_directory: Pairs文件路径
        
    Returns:
        List[Pair]: 交易对列表
    """
    config = _load_config_with_paths(config_path, csv_directory)
    exchanges = list(config['exchanges'].keys())
    
    if len(exchanges) < 2:
        raise ValueError("至少需要配置两个交易所才能进行套利回测")
    
    # 使用配置中的前两个交易所作为做多和做空交易所
    long_exchange_name = exchanges[0]
    short_exchange_name = exchanges[1]
        
    # 按字母顺序排列交易所名称，构成文件名
    sorted_exchanges = sorted([long_exchange_name, short_exchange_name])
    pair_file = DATA_DIR / f"{sorted_exchanges[0]}_{sorted_exchanges[1]}_pairs.json"
    
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

def _load_config_with_paths(config_path: str, csv_directory: str):
    """
    从指定路径加载配置
    """
    config_manager = ConfigManager()
    global_config = config_manager.load_or_create_config(config_path, {})
    return {
        'exchanges': global_config['exchanges'],
        'csv_directory': csv_directory
    }
