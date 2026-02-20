#!/usr/bin/env python3
"""
马来西亚股市数据获取工具
使用 Yahoo Finance 作为数据源
支持 Bursa Malaysia (KLS) 股票数据获取
"""

import time
import json
import os
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from tradingagents.config.runtime_settings import get_int
# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 新增：使用统一的数据目录配置
try:
    from utils.data_config import get_cache_dir
except Exception:
    # 回退：在项目根目录下的 data/cache/my
    def get_cache_dir(subdir: Optional[str] = None, create: bool = True):
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'cache')
        if subdir:
            base = os.path.join(base, subdir)
        if create:
            os.makedirs(base, exist_ok=True)
        return base


class MYStockProvider:
    """马来西亚股市数据提供器"""

    # 内置马来西亚股票名称映射（避免API调用）
    MY_STOCK_NAMES = {
        # 银行
        '1155.KL': 'Maybank (马来亚银行)',
        '1066.KL': 'CIMB (联昌银行)',
        '5234.KL': 'Public Bank (大众银行)',
        '1295.KL': 'AmBank (大马银行)',
        '6888.KL': 'RHB Bank (兴业银行)',
        '2488.KL': 'Hong Leong Bank (丰隆银行)',

        # 公用事业
        '5347.KL': 'Tenaga Nasional (国家能源)',
        '6947.KL': 'Telekom Malaysia (马电讯)',
        '6742.KL': 'Maxis (明讯)',
        '5398.KL': 'CelcomDigi',
        '6793.KL': 'Gas Malaysia (马天然气)',

        # 石油天然气
        '5181.KL': 'Petronas Gas (国油气体)',
        '5681.KL': 'Petronas Dagangan (国油贸易)',
        '4481.KL': 'MRCB',
        '5227.KL': 'Petronas Chemicals (国油化学)',

        # 种植
        '4545.KL': 'IOI Corporation (IOI集团)',
        '5285.KL': 'KLK (吉隆坡甲洞)',
        '5027.KL': 'Sime Darby Plantation (森那美种植)',
        '1961.KL': 'Hap Seng Plantations',
        '2525.KL': 'Boustead Plantation',

        # 消费
        '4707.KL': 'Nestle (雀巢)',
        '1817.KL': 'F&N (花莎尼)',
        '5099.KL': 'Genting (云顶)',
        '4715.KL': 'Genting Malaysia (云顶大马)',
        '5348.KL': 'QL Resources',
        '7081.KL': 'Hup Seng Industries',
        '2828.KL': 'Power Root',

        # 科技
        '7113.KL': 'Inari Amertron',
        '7089.KL': 'Unisem (友尼森)',
        '7204.KL': 'Vitrox (伟特)',
        '0166.KL': 'Notion VTec',
        '7277.KL': 'Globetronics Technology',
        '5284.KL': 'Penta Ocean',

        # 建筑
        '3239.KL': 'Gamuda (金务大)',
        '5819.KL': 'Hong Leong Industries',
        '6801.KL': 'IJM Corporation',
        '5081.KL': 'Sunway Construction',

        # 房地产
        '5223.KL': 'SP Setia (实达集团)',
        '5168.KL': 'UMW Holdings',
        '1783.KL': 'Top Glove (顶级手套)',
        '7106.KL': 'Hartalega',

        # 其他
        '5216.KL': 'IHH Healthcare (IHH医疗保健)',
        '6012.KL': 'Maxis',
        '5274.KL': 'MISC (马国际船务)',
        '5288.KL': 'Hong Leong Financial Group',
        '1082.KL': 'Malayan Flour Mills',
    }

    def __init__(self):
        # 将缓存文件写入到统一的数据缓存目录下，避免污染项目根目录
        my_cache_dir = get_cache_dir('my')
        if hasattr(my_cache_dir, 'joinpath'):  # Path
            self.cache_file = str(my_cache_dir.joinpath('my_stock_cache.json'))
        else:  # str
            self.cache_file = os.path.join(my_cache_dir, 'my_stock_cache.json')

        self.cache_ttl = get_int("TA_MY_CACHE_TTL_SECONDS", "ta_my_cache_ttl_seconds", 3600)  # 1 hour
        self.rate_limit_wait = get_int("TA_MY_RATE_LIMIT_WAIT_SECONDS", "ta_my_rate_limit_wait_seconds", 2)
        self.last_request_time = 0

        self._load_cache()

    def _load_cache(self):
        """加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
            else:
                self.cache = {}
        except Exception as e:
            logger.debug(f"📊 [马股缓存] 加载缓存失败: {e}")
            self.cache = {}

    def _save_cache(self):
        """保存缓存"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"📊 [马股缓存] 保存缓存失败: {e}")

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache:
            return False

        cache_time = self.cache[key].get('timestamp', 0)
        return (time.time() - cache_time) < self.cache_ttl

    def _rate_limit(self):
        """速率限制：确保两次请求之间有足够的间隔"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_wait:
            wait_time = self.rate_limit_wait - time_since_last_request
            logger.debug(f"⏱️ [速率限制] 等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    def _normalize_my_symbol(self, symbol: str) -> str:
        """
        标准化马来西亚股票代码

        Args:
            symbol: 原始股票代码

        Returns:
            str: 标准化后的股票代码 (如 5347.KL)
        """
        if not symbol:
            return symbol

        symbol = str(symbol).strip().upper()

        # 如果已经是正确格式，直接返回
        if symbol.endswith('.KL'):
            return symbol

        # 如果是纯数字，添加.KL后缀
        if symbol.isdigit():
            if len(symbol) == 4:
                return f"{symbol}.KL"
            elif len(symbol) < 4:
                # 补齐到4位
                return f"{symbol.zfill(4)}.KL"

        return symbol

    def get_company_name(self, symbol: str) -> str:
        """
        获取马来西亚公司名称

        Args:
            symbol: 马来西亚股票代码

        Returns:
            str: 公司名称
        """
        try:
            # 检查缓存
            cache_key = f"name_{symbol}"
            if self._is_cache_valid(cache_key):
                cached_name = self.cache[cache_key]['data']
                logger.debug(f"📊 [马股缓存] 从缓存获取公司名称: {symbol} -> {cached_name}")
                return cached_name

            # 方案1：使用内置映射
            normalized_symbol = self._normalize_my_symbol(symbol)

            if normalized_symbol in self.MY_STOCK_NAMES:
                company_name = self.MY_STOCK_NAMES[normalized_symbol]

                # 缓存结果
                self.cache[cache_key] = {
                    'data': company_name,
                    'timestamp': time.time(),
                    'source': 'builtin_mapping'
                }
                self._save_cache()

                logger.debug(f"📊 [马股映射] 获取公司名称: {symbol} -> {company_name}")
                return company_name

            # 方案2：尝试从 Yahoo Finance 获取
            try:
                self._rate_limit()

                import yfinance as yf
                ticker = yf.Ticker(normalized_symbol)
                info = ticker.info

                if info and 'shortName' in info:
                    api_name = info['shortName']

                    # 缓存API结果
                    self.cache[cache_key] = {
                        'data': api_name,
                        'timestamp': time.time(),
                        'source': 'yahoo_finance'
                    }
                    self._save_cache()

                    logger.debug(f"📊 [马股Yahoo] 获取公司名称: {symbol} -> {api_name}")
                    return api_name

            except Exception as e:
                logger.debug(f"📊 [马股Yahoo] API获取失败: {e}")

            # 方案3：生成友好的默认名称
            clean_symbol = normalized_symbol.replace('.KL', '')
            default_name = f"马来西亚股票{clean_symbol}"

            # 缓存默认结果（较短的TTL）
            self.cache[cache_key] = {
                'data': default_name,
                'timestamp': time.time() - self.cache_ttl + 1800,  # 30分钟后过期
                'source': 'default'
            }
            self._save_cache()

            logger.debug(f"📊 [马股默认] 使用默认名称: {symbol} -> {default_name}")
            return default_name

        except Exception as e:
            logger.error(f"❌ [马股] 获取公司名称失败: {e}")
            clean_symbol = self._normalize_my_symbol(symbol).replace('.KL', '')
            return f"马来西亚股票{clean_symbol}"

    def get_stock_data(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取马来西亚股票历史数据

        Args:
            symbol: 马来西亚股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            pd.DataFrame: 股票数据
        """
        try:
            import yfinance as yf

            # 标准化代码
            normalized_symbol = self._normalize_my_symbol(symbol)

            # 设置默认日期
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            logger.info(f"📊 [马股] 获取历史数据: {normalized_symbol} ({start_date} ~ {end_date})")

            # 速率限制
            self._rate_limit()

            # 获取数据
            ticker = yf.Ticker(normalized_symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                logger.warning(f"⚠️ [马股] 返回空数据: {normalized_symbol}")
                return pd.DataFrame()

            # 重置索引
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date'])

            # 重命名列
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })

            # 添加前收盘价和涨跌幅
            df['pre_close'] = df['close'].shift(1)
            df['change'] = df['close'] - df['pre_close']
            df['pct_change'] = (df['change'] / df['pre_close'] * 100).round(2)

            logger.info(f"✅ [马股] 获取历史数据成功: {normalized_symbol} ({len(df)}条)")
            return df

        except Exception as e:
            logger.error(f"❌ [马股] 获取历史数据失败: {symbol} - {e}")
            return pd.DataFrame()

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取马来西亚股票基本信息

        Args:
            symbol: 马来西亚股票代码

        Returns:
            Dict: 股票信息
        """
        try:
            import yfinance as yf

            # 标准化代码
            normalized_symbol = self._normalize_my_symbol(symbol)
            company_name = self.get_company_name(symbol)

            # 速率限制
            self._rate_limit()

            # 获取基本信息
            ticker = yf.Ticker(normalized_symbol)
            info = ticker.info or {}

            return {
                'symbol': normalized_symbol,
                'name': company_name,
                'currency': 'MYR',
                'exchange': 'KLS',
                'market': '马来西亚股市',
                'source': 'yahoo_finance',
                'current_price': info.get('currentPrice'),
                'previous_close': info.get('previousClose'),
                'open': info.get('open'),
                'day_high': info.get('dayHigh'),
                'day_low': info.get('dayLow'),
                'volume': info.get('volume'),
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow'),
            }

        except Exception as e:
            logger.error(f"❌ [马股] 获取股票信息失败: {e}")
            normalized_symbol = self._normalize_my_symbol(symbol)
            return {
                'symbol': normalized_symbol,
                'name': self.get_company_name(symbol),
                'currency': 'MYR',
                'exchange': 'KLS',
                'market': '马来西亚股市',
                'source': 'error',
                'error': str(e)
            }

    def format_stock_data(self, symbol: str, start_date: str = None, end_date: str = None,
                          include_indicators: bool = True) -> str:
        """
        格式化输出股票数据

        Args:
            symbol: 马来西亚股票代码
            start_date: 开始日期
            end_date: 结束日期
            include_indicators: 是否包含技术指标

        Returns:
            str: 格式化的股票数据
        """
        try:
            # 标准化代码
            normalized_symbol = self._normalize_my_symbol(symbol)
            company_name = self.get_company_name(symbol)

            # 获取数据
            df = self.get_stock_data(normalized_symbol, start_date, end_date)

            if df.empty:
                return f"❌ 无法获取马来西亚股票 {normalized_symbol} 的数据"

            # 设置默认日期
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

            # 添加技术指标
            if include_indicators:
                try:
                    from tradingagents.tools.analysis.indicators import add_all_indicators
                    df = add_all_indicators(df, close_col='close', high_col='high', low_col='low')
                except Exception as e:
                    logger.debug(f"📊 [马股] 添加技术指标失败: {e}")

            # 获取最新数据
            latest = df.iloc[-1]

            # 格式化输出
            result = f"""## 马来西亚股票历史数据 ({company_name} / {normalized_symbol})
**数据源**: Yahoo Finance (马来西亚股市)
**日期范围**: {start_date} ~ {end_date}
**数据条数**: {len(df)} 条

### 基本信息
- 代码: {normalized_symbol}
- 名称: {company_name}
- 货币: 马来西亚林吉特 (MYR)
- 交易所: Bursa Malaysia (KLS)

### 最新价格信息
- 最新价: RM{latest['close']:.2f}
- 昨收: RM{latest['pre_close']:.2f}
- 涨跌额: RM{latest['change']:.2f}
- 涨跌幅: {latest['pct_change']:.2f}%
- 最高: RM{latest['high']:.2f}
- 最低: RM{latest['low']:.2f}
- 成交量: {latest['volume']:,.0f}
"""

            # 添加技术指标
            if include_indicators and 'ma5' in df.columns:
                result += f"""
### 技术指标（最新值）
**移动平均线**:
- MA5: RM{latest['ma5']:.2f}
- MA10: RM{latest['ma10']:.2f}
- MA20: RM{latest['ma20']:.2f}
- MA60: RM{latest['ma60']:.2f}

**MACD指标**:
- DIF: {latest['macd_dif']:.4f}
- DEA: {latest['macd_dea']:.4f}
- MACD: {latest['macd']:.4f}

**RSI指标**:
- RSI(14): {latest['rsi']:.2f}

**布林带**:
- 上轨: RM{latest['boll_upper']:.2f}
- 中轨: RM{latest['boll_mid']:.2f}
- 下轨: RM{latest['boll_lower']:.2f}
"""

            # 添加最近10个交易日价格
            result += f"""
### 最近10个交易日价格
{df[['date', 'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_change', 'volume']].tail(10).to_string(index=False)}

### 数据统计
- 最高价: RM{df['high'].max():.2f}
- 最低价: RM{df['low'].min():.2f}
- 平均收盘价: RM{df['close'].mean():.2f}
- 总成交量: {df['volume'].sum():,.0f}
"""

            return result

        except Exception as e:
            logger.error(f"❌ [马股] 格式化数据失败: {symbol} - {e}")
            return f"❌ 马来西亚股票 {symbol} 数据格式化失败: {str(e)}"


# 全局实例
_my_stock_provider = None


def get_my_stock_provider() -> MYStockProvider:
    """获取马来西亚股票提供器实例"""
    global _my_stock_provider
    if _my_stock_provider is None:
        _my_stock_provider = MYStockProvider()
    return _my_stock_provider


def get_my_stock_data(symbol: str, start_date: str = None, end_date: str = None) -> str:
    """
    获取马来西亚股票数据（格式化字符串）

    Args:
        symbol: 马来西亚股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        str: 格式化的股票数据
    """
    provider = get_my_stock_provider()
    return provider.format_stock_data(symbol, start_date, end_date)


def get_my_stock_info(symbol: str) -> Dict[str, Any]:
    """
    获取马来西亚股票信息

    Args:
        symbol: 马来西亚股票代码

    Returns:
        Dict: 股票信息
    """
    provider = get_my_stock_provider()
    return provider.get_stock_info(symbol)


def get_my_stock_data_yfinance(symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    获取马来西亚股票原始数据（DataFrame）

    Args:
        symbol: 马来西亚股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        pd.DataFrame: 股票数据
    """
    provider = get_my_stock_provider()
    return provider.get_stock_data(symbol, start_date, end_date)
