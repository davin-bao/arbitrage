from src.domain.services.account_service import AccountService
from decimal import Decimal
from typing import List
from src.domain.entities.hedge_position import HedgePosition

class SimulatedAccountService(AccountService):
    """
    模拟账户服务，用于回测和模拟运行
    """
    def __init__(self, initial_balance: Decimal = Decimal('10000')):
        self._total_balance = initial_balance
        self._available_balance = initial_balance
        self._positions: List[HedgePosition] = []
        self._initial_balance = initial_balance

    def get_total_balance(self) -> Decimal:
        """获取总资产（USD）"""
        return self._total_balance

    def get_available_balance(self) -> Decimal:
        """获取可用余额（USD）"""
        return self._available_balance

    def get_real_positions(self) -> List[HedgePosition]:
        """
        获取当前模拟的对冲持仓列表
        """
        return self._positions.copy()

    def get_account_snapshot(self):
        """
        获取账户快照，包含余额、持仓等信息
        """
        return {
            'total_balance': self.get_total_balance(),
            'available_balance': self.get_available_balance(),
            'positions': self.get_real_positions(),
            'initial_balance': self._initial_balance
        }

    def update_balance(self, amount: Decimal):
        """
        更新账户余额（例如，根据盈亏调整）
        """
        self._total_balance += amount
        self._available_balance += amount