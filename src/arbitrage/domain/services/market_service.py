from abc import ABC, abstractmethod
from typing import List, Dict
from arbitrage.domain.entities.pair import Pair
from arbitrage.domain.models.market_snapshot import MarketSnapshot
from arbitrage.domain.models.market_ticker_snapshot import MarketTickerSnapshot
from arbitrage.domain.entities.ohlcv_diff_result import OHLCVDiffResult

class MarketService(ABC):
    """
    市场信息服务接口：提供实时行情数据，不涉及交易执行。
    所有价格单位为 USD，时间戳为 Unix 时间（秒，含小数）。
    """

    @abstractmethod
    def fetch_tickers(self, pairs: List[Pair]) -> Dict[str, MarketTickerSnapshot]:
        """
        获取指定交易所的行情数据。
        返回 {symbol: {timestamp: timestamp, price: price}}
        """
        pass

    @abstractmethod
    def get_snapshot(self, pairs: List[Pair]) -> Dict[str, MarketSnapshot]:
        """
        获取套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
        返回 {pair_id: MarketSnapshot}
        """
        pass

    @abstractmethod
    def get_ohlcv_diff(self, market_snapshot: MarketSnapshot) -> OHLCVDiffResult:
        """
        获取市场快照的OHLCV差值统计，返回平均价差和最大价差
        """
        pass