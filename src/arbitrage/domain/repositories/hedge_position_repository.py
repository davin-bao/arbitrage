from abc import ABC, abstractmethod

from typing import List, Optional

from arbitrage.domain.entities.hedge_position import HedgePosition


class HedgePositionRepository(ABC):
    @abstractmethod
    def save(self, position: HedgePosition) -> bool:
        """保存持仓信息"""
        pass

    @abstractmethod
    def update(self, position: HedgePosition) -> bool:
        """更新持仓信息"""
        pass

    @abstractmethod
    def get_all_positions(self) -> List[HedgePosition]:
        """获取所有持仓信息"""
        pass

    @abstractmethod
    def get_position_by_id(self, position_id: str) -> Optional[HedgePosition]:
        """根据ID获取持仓信息"""
        pass
    
    @abstractmethod
    def get_open_positions(self) -> List[HedgePosition]:
        """获取所有持仓信息"""
        pass

    @abstractmethod
    def _row_to_entity(self, row) -> Optional[HedgePosition]:
        """将数据库行转换为HedgePosition实体"""
        pass