from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List
from arbitrage.domain.entities.hedge_position import HedgePosition


class AccountService(ABC):
    
    @abstractmethod
    def get_total_balance(self) -> Decimal:
        """获取总资产（USD）"""
        pass

    @abstractmethod
    def get_available_balance(self) -> Decimal:
        """获取可用余额（USD）"""
        pass
    
    @abstractmethod
    def get_real_positions(self) -> List[HedgePosition]:
        """
        从交易所获取当前真实的对冲持仓列表。
        注意：可能无法还原完整的 TradeLeg（如滑点、历史价格），
        但至少能知道"是否有仓"、"数量"、"方向"。
        """
        pass

    @abstractmethod
    def add_position(self, position: HedgePosition):
        """
        添加对冲持仓
        """
        pass

    @abstractmethod
    def remove_position(self, position):
        """
        删除对冲持仓
        支持通过HedgePosition对象或position ID删除
        """
        pass

    @abstractmethod
    def get_account_snapshot(self):
        """
        获取账户快照，包含余额、持仓、订单等信息
        """
        pass
