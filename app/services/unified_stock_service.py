#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一股票数据服务（跨市场，支持多数据源）

功能：
1. 跨市场数据访问（A股/港股/美股）
2. 多数据源优先级查询
3. 统一的查询接口

设计说明：
- 参考A股多数据源设计
- 同一股票可有多个数据源记录
- 通过 (code, source) 联合查询
- 数据源优先级从数据库配置读取
"""

import logging
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("webapi")


class UnifiedStockService:
    """统一股票数据服务（跨市场，支持多数据源）"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # 集合映射
        self.collection_map = {
            "CN": {
                "basic_info": "stock_basic_info",
                "quotes": "market_quotes",
                "daily": "stock_daily_quotes",
                "financial": "stock_financial_data",
                "news": "stock_news"
            },
            "HK": {
                "basic_info": "stock_basic_info_hk",
                "quotes": "market_quotes_hk",
                "daily": "stock_daily_quotes_hk",
                "financial": "stock_financial_data_hk",
                "news": "stock_news_hk"
            },
            "US": {
                "basic_info": "stock_basic_info_us",
                "quotes": "market_quotes_us",
                "daily": "stock_daily_quotes_us",
                "financial": "stock_financial_data_us",
                "news": "stock_news_us"
            },
            "MY": {
                "basic_info": "stock_basic_info_my",
                "quotes": "market_quotes_my",
                "daily": "stock_daily_quotes_my",
                "financial": "stock_financial_data_my",
                "news": "stock_news_my"
            }
        }

    async def get_stock_info(
        self,
        market: str,
        code: str,
        source: Optional[str] = None
    ) -> Optional[Dict]:
        """
        获取股票基础信息（支持多数据源）

        Args:
            market: 市场类型 (CN/HK/US/MY)
            code: 股票代码
            source: 指定数据源（可选）

        Returns:
            股票基础信息字典
        """
        # 马来西亚市场直接从Yahoo Finance获取
        if market == "MY":
            return await self._get_my_stock_info(code)

        collection_name = self.collection_map[market]["basic_info"]
        collection = self.db[collection_name]

        if source:
            # 指定数据源
            query = {"code": code, "source": source}
            doc = await collection.find_one(query, {"_id": 0})
            if doc:
                logger.debug(f"✅ 使用指定数据源: {source}")
        else:
            # 🔥 按优先级查询（参考A股设计）
            source_priority = await self._get_source_priority(market)
            doc = None

            for src in source_priority:
                query = {"code": code, "source": src}
                doc = await collection.find_one(query, {"_id": 0})
                if doc:
                    logger.debug(f"✅ 使用数据源: {src} (优先级查询)")
                    break

            # 如果没有找到，尝试不指定source查询（兼容旧数据）
            if not doc:
                doc = await collection.find_one({"code": code}, {"_id": 0})
                if doc:
                    logger.debug(f"✅ 使用默认数据源（兼容模式）")

        return doc

    async def _get_my_stock_info(self, code: str) -> Optional[Dict]:
        """
        获取马来西亚股票信息（直接从Yahoo Finance获取）

        Args:
            code: 股票代码

        Returns:
            股票基础信息字典
        """
        try:
            from tradingagents.dataflows.providers.my import get_my_stock_info as fetch_my_info
            info = fetch_my_info(code)
            if info:
                # 转换为统一格式
                return {
                    "code": info.get("symbol", code),
                    "name": info.get("name", ""),
                    "name_en": info.get("name", ""),
                    "market": "MY",
                    "source": "yfinance",
                    "currency": info.get("currency", "MYR"),
                    "exchange": info.get("exchange", "KLS"),
                    "total_mv": info.get("market_cap"),
                    "pe": info.get("pe_ratio"),
                    "pb": info.get("pb_ratio"),
                    "current_price": info.get("current_price"),
                    "previous_close": info.get("previous_close"),
                    "fifty_two_week_high": info.get("fifty_two_week_high"),
                    "fifty_two_week_low": info.get("fifty_two_week_low"),
                }
        except Exception as e:
            logger.error(f"❌ 获取马来西亚股票信息失败: {code} - {e}")
        return None

    async def _get_source_priority(self, market: str) -> List[str]:
        """
        从数据库获取数据源优先级
        
        Args:
            market: 市场类型 (CN/HK/US)
        
        Returns:
            数据源优先级列表
        """
        market_category_map = {
            "CN": "a_shares",
            "HK": "hk_stocks",
            "US": "us_stocks",
            "MY": "my_stocks"
        }
        
        market_category_id = market_category_map.get(market)
        
        try:
            # 从 datasource_groupings 集合查询
            groupings = await self.db.datasource_groupings.find({
                "market_category_id": market_category_id,
                "enabled": True
            }).sort("priority", -1).to_list(length=None)
            
            if groupings:
                priority_list = [g["data_source_name"] for g in groupings]
                logger.debug(f"📊 {market} 数据源优先级（从数据库）: {priority_list}")
                return priority_list
        except Exception as e:
            logger.warning(f"⚠️ 从数据库读取数据源优先级失败: {e}")
        
        # 默认优先级
        default_priority = {
            "CN": ["tushare", "akshare", "baostock"],
            "HK": ["yfinance_hk", "akshare_hk"],
            "US": ["yfinance_us"],
            "MY": ["yfinance_my"]
        }
        priority_list = default_priority.get(market, [])
        logger.debug(f"📊 {market} 数据源优先级（默认）: {priority_list}")
        return priority_list

    async def get_stock_quote(self, market: str, code: str) -> Optional[Dict]:
        """
        获取实时行情

        Args:
            market: 市场类型 (CN/HK/US/MY)
            code: 股票代码

        Returns:
            实时行情字典
        """
        # 马来西亚市场直接从Yahoo Finance获取
        if market == "MY":
            return await self._get_my_stock_quote(code)

        collection_name = self.collection_map[market]["quotes"]
        collection = self.db[collection_name]
        return await collection.find_one({"code": code}, {"_id": 0})

    async def _get_my_stock_quote(self, code: str) -> Optional[Dict]:
        """
        获取马来西亚股票实时行情（直接从Yahoo Finance获取）

        Args:
            code: 股票代码

        Returns:
            实时行情字典
        """
        try:
            from tradingagents.dataflows.providers.my import get_my_stock_info as fetch_my_info
            info = fetch_my_info(code)
            if info:
                return {
                    "code": info.get("symbol", code),
                    "name": info.get("name", ""),
                    "market": "MY",
                    "source": "yfinance",
                    "currency": info.get("currency", "MYR"),
                    "close": info.get("current_price"),
                    "pre_close": info.get("previous_close"),
                    "open": info.get("open"),
                    "high": info.get("day_high"),
                    "low": info.get("day_low"),
                    "volume": info.get("volume"),
                }
        except Exception as e:
            logger.error(f"❌ 获取马来西亚股票行情失败: {code} - {e}")
        return None

    async def search_stocks(
        self,
        market: str,
        query: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        搜索股票（去重，只返回每个股票的最优数据源）

        Args:
            market: 市场类型 (CN/HK/US/MY)
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            股票列表
        """
        # 马来西亚市场直接从Yahoo Finance搜索
        if market == "MY":
            return await self._search_my_stocks(query, limit)

        collection_name = self.collection_map[market]["basic_info"]
        collection = self.db[collection_name]

        # 支持代码和名称搜索
        filter_query = {
            "$or": [
                {"code": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"name_en": {"$regex": query, "$options": "i"}}
            ]
        }

        # 查询所有匹配的记录
        cursor = collection.find(filter_query)
        all_results = await cursor.to_list(length=None)

        if not all_results:
            return []

        # 按 code 分组，每个 code 只保留优先级最高的数据源
        source_priority = await self._get_source_priority(market)
        unique_results = {}

        for doc in all_results:
            code = doc.get("code")
            source = doc.get("source")

            if code not in unique_results:
                unique_results[code] = doc
            else:
                # 比较优先级
                current_source = unique_results[code].get("source")
                try:
                    if source in source_priority and current_source in source_priority:
                        if source_priority.index(source) < source_priority.index(current_source):
                            unique_results[code] = doc
                except ValueError:
                    # 如果source不在优先级列表中，保持当前记录
                    pass

        # 返回前 limit 条
        result_list = list(unique_results.values())[:limit]
        logger.info(f"🔍 搜索 {market} 市场: '{query}' -> {len(result_list)} 条结果（已去重）")
        return result_list

    async def _search_my_stocks(self, query: str, limit: int = 20) -> List[Dict]:
        """
        搜索马来西亚股票（从内置映射中搜索）

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            股票列表
        """
        try:
            from tradingagents.dataflows.providers.my import get_my_stock_provider
            provider = get_my_stock_provider()

            results = []
            query_lower = query.lower()

            # 从内置映射中搜索
            for symbol, name in provider.MY_STOCK_NAMES.items():
                if query_lower in symbol.lower() or query_lower in name.lower():
                    results.append({
                        "code": symbol,
                        "name": name,
                        "name_en": name,
                        "market": "MY",
                        "source": "yfinance",
                    })
                    if len(results) >= limit:
                        break

            logger.info(f"🔍 搜索 MY 市场: '{query}' -> {len(results)} 条结果")
            return results
        except Exception as e:
            logger.error(f"❌ 搜索马来西亚股票失败: {query} - {e}")
            return []

    async def get_daily_quotes(
        self,
        market: str,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取历史K线数据

        Args:
            market: 市场类型 (CN/HK/US/MY)
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        # 马来西亚市场直接从Yahoo Finance获取
        if market == "MY":
            return await self._get_my_daily_quotes(code, start_date, end_date, limit)

        collection_name = self.collection_map[market]["daily"]
        collection = self.db[collection_name]

        query = {"code": code}
        if start_date or end_date:
            query["trade_date"] = {}
            if start_date:
                query["trade_date"]["$gte"] = start_date
            if end_date:
                query["trade_date"]["$lte"] = end_date

        cursor = collection.find(query, {"_id": 0}).sort("trade_date", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def _get_my_daily_quotes(
        self,
        code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取马来西亚股票历史K线数据（直接从Yahoo Finance获取）

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回数量限制

        Returns:
            K线数据列表
        """
        try:
            from tradingagents.dataflows.providers.my import get_my_stock_data_yfinance
            df = get_my_stock_data_yfinance(code, start_date, end_date)

            if df.empty:
                return []

            # 转换为字典列表
            quotes = []
            for _, row in df.tail(limit).iterrows():
                quote = {
                    "trade_date": row.get("date", "").strftime("%Y-%m-%d") if hasattr(row.get("date", ""), "strftime") else str(row.get("date", "")),
                    "open": row.get("open"),
                    "high": row.get("high"),
                    "low": row.get("low"),
                    "close": row.get("close"),
                    "volume": row.get("volume"),
                    "code": code,
                    "market": "MY",
                    "source": "yfinance",
                }
                quotes.append(quote)

            # 按日期降序排列
            quotes.sort(key=lambda x: x.get("trade_date", ""), reverse=True)
            return quotes[:limit]
        except Exception as e:
            logger.error(f"❌ 获取马来西亚股票历史K线失败: {code} - {e}")
            return []

    async def get_supported_markets(self) -> List[Dict]:
        """
        获取支持的市场列表

        Returns:
            市场列表
        """
        return [
            {
                "code": "CN",
                "name": "A股",
                "name_en": "China A-Share",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            },
            {
                "code": "HK",
                "name": "港股",
                "name_en": "Hong Kong Stock",
                "currency": "HKD",
                "timezone": "Asia/Hong_Kong"
            },
            {
                "code": "US",
                "name": "美股",
                "name_en": "US Stock",
                "currency": "USD",
                "timezone": "America/New_York"
            },
            {
                "code": "MY",
                "name": "马股",
                "name_en": "Malaysia Stock",
                "currency": "MYR",
                "timezone": "Asia/Kuala_Lumpur"
            }
        ]

