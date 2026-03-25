from typing import List, Optional
import json

from arbitrage.application.utils.types import safe_decimal, safe_float
from arbitrage.domain.entities.enums import PositionState
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
                open_time INTEGER,
                close_time INTEGER,
                ohlcv_average DECIMAL,
                ohlcv_max DECIMAL,
                long_leg_exchange TEXT,
                long_leg_symbol TEXT,
                long_leg_side TEXT,
                long_leg_amount DECIMAL,
                long_leg_price DECIMAL,
                long_leg_fee DECIMAL,
                long_leg_slippage_loss DECIMAL,
                long_leg_order_type TEXT,
                long_leg_timestamp REAL,
                long_leg_close_price DECIMAL,
                long_leg_close_timestamp REAL,
                short_leg_exchange TEXT,
                short_leg_symbol TEXT,
                short_leg_side TEXT,
                short_leg_amount DECIMAL,
                short_leg_price DECIMAL,
                short_leg_fee DECIMAL,
                short_leg_slippage_loss DECIMAL,
                short_leg_order_type TEXT,
                short_leg_timestamp REAL,
                short_leg_close_price DECIMAL,
                short_leg_close_timestamp REAL,
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
                    'contract_size': safe_float(info.contract_size),
                    'min_qty': safe_float(info.min_qty),
                    'leverage_max': safe_float(info.leverage_max) if info.leverage_max else None
                } 
                for ex, info in position.pair.contracts.items()
            })
            
            cursor.execute("""
                INSERT INTO hedge_position (
                    id, symbol, base, quote, long_exchange, short_exchange, 
                    contracts, state,
                    open_time, close_time, ohlcv_average, ohlcv_max,
                    long_leg_exchange, long_leg_symbol, long_leg_side, 
                    long_leg_amount, long_leg_price, long_leg_fee, 
                    long_leg_slippage_loss, long_leg_order_type, long_leg_timestamp,
                    short_leg_exchange, short_leg_symbol, short_leg_side, 
                    short_leg_amount, short_leg_price, short_leg_fee, 
                    short_leg_slippage_loss, short_leg_order_type, short_leg_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.id,
                position.pair.symbol,
                position.pair.base,
                position.pair.quote,
                position.pair.long_exchange,
                position.pair.short_exchange,
                contracts_json,
                position.state.value,
                int(position.open_timestamp),
                position.close_timestamp,
                safe_float(position.ohlcv_average),
                safe_float(position.ohlcv_max),
                
                # Long leg data
                position.long_leg.exchange,
                position.long_leg.symbol,
                position.long_leg.side.value,
                safe_float(position.long_leg.amount),
                safe_float(position.long_leg.price),
                safe_float(position.long_leg.fee),
                safe_float(position.long_leg.slippage_loss),
                position.long_leg.order_type.value,
                position.long_leg.timestamp,
                
                # Short leg data
                position.short_leg.exchange,
                position.short_leg.symbol,
                position.short_leg.side.value,
                safe_float(position.short_leg.amount),
                safe_float(position.short_leg.price),
                safe_float(position.short_leg.fee),
                safe_float(position.short_leg.slippage_loss),
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
                    'contract_size': safe_float(info.contract_size),
                    'min_qty': safe_float(info.min_qty),
                    'leverage_max': safe_float(info.leverage_max) if info.leverage_max else None
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
                    open_time = ?,
                    close_time = ?,
                    ohlcv_average = ?,
                    ohlcv_max = ?,
                    long_leg_exchange = ?,
                    long_leg_symbol = ?,
                    long_leg_side = ?,
                    long_leg_amount = ?,
                    long_leg_price = ?,
                    long_leg_fee = ?,
                    long_leg_slippage_loss = ?,
                    long_leg_order_type = ?,
                    long_leg_timestamp = ?,
                    long_leg_close_price = ?,
                    long_leg_close_timestamp = ?,
                    short_leg_exchange = ?,
                    short_leg_symbol = ?,
                    short_leg_side = ?,
                    short_leg_amount = ?,
                    short_leg_price = ?,
                    short_leg_fee = ?,
                    short_leg_slippage_loss = ?,
                    short_leg_order_type = ?,
                    short_leg_timestamp = ?,
                    short_leg_close_price = ?,
                    short_leg_close_timestamp = ?,
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
                int(position.open_timestamp),
                position.close_timestamp,
                safe_float(position.ohlcv_average),
                safe_float(position.ohlcv_max),
                
                # Long leg data
                position.long_leg.exchange,
                position.long_leg.symbol,
                position.long_leg.side.value,
                safe_float(position.long_leg.amount),
                safe_float(position.long_leg.price),
                safe_float(position.long_leg.fee),
                safe_float(position.long_leg.slippage_loss),
                position.long_leg.order_type.value,
                position.long_leg.timestamp,
                safe_float(position.long_leg.close_price),
                position.long_leg.close_timestamp,
                
                # Short leg data
                position.short_leg.exchange,
                position.short_leg.symbol,
                position.short_leg.side.value,
                safe_float(position.short_leg.amount),
                safe_float(position.short_leg.price),
                safe_float(position.short_leg.fee),
                safe_float(position.short_leg.slippage_loss),
                position.short_leg.order_type.value,
                position.short_leg.timestamp,
                safe_float(position.short_leg.close_price),
                position.short_leg.close_timestamp,
                
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
                WHERE state IN (?, ?) 
                ORDER BY created_at DESC
            """, (PositionState.OPEN.value, PositionState.CLOSING.value,))
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
            from arbitrage.domain.entities.trade_leg import TradeLeg
            from arbitrage.domain.entities.enums import TradeSide, OrderType
            
            # 解析contracts JSON
            contracts_data = json.loads(row[6]) if row[6] else {}
            contracts = {}
            for exchange, info in contracts_data.items():
                contracts[exchange] = ContractInfo(
                    contract_size=safe_decimal(str(info['contract_size'])),
                    min_qty=safe_decimal(str(info['min_qty'])),
                    leverage_max=safe_decimal(str(info['leverage_max'])) if info['leverage_max'] else None
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
                exchange=row[12],
                symbol=row[13],
                side=TradeSide(row[14]),
                amount=safe_decimal(str(row[15])),
                price=safe_decimal(str(row[16])),
                fee=safe_decimal(str(row[17])),
                slippage_loss=safe_decimal(str(row[18])),
                order_type=OrderType(row[19]),
                timestamp=safe_float(row[20]),
                close_price=safe_decimal(str(row[21])),
                close_timestamp=safe_float(row[22])
            )
            
            short_leg = TradeLeg(
                exchange=row[23],
                symbol=row[24],
                side=TradeSide(row[25]),
                amount=safe_decimal(str(row[26])),
                price=safe_decimal(str(row[27])),
                fee=safe_decimal(str(row[28])),
                slippage_loss=safe_decimal(str(row[29])),
                order_type=OrderType(row[30]),
                timestamp=safe_float(row[31]),
                close_price=safe_decimal(str(row[32])),
                close_timestamp=safe_float(row[33])
            )
            
            # 构建HedgePosition对象
            position = HedgePosition(
                id=row[0],
                pair=pair,
                state=state,
                open_timestamp=safe_float(row[8]),
                close_timestamp=safe_float(row[9]),
                ohlcv_average=safe_decimal(row[10]),
                ohlcv_max=safe_decimal(row[11]),
                long_leg=long_leg,
                short_leg=short_leg
            )
            
            return position
        except Exception as e:
            print(f"Error converting row to entity: {e}")
            return None
