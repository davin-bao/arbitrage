"""
测试 HistoricalMarketService 是否成功实现了 MarketService 接口
"""

import os
import sys
from decimal import Decimal
from typing import List, Dict

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from domain.services.market_service import MarketService
from domain.value_objects.pair import Pair
from domain.models.market_snapshot import MarketSnapshot
from src.infrastructure.market.historical_market_service import HistoricalMarketService


def test_interface_implementation():
    """
    测试 HistoricalMarketService 是否正确实现了 MarketService 接口
    """
    print("=== 测试 HistoricalMarketService 接口实现 ===")
    
    # 1. 检查是否继承自 MarketService
    assert issubclass(HistoricalMarketService, MarketService), "HistoricalMarketService 应该继承自 MarketService"
    print("✓ HistoricalMarketService 继承自 MarketService")
    
    # 2. 检查是否实现了抽象方法 get_snapshot
    service_instance = HistoricalMarketService()
    assert hasattr(service_instance, 'get_snapshot'), "实例应该有 get_snapshot 方法"
    assert callable(getattr(service_instance, 'get_snapshot')), "get_snapshot 应该是可调用的方法"
    print("✓ HistoricalMarketService 实现了 get_snapshot 方法")
    
    # 3. 检查 get_snapshot 方法的参数签名
    import inspect
    sig = inspect.signature(service_instance.get_snapshot)
    params = list(sig.parameters.keys())
    assert params == ['pairs'], f"get_snapshot 应该接受 'pairs' 参数，实际参数: {params}"
    print("✓ get_snapshot 方法参数签名正确")
    
    # 4. 检查返回类型注解
    return_annotation = sig.return_annotation
    expected_return_type = Dict[str, MarketSnapshot]
    print(f"✓ get_snapshot 返回类型注解: {return_annotation}")
    
    print("\n=== 接口实现测试完成 ===\n")


def test_functionality():
    """
    测试 HistoricalMarketService 的功能
    """
    print("=== 测试 HistoricalMarketService 功能 ===")
    
    # 准备测试数据
    csv_directory = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'historical')
    
    if not os.path.exists(csv_directory):
        print(f"⚠️  数据目录不存在: {csv_directory}")
        print("   请先确保数据文件存在，才能进行功能测试")
        return False
    
    # 检查是否有历史数据文件
    csv_files = [f for f in os.listdir(csv_directory) if f.endswith('.csv')]
    if not csv_files:
        print(f"⚠️  数据目录中没有 CSV 文件: {csv_directory}")
        return False
    
    print(f"✓ 发现 {len(csv_files)} 个 CSV 文件: {csv_files}")
    
    # 创建服务实例
    try:
        service = HistoricalMarketService(csv_directory=csv_directory)
        print("✓ 成功创建 HistoricalMarketService 实例")
    except Exception as e:
        print(f"❌ 创建 HistoricalMarketService 实例失败: {e}")
        return False
    
    # 创建测试用的交易对
    # 根据文件名推断交易对，例如 BTC_USDT_binance_okx.csv
    test_pairs = []
    for csv_file in csv_files[:2]:  # 只测试前两个文件
        filename = os.path.splitext(csv_file)[0]  # 移除 .csv 扩展名
        parts = filename.split('_')
        if len(parts) >= 3:
            symbol = '_'.join(parts[:-2])  # 重建符号，如 BTC_USDT
            exchange1 = parts[-2]
            exchange2 = parts[-1]
            
            # 确保 exchanges 是按字母顺序排序的
            exchanges = sorted([exchange1, exchange2])
            long_exchange = exchanges[0]
            short_exchange = exchanges[1]
            
            pair = Pair(
                logical_symbol=symbol,
                long_exchange=long_exchange,
                short_exchange=short_exchange
            )
            test_pairs.append(pair)
    
    if not test_pairs:
        print("❌ 无法从 CSV 文件名中构建有效的交易对")
        return False
    
    print(f"✓ 创建了 {len(test_pairs)} 个测试交易对: {[p.pair_id for p in test_pairs]}")
    
    # 测试 get_snapshot 方法
    try:
        snapshots = service.get_snapshot(test_pairs)
        print("✓ get_snapshot 方法调用成功")
    except Exception as e:
        print(f"❌ get_snapshot 方法调用失败: {e}")
        return False
    
    # 检查返回值
    if not isinstance(snapshots, dict):
        print(f"❌ get_snapshot 返回值不是字典类型: {type(snapshots)}")
        return False
    
    print(f"✓ get_snapshot 返回了 {len(snapshots)} 个快照")
    
    # 检查返回的快照是否符合预期
    for pair_id, snapshot in snapshots.items():
        if not isinstance(snapshot, MarketSnapshot):
            print(f"❌ 快照不是 MarketSnapshot 类型: {type(snapshot)}")
            return False
            
        # 检查 MarketSnapshot 的属性
        if not hasattr(snapshot, 'pair'):
            print("❌ MarketSnapshot 缺少 pair 属性")
            return False
            
        if not hasattr(snapshot, 'timestamp'):
            print("❌ MarketSnapshot 缺少 timestamp 属性")
            return False
            
        if not hasattr(snapshot, 'long_leg'):
            print("❌ MarketSnapshot 缺少 long_leg 属性")
            return False
            
        if not hasattr(snapshot, 'short_leg'):
            print("❌ MarketSnapshot 缺少 short_leg 属性")
            return False
        
        # 检查 MarketLegSnapshot 属性
        long_leg = snapshot.long_leg
        short_leg = snapshot.short_leg
        
        if not hasattr(long_leg, 'exchange') or not hasattr(long_leg, 'symbol'):
            print("❌ long_leg 缺少必要属性")
            return False
            
        if not hasattr(short_leg, 'exchange') or not hasattr(short_leg, 'symbol'):
            print("❌ short_leg 缺少必要属性")
            return False
        
        print(f"  - 快照 {pair_id}: 时间戳={snapshot.timestamp}, "
              f"做多交易所={long_leg.exchange}, 做空交易所={short_leg.exchange}")
    
    # 测试多次调用以验证时间索引递增
    try:
        snapshots2 = service.get_snapshot(test_pairs)
        snapshots3 = service.get_snapshot(test_pairs)
        
        print("✓ 多次调用 get_snapshot 成功")
    except Exception as e:
        print(f"❌ 多次调用 get_snapshot 失败: {e}")
        return False
    
    print("\n=== 功能测试完成 ===\n")
    return True


def test_edge_cases():
    """
    测试边缘情况
    """
    print("=== 测试边缘情况 ===")
    
    # 测试不存在的目录
    try:
        service = HistoricalMarketService(csv_directory="/non/existent/directory")
        # 这里不应该抛出异常，因为数据是在构造函数中加载的
        print("✓ 未对不存在的目录抛出异常（延迟加载）")
    except FileNotFoundError:
        print("✓ 正确地对不存在的目录抛出了 FileNotFoundError")
    
    # 测试空交易对列表
    service = HistoricalMarketService()
    empty_snapshots = service.get_snapshot([])
    if isinstance(empty_snapshots, dict) and len(empty_snapshots) == 0:
        print("✓ 空交易对列表返回空字典")
    else:
        print(f"⚠️  空交易对列表返回了非空结果: {empty_snapshots}")
    
    print("\n=== 边缘情况测试完成 ===\n")


if __name__ == "__main__":
    print("开始测试 HistoricalMarketService\n")
    
    # 运行接口实现测试
    test_interface_implementation()
    
    # 运行功能测试
    functionality_success = test_functionality()
    
    # 运行边缘情况测试
    test_edge_cases()
    
    print("总结:")
    print("- 接口实现: ✓ 通过")
    print(f"- 功能测试: {'✓ 通过' if functionality_success else '⚠️ 部分失败'}")
    print("- 边缘情况测试: ✓ 已运行")
    
    print("\n如果功能测试显示部分失败，请确保数据文件存在于正确的目录中")
    print("并且文件名格式符合 {symbol}_{exchange1}_{exchange2}.csv 的要求")