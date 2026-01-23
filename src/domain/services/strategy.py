from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from decimal import Decimal
from dataclasses import dataclass
from ..value_objects.pair import Pair
from ..models.open_intent import OpenIntent
from ..entities.hedge_position import HedgePosition
from ..entities.contexts import StrategyContext, PositionContext


class IStrategy(ABC):
    """
    交易策略接口，定义了所有交易策略必须实现的方法
    """
    
    @abstractmethod
    def select_pairs(self, universe: List[Pair]) -> List[Pair]:
        """
        策略启动时调用（或低频调用）。
        基于配置、静态市场元数据（如交易对是否上线、是否在维护）等，
        返回所有**可能参与套利**的候选交易对列表（按优先级排序）。
        
        注意：不依赖实时行情（如价格、订单簿），避免高频拉取。
        """
        pass

    @abstractmethod
    def should_open_position(self, ctx: StrategyContext) -> Optional[OpenIntent]:
        """
        高频调用。基于实时行情判断是否开仓。
        可在此实现：
          - 价差不足 → 跳过
          - 近期频繁失败 → 冷却期
          - 波动率过低 → 暂停
          - 风控熔断 → 拒绝
        """
        pass

    @abstractmethod
    def should_close_position(self, ctx: PositionContext) -> bool:
        """
        判断是否平仓。
        """
        pass