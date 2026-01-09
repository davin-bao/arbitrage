from config import Config


def load_config(config_path: str = "config.yml") -> Config:
    """加载配置文件并返回Config对象"""
    return Config.from_yaml(config_path)