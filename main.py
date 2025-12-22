"""
TradeSwarm 入口模块：加载配置并交由数据管理器初始化持久化资源。
"""

from data_manager import DataManager
from utils.config_loader import load_config


def main() -> None:
    """
    主函数：加载配置并直接传递给数据管理器完成初始化。
    """

    config = load_config()
    _data_manager = DataManager(config=config)


if __name__ == "__main__":
    main()