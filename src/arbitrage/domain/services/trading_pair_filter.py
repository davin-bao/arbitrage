from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from arbitrage.domain.entities.pair import Pair
from arbitrage.domain.models.market_ticker_snapshot import MarketTickerSnapshot


@dataclass
class PairQualityMetrics:
    """交易对质量指标"""
    pair: Pair
    volume_24h_usd: Decimal  # 24 小时成交量 (USD)
    bid_depth_usd: Decimal   # 买盘深度 (前 5 档总和)
    ask_depth_usd: Decimal   # 卖盘深度 (前 5 档总和)
    spread_percentage: Decimal  # 价差百分比
    
    @property
    def total_depth_usd(self) -> Decimal:
        """总深度"""
        return self.bid_depth_usd + self.ask_depth_usd


class TradingPairFilter:
    """
    交易对质量筛选器
    - 基于成交量和订单簿深度评估交易对质量
    - 在引擎启动前过滤低质量交易对
    """
    
    def __init__(
        self,
        min_volume_usd: Decimal = Decimal('1000000'),  # 最小 24h 成交量
        min_depth_usd: Decimal = Decimal('100000'),    # 最小订单簿深度
        max_spread_pct: Decimal = Decimal('0.001')     # 最大价差 (0.1%)
    ):
        self.min_volume_usd = min_volume_usd
        self.min_depth_usd = min_depth_usd
        self.max_spread_pct = max_spread_pct
    
    def calculate_metrics(
        self, 
        pair: Pair, 
        snapshot: MarketTickerSnapshot
    ) -> Optional[PairQualityMetrics]:
        """
        计算交易对质量指标
        
        Args:
            pair: 交易对信息
            snapshot: 市场快照（包含深度数据）
            
        Returns:
            PairQualityMetrics 或 None（数据不全时）
        """
        try:
            long_leg = snapshot.long_leg
            short_leg = snapshot.short_leg
            
            # 获取成交量（取两个交易所的平均值）
            long_volume = Decimal(str(long_leg.last_size)) if long_leg.last_size else Decimal('0')
            short_volume = Decimal(str(short_leg.last_size)) if short_leg.last_size else Decimal('0')
            avg_volume = (long_volume + short_volume) / 2
            
            # TODO: 如果有 24h 成交量数据，替换此处
            volume_24h = avg_volume * Decimal('100')  # 临时估算
            
            # 计算价差和深度（需要从 market_service 获取完整深度数据）
            # 此处使用 ticker 数据作为近似
            if long_leg.last_price and short_leg.last_price:
                spread = abs(long_leg.last_price - short_leg.last_price) / long_leg.last_price
            else:
                spread = Decimal('999')  # 数据缺失，设为极大值
            
            # 深度数据需要从 orderbook 获取，ticker 中不可用
            # 暂时设为 0，实际使用时需通过 market_service.get_snapshot 获取
            bid_depth = Decimal('0')
            ask_depth = Decimal('0')
            
            return PairQualityMetrics(
                pair=pair,
                volume_24h_usd=volume_24h,
                bid_depth_usd=bid_depth,
                ask_depth_usd=ask_depth,
                spread_percentage=spread
            )
        except Exception:
            return None
    
    def check_volume(self, metrics: PairQualityMetrics) -> bool:
        """检查成交量是否达标"""
        return metrics.volume_24h_usd >= self.min_volume_usd
    
    def check_depth(self, metrics: PairQualityMetrics) -> bool:
        """检查深度是否达标"""
        return metrics.total_depth_usd >= self.min_depth_usd
    
    def check_spread(self, metrics: PairQualityMetrics) -> bool:
        """检查价差是否合理"""
        return metrics.spread_percentage <= self.max_spread_pct
    
    def is_quality_pair(
        self, 
        metrics: PairQualityMetrics,
        require_volume: bool = True,
        require_depth: bool = True
    ) -> bool:
        """
        综合判断是否为高质量交易对
        
        Args:
            metrics: 质量指标
            require_volume: 是否要求成交量达标
            require_depth: 是否要求深度达标
            
        Returns:
            bool: 是否为高质量交易对
        """
        volume_ok = not require_volume or self.check_volume(metrics)
        depth_ok = not require_depth or self.check_depth(metrics)
        spread_ok = self.check_spread(metrics)
        
        return volume_ok and depth_ok and spread_ok
    
    def filter_pairs(
        self, 
        all_pairs: List[Tuple[Pair, MarketTickerSnapshot]],
        require_volume: bool = True,
        require_depth: bool = False  # 初始运行时深度数据可能不可用
    ) -> List[Pair]:
        """
        筛选高质量交易对
        
        Args:
            all_pairs: [(Pair, MarketTickerSnapshot), ...]
            require_volume: 是否要求成交量达标
            require_depth: 是否要求深度达标
            
        Returns:
            List[Pair]: 筛选后的交易对列表
        """
        quality_pairs = []
        
        for pair, snapshot in all_pairs:
            metrics = self.calculate_metrics(pair, snapshot)
            
            if metrics is None:
                continue
            
            if self.is_quality_pair(metrics, require_volume, require_depth):
                quality_pairs.append(pair)
                print(f"[✓ 筛选通过] {pair.symbol} | "
                      f"成交量：{metrics.volume_24h_usd:.2f} USD | "
                      f"价差：{metrics.spread_percentage * 100:.4f}%")
            else:
                reasons = []
                if not self.check_volume(metrics):
                    reasons.append(f"成交量不足 ({metrics.volume_24h_usd:.2f})")
                if not self.check_depth(metrics):
                    reasons.append(f"深度不足 ({metrics.total_depth_usd:.2f})")
                if not self.check_spread(metrics):
                    reasons.append(f"价差过大 ({metrics.spread_percentage * 100:.4f}%)")
                
                print(f"[筛选忽略] {pair.symbol} | 原因：{', '.join(reasons)}")
        
        return quality_pairs