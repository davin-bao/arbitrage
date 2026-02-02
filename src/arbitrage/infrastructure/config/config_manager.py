import os
import yaml
from typing import Dict, Any, Optional


class ConfigManager:
    """
    通用配置管理类，用于加载和创建配置文件
    """
    
    @classmethod
    def load_or_create_config(cls, config_path: str, default_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建
        
        Args:
            config_path: 配置文件路径
            default_config: 默认配置数据
            
        Returns:
            配置数据字典
        """
        if default_config is None:
            default_config = {}
        
        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}，正在创建默认配置...")
            cls._create_default_config(config_path, default_config)
            return default_config
        
        return cls._load_config(config_path)
    
    @classmethod
    def _create_default_config(cls, config_path: str, default_config: Dict[str, Any]) -> None:
        """
        创建默认配置文件
        """
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    @classmethod
    def _load_config(cls, config_path: str) -> Dict[str, Any]:
        """
        加载配置文件
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    @classmethod
    def update_config_value(cls, config_path: str, key_path: str, value: Any) -> None:
        """
        更新配置文件中的特定键值
        
        Args:
            config_path: 配置文件路径
            key_path: 键路径，使用点号分隔，如 'exchanges.binance.enabled'
            value: 新值
        """
        config = cls.load_or_create_config(config_path)
        
        keys = key_path.split('.')
        current_dict = config
        
        # 遍历到倒数第二个键
        for key in keys[:-1]:
            if key not in current_dict:
                current_dict[key] = {}
            current_dict = current_dict[key]
        
        # 设置最后一个键的值
        current_dict[keys[-1]] = value
        
        # 保存配置
        cls._save_config(config_path, config)
    
    @classmethod
    def _save_config(cls, config_path: str, config: Dict[str, Any]) -> None:
        """
        保存配置到文件
        """
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)