请仔细阅读如下文档，并查找是否有不合理的地方，提出修改方案：
```
# 套利策略系统：大模型编码指导文档（2026年1月版）

> **用途**：供大模型在辅助开发本项目时参考。包含完整架构、接口定义、核心逻辑与防御机制，确保生成代码符合工程规范。

---

## 一、项目目录结构

采用清晰分层架构，遵循 Python 工程最佳实践：

```text
arbitrage_system/
├── main.py                     # 程序入口（启动引擎）
├── streamlit_app.py            # 监控面板（独立进程）
├── data/                       # 运行时数据目录（由引擎写入）
│   ├── pnl_history.jsonl       # 追加式盈亏历史（JSONL格式）
│   └── engine_snapshot.json    # 原子更新的最新状态快照
├── src/
│   ├── domain/                 # 领域层（核心业务概念）
│   │   ├── entities/           # 实体
│   │   │   ├── hedge_position.py
│   │   │   ├── trade_leg.py
│   │   │   └── account_summary.py
│   │   ├── value_objects/      # 值对象
│   │   │   ├── enums.py
│   │   │   └── pair.py
│   │   ├── models/             # 数据模型（用于序列化）
│   │   │   ├── market_snapshot.py
│   │   │   └── strategy_snapshot.py
│   │   └── services/           # 领域服务接口
│   │       ├── account_service.py
│   │       ├── market_service.py
│   │       ├── execution_service.py
│   │       ├── storage_service.py
│   │       └── strategy.py
│   ├── application/            # 应用层
│   │   └── services/
│   │       └── arbitrage_engine.py
│   ├── infrastructure/         # 基础设施层
│   │   ├── implementations/    # 抽象实现
│   │   │   ├── ccxt_execution_service.py
│   │   │   ├── ccxt_market_service.py
│   │   │   ├── ccxt_account_service.py
│   │   │   ├── simulated_execution_service.py
│   │   │   ├── simulated_market_service.py
│   │   │   ├── simulated_account_service.py
│   │   │   ├── file_storage_service.py
│   │   │   └── sqlite_storage_service.py
│   └── main/
│       └── bootstrap.py        # 依赖注入与初始化
└── requirements.txt
```

---

## 二、分层说明

| 层级 | 职责 | 关键约束 |
|------|------|----------|
| **Domain（领域层）** | 定义核心业务概念、实体、值对象、接口 | 无外部依赖，纯 Python |
| **Application（应用层）** | 编排业务流程（如 `ArbitrageEngine`） | 仅依赖 Domain 接口 |
| **Infrastructure（基础设施层）** | 实现 Domain 接口（如 CCXT 执行） | 可依赖第三方库（ccxt, pandas） |
| **Main（入口层）** | 组装各层，启动应用 | 包含配置、依赖注入 |

> ✅ **依赖方向**：Main → Application → Domain ← Infrastructure

---

## 三、核心接口定义

### 3.1 `AccountService`（领域服务接口）

```python
# src/domain/services/account_service.py
from abc import ABC, abstractmethod
from decimal import Decimal

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
        但至少能知道“是否有仓”、“数量”、“方向”。
        """
        pass

    @abstractmethod
    def get_open_orders(self, exchange_name: str, symbol: str) -> List[ExchangeOrder]:
        """
        返回指定交易所、交易对的当前挂单列表。
        ExchangeOrder 至少包含: id, symbol, side, amount, price, status
        """
        pass

    @abstractmethod
    def is_dry_run(self) -> bool:
        """是否为模拟模式"""
        pass
```

### 3.2 `MarketService`（领域服务接口）

```python
# src/domain/services/market_service.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional
from ..entities.hedge_position import HedgePosition
from ..value_objects.pair import Pair
from ..models.market_snapshot import MarketSnapshot

class MarketService(ABC):
    """
    市场信息服务接口：提供实时行情数据，不涉及交易执行。
    所有价格单位为 USD，时间戳为 Unix 时间（秒，含小数）。
    """

    @abstractmethod
    def get_snapshot(self, pairs: List[Pair]) -> dict[str, MarketSnapshot]:
        """
        获取套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
        返回 {pair_id: MarketSnapshot}
        """
        pass
```

### 3.3 `StorageService`（领域服务接口）

```python
# src/domain/services/storage_service.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from decimal import Decimal
from ..models.strategy_snapshot import StrategySnapshot
from ..models.market_snapshot import MarketSnapshot

class StrategyStateStorage(ABC):
    # ===== 策略状态存储（用于 Streamlit） =====
    @abstractmethod
    def append_strategy_snapshot(self, snapshot: StrategySnapshot) -> None:
        """追加策略执行快照（账户+持仓+盈亏）"""
        pass

    @abstractmethod
    def load_latest_strategy_snapshot(self) -> Optional[StrategySnapshot]:
        """加载最新策略快照（实时监控）"""
        pass

    @abstractmethod
    def load_strategy_history(self, limit: int = 1000) -> List[StrategySnapshot]:
        """加载策略历史快照（绘制收益曲线）"""
        pass

class MarketDataStorage(ABC):
    # ===== 市场数据存储（用于回测） =====
    @abstractmethod
    def save_market_data(self, pair_id: str, data_points: List[MarketSnapshot]) -> None:
        """保存原始行情数据（回测用）"""
        pass

    @abstractmethod
    def load_market_data(self, pair_id: str, start_time: float, end_time: float) -> List[MarketSnapshot]:
        """加载指定时间段的行情数据（回测引擎调用）"""
        pass

    @abstractmethod
    def clear_all(self) -> None:
        """清空所有数据（回测前重置）"""
        pass
```

### 3.4 `ExecutionService`（领域服务接口）

```python
# src/domain/services/execution_service.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional
from ..entities.hedge_position import HedgePosition
from ..value_objects.pair import Pair

class ExecutionService(ABC):
    @abstractmethod
    def open_position(
        self,
        intent: OpenIntent,
        market: MarketSnapshot
    ) -> ExecutionResult:
        pass

    @abstractmethod
    def close_position(
        self,
        position: HedgePosition,
        market: MarketSnapshot
    ) -> ExecutionResult:
        pass
```

### 3.5 `TimeService`（接口）

```python
# src/domain/services/time_service.py
from abc import ABC, abstractmethod

class TimeService(ABC):
    @abstractmethod
    def now(self) -> float:
        """返回当前时间（Unix 秒，含小数）"""
        pass
```

### 3.6 `IStrategy`（策略接口）

```python
# src/domain/services/strategy.py
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Tuple, Optional
from ..value_objects.pair import Pair
from ..models.market_snapshot import MarketSnapshot

class IStrategy(ABC):
    
    @abstractmethod
    def select_pairs(self, universe: List[Pair]) -> List[Pair]:
        """
        策略启动时调用（或低频周期调用）。
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
```

---

## 四、核心业务逻辑

### 4.1 `HedgePosition` 实体

```python
# src/domain/entities/hedge_position.py
import time

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from .trade_leg import TradeLeg
from ..value_objects.pair import Pair

@dataclass
class HedgePosition:
    id: str
    pair: Pair
    long_leg: TradeLeg
    short_leg: TradeLeg
    open_timestamp: float = field(default_factory=lambda: time.time())
```

---

### 4.2 `TradeLeg` 值对象

```python
# src/domain/entities/trade_leg.py
from dataclasses import dataclass
from decimal import Decimal
from ..value_objects.enums import OrderType, TradeSide

@dataclass(frozen=True)
class TradeLeg:
    exchange: str
    symbol: str
    side: TradeSide
    amount: Decimal
    price: Decimal
    fee: Decimal            # 手续费（USD）
    slippage_loss: Decimal  # 滑点损失（USD）
    order_type: OrderType         # 'limit', 'market', 'emergency_market'
    timestamp: float
```

### 4.3 `MarketSnapshot` 值对象

```python
@dataclass(frozen=True)
class MarketLegSnapshot:
    """
    单腿（单交易所）的市场快照。
    """
    exchange: str
    symbol: str
    
    # 最新成交
    last_price: Optional[Decimal] = None
    last_size: Optional[Decimal] = None
    last_timestamp: Optional[float] = None

    # 订单簿顶部（Top of Book）
    best_bid_price: Optional[Decimal] = None
    best_bid_size: Optional[Decimal] = None
    best_ask_price: Optional[Decimal] = None
    best_ask_size: Optional[Decimal] = None

    # 深度快照（可选，用于滑点模拟）
    orderbook_bids: List[List[Decimal]] = field(default_factory=list)  # [[price, size], ...]
    orderbook_asks: List[List[Decimal]] = field(default_factory=list)  # [[price, size], ...]

@dataclass(frozen=True)
class MarketSnapshot:
    """
    套利交易对的完整市场快照（包含 Long 腿和 Short 腿）。
    """
    pair: Pair
    timestamp: float  # Unix 时间戳（秒，含小数）

    long_leg: MarketLegSnapshot   # 做多腿（如 Binance BTC/USDT）
    short_leg: MarketLegSnapshot  # 做空腿（如 Bybit BTC/USDT）

```

### 4.4 `Pair` 值对象

```python
# src/domain/value_objects/pair.py
@dataclass(frozen=True)
class Pair:
    logical_symbol: str
    long_exchange: str
    short_exchange: str

    @property
    def pair_id(self) -> str:
        return f"{self.logical_symbol}_{self.long_exchange}_{self.short_exchange}"
```

### 4.5 `Enum` 对象

```python
# src/domain/value_objects/enums.py
class TradeSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    EMERGENCY = "emergency_market"
```


### 4.6 `ExecutionResult` 值对象

```python
# src/domain/value_objects/execution_result.py
@dataclass
class ExecutionResult:
    success: bool
    position: Optional[HedgePosition]

    state: Literal[
        "OPENED",
        "PARTIAL",
        "FAILED",
        "EMERGENCY_CLOSED"
    ]

    error: Optional[str]
```

### 4.6 `OpenIntent` 值对象

```python
@dataclass(frozen=True)
class OpenIntent:
    pair: Pair
    notional_usd: Decimal

    entry_type: Literal["limit", "market"]
    max_slippage: Decimal

    reason: str  # 用于日志 / 分析
```

## 五、`ArbitrageEngine` 业务逻辑

```python
# src/application/services/arbitrage_engine.py
class ArbitrageEngine:
    def __init__(
        self,
        strategy: IStrategy,
        market_service: MarketService,
        account_service: AccountService,
        execution_service: ExecutionService,
        logger: Optional[ILogger] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.strategy = strategy
        self.market_service = market_service
        self.account_service = account_service
        self.execution_service = execution_service
        self.logger = logger or NullLogger()
        self.config = config or {}
        self.candidate_pairs = self.strategy.select_pairs()  # ← 启动时一次性获取
        self.active_positions = {}  # 主状态源
        self.last_sync_time = 0

    def run_single_cycle(self):
        # 【可选】低频同步：每 N 分钟校验一次真实持仓
        if time.time() - self.last_sync_time > 300:  # 5分钟
            self._sync_positions_with_exchange()
            self.last_sync_time = time.time()

        # 1. 获取市场快照
        snapshot = self.market_service.get_snapshot(self.candidate_pairs)
        
        # 2. 检查现有仓位是否需要平仓
        to_close = []
        for pos in self.active_positions.values():
            current_spread = self._get_current_spread(pos.pair, snapshot)
            if self.strategy.should_close_position(pos, current_spread):
                if self.execution_service.close_position(pos):
                    to_close.append(pos.id)

        # 3. 清理已平仓位
        for pid in to_close:
            del self.active_positions[pid]

        # 开仓逻辑：遍历候选对
        for pair in self.candidate_pairs[:self.config['max_new_positions']]:
            if len(self.active_positions) >= self.config['max_total_positions']:
                break
            
            # 实时决策：是否开仓（含冷却期、风控等）
            should_open, long_price, short_price = self.strategy.should_open_position(pair, snapshot)
            
            if should_open:
                position = self.execution_service.place_hedge_order(...)
                if position:
                    self.active_positions[position.id] = position

    def _sync_positions_with_exchange(self):
        """
        1. 调用 AccountService.get_real_positions() 获取真实持仓
        2. 对比内存 active_positions
        3. 处理差异：
        - 内存有但交易所无 → 视为已平仓，记录异常日志
        - 交易所有但内存无 → 视为“孤儿仓位”，尝试接管或报警
        """
        real_positions = self.account_service.get_real_positions()  # 新增接口
        
        memory_ids = set(self.active_positions.keys())
        real_ids = {pos.id for pos in real_positions}

        # 情况1：内存有，交易所无 → 已被外部平仓
        for pid in memory_ids - real_ids:
            logger.warning(f"Position {pid} closed externally!")
            del self.active_positions[pid]

        # 情况2：交易所有，内存无 → 孤儿仓位（危险！）
        for pid in real_ids - memory_ids:
            orphan = next(p for p in real_positions if p.id == pid)
            logger.fatal(f"Orphan position detected! {orphan}. Manual intervention required.")
            # 可选：自动接管（需谨慎）
            # self.active_positions[pid] = orphan
```

---

## 六、原子开仓防御措施（关键！）

### 实现位置：`ExecutionService`

```python
# src/infrastructure/execution/ccxt_execution_service.py
def place_hedge_order(self, pair, long_price, short_price, notional_usd):
    # ... [发送限价单] ...
    
    # 轮询订单状态
    time.sleep(2)
    long_status = self._fetch_order_status(self.long_ccxt, long_order_id)
    short_status = self._fetch_order_status(self.short_ccxt, short_order_id)
    
    # 单边成交处理
    if long_filled > 0 and short_filled == 0:
        self._emergency_market_close(self.long_ccxt, pair, long_filled, 'sell')
        return None  # 未建立有效对冲
    elif short_filled > 0 and long_filled == 0:
        self._emergency_market_close(self.short_ccxt, pair, short_filled, 'buy')
        return None
    elif long_filled > 0 and short_filled > 0:
        return HedgePosition(...)  # 正常创建
    else:
        return None

def _emergency_market_close(self, exchange, pair, amount, side):
    """紧急市价平仓（核心防御）"""
    try:
        order = exchange.create_market_order(pair.symbol, side, float(amount))
        # 记录滑点和手续费
        avg_price = Decimal(str(order['average']))
        fee = self._extract_fee(order)
        ideal_price = self._get_ideal_price(pair, side)  # 从最新行情获取
        slippage = abs(avg_price - ideal_price) * amount
        # 创建 TradeLeg 并关联（在 HedgePosition 中记录）
        return TradeLeg(..., fee=fee, slippage_loss=slippage, order_type='emergency_market')
    except Exception as e:
        logger.fatal("Emergency close failed! Manual intervention required!")
        raise
```

> ✅ **原则**：宁可放弃机会，不可暴露单边风险。

---

## 七、策略评估参数计算

最终评估指标在 `AccountSummary` 中计算：

```python
# src/domain/entities/account_summary.py
@dataclass(frozen=True)
class AccountSummary:
    total_balance: Decimal
    available_balance: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal          # 含紧急平仓损失
    total_positions: int
    emergency_close_count: int
    is_dry_run: bool
    
    @property
    def total_pnl(self) -> Decimal:
        return self.unrealized_pnl + self.realized_pnl
    
    @property
    def sharpe_ratio(self) -> float:
        # 从 pnl_history 计算（需传入历史数据）
        pass
    
    @property
    def max_drawdown(self) -> float:
        # 从 pnl_history 计算
        pass
```

> 📊 **关键**：`realized_pnl` 必须包含紧急平仓的额外成本。

---

## 八、Streamlit 监控面板实现

### 8.1 数据文件格式

- **`pnl_history.jsonl`**（追加写入）：
  ```json
  {"timestamp": 1705723200.123, "total_pnl": 250.30}
  {"timestamp": 1705723205.456, "total_pnl": 251.10}
  ```

- **`engine_snapshot.json`**（原子更新）：
  ```json
  {
    "timestamp": 1705723205.456,
    "mode": "dry_run",
    "total_balance": 10250.30,
    "total_pnl": 250.30,
    "positions": [
      {
        "pair_id": "BTC-USDT.BINANCE-BYBIT",
        "current_pnl": 120.50,
        "amount": 0.1
      }
    ]
  }
  ```

### 8.2 Streamlit 读取逻辑

```python
# streamlit_app.py
import json
import pandas as pd
from pathlib import Path

SNAPSHOT_FILE = Path("data/engine_snapshot.json")
HISTORY_FILE = Path("data/pnl_history.jsonl")

def load_pnl_history():
    records = []
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    return pd.DataFrame(records[-1000:])  # 最近1000条

def load_snapshot():
    if SNAPSHOT_FILE.exists():
        try:
            with open(SNAPSHOT_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None  # 文件正在更新，跳过本次
    return None

# 在 Streamlit 主循环中
snapshot = load_snapshot()
history_df = load_pnl_history()

if snapshot:
    # 显示账户指标
    st.metric("总盈亏", f"${snapshot['total_pnl']:,.2f}")
    
if not history_df.empty:
    # 绘制盈亏曲线
    history_df['time'] = pd.to_datetime(history_df['timestamp'], unit='s')
    st.line_chart(history_df.set_index('time')['total_pnl'])

if snapshot and snapshot.get('positions'):
    # 显示持仓列表
    st.dataframe(pd.DataFrame(snapshot['positions']))
```

> ✅ **安全机制**：
> - 快照读取失败时跳过（不崩溃）
> - 历史文件按行解析，损坏行自动跳过

---

## 九、启动方式（独立进程）

### 启动主引擎
```bash
python main.py
```

### 启动监控面板
```bash
streamlit run streamlit_app.py --server.port=8501
```

> 🔓 **优势**：完全解耦，可独立重启任一进程。

---

## 十、关键设计总结

| 模块 | 设计要点 |
|------|--------|
| **原子开仓** | 限价开仓 + 轮询 + 单边失败市价紧急平仓 |
| **盈亏核算** | `TradeLeg` 记录滑点+手续费，`HedgePosition` 扣除损失 |
| **数据同步** | 快照文件（原子更新） + 历史日志（追加写入） |
| **架构分层** | Domain 定义接口，Infrastructure 实现，Application 编排 |
| **策略接口** | 三方法：`select_pairs`, `should_open_position`, `should_close_position` |

此文档为大模型提供完整上下文，确保生成的代码符合项目架构、防御要求与工程规范。
```