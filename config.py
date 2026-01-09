from pathlib import Path

import yaml


class Config:
    def __init__(self, config_dict=None):
        if config_dict is None:
            config_dict = {}
        self._raw_config = config_dict

    def get(self, path: str, default=None):
        """
        通过点分路径获取配置值
        如果路径指向一个嵌套对象，则返回字典格式
        例如: config.get('exchange.options') 返回字典 {'defaultType': 'future'}
        """
        keys = path.split('.')
        current = self._raw_config

        try:
            for key in keys:
                current = current[key]

            # 如果结果是字典，返回字典；否则返回原始值
            if isinstance(current, dict):
                return current.copy()  # 返回副本以避免意外修改
            return current
        except (KeyError, TypeError):
            return default

    def to_dict(self):
        """返回原始配置字典"""
        return self._raw_config

    @classmethod
    def from_yaml(cls, config_path: str = "config.yml"):
        """从YAML文件加载配置"""
        with Path.open(config_path, mode="r", encoding='utf-8') as file:
            config_dict = yaml.safe_load(file)
        return cls(config_dict)


def load_config(config_path: str = "config.yml") -> Config:
    """加载配置文件并返回Config对象"""
    return Config.from_yaml(config_path)
