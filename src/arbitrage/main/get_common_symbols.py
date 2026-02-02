import json
import os
from typing import Dict, List
from decimal import Decimal

from arbitrage.infrastructure.market.ccxt_market_service import CCXTMarketService
from arbitrage.infrastructure.config.config_manager import ConfigManager

# 全局配置常量
QUOTE_CURRENCY = "USDT"  # 计价货币
SWAP_TYPES = ['swap', 'perpetual']  # 永续合约类型关键词
SYMBOL_SUFFIXES = ['SWAP', 'PERP']  # 符号后缀关键词


def load_config(global_config_path: str = "config/global.yml") -> Dict:
    """
    从配置文件加载交易所配置
    """
    config_manager = ConfigManager()
    global_config = config_manager.load_or_create_config(global_config_path, {})
    return global_config


def get_enabled_exchanges(config: Dict) -> Dict:
    """
    获取启用的交易所配置
    """
    enabled_exchanges = {}
    
    for exchange_name, exchange_config in config.get('exchanges', {}).items():
        if exchange_config.get('enabled', False):
            enabled_exchanges[exchange_name] = exchange_config
    
    return enabled_exchanges


def fetch_exchange_symbols(market_service: CCXTMarketService, exchange_name: str) -> List[Dict]:
    """
    获取指定交易所的所有符号
    """
    print(f"正在获取 {exchange_name} 的交易对信息...")
    try:
        exchange = market_service.exchanges[exchange_name]
        markets = exchange.load_markets()
        
        # 筛选出USDT永续合约
        filtered_symbols = []
        for symbol, market in markets.items():
            # 检查是否是USDT相关的交易对，并且是永续合约
            is_usdt_quote = market.get('quote') == QUOTE_CURRENCY or symbol.endswith(QUOTE_CURRENCY)
            is_swap_contract = (
                market.get('swap', False) or 
                any(suffix in symbol.upper() for suffix in SYMBOL_SUFFIXES) or
                any(swap_type in (market.get('type', '') or '').lower() for swap_type in SWAP_TYPES)
            )
            
            if is_usdt_quote and is_swap_contract:
                # 处理杠杆值，确保空值被设置为None
                leverage_info = market.get('info', {})
                leverage_val = leverage_info.get('leverage') if leverage_info.get('leverage') is not None else leverage_info.get('maxLeverage')
                leverage_max = float(leverage_val) if leverage_val is not None and str(leverage_val).strip() != '' else None
                
                # 处理合约大小，确保空值被设置为默认值1
                contract_size_val = market.get('contractSize', 1)
                contract_size = float(contract_size_val) if contract_size_val is not None and str(contract_size_val).strip() != '' else 1.0
                
                # 处理最小数量，确保空值被设置为默认值1
                min_qty_val = market.get('limits', {}).get('amount', {}).get('min', 1)
                min_qty = float(min_qty_val) if min_qty_val is not None and str(min_qty_val).strip() != '' else 1.0
                
                contract_info = {
                    "exchange_id": exchange_name,
                    "symbol": market.get('symbol'),
                    "base": market.get('base'),
                    "quote": market.get('quote'),
                    "contract_size": contract_size,
                    "min_qty": min_qty,
                    "leverage_max": leverage_max
                }
                
                filtered_symbols.append(contract_info)
        
        print(f"从 {exchange_name} 获取到 {len(filtered_symbols)} 个交易对")
        return filtered_symbols
    except Exception as e:
        print(f"获取 {exchange_name} 交易对时出现错误: {str(e)}")
        return []


def find_common_symbols(symbols_a: List[Dict], symbols_b: List[Dict]) -> List[Dict]:
    """
    查找两个交易所的共同交易对
    """
    # 提取base币种，组成交易对名称作为键
    symbols_a_map = {item['base']: item for item in symbols_a}
    symbols_b_map = {item['base']: item for item in symbols_b}
    
    common_symbols = []
    
    for base_coin in symbols_a_map:
        if base_coin in symbols_b_map:
            # 创建包含两个交易所合约信息的对象
            pair_obj = {
                "symbol": symbols_a_map[base_coin]['symbol'],  # 使用第一个交易所的symbol
                "base": base_coin,
                "quote": QUOTE_CURRENCY,
                'long_exchange': symbols_a_map[base_coin]['exchange_id'],
                'short_exchange': symbols_b_map[base_coin]['exchange_id'],
                "contracts": {
                    symbols_a_map[base_coin]['exchange_id']: {
                        "contract_size": symbols_a_map[base_coin]['contract_size'],
                        "min_qty": symbols_a_map[base_coin]['min_qty'],
                        "leverage_max": symbols_a_map[base_coin]['leverage_max']
                    },
                    symbols_b_map[base_coin]['exchange_id']: {
                        "contract_size": symbols_b_map[base_coin]['contract_size'],
                        "min_qty": symbols_b_map[base_coin]['min_qty'],
                        "leverage_max": symbols_b_map[base_coin]['leverage_max']
                    }
                }
            }
            common_symbols.append(pair_obj)
    
    return common_symbols


def main():
    """
    主函数：获取两个交易所共有的USDT交易对并保存到文件
    """
    print("开始获取交易所共有交易对...")
    
    # 加载全局配置
    config = load_config()
    if not config:
        print("无法加载配置文件")
        return
    
    # 获取启用的交易所
    enabled_exchanges = get_enabled_exchanges(config)
    if not enabled_exchanges:
        print("没有启用的交易所，请检查配置文件")
        return
    
    exchange_names = list(enabled_exchanges.keys())
    
    if len(exchange_names) < 2:
        print("启用的交易所少于2个，无法查找共同交易对")
        return
    
    # 只使用前两个启用的交易所
    exchange_a, exchange_b = sorted(exchange_names)[:2]  # 按字母顺序排序
    
    print(f"将获取 {exchange_a} 和 {exchange_b} 的共同{QUOTE_CURRENCY}交易对")
    
    # 准备交易所配置（去除不必要的配置项，只保留API等基本配置）
    exchanges_config = {}
    for exch_name in [exchange_a, exchange_b]:
        exch_config = enabled_exchanges[exch_name].copy()
        # 移除可能影响市场数据获取的特定选项
        if 'options' in exch_config:
            opts = exch_config['options'].copy()
            # 保留重要选项，但移除可能干扰获取市场数据的选项
            exch_config['options'] = opts
        exchanges_config[exch_name] = exch_config
    
    # 创建市场服务
    market_service = CCXTMarketService(exchanges_config)
    
    # 获取两个交易所的USDT交易对
    symbols_a = fetch_exchange_symbols(market_service, exchange_a)
    symbols_b = fetch_exchange_symbols(market_service, exchange_b)
    
    # 查找共同的交易对
    common_symbols = find_common_symbols(symbols_a, symbols_b)
    
    # 按字母顺序排列交易所名称，形成文件名
    sorted_names = sorted([exchange_a, exchange_b])
    filename = f"{sorted_names[0]}_{sorted_names[1]}_pairs.json"
    filepath = os.path.join("data", filename)
    
    # 确保data目录存在
    os.makedirs("data", exist_ok=True)
    
    # 保存到文件
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(common_symbols, f, indent=2, ensure_ascii=False)
    
    print(f"已找到 {len(common_symbols)} 个共同的{QUOTE_CURRENCY}交易对")
    print(f"已保存到 {filepath}")
    
    # 显示前几个例子
    for i, pair in enumerate(common_symbols[:5]):
        print(f"  {i+1}. {pair['symbol']} ({pair['base']}/{QUOTE_CURRENCY})")


if __name__ == "__main__":
    main()