import time
from arbitrage.domain.services.time_service import TimeService


class RealTimeService(TimeService):
    """
    实时时间服务实现，返回当前系统时间
    """
    
    def now(self) -> float:
        """
        返回当前系统时间（Unix 秒，含小数）
        
        Returns:
            float: 当前Unix时间戳，包含毫秒精度
        """
        return time.time()