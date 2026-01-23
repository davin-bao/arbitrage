from abc import ABC, abstractmethod
from typing import List, Dict
from ..value_objects.pair import Pair
from ..models.market_snapshot import MarketSnapshot


class MarketService(ABC):
    """
    市场信息服务接口：提供实时行情数据，不涉及交易执行。
    所有价格单位为 USD，时间戳为 Unix 时间（秒，含小数）。
    """

    @abstractmethod
    def get_snapshot(self, pairs: List[Pair]) -> Dict[str, MarketSnapshot]:
        """
        获取套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
        返回 {pair_id: MarketSnapshot}
        """
        pass