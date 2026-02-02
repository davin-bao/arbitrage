from ...domain.services.time_service import TimeService


class BacktestTimeService(TimeService):
    """
    回测时间服务，用于回测场景
    在回测中，时间由市场数据驱动，而不是真实时间
    """
    def __init__(self, initial_time: float = None):
        # 如果没有提供初始时间，则使用0作为起始时间
        self._current_time = initial_time or 0.0

    def now(self) -> float:
        """
        返回当前模拟时间（Unix 秒，含小数）
        在回测中，这个时间由市场数据决定，而不是真实时间
        """
        return self._current_time

    def set_time(self, timestamp: float):
        """
        设置当前模拟时间，主要用于回测过程中更新时间
        """
        self._current_time = timestamp