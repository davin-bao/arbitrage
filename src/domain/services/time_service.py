from abc import ABC, abstractmethod


class TimeService(ABC):
    @abstractmethod
    def now(self) -> float:
        """返回当前时间（Unix 秒，含小数）"""
        pass