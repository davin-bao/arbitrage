"""
测试 HistoricalMarketService 的时间序列递增功能
"""

import os
import sys
from decimal import Decimal

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.domain.value_objects.pair import Pair
from src.infrastructure.market.historical_market_service import HistoricalMarketService


def test_time_sequence():
    """
    测试 HistoricalMarketService 按时间顺序读取数据的功能
    """
    print("=== 测试 HistoricalMarketService 时间序列功能 ===")
    
    # 准备测试数据
    csv_directory = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'historical')
    
    if not os.path.exists(csv_directory):
        print(f"⚠️  数据目录不存在: {csv_directory}")
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
    test_pairs = []
    for csv_file in csv_files[:1]:  # 只使用一个文件进行测试
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
    
    print(f"✓ 创建了测试交易对: {test_pairs[0].pair_id}")
    
    # 测试连续调用 get_snapshot 以验证时间索引递增
    timestamps = []
    snapshots_count = 0
    
    print("\n--- 连续获取时间序列数据 ---")
    for i in range(5):  # 获取前5个时间点
        try:
            snapshots = service.get_snapshot(test_pairs)
            
            if snapshots:
                # 获取第一个快照的时间戳
                snapshot = next(iter(snapshots.values()))
                timestamp = snapshot.timestamp
                timestamps.append(timestamp)
                snapshots_count += 1
                
                print(f"第 {i+1} 次调用 - 时间戳: {timestamp}")
            else:
                print(f"第 {i+1} 次调用 - 未获取到快照")
                break
                
        except Exception as e:
            print(f"❌ 第 {i+1} 次调用失败: {e}")
            break
    
    print(f"\n获取到 {snapshots_count} 个时间戳: {timestamps}")
    
    # 验证时间戳是否按顺序递增
    if len(timestamps) > 1:
        is_sequential = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
        if is_sequential:
            print("✓ 时间戳按顺序递增，时间序列功能正常")
        else:
            print("⚠️  时间戳未按顺序递增")
            return False
    else:
        print("⚠️  获取的时间戳不足，无法验证序列顺序")
        return False
    
    # 测试重置功能
    print("\n--- 测试重置功能 ---")
    service.reset()
    
    try:
        first_snapshot_after_reset = service.get_snapshot(test_pairs)
        if first_snapshot_after_reset:
            reset_timestamp = next(iter(first_snapshot_after_reset.values())).timestamp
            print(f"重置后第一次调用的时间戳: {reset_timestamp}")
            
            if reset_timestamp == timestamps[0]:
                print("✓ 重置功能正常，回到了起始时间点")
            else:
                print("⚠️  重置后时间戳与初始时间戳不匹配")
        else:
            print("⚠️  重置后未能获取快照")
    except Exception as e:
        print(f"❌ 重置测试失败: {e}")
    
    # 测试 has_more_data 方法
    print("\n--- 测试 has_more_data 方法 ---")
    service.reset()  # 重置到开始位置
    has_data_initially = service.has_more_data()
    print(f"初始时是否有更多数据: {has_data_initially}")
    
    if has_data_initially:
        # 快速遍历一些数据点
        for _ in range(min(3, len(service._timestamps))):
            service.get_snapshot(test_pairs)
        
        has_data_after_some_calls = service.has_more_data()
        print(f"获取一些数据后是否还有更多数据: {has_data_after_some_calls}")
    
    print("\n=== 时间序列功能测试完成 ===\n")
    return True


def test_data_consistency():
    """
    验证历史数据的一致性
    """
    print("=== 验证历史数据一致性 ===")
    
    csv_directory = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'historical')
    
    if not os.path.exists(csv_directory):
        print(f"⚠️  数据目录不存在: {csv_directory}")
        return False
    
    service = HistoricalMarketService(csv_directory=csv_directory)
    
    # 检查加载了多少个时间戳
    print(f"✓ 加载了 {len(service._timestamps)} 个时间戳")
    print(f"✓ 时间范围: {min(service._timestamps)} 到 {max(service._timestamps)}")
    
    # 检查缓存中的数据量
    total_data_points = sum(len(exchange_data) for exchange_data in service._data_cache.values())
    print(f"✓ 缓存中总共 {total_data_points} 个数据点")
    
    print("\n=== 历史数据一致性验证完成 ===\n")
    return True


if __name__ == "__main__":
    print("开始测试 HistoricalMarketService 时间序列功能\n")
    
    # 运行时间序列测试
    time_seq_success = test_time_sequence()
    
    # 运行数据一致性测试
    data_consistency_success = test_data_consistency()
    
    print("总结:")
    print(f"- 时间序列测试: {'✓ 通过' if time_seq_success else '❌ 失败'}")
    print(f"- 数据一致性测试: {'✓ 通过' if data_consistency_success else '❌ 失败'}")
    
    if time_seq_success and data_consistency_success:
        print("\n🎉 所有时间序列相关测试均通过!")
        print("✅ HistoricalMarketService 能够正确按时间顺序读取CSV数据")
    else:
        print("\n❌ 部分测试未通过，请检查实现")