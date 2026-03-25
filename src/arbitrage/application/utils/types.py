    
from decimal import Decimal, InvalidOperation

def safe_decimal(value) -> Decimal:
        """安全地将值转换为 Decimal,若失败则返回默认值 0"""
        if value is None or value == '':
            return Decimal('0')
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal('0')

def safe_float(value) -> Decimal:
    """安全地将值转换为 Decimal,若失败则返回默认值 0"""
    if value is None or value == '':
        return float('0')
    try:
        return float(str(value))
    except (InvalidOperation, ValueError):
        return float('0')