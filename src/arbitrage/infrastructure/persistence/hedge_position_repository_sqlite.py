import sqlite3
from typing import List, Optional
import json

from arbitrage.domain.entities.hedge_position import HedgePosition
from arbitrage.domain.repositories.hedge_position_repository import HedgePositionRepository
from arbitrage.infrastructure.persistence.sqlite_connection import SqliteConnection


class HedgePositionRepositorySqlite(HedgePositionRepository):
    def __init__(self, conn: SqliteConnection):
        self.conn = conn.get_connection()
        self.init_table()

    def init_table(self):
        """初始化持仓表"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hedge_position (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                base TEXT NOT NULL,
                quote TEXT NOT NULL,
                long_exchange TEXT NOT NULL,
                short_exchange TEXT NOT NULL,
                contracts TEXT,
                state TEXT NOT NULL,
                quantity DECIMAL NOT NULL,
                notional_usd DECIMAL NOT NULL,
                entry_price_long DECIMAL,
                entry_price_short DECIMAL,
                current_price_long DECIMAL,
                current_price_short DECIMAL,
                pnl_unrealized DECIMAL,
                pnl_realized DECIMAL,
                fees DECIMAL,
                open_time INTEGER,
                close_time INTEGER,
                close_reason TEXT,
                long_leg_exchange TEXT,
                long_leg_symbol TEXT,
                long_leg_side TEXT,
                long_leg_amount DECIMAL,
                long_leg_price DECIMAL,
                long_leg_fee DECIMAL,
                long_leg_slippage_loss DECIMAL,
                long_leg_order_type TEXT,
                long_leg_timestamp REAL,
                short_leg_exchange TEXT,
                short_leg_symbol TEXT,
                short_leg_side TEXT,
                short_leg_amount DECIMAL,
                short_leg_price DECIMAL,
                short_leg_fee DECIMAL,
                short_leg_slippage_loss DECIMAL,
                short_leg_order_type TEXT,
                short_leg_timestamp REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save(self, position: HedgePosition) -> bool:
        """保存持仓到数据库"""
        try:
            cursor = self.conn.cursor()
            
            # 将contracts转换为JSON字符串
            contracts_json = json.dumps({
                ex: {
                    'contract_size': float(info.contract_size),
                    'min_qty': float(info.min_qty),
                    'leverage_max': float(info.leverage_max) if info.leverage_max else None
                } 
                for ex, info in position.pair.contracts.items()
            })
            
            cursor.execute("""
                INSERT INTO hedge_position (
                    id, symbol, base, quote, long_exchange, short_exchange, 
                    contracts, state, quantity, notional_usd, 
                    entry_price_long, entry_price_short,
                    current_price_long, current_price_short,
                    pnl_unrealized, pnl_realized, fees,
                    open_time, close_time, close_reason,
                    long_leg_exchange, long_leg_symbol, long_leg_side, 
                    long_leg_amount, long_leg_price, long_leg_fee, 
                    long_leg_slippage_loss, long_leg_order_type, long_leg_timestamp,
                    short_leg_exchange, short_leg_symbol, short_leg_side, 
                    short_leg_amount, short_leg_price, short_leg_fee, 
                    short_leg_slippage_loss, short_leg_order_type, short_leg_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.id,
                position.pair.symbol,
                position.pair.base,
                position.pair.quote,
                position.pair.long_exchange,
                position.pair.short_exchange,
                contracts_json,
                position.state.value,
                float(position.quantity) if position.quantity else 0,
                float(position.notional_usd) if position.notional_usd else 0,
                float(position.entry_price_long) if position.entry_price_long else None,
                float(position.entry_price_short) if position.entry_price_short else None,
                float(position.current_price_long) if position.current_price_long else None,
                float(position.current_price_short) if position.current_price_short else None,
                float(position.pnl_unrealized) if position.pnl_unrealized else 0,
                float(position.pnl_realized) if position.pnl_realized else 0,
                float(position.fees) if position.fees else 0,
                int(position.open_timestamp),
                position.close_timestamp,
                position.close_reason,
                
                # Long leg data
                position.long_leg.exchange,
                position.long_leg.symbol,
                position.long_leg.side.value,
                float(position.long_leg.amount),
                float(position.long_leg.price),
                float(position.long_leg.fee),
                float(position.long_leg.slippage_loss),
                position.long_leg.order_type.value,
                position.long_leg.timestamp,
                
                # Short leg data
                position.short_leg.exchange,
                position.short_leg.symbol,
                position.short_leg.side.value,
                float(position.short_leg.amount),
                float(position.short_leg.price),
                float(position.short_leg.fee),
                float(position.short_leg.slippage_loss),
                position.short_leg.order_type.value,
                position.short_leg.timestamp
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving position: {e}")
            return False

    def update(self, position: HedgePosition) -> bool:
        """更新持仓信息"""
        try:
            cursor = self.conn.cursor()
            
            # 将contracts转换为JSON字符串
            contracts_json = json.dumps({
                ex: {
                    'contract_size': float(info.contract_size),
                    'min_qty': float(info.min_qty),
                    'leverage_max': float(info.leverage_max) if info.leverage_max else None
                } 
                for ex, info in position.pair.contracts.items()
            })

            cursor.execute("""
                UPDATE hedge_position SET
                    symbol = ?,
                    base = ?,
                    quote = ?,
                    long_exchange = ?,
                    short_exchange = ?,
                    contracts = ?,
                    state = ?,
                    quantity = ?,
                    notional_usd = ?,
                    entry_price_long = ?,
                    entry_price_short = ?,
                    current_price_long = ?,
                    current_price_short = ?,
                    pnl_unrealized = ?,
                    pnl_realized = ?,
                    fees = ?,
                    open_time = ?,
                    close_time = ?,
                    close_reason = ?,
                    long_leg_exchange = ?,
                    long_leg_symbol = ?,
                    long_leg_side = ?,
                    long_leg_amount = ?,
                    long_leg_price = ?,
                    long_leg_fee = ?,
                    long_leg_slippage_loss = ?,
                    long_leg_order_type = ?,
                    long_leg_timestamp = ?,
                    short_leg_exchange = ?,
                    short_leg_symbol = ?,
                    short_leg_side = ?,
                    short_leg_amount = ?,
                    short_leg_price = ?,
                    short_leg_fee = ?,
                    short_leg_slippage_loss = ?,
                    short_leg_order_type = ?,
                    short_leg_timestamp = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                position.pair.symbol,
                position.pair.base,
                position.pair.quote,
                position.pair.long_exchange,
                position.pair.short_exchange,
                contracts_json,
                position.state.value,
                float(position.quantity) if position.quantity else 0,
                float(position.notional_usd) if position.notional_usd else 0,
                float(position.entry_price_long) if position.entry_price_long else None,
                float(position.entry_price_short) if position.entry_price_short else None,
                float(position.current_price_long) if position.current_price_long else None,
                float(position.current_price_short) if position.current_price_short else None,
                float(position.pnl_unrealized) if position.pnl_unrealized else 0,
                float(position.pnl_realized) if position.pnl_realized else 0,
                float(position.fees) if position.fees else 0,
                int(position.open_timestamp),
                position.close_timestamp,
                position.close_reason,
                
                # Long leg data
                position.long_leg.exchange,
                position.long_leg.symbol,
                position.long_leg.side.value,
                float(position.long_leg.amount),
                float(position.long_leg.price),
                float(position.long_leg.fee),
                float(position.long_leg.slippage_loss),
                position.long_leg.order_type.value,
                position.long_leg.timestamp,
                
                # Short leg data
                position.short_leg.exchange,
                position.short_leg.symbol,
                position.short_leg.side.value,
                float(position.short_leg.amount),
                float(position.short_leg.price),
                float(position.short_leg.fee),
                float(position.short_leg.slippage_loss),
                position.short_leg.order_type.value,
                position.short_leg.timestamp,
                
                position.id
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating position: {e}")
            return False

    def get_all_positions(self) -> List[HedgePosition]:
        """获取所有持仓"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM hedge_position ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            positions = []
            for row in rows:
                position = self._row_to_entity(row)
                if position:
                    positions.append(position)
            return positions
        except Exception as e:
            print(f"Error getting all positions: {e}")
            return []

    def get_position_by_id(self, position_id: str) -> Optional[HedgePosition]:
        """根据ID获取持仓"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM hedge_position WHERE id = ?
            """, (position_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_entity(row)
            return None
        except Exception as e:
            print(f"Error getting position by ID: {e}")
            return None

    def get_open_positions(self) -> List[HedgePosition]:
        """获取所有开仓的持仓"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM hedge_position 
                WHERE state IN ('OPEN', 'CLOSING') 
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            positions = []
            for row in rows:
                position = self._row_to_entity(row)
                if position:
                    positions.append(position)
            return positions
        except Exception as e:
            print(f"Error getting open positions: {e}")
            return []

    def _row_to_entity(self, row) -> Optional[HedgePosition]:
        """将数据库行转换为HedgePosition实体"""
        try:
            from arbitrage.domain.entities.pair import Pair, ContractInfo
            from arbitrage.domain.entities.hedge_position import HedgePosition, PositionState
            from decimal import Decimal
            from arbitrage.domain.entities.trade_leg import TradeLeg
            from arbitrage.domain.entities.enums import TradeSide, OrderType
            
            # 解析contracts JSON
            contracts_data = json.loads(row[6]) if row[6] else {}
            contracts = {}
            for exchange, info in contracts_data.items():
                contracts[exchange] = ContractInfo(
                    contract_size=Decimal(str(info['contract_size'])),
                    min_qty=Decimal(str(info['min_qty'])),
                    leverage_max=Decimal(str(info['leverage_max'])) if info['leverage_max'] else None
                )
            
            # 构建Pair对象
            pair = Pair(
                symbol=row[1],
                base=row[2],
                quote=row[3],
                long_exchange=row[4],
                short_exchange=row[5],
                contracts=contracts
            )
            
            # 创建PositionState枚举
            state = PositionState(row[7])
            
            # 构建TradeLeg对象
            long_leg = TradeLeg(
                exchange=row[20],
                symbol=row[21],
                side=TradeSide(row[22]),
                amount=Decimal(str(row[23])),
                price=Decimal(str(row[24])),
                fee=Decimal(str(row[25])),
                slippage_loss=Decimal(str(row[26])),
                order_type=OrderType(row[27]),
                timestamp=float(row[28])
            )
            
            short_leg = TradeLeg(
                exchange=row[29],
                symbol=row[30],
                side=TradeSide(row[31]),
                amount=Decimal(str(row[32])),
                price=Decimal(str(row[33])),
                fee=Decimal(str(row[34])),
                slippage_loss=Decimal(str(row[35])),
                order_type=OrderType(row[36]),
                timestamp=float(row[37])
            )
            
            # 构建HedgePosition对象
            position = HedgePosition(
                id=row[0],
                pair=pair,
                state=state,
                quantity=Decimal(str(row[8])) if row[8] else Decimal('0'),
                notional_usd=Decimal(str(row[9])) if row[9] else Decimal('0'),
                entry_price_long=Decimal(str(row[10])) if row[10] else None,
                entry_price_short=Decimal(str(row[11])) if row[11] else None,
                current_price_long=Decimal(str(row[12])) if row[12] else None,
                current_price_short=Decimal(str(row[13])) if row[13] else None,
                pnl_unrealized=Decimal(str(row[14])) if row[14] else Decimal('0'),
                pnl_realized=Decimal(str(row[15])) if row[15] else Decimal('0'),
                fees=Decimal(str(row[16])) if row[16] else Decimal('0'),
                open_timestamp=float(row[17]),
                close_timestamp=row[18],
                long_leg=long_leg,
                short_leg=short_leg,
                close_reason=row[19]
            )
            
            return position
        except Exception as e:
            print(f"Error converting row to entity: {e}")
            return None