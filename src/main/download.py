import os
import time
import csv
from datetime import datetime, timedelta
from typing import List, Dict

from domain.value_objects.pair import Pair
from infrastructure.config.config_manager import ConfigManager
from infrastructure.market.ccxt_market_service import CCXTMarketService


def _load_config(config_path: str = "config/download.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    configManager = ConfigManager()
    return configManager.load_or_create_config(config_path, _get_sample_config())


def _get_sample_config():
    """
    创建示例配置文件
    """
    return {
        'exchanges': {
            'binance': {
                'enabled': True,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                },
                'proxies': {
                    'https': 'http://127.0.0.1:7897'
                },
                'fees': {
                    'maker': 0.001,
                    'taker': 0.002
                },
                'apiKey': 'your_api_key_here',
                'secret': 'your_secret_here',
                'sandbox': False,
            },
            'gateio': {
                'enabled': True,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'
                },
                'proxies': {
                    'https': 'http://127.0.0.1:7897'
                },
                'fees': {
                    'maker': 0.001,
                    'taker': 0.002
                },
                'apiKey': 'your_api_key_here',
                'secret': 'your_secret_here',
                'sandbox': False
            }
        },
        'pairs': [
            {
                'logical_symbol': 'BTC/USDT',
                'long_exchange': 'binance',
                'short_exchange': 'gateio'
            }
        ],
        'time_service': {
            'start_time': datetime.now() - timedelta(days=7),
            'end_time': datetime.now(),
            'interval': 60
        },
        'download': {
            'output_dir': 'data/historical'
        }
    }

def get_enabled_exchanges(config: Dict) -> Dict:
    """
    获取启用的交易所配置
    """
    enabled_exchanges = {}
    
    for exchange_name, exchange_config in config.get('exchanges', {}).items():
        if exchange_config.get('enabled', False):
            enabled_exchanges[exchange_name] = exchange_config
    
    return enabled_exchanges


def fetch_and_save_historical_data_with_ccxt_service(
    exchanges_config: Dict,
    pairs: List[Pair],
    start_time: float,
    end_time: float,
    interval: int = 60,  # 数据采集间隔（秒）
    output_dir: str = "data/historical"
):
    """
    使用 CCXTMarketService 获取并保存历史数据
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"开始下载数据，时间范围: {datetime.fromtimestamp(start_time)} - {datetime.fromtimestamp(end_time)}")
    
    # 创建 CCXTMarketService 实例
    market_service = CCXTMarketService(exchanges_config)
    
    current_time = start_time
    
    while current_time <= end_time:
        print(f"正在获取时间点: {datetime.fromtimestamp(current_time)}")
        
        # 获取市场快照
        snapshots = market_service.get_snapshot(pairs)
        
        for pair in pairs:
            if pair.pair_id in snapshots:
                snapshot = snapshots[pair.pair_id]
                
                # 为长仓交易所准备数据
                long_data = {
                    'timestamp': current_time,
                    'exchange': snapshot.long_leg.exchange,
                    'symbol': snapshot.long_leg.symbol,
                    'last_price': str(snapshot.long_leg.last_price) if snapshot.long_leg.last_price else None,
                    'bid_price': str(snapshot.long_leg.best_bid_price) if snapshot.long_leg.best_bid_price else None,
                    'bid_size': str(snapshot.long_leg.best_bid_size) if snapshot.long_leg.best_bid_size else None,
                    'ask_price': str(snapshot.long_leg.best_ask_price) if snapshot.long_leg.best_ask_price else None,
                    'ask_size': str(snapshot.long_leg.best_ask_size) if snapshot.long_leg.best_ask_size else None
                }
                
                # 为短仓交易所准备数据
                short_data = {
                    'timestamp': current_time,
                    'exchange': snapshot.short_leg.exchange,
                    'symbol': snapshot.short_leg.symbol,
                    'last_price': str(snapshot.short_leg.last_price) if snapshot.short_leg.last_price else None,
                    'bid_price': str(snapshot.short_leg.best_bid_price) if snapshot.short_leg.best_bid_price else None,
                    'bid_size': str(snapshot.short_leg.best_bid_size) if snapshot.short_leg.best_bid_size else None,
                    'ask_price': str(snapshot.short_leg.best_ask_price) if snapshot.short_leg.best_ask_price else None,
                    'ask_size': str(snapshot.short_leg.best_ask_size) if snapshot.short_leg.best_ask_size else None
                }
                
                # 保存长仓数据
                long_filename = os.path.join(
                    output_dir,
                    f"{pair.logical_symbol.replace('/', '_')}_{pair.long_exchange}_{pair.short_exchange}.csv"
                )
                
                save_data_to_csv(long_data, long_filename, is_first=current_time==start_time)
                
                # 保存短仓数据
                short_filename = os.path.join(
                    output_dir,
                    f"{pair.logical_symbol.replace('/', '_')}_{pair.short_exchange}_{pair.long_exchange}.csv"
                )
                
                save_data_to_csv(short_data, short_filename, is_first=current_time==start_time)
        
        current_time += interval
        time.sleep(0.1)  # 避免请求过于频繁
    
    print("数据下载完成")


def save_data_to_csv(data: Dict, filename: str, is_first: bool):
    """
    将数据保存到CSV文件
    """
    write_header = is_first and not os.path.exists(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'timestamp', 
            'exchange', 
            'symbol', 
            'last_price', 
            'bid_price', 
            'bid_size', 
            'ask_price', 
            'ask_size'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if write_header:
            writer.writeheader()
        
        if data:
            writer.writerow(data)


def main():
    """
    主函数
    """
    print("开始下载历史行情数据...")
    
    # 加载配置
    config = _load_config()
    if not config:
        return
    
    # 获取启用的交易所配置
    exchanges_config = get_enabled_exchanges(config)
    if not exchanges_config:
        print("没有启用的交易所，请检查配置文件")
        return
    
    # 从配置中获取交易对
    pairs_config = config.get('pairs', [])
    if not pairs_config:
        print("配置中没有定义交易对")
        return
    
    pairs = convert_pairs_config(pairs_config)
    
    # 从配置中获取时间设置
    time_config = config.get('time_service', {})
    start_offset = time_config.get('start_time_offset_days', 7)  # 默认7天前
    interval = time_config.get('interval_seconds', 60)  # 默认每60秒一个数据点

    end_time = time.time()
    start_time = end_time - (start_offset * 24 * 3600)  # 计算开始时间
    
    # 从配置中获取输出目录
    download_config = config.get('download', {})
    output_dir = download_config.get('output_dir', 'data/historical')
    
    # 使用 CCXTMarketService 下载数据
    fetch_and_save_historical_data_with_ccxt_service(
        exchanges_config=exchanges_config,
        pairs=pairs,
        start_time=start_time,
        end_time=end_time,
        interval=interval,
        output_dir=output_dir
    )
    


def convert_pairs_config(pairs_config: List[Dict]) -> List[Pair]:
    """
    将配置中的字典格式转换为Pair对象
    """
    pairs = []
    for pair_config in pairs_config:
        pair = Pair(
            logical_symbol=pair_config['logical_symbol'],
            long_exchange=pair_config['long_exchange'],
            short_exchange=pair_config['short_exchange']
        )
        pairs.append(pair)
    return pairs


if __name__ == "__main__":
    main()