"""
TradeSwarm 入口模块：加载配置并初始化数据管理器与数据提供者。
"""

from data_manager import DataManager
from utils.config_loader import load_config
from data_sources.akshare_provider import AkshareProvider
from data_sources.tushare_provider import TushareProvider


def main() -> None:
    """
    主函数：加载配置并初始化数据管理器与数据提供者。
    """

    # 第一阶段：加载配置
    config = load_config()
    
    # 第二阶段：初始化数据管理器
    data_manager = DataManager(config=config)
    
    # 第三阶段：实例化数据提供者
    akshare_provider = AkshareProvider(config=config)
    tushare_provider = TushareProvider(config=config)
    
    # 验证数据提供者是否已正确实例化
    print("数据管理器已初始化:", type(data_manager).__name__)
    print("AkShare 数据提供者已初始化:", type(akshare_provider).__name__)
    print("Tushare 数据提供者已初始化:", type(tushare_provider).__name__)


if __name__ == "__main__":
    main()