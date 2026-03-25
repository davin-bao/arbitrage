import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class ContractInfo:
    contract_size: float
    min_qty: float
    leverage_max: Optional[float]


@dataclass
class Pair:
    symbol: str
    base: str
    quote: str
    long_exchange: str
    short_exchange: str
    contracts: Dict[str, ContractInfo]
    locked_timestamp: float = field(default_factory=lambda: time.time() - 300)

    @property
    def pair_id(self) -> str:
        return f"{self.symbol}_{self.base}_{self.quote}"
    
    @classmethod
    def from_dict(cls, pair_dict: Dict) -> 'Pair':
        """
        根据字典结构创建 Pair 对象
        输入字典格式如:
        {
            "symbol": "TRUST/USDT:USDT",
            "base": "TRUST",
            "quote": "USDT",
            "long_exchange": "binance",
            "short_exchange": "okx",
            "contracts": {
              "binance": {
                "contract_size": 1.0,
                "min_qty": 1.0,
                "leverage_max": null
              },
              "okx": {
                "contract_size": 10.0,
                "min_qty": 1.0,
                "leverage_max": null
              }
            }
        }
        """
        # 转换 contracts 字典
        contracts = {}
        if 'contracts' in pair_dict and pair_dict['contracts']:
            for exchange_id, contract_data in pair_dict['contracts'].items():
                contract_info = ContractInfo(
                    contract_size=contract_data.get('contract_size', 1.0),
                    min_qty=contract_data.get('min_qty', 0.001),
                    leverage_max=contract_data.get('leverage_max')
                )
                contracts[exchange_id] = contract_info

        # 创建 Pair 对象
        return cls(
            symbol=pair_dict['symbol'],
            base=pair_dict['base'],
            quote=pair_dict['quote'],
            long_exchange=pair_dict['long_exchange'],
            short_exchange=pair_dict['short_exchange'],
            contracts=contracts
        )