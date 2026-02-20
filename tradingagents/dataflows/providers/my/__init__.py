"""
马来西亚股市数据提供器
支持 Bursa Malaysia 股票数据获取
"""

try:
    from .yfinance_my import (
        MYStockProvider,
        get_my_stock_provider,
        get_my_stock_data,
        get_my_stock_info,
        get_my_stock_data_yfinance,
    )
    MY_PROVIDER_AVAILABLE = True
except ImportError:
    MYStockProvider = None
    get_my_stock_provider = None
    get_my_stock_data = None
    get_my_stock_info = None
    get_my_stock_data_yfinance = None
    MY_PROVIDER_AVAILABLE = False

__all__ = [
    'MYStockProvider',
    'get_my_stock_provider',
    'get_my_stock_data',
    'get_my_stock_info',
    'get_my_stock_data_yfinance',
    'MY_PROVIDER_AVAILABLE',
]
