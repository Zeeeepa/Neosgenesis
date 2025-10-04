#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
搜索工具客户端 - 用于连接外部搜索引擎
Search Tool Client - for connecting to external search engines
"""

import os
import json
import logging
import time
import ssl
import certifi
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from urllib3.poolmanager import PoolManager

# 🔧 新增：支持真实Firecrawl搜索
try:
    from firecrawl import FirecrawlApp
    FIRECRAWL_AVAILABLE = True
except ImportError:
    FIRECRAWL_AVAILABLE = False
    logging.warning("⚠️ firecrawl-py库未安装，将使用模拟搜索结果")

# 🔥 新增：支持Tavily搜索
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logging.warning("⚠️ tavily-python库未安装，将使用模拟搜索结果")

# 🔑 Tavily API密钥
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "Your_API_Key")


# 🔥 根本性SSL修复：自定义SSL适配器
class SSLAdapter(HTTPAdapter):
    """
    自定义SSL适配器，解决SSL/TLS握手问题
    使用现代化的TLS配置，支持TLS 1.2和1.3
    """
    def init_poolmanager(self, *args, **kwargs):
        # 创建SSL上下文，使用最新的TLS协议
        context = create_urllib3_context()
        
        # 设置支持的TLS版本（TLS 1.2 和 1.3）
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        
        # 加载系统CA证书
        try:
            context.load_verify_locations(certifi.where())
        except Exception:
            pass
        
        # 设置密码套件（使用现代安全的密码套件）
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # 配置SSL选项
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        # 设置ALPN协议（支持HTTP/2）
        try:
            context.set_alpn_protocols(['h2', 'http/1.1'])
        except AttributeError:
            pass
        
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

# 导入配置
try:
    from neogenesis_system.config import RAG_CONFIG
except ImportError:
    try:
        from ..config import RAG_CONFIG
    except ImportError:
        # 默认配置（如果无法导入）
        RAG_CONFIG = {"enable_real_web_search": False}

logger = logging.getLogger(__name__)

# 全局搜索请求管理器，用于控制请求频率
class SearchRateLimiter:
    """搜索速率限制管理器"""
    def __init__(self):
        self.last_request_time = 0
        # 从配置获取请求间隔，如果配置不存在则使用默认值
        self.min_interval = RAG_CONFIG.get("search_rate_limit_interval", 1.5)
    
    def wait_if_needed(self):
        """如果需要，等待到下一个允许的请求时间"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            logger.debug(f"⏳ 速率限制等待: {wait_time:.1f}秒")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()

# 全局速率限制器实例
_rate_limiter = SearchRateLimiter()

@dataclass
class SearchResult:
    """搜索结果数据结构"""
    title: str
    snippet: str
    url: str
    relevance_score: float = 0.0

@dataclass
class SearchResponse:
    """搜索响应数据结构"""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time: float
    success: bool = True
    error_message: str = ""
    metadata: Optional[Dict[str, Any]] = None  # 🔥 新增：支持额外的元数据（如Tavily的AI答案）

@dataclass
class IdeaVerificationResult:
    """想法验证结果数据结构"""
    idea_text: str
    feasibility_score: float
    analysis_summary: str
    search_results: List[SearchResult]
    success: bool = True
    error_message: str = ""

class WebSearchClient:
    """网络搜索客户端"""
    
    def __init__(self, search_engine: str = "tavily", max_results: int = 5):
        """
        初始化搜索客户端
        
        Args:
            search_engine: 搜索引擎类型 ("tavily", "firecrawl", "bing", "google")
            max_results: 最大结果数量
        """
        self.search_engine = search_engine
        self.max_results = max_results
        
        # 🔥 根本性SSL修复：使用自定义SSL适配器
        self.session = requests.Session()
        
        # 配置现代化的请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        # 挂载自定义SSL适配器到所有HTTPS连接
        ssl_adapter = SSLAdapter(
            max_retries=3,  # 连接重试次数
            pool_connections=10,  # 连接池大小
            pool_maxsize=10,  # 最大连接数
        )
        self.session.mount('https://', ssl_adapter)
        self.session.mount('http://', HTTPAdapter(max_retries=3))
        
        # 设置合理的超时配置
        self.timeout = (10, 30)  # (连接超时, 读取超时)
        
        # 搜索统计
        self.search_stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'total_search_time': 0.0,
            'avg_search_time': 0.0
        }
        
        logger.info(f"🔍 WebSearchClient初始化完成 - 使用{search_engine}搜索引擎")
        logger.info(f"🔒 SSL配置：TLS 1.2/1.3 + 现代密码套件 + certifi证书")
    
    def search(self, query: str, max_results: Optional[int] = None) -> SearchResponse:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数量（覆盖默认值）
            
        Returns:
            SearchResponse: 搜索响应
        """
        start_time = time.time()
        max_results = max_results or self.max_results
        
        logger.info(f"🔍 [WebSearchClient] 开始搜索: {query[:50]}...")
        logger.info(f"🔍 [WebSearchClient] 搜索引擎: {self.search_engine}")
        logger.info(f"🔍 [WebSearchClient] 最大结果数: {max_results}")
        
        try:
            if self.search_engine == "tavily":
                logger.info(f"🔍 [WebSearchClient] 调用_search_tavily方法...")
                response = self._search_tavily(query, max_results)
            elif self.search_engine == "firecrawl":
                logger.info(f"🔍 [WebSearchClient] 调用_search_firecrawl方法...")
                response = self._search_firecrawl(query, max_results)
            elif self.search_engine == "bing":
                response = self._search_bing(query, max_results)
            else:
                response = self._search_fallback(query, max_results)
            
            search_time = time.time() - start_time
            response.search_time = search_time
            
            # 更新统计
            self._update_search_stats(search_time, response.success)
            
            logger.info(f"🔍 搜索完成: 找到{len(response.results)}个结果，耗时{search_time:.2f}秒")
            return response
            
        except Exception as e:
            search_time = time.time() - start_time
            logger.error(f"❌ 搜索失败: {e}")
            
            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                search_time=search_time,
                success=False,
                error_message=str(e)
            )
    
    def _search_tavily(self, query: str, max_results: int) -> SearchResponse:
        """🔥 使用Tavily搜索 - AI搜索引擎"""
        logger.info(f"🌐 开始Tavily搜索: {query[:50]}...")
        
        if not TAVILY_AVAILABLE:
            logger.warning("⚠️ Tavily库不可用，使用模拟搜索模式")
            return self._search_fallback(query, max_results)
        
        try:
            # 初始化Tavily客户端
            tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
            logger.info(f"✅ Tavily客户端初始化成功")
            
            # 执行搜索
            logger.info(f"🔍 正在搜索: {query}")
            search_response = tavily_client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",  # 使用高级搜索模式
                include_answer=True,       # 包含AI总结答案
                include_raw_content=False  # 不包含原始内容（节省token）
            )
            
            logger.debug(f"🔍 Tavily响应类型: {type(search_response)}")
            logger.debug(f"🔍 Tavily响应内容: {search_response}")
            
            # 解析搜索结果
            results = []
            if isinstance(search_response, dict):
                tavily_results = search_response.get('results', [])
                
                for idx, item in enumerate(tavily_results[:max_results]):
                    try:
                        result = SearchResult(
                            title=item.get('title', f'结果 {idx + 1}'),
                            url=item.get('url', ''),
                            snippet=item.get('content', '')[:500],  # 限制长度
                            relevance_score=item.get('score', 0.8)  # Tavily提供相关性分数
                        )
                        results.append(result)
                        logger.debug(f"  ✅ 结果 {idx + 1}: {result.title[:50]}")
                    except Exception as e:
                        logger.warning(f"⚠️ 解析Tavily结果项失败: {e}")
                        continue
                
                # 构建成功响应
                return SearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    search_time=0.0,  # 将在外层计算
                    success=True,
                    metadata={
                        'search_engine': 'tavily',
                        'answer': search_response.get('answer', ''),  # Tavily的AI总结答案
                        'search_depth': 'advanced'
                    }
                )
            else:
                logger.warning(f"⚠️ Tavily返回了非预期的响应格式: {type(search_response)}")
                return self._search_fallback(query, max_results)
                
        except Exception as e:
            logger.error(f"❌ Tavily搜索失败: {e}")
            logger.exception(e)
            
            # 构建失败响应
            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                search_time=0.0,
                success=False,
                error_message=f"Tavily搜索失败: {str(e)}"
            )
    
    def _search_firecrawl(self, query: str, max_results: int) -> SearchResponse:
        """使用Firecrawl搜索 - 带智能备用机制"""
        
        # 🔧 详细的搜索模式诊断
        enable_real_search = RAG_CONFIG.get("enable_real_web_search", False)
        logger.info(f"🔍 搜索模式诊断:")
        logger.info(f"   - enable_real_web_search: {enable_real_search}")
        logger.info(f"   - REAL_SEARCH_AVAILABLE: {REAL_SEARCH_AVAILABLE}")
        logger.info(f"   - 查询: {query[:50]}...")
        
        # 🔧 检查是否启用真实搜索
        if enable_real_search and REAL_SEARCH_AVAILABLE:
            logger.info("🌐 尝试真实Firecrawl搜索...")
            # 尝试真实搜索
            response = self._search_firecrawl_real(query, max_results)
            
            # 🔥 增强版：如果真实搜索失败，智能回退到模拟搜索
            if not response.success:
                logger.warning(f"🚨 Firecrawl真实搜索失败，原因: {response.error_message}")
                
                # 检查是否应该回退到模拟搜索
                should_fallback = self._should_fallback_to_mock(response.error_message)
                
                if should_fallback:
                    logger.warning("🚨 建议暂时切换到模拟搜索模式")
                    logger.info("💡 解决方案：在config.py中设置 'enable_real_web_search': False")
                    logger.info("🔄 自动回退到模拟搜索...")
                    
                    # 自动回退到模拟搜索
                    mock_result = self._search_firecrawl_mock(query, max_results)
                    # 在模拟结果中添加回退信息
                    if mock_result.success:
                        mock_result.error_message = f"已从真实搜索回退: {response.error_message}"
                        logger.info(f"✅ 模拟搜索回退成功，返回{len(mock_result.results)}个结果")
                    return mock_result
                else:
                    # 不回退，返回原始错误
                    return response
            else:
                logger.info(f"✅ 真实搜索成功，返回{len(response.results)}个结果")
                return response
        else:
            if not enable_real_search:
                logger.info("🎭 配置禁用真实搜索，使用模拟搜索模式")
                return self._search_firecrawl_mock(query, max_results)
            elif not REAL_SEARCH_AVAILABLE:
                logger.warning("⚠️ firecrawl库不可用，使用模拟搜索模式")
                return self._search_firecrawl_mock(query, max_results)
    
    def _search_firecrawl_real(self, query: str, max_results: int) -> SearchResponse:
        """🔥 真实的Firecrawl搜索 - 使用正确的SSL配置和智能重试机制"""
        max_retries = RAG_CONFIG.get("search_max_retries", 2)
        base_delay = RAG_CONFIG.get("search_retry_base_delay", 2.0)
        
        # 获取Firecrawl API密钥（从环境变量或配置）
        FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY") or RAG_CONFIG.get("firecrawl_api_key", "")
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 智能速率限制处理
                _rate_limiter.wait_if_needed()
                
                # 根据错误类型调整延迟策略
                if attempt > 0:
                    if last_error and "rate" in str(last_error).lower():
                        delay = min(base_delay * (3 ** attempt), 60.0)
                        logger.info(f"⏳ 速率限制重试，等待{delay:.1f}秒...")
                    else:
                        delay = min(base_delay * (2 ** attempt), 30.0)
                        logger.info(f"⏳ 第{attempt + 1}次尝试，等待{delay:.1f}秒...")
                    time.sleep(delay)
                
                logger.info(f"🌐 开始真实Firecrawl搜索: {query} (尝试 {attempt + 1}/{max_retries})")
                search_start_time = time.time()
                
                # 🔥 根本性修复：配置Firecrawl使用我们的SSL适配器
                import requests as firecrawl_requests
                
                # 创建一个配置好SSL的session
                configured_session = requests.Session()
                configured_session.headers.update(self.session.headers)
                
                # 挂载我们的SSL适配器
                ssl_adapter = SSLAdapter(
                    max_retries=3,
                    pool_connections=10,
                    pool_maxsize=10,
                )
                configured_session.mount('https://', ssl_adapter)
                configured_session.mount('http://', HTTPAdapter(max_retries=3))
                
                # 保存原始Session类
                original_session_class = firecrawl_requests.Session
                
                # 创建一个返回我们配置好的session的包装类
                class ConfiguredSession:
                    def __new__(cls):
                        return configured_session
                
                # 替换requests.Session
                firecrawl_requests.Session = ConfiguredSession
                
                try:
                    # 初始化Firecrawl客户端（会使用我们配置好的session）
                    firecrawl = FirecrawlApp(api_key=FIRECRAWL_API_KEY)
                    
                    # 执行搜索，带超时配置
                    search_response = firecrawl.search(query=query, limit=max_results)
                finally:
                    # 恢复原始Session类
                    firecrawl_requests.Session = original_session_class
                
                search_time = time.time() - search_start_time
                
                # 转换结果格式
                results = []
                logger.debug(f"🔍 Firecrawl响应类型: {type(search_response)}")
                
                # 处理 Firecrawl SearchResponse 对象
                if hasattr(search_response, 'success') and search_response.success and hasattr(search_response, 'data'):
                    search_data = search_response.data
                    logger.debug(f"🔍 搜索数据类型: {type(search_data)}, 长度: {len(search_data) if search_data else 0}")
                    
                    if search_data:  # search_data 是一个列表
                        for result in search_data:
                            results.append(SearchResult(
                                title=result.get('title', ''),
                                snippet=result.get('snippet', result.get('description', '')),
                                url=result.get('url', ''),
                                relevance_score=0.8  # Firecrawl不提供相关性分数，使用默认值
                            ))
                
                # 兼容字典格式响应（备用方案）
                elif isinstance(search_response, dict) and 'data' in search_response:
                    search_data = search_response['data']
                    if isinstance(search_data, list):
                        for result in search_data:
                            results.append(SearchResult(
                                title=result.get('title', ''),
                                snippet=result.get('snippet', result.get('description', '')),
                                url=result.get('url', ''),
                                relevance_score=0.8
                            ))
                    elif isinstance(search_data, dict) and 'web' in search_data:
                        for result in search_data['web']:
                            results.append(SearchResult(
                                title=result.get('title', ''),
                                snippet=result.get('snippet', result.get('description', '')),
                                url=result.get('url', ''),
                                relevance_score=0.8
                            ))
                
                logger.info(f"✅ 真实搜索成功: 找到{len(results)}个结果，耗时{search_time:.2f}秒")
                
                return SearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    search_time=search_time,
                    success=True
                )
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = e
                
                # 🔥 增强版：更精确的错误分类和处理
                if any(keyword in error_msg for keyword in ['rate', 'limit', '429', 'too many']):
                    logger.warning(f"⚠️ 遇到速率限制 (尝试 {attempt + 1}/{max_retries}): {e}")
                    
                    # 🔥 从错误消息中提取等待时间
                    wait_time = self._extract_retry_after_time(str(e))
                    if wait_time and wait_time > 0:
                        logger.info(f"📋 API建议等待时间: {wait_time}秒")
                        # 如果API建议的等待时间合理，使用它
                        if wait_time <= 120:  # 最多等待2分钟
                            time.sleep(wait_time)
                    
                    if attempt < max_retries - 1:
                        continue  # 继续重试
                    else:
                        logger.error(f"❌ 达到最大重试次数，速率限制仍然存在")
                        
                elif any(keyword in error_msg for keyword in ['timeout', 'connection', 'network']):
                    logger.warning(f"⚠️ 网络错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        continue  # 网络错误也重试
                    else:
                        logger.error(f"❌ 网络连接问题，所有重试都失败")
                        
                elif any(keyword in error_msg for keyword in ['auth', '401', '403', 'unauthorized']):
                    logger.error(f"❌ 认证错误，停止重试: {e}")
                    break  # 认证错误不重试
                    
                else:
                    # 其他未知错误
                    logger.error(f"❌ 真实Firecrawl搜索失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        continue  # 未知错误也重试一次
                    else:
                        break
        
        # 🔥 增强版：所有重试都失败了，提供详细的错误信息和建议
        logger.error("❌ 所有Firecrawl搜索尝试都失败了")
        
        # 生成详细的错误报告
        error_report = "Firecrawl搜索服务不可用，所有重试都失败"
        if last_error:
            error_msg = str(last_error).lower()
            if "rate" in error_msg or "limit" in error_msg:
                error_report = "Firecrawl API速率限制，建议稍后重试或升级计划"
            elif "auth" in error_msg:
                error_report = "Firecrawl API认证失败，请检查API密钥"
            elif "network" in error_msg or "connection" in error_msg:
                error_report = "网络连接问题，请检查网络状态"
        
        return SearchResponse(
            query=query,
            results=[],
            total_results=0,
            search_time=0.0,
            success=False,
            error_message=error_report
        )
    
    def _extract_retry_after_time(self, error_message: str) -> Optional[int]:
        """🔥 新增：从错误消息中提取建议的重试等待时间"""
        import re
        
        # 尝试匹配各种格式的重试时间
        patterns = [
            r'retry after (\d+)s',
            r'please retry after (\d+)s',
            r'wait (\d+) seconds',
            r'resets at.*?(\d+)s'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message.lower())
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _should_fallback_to_mock(self, error_message: Optional[str]) -> bool:
        """🔥 新增：判断是否应该回退到模拟搜索"""
        if not error_message:
            return True  # 没有错误信息，默认回退
        
        error_msg = error_message.lower()
        
        # 以下情况应该回退到模拟搜索
        fallback_conditions = [
            "rate" in error_msg and "limit" in error_msg,  # 速率限制
            "quota" in error_msg and "exceeded" in error_msg,  # 配额超限
            "429" in error_msg,  # HTTP 429错误
            "service unavailable" in error_msg,  # 服务不可用
            "timeout" in error_msg,  # 超时
            "network" in error_msg,  # 网络问题
        ]
        
        # 以下情况不应该回退（需要用户修复）
        no_fallback_conditions = [
            "auth" in error_msg,  # 认证问题
            "401" in error_msg,   # 未授权
            "403" in error_msg,   # 禁止访问
            "api key" in error_msg,  # API密钥问题
        ]
        
        # 检查不回退条件
        for condition in no_fallback_conditions:
            if condition:
                return False
        
        # 检查回退条件
        for condition in fallback_conditions:
            if condition:
                return True
        
        # 默认情况下回退（保守策略）
        return True
    
    def _search_firecrawl_mock(self, query: str, max_results: int) -> SearchResponse:
        """🔥 新增：模拟Firecrawl搜索结果"""
        logger.info(f"🎭 使用模拟搜索模式: {query}")
        
        # 模拟搜索延迟
        time.sleep(0.5)
        
        # 生成模拟结果
        mock_results = []
        
        # 根据查询生成相关的模拟结果
        if "实用务实" in query or "practical" in query.lower():
            mock_results = [
                SearchResult(
                    title="实用主义方法论 - 注重实际效果的解决方案",
                    snippet="实用务实型思维强调以结果为导向，注重可行性和立即执行。这种方法适用于需要快速解决的实际问题，通过务实的策略来达成目标。",
                    url="https://example.com/practical-methodology",
                    relevance_score=0.9
                ),
                SearchResult(
                    title="快速执行策略：从想法到实现",
                    snippet="探讨如何将抽象概念转化为具体的执行计划，包括优先级排序、资源分配和风险评估等关键要素。",
                    url="https://example.com/execution-strategy",
                    relevance_score=0.8
                ),
                SearchResult(
                    title="实际问题解决框架",
                    snippet="提供一套系统化的问题解决方法，强调实用性和可操作性，帮助快速识别和解决实际挑战。",
                    url="https://example.com/problem-solving-framework",
                    relevance_score=0.7
                )
            ]
        else:
            # 通用模拟结果
            mock_results = [
                SearchResult(
                    title=f"关于'{query[:30]}'的综合分析",
                    snippet=f"这是关于{query[:30]}的详细分析和解决方案，包含多个角度的深入探讨。",
                    url="https://example.com/analysis",
                    relevance_score=0.8
                ),
                SearchResult(
                    title=f"{query[:30]} - 实施指南",
                    snippet=f"提供{query[:30]}的具体实施步骤和最佳实践，帮助您快速上手。",
                    url="https://example.com/guide",
                    relevance_score=0.7
                ),
                SearchResult(
                    title=f"{query[:30]} - 案例研究",
                    snippet=f"通过真实案例展示{query[:30]}的应用场景和效果，为您提供参考。",
                    url="https://example.com/case-study",
                    relevance_score=0.6
                )
            ]
        
        # 限制结果数量
        mock_results = mock_results[:max_results]
        
        logger.info(f"🎭 模拟搜索完成: 生成{len(mock_results)}个结果")
        
        return SearchResponse(
            query=query,
            results=mock_results,
            total_results=len(mock_results),
            search_time=0.5,
            success=True,
            error_message=""
        )
    
    
    def _search_bing(self, query: str, max_results: int) -> SearchResponse:
        """使用Bing搜索（需要API密钥）"""
        logger.error("❌ Bing搜索未实现")
        return SearchResponse(
            query=query,
            results=[],
            total_results=0,
            search_time=0.0,
            success=False,
            error_message="Bing搜索功能未实现，请使用Firecrawl搜索"
        )
    
    def _update_search_stats(self, search_time: float, success: bool):
        """更新搜索统计"""
        self.search_stats['total_searches'] += 1
        if success:
            self.search_stats['successful_searches'] += 1
        
        self.search_stats['total_search_time'] += search_time
        self.search_stats['avg_search_time'] = (
            self.search_stats['total_search_time'] / self.search_stats['total_searches']
        )
    
    def get_search_stats(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        return self.search_stats.copy()

class IdeaVerificationSearchClient:
    """想法验证专用搜索客户端"""
    
    def __init__(self, web_search_client: WebSearchClient, semantic_analyzer=None):
        """
        初始化想法验证搜索客户端
        
        Args:
            web_search_client: 网络搜索客户端
            semantic_analyzer: 语义分析器（可选）
        """
        self.web_search_client = web_search_client
        self.semantic_analyzer = semantic_analyzer
        self.verification_cache = {}  # 验证结果缓存
        
        logger.info("🔍 IdeaVerificationSearchClient初始化完成")
    
    def search_for_idea_verification(self, idea_text: str, context: Optional[Dict] = None) -> SearchResponse:
        """
        为想法验证进行专门的搜索
        
        Args:
            idea_text: 需要验证的想法文本
            context: 上下文信息
            
        Returns:
            SearchResponse: 搜索响应
        """
        logger.info(f"🔍 [验证搜索] 开始为想法验证进行搜索")
        logger.info(f"🔍 [验证搜索] 想法文本长度: {len(idea_text)} 字符")
        logger.info(f"🔍 [验证搜索] 上下文: {context}")
        
        # 检查缓存
        cache_key = f"{idea_text}_{hash(str(context))}"
        if cache_key in self.verification_cache:
            logger.info(f"✅ [验证搜索] 使用缓存的搜索结果")
            return self.verification_cache[cache_key]
        
        # 构建搜索查询
        logger.info(f"🔍 [验证搜索] 构建搜索查询...")
        search_query = self._build_verification_query(idea_text, context)
        logger.info(f"🔍 [验证搜索] 搜索查询: {search_query}")
        
        # 执行搜索
        logger.info(f"🔍 [验证搜索] 调用WebSearchClient进行搜索...")
        try:
            search_response = self.web_search_client.search(search_query, max_results=5)
            
            if search_response.success:
                logger.info(f"✅ [验证搜索] 搜索成功，找到 {len(search_response.results)} 个结果")
                # 缓存结果
                self.verification_cache[cache_key] = search_response
            else:
                logger.warning(f"⚠️ [验证搜索] 搜索失败: {search_response.error_message}")
            
            return search_response
            
        except Exception as e:
            logger.error(f"❌ [验证搜索] 搜索过程出错: {e}")
            # 返回空的搜索响应
            return SearchResponse(
                query=search_query,
                results=[],
                total_results=0,
                search_time=0.0,
                success=False,
                error_message=str(e)
            )
    
    def _build_verification_query(self, idea_text: str, context: Optional[Dict] = None) -> str:
        """
        构建用于想法验证的搜索查询
        
        Args:
            idea_text: 想法文本（思维种子）
            context: 上下文信息
            
        Returns:
            str: 搜索查询字符串
        """
        # 🔥 调试：打印上下文信息
        logger.info(f"🔍 _build_verification_query 接收到的context: {context}")
        
        # 🔥 优先使用LLM整合思维种子和用户查询
        user_query = None
        if context:
            user_query = context.get('user_query') or context.get('original_query')
            logger.info(f"🔍 从context中提取的user_query: {user_query}")
        
        if user_query and self.semantic_analyzer:
            # 使用LLM整合思维种子和用户原始查询
            logger.info(f"🎯 检测到用户查询，尝试LLM整合: {user_query[:30]}...")
            integrated_query = self._llm_integrate_seed_and_query(idea_text, user_query, context)
            logger.info(f"🧠 LLM整合查询结果: {integrated_query}")
            return integrated_query
        else:
            if not user_query:
                logger.warning("⚠️ 未检测到用户查询，使用传统方法")
            if not self.semantic_analyzer:
                logger.warning("⚠️ 语义分析器不可用，使用传统方法")
        
        # 🔥 修复：回退到传统方法时，优先使用用户查询
        # 检查上下文中是否有用户查询
        if context and ('user_query' in context or 'original_query' in context):
            user_query_fallback = context.get('user_query') or context.get('original_query')
            if user_query_fallback:
                logger.info(f"🔄 使用传统回退方法，基于用户查询: {user_query_fallback[:40]}")
                return self._fallback_integrate_query(idea_text, user_query_fallback, context)
        
        # 如果没有用户查询，使用简单的文本截取
        # 使用原始文本的前50个字符作为查询
        query = idea_text[:50].strip()
        
        # 添加上下文信息（如果有具体领域）
        if context and 'domain' in context:
            domain = context['domain']
            # 只有在domain不是通用词时才添加
            if domain and domain not in ['general', 'unknown', '通用']:
                query = f"{query} {domain}"
        
        logger.debug(f"🔍 构建验证查询（传统方法）: {query}")
        return query
    
    
    def _llm_integrate_seed_and_query(self, thinking_seed: str, user_query: str, context: Optional[Dict] = None) -> str:
        """
        使用LLM整合思维种子和用户原始查询，生成更相关的搜索查询
        
        🎯 核心原则：搜索查询必须聚焦于用户问题的核心内容，而不是思维路径的方法论
        
        Args:
            thinking_seed: 第一阶段生成的思维种子（仅作为辅助参考）
            user_query: 用户原始查询（主要信息来源）
            context: 上下文信息
            
        Returns:
            str: LLM整合后的搜索查询
        """
        try:
            # 关键修复：注入当前时间信息
            from datetime import datetime
            now = datetime.now()
            current_year = now.year
            current_time_info = f"""
📅 **重要时间信息** (生成搜索查询时必须参考):
- 当前年份: {current_year}年
- 当前日期: {now.strftime('%Y年%m月%d日')}
"""
            
            # 🔥 修复后的LLM提示 - 强调搜索用户问题的核心内容
            integration_prompt = f"""你的任务是为用户查询生成一个精准的搜索查询字符串。

{current_time_info}

**用户的问题：**
{user_query}

**AI建议的思考角度（仅供参考）：**
{thinking_seed[:200]}

**🎯 核心任务：**
生成一个网络搜索查询，用于查找能够**直接回答用户问题**的信息。

**⚠️ 关键原则：**
1. ✅ **必须做**：提取用户查询中的核心主题、关键实体、具体问题
   - 例如：用户问"ChatGPT最新模型"，应搜索"ChatGPT 模型 {current_year}"
   - 例如：用户问"Python爬虫技术"，应搜索"Python 爬虫技术 教程"

2. ❌ **禁止做**：搜索思维种子中的抽象方法论词汇
   - 禁止搜索："系统分析方法"、"实用务实型解决方案"、"批判性思维"等
   - 禁止搜索："可行性"、"验证"、"评估"等验证类词汇

3. 🎯 **搜索目标**：找到能直接回答用户问题的事实、数据、案例、教程
   - 搜索用户想知道的**具体内容**，而不是如何思考这个问题

4. ⏰ **时间处理**：
   - 如果用户问"最新"、"当前"、"{current_year}年"，搜索查询必须包含当前年份
   - 避免使用过时的年份信息

**输出要求：**
- 直接输出一个简洁的搜索查询字符串（30字以内）
- 不要解释，不要添加引号
- 专注于用户问题的核心关键词

搜索查询："""

            # 调用语义分析器的LLM功能
            if hasattr(self.semantic_analyzer, 'llm_manager') and self.semantic_analyzer.llm_manager:
                logger.info("🔧 使用语义分析器的LLM管理器进行整合")
                try:
                    # 使用LLM管理器的chat_completion方法
                    response = self.semantic_analyzer.llm_manager.chat_completion(
                        messages=[{"role": "user", "content": integration_prompt}],
                        temperature=0.1,
                        max_tokens=200
                    )
                    
                    if response and response.content and response.content.strip():
                        integrated_query = response.content.strip()
                        logger.info(f"🧠 LLM成功整合查询: {user_query[:30]}... -> {integrated_query}")
                        return integrated_query
                    else:
                        logger.warning("⚠️ LLM返回空响应，使用回退方法")
                except Exception as e:
                    logger.error(f"❌ LLM调用失败: {e}")
            else:
                logger.warning("⚠️ 语义分析器缺少LLM管理器，使用回退方法")
                
        except Exception as e:
            logger.error(f"❌ LLM整合查询失败: {e}")
        
        # 回退方法：简单组合用户查询和思维种子关键词
        return self._fallback_integrate_query(thinking_seed, user_query, context)
    
    def _fallback_integrate_query(self, thinking_seed: str, user_query: str, context: Optional[Dict] = None) -> str:
        """
        回退方法：简单整合思维种子和用户查询
        
        🎯 核心原则：优先使用用户查询的核心内容，避免添加抽象的方法论词汇
        
        Args:
            thinking_seed: 思维种子（辅助参考）
            user_query: 用户查询（主要来源）
            context: 上下文
            
        Returns:
            str: 整合后的搜索查询
        """
        import re
        from datetime import datetime
        
        # 🔥 修复：直接提取用户查询的核心内容
        # 移除常见的方法论词汇，保留实际问题
        method_keywords_to_remove = [
            '实用务实型', '解决方案', '系统分析', '批判性思维', '探索性研究',
            '创新思维', '方法', '策略', '思路', '方案', '角度', '途径'
        ]
        
        # 清理用户查询
        cleaned_query = user_query
        for keyword in method_keywords_to_remove:
            cleaned_query = cleaned_query.replace(keyword, ' ')
        
        # 移除多余空格
        cleaned_query = ' '.join(cleaned_query.split())
        
        # 提取关键实体和主题词（保留中英文、数字）
        # 优先保留：专有名词、技术术语、具体概念
        core_keywords = re.findall(r'[A-Z][a-zA-Z]+|[a-z]+|[\u4e00-\u9fa5]{2,}|\d+', cleaned_query)
        
        # 如果提取的关键词太少，直接使用清理后的查询
        if len(core_keywords) < 2:
            query = cleaned_query[:60].strip()
        else:
            # 重建查询，保留核心关键词
            query = ' '.join(core_keywords[:8])  # 最多8个关键词
        
        # 检查时间相关词汇，添加当前年份
        time_keywords = ['最新', '当前', '今年', '现在', '新版', '最近']
        has_time_keyword = any(kw in user_query for kw in time_keywords)
        
        if has_time_keyword:
            current_year = datetime.now().year
            # 避免重复添加年份
            if str(current_year) not in query:
                query = f"{query} {current_year}"
        
        # 🎯 最终查询：优先使用核心内容，避免添加"方法"、"实践"等通用词
        query = query.strip()
        
        logger.info(f"🔄 回退整合查询: {user_query[:40]} -> {query}")
        return query
    
    def verify_idea_feasibility(self, idea_text: str, context: Optional[Dict] = None) -> IdeaVerificationResult:
        """
        验证想法的可行性
        
        Args:
            idea_text: 需要验证的想法文本
            context: 上下文信息
            
        Returns:
            IdeaVerificationResult: 验证结果
        """
        try:
            logger.info(f"🔍 [可行性验证] 开始验证想法可行性: {idea_text[:50]}...")
            logger.info(f"🔍 [可行性验证] 上下文: {context}")
            
            # 执行专门的验证搜索
            logger.info(f"🔍 [可行性验证] 调用search_for_idea_verification...")
            search_response = self.search_for_idea_verification(idea_text, context)
            logger.info(f"🔍 [可行性验证] 搜索完成，成功: {search_response.success}")
            logger.info(f"🔍 [可行性验证] 搜索结果数: {len(search_response.results)}")
            
            if not search_response.success:
                # 🔥 增强版：搜索失败时提供更好的用户体验
                logger.warning(f"⚠️ [可行性验证] 搜索失败，使用回退分析: {search_response.error_message}")
                
                # 即使搜索失败，也尝试提供基础的可行性分析
                fallback_analysis = self._generate_fallback_analysis(idea_text, search_response.error_message)
                
                return IdeaVerificationResult(
                    idea_text=idea_text,
                    feasibility_score=fallback_analysis['score'],
                    analysis_summary=fallback_analysis['summary'],
                    search_results=[],
                    success=True,  # 🔥 标记为成功，因为我们提供了回退分析
                    error_message=f"搜索服务不可用，提供基础分析: {search_response.error_message}"
                )
            
            # 提取用户查询用于LLM评分
            user_query = None
            if context:
                user_query = context.get('user_query') or context.get('original_query') or context.get('query')
            
            # 分析搜索结果计算可行性分数（传入user_query用于LLM评分）
            feasibility_score = self._calculate_feasibility_score(
                search_response.results, 
                idea_text, 
                user_query=user_query,
                context=context
            )
            
            # 生成分析摘要
            analysis_summary = self._generate_analysis_summary(search_response.results, idea_text, feasibility_score)
            
            logger.info(f"✅ 想法验证完成 - 可行性分数: {feasibility_score:.2f}")
            
            return IdeaVerificationResult(
                idea_text=idea_text,
                feasibility_score=feasibility_score,
                analysis_summary=analysis_summary,
                search_results=search_response.results,
                success=True,
                error_message=""
            )
            
        except Exception as e:
            logger.error(f"❌ 想法验证失败: {e}")
            return IdeaVerificationResult(
                idea_text=idea_text,
                feasibility_score=0.0,
                analysis_summary=f"验证过程发生错误: {str(e)}",
                search_results=[],
                success=False,
                error_message=str(e)
            )
    
    def _calculate_feasibility_score(self, search_results: List[SearchResult], idea_text: str, 
                                     user_query: str = None, context: Optional[Dict] = None) -> float:
        """
        🔥 完全基于LLM语义分析计算可行性分数
        
        改进：
        1. 完全依赖LLM语义相关度评分（摒弃关键词匹配）
        2. 根据问题类型进行精准评估
        3. LLM不可用时使用保守的默认分数
        
        Args:
            search_results: 搜索结果列表
            idea_text: 想法文本
            user_query: 用户原始查询（用于LLM评分）
            context: 上下文信息
            
        Returns:
            float: 可行性分数 (0.0-1.0)
        """
        if not search_results:
            return 0.1  # 如果没有搜索结果，给一个很低的分数
        
        # 🎯 检测问题类型（知识科普 vs 技术实现）
        query_type = self._detect_query_type(user_query or idea_text)
        logger.info(f"🎯 检测到问题类型: {query_type}")
        
        # 🔥 使用LLM进行语义相关度评分
        llm_semantic_score = self._calculate_llm_semantic_relevance(
            search_results, idea_text, user_query, context
        )
        
        if llm_semantic_score is not None:
            # LLM可用：直接使用语义评分
            final_score = llm_semantic_score
            logger.info(f"✅ LLM语义评分: {final_score:.3f} (问题类型: {query_type})")
        else:
            # LLM不可用：使用保守的默认评分
            # 基于搜索结果数量给出保守估计
            result_count = len(search_results)
            if result_count >= 5:
                final_score = 0.6  # 有足够多结果，中等偏上
            elif result_count >= 3:
                final_score = 0.5  # 有一些结果，中等
            else:
                final_score = 0.4  # 结果较少，中等偏下
            logger.warning(f"⚠️ LLM不可用，使用保守默认评分: {final_score:.3f} (基于{result_count}个搜索结果)")
        
        # 确保分数在合理范围内
        final_score = max(0.0, min(1.0, final_score))
        
        return final_score
    
    def _detect_query_type(self, text: str) -> str:
        """
        检测查询类型
        
        Returns:
            "knowledge": 知识科普类（了解、学习、介绍）
            "implementation": 技术实现类（实现、开发、构建）
            "general": 通用类型
        """
        text_lower = text.lower()
        
        # 知识科普类关键词
        knowledge_keywords = [
            '了解', '学习', '知识', '什么是', '介绍', '解释', '理解', '认识',
            'learn', 'know', 'understand', 'what is', 'introduce', 'explain'
        ]
        
        # 技术实现类关键词
        implementation_keywords = [
            '实现', '开发', '构建', '设计', '创建', '搭建', '编写', '制作',
            'implement', 'develop', 'build', 'create', 'design', 'code', 'make'
        ]
        
        knowledge_matches = sum(1 for kw in knowledge_keywords if kw in text_lower)
        implementation_matches = sum(1 for kw in implementation_keywords if kw in text_lower)
        
        if knowledge_matches > implementation_matches and knowledge_matches > 0:
            return "knowledge"
        elif implementation_matches > knowledge_matches and implementation_matches > 0:
            return "implementation"
        else:
            return "general"
    
    def _calculate_llm_semantic_relevance(self, search_results: List[SearchResult], 
                                          idea_text: str, user_query: str = None,
                                          context: Optional[Dict] = None) -> Optional[float]:
        """
        🔥 使用LLM进行语义相关度评分（核心创新）
        
        Args:
            search_results: 搜索结果列表
            idea_text: 想法文本
            user_query: 用户原始查询
            context: 上下文信息
            
        Returns:
            Optional[float]: 语义相关度分数 (0.0-1.0)，如果LLM不可用则返回None
        """
        # 检查语义分析器是否可用
        if not self.semantic_analyzer or not hasattr(self.semantic_analyzer, 'llm_manager'):
            logger.warning("⚠️ 语义分析器不可用，跳过LLM评分")
            return None
        
        if not self.semantic_analyzer.llm_manager:
            logger.warning("⚠️ LLM管理器不可用，跳过LLM评分")
            return None
        
        try:
            # 准备搜索结果摘要（取前3个结果）
            search_summary = self._format_search_results_for_llm(search_results[:3])
            
            # 构建LLM评分提示词
            evaluation_prompt = f"""你是一个专业的信息相关性评估专家。请评估搜索结果与用户问题的相关性。

**用户原始问题：**
{user_query or idea_text}

**AI思考要点：**
{idea_text[:300]}

**搜索结果摘要：**
{search_summary}

**评估维度：**
请从以下三个维度评估搜索结果的质量（每个维度0.0-1.0分）：

1. **内容相关性 (relevance)**：搜索结果是否直接回答了用户的问题？
   - 1.0: 完全相关，直接回答问题
   - 0.7: 高度相关，提供了有用信息
   - 0.4: 部分相关，有一些关联
   - 0.0: 完全不相关

2. **信息质量 (quality)**：搜索结果的内容质量如何？
   - 1.0: 信息详细、权威、准确
   - 0.7: 信息较为完整和可靠
   - 0.4: 信息简单但基本准确
   - 0.0: 信息不足或不可靠

3. **实用价值 (actionability)**：搜索结果对用户是否有实用价值？
   - 1.0: 提供了明确的答案或可行的建议
   - 0.7: 提供了有价值的信息或思路
   - 0.4: 提供了一些参考价值
   - 0.0: 缺乏实用价值

**输出要求：**
请仅返回JSON格式，不要其他内容：
{{
    "relevance": 0.0-1.0的相关性分数,
    "quality": 0.0-1.0的质量分数,
    "actionability": 0.0-1.0的实用价值分数,
    "explanation": "简短说明评分理由（1-2句话）"
}}"""

            logger.info("🔍 [LLM评分] 调用语义分析器进行评分...")
            
            # 调用LLM
            response = self.semantic_analyzer.llm_manager.chat_completion(
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1,  # 低温度保证评分稳定
                max_tokens=300
            )
            
            if response and response.success and response.content:
                # 解析JSON响应
                from ..providers.rag_seed_generator import parse_json_response
                result_data = parse_json_response(response.content)
                
                if result_data and all(k in result_data for k in ['relevance', 'quality', 'actionability']):
                    # 计算综合分数（三个维度的加权平均）
                    relevance = float(result_data['relevance'])
                    quality = float(result_data['quality'])
                    actionability = float(result_data['actionability'])
                    
                    # 加权：相关性40%，质量30%，实用价值30%
                    semantic_score = relevance * 0.4 + quality * 0.3 + actionability * 0.3
                    
                    explanation = result_data.get('explanation', '')
                    logger.info(f"✅ [LLM评分] 相关性:{relevance:.2f} 质量:{quality:.2f} 实用:{actionability:.2f} → 综合:{semantic_score:.3f}")
                    logger.info(f"💡 [LLM评分] 评分理由: {explanation}")
                    
                    return semantic_score
                else:
                    logger.warning(f"⚠️ [LLM评分] JSON解析不完整: {result_data}")
                    return None
            else:
                logger.warning(f"⚠️ [LLM评分] LLM调用失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ [LLM评分] 语义相关度评分失败: {e}")
            return None
    
    def _format_search_results_for_llm(self, search_results: List[SearchResult]) -> str:
        """格式化搜索结果供LLM评估"""
        if not search_results:
            return "未找到搜索结果"
        
        formatted = []
        for i, result in enumerate(search_results, 1):
            formatted.append(f"{i}. 标题: {result.title}")
            formatted.append(f"   摘要: {result.snippet[:150]}...")
            formatted.append("")
        
        return "\n".join(formatted)
    
    def _generate_analysis_summary(self, search_results: List[SearchResult], 
                                 idea_text: str, feasibility_score: float) -> str:
        """
        生成分析摘要
        
        Args:
            search_results: 搜索结果
            idea_text: 想法文本
            feasibility_score: 可行性分数
            
        Returns:
            str: 分析摘要
        """
        if not search_results:
            return "未找到相关信息，可行性分析受限。"
        
        # 根据可行性分数生成基础评估
        if feasibility_score >= 0.8:
            base_assessment = "该想法具有很高的可行性"
        elif feasibility_score >= 0.6:
            base_assessment = "该想法具有较好的可行性" 
        elif feasibility_score >= 0.4:
            base_assessment = "该想法具有一定的可行性，但需要谨慎评估"
        elif feasibility_score >= 0.2:
            base_assessment = "该想法可行性较低，存在较大挑战"
        else:
            base_assessment = "该想法可行性很低，实现困难"
        
        # 提取关键信息
        key_findings = []
        
        # 统计相关结果数量
        key_findings.append(f"搜索到{len(search_results)}个相关结果")
        
        # 分析搜索结果质量（基于内容长度）
        if search_results:
            has_detailed_content = sum(1 for r in search_results if len(r.snippet) > 50)
            if has_detailed_content >= len(search_results) * 0.6:
                key_findings.append("找到了详细的相关资料")
            else:
                key_findings.append("相关资料有限")
        
        # 构建完整摘要
        summary_parts = [base_assessment]
        
        if key_findings:
            summary_parts.append("。分析发现：" + "，".join(key_findings))
        
        summary_parts.append(f"。综合评估可行性得分为{feasibility_score:.1f}/1.0。")
        
        return "".join(summary_parts)
    
    def _generate_fallback_analysis(self, idea_text: str, error_message: str) -> Dict[str, Any]:
        """
        🔥 新增：当搜索失败时生成回退分析
        
        Args:
            idea_text: 想法文本
            error_message: 错误消息
            
        Returns:
            Dict: 包含score和summary的分析结果
        """
        logger.info(f"🎭 生成回退分析: {idea_text[:50]}...")
        
        # 基于文本内容的简单可行性评估
        score = 0.5  # 默认中等可行性
        
        # 关键词分析
        tech_indicators = [
            'API', 'api', '算法', '数据库', '系统', '架构', '优化',
            '机器学习', 'ML', 'AI', '人工智能', '深度学习',
            '网络', '爬虫', '数据分析', '实时', '性能', '安全'
        ]
        
        positive_indicators = [
            '简单', '基础', '标准', '常见', '成熟', '开源',
            'simple', 'basic', 'standard', 'common', 'mature'
        ]
        
        challenging_indicators = [
            '复杂', '高级', '创新', '前沿', '实验', '研究',
            'complex', 'advanced', 'innovative', 'cutting-edge'
        ]
        
        text_lower = idea_text.lower()
        
        # 技术复杂度评估
        tech_count = sum(1 for indicator in tech_indicators if indicator.lower() in text_lower)
        positive_count = sum(1 for indicator in positive_indicators if indicator in text_lower)
        challenging_count = sum(1 for indicator in challenging_indicators if indicator in text_lower)
        
        # 调整分数
        if tech_count > 0:
            score += 0.1  # 有技术关键词，稍微提高可行性
        
        if positive_count > challenging_count:
            score += 0.2  # 更多正面指标
        elif challenging_count > positive_count:
            score -= 0.1  # 更多挑战性指标
        
        # 文本长度影响（更详细的描述通常更可行）
        if len(idea_text) > 100:
            score += 0.1
        elif len(idea_text) < 50:
            score -= 0.1
        
        # 确保分数在合理范围内
        score = max(0.1, min(0.9, score))
        
        # 生成分析摘要
        summary_parts = [
            f"基于文本分析，「{idea_text[:50]}{'...' if len(idea_text) > 50 else ''}」"
        ]
        
        if score >= 0.7:
            summary_parts.append("显示出较高的可行性")
        elif score >= 0.5:
            summary_parts.append("具有中等可行性")
        else:
            summary_parts.append("可行性相对较低")
        
        # 添加技术评估
        if tech_count > 2:
            summary_parts.append("，涉及多项技术要素")
        elif tech_count > 0:
            summary_parts.append("，包含技术实现要素")
        
        # 添加复杂度评估
        if challenging_count > positive_count:
            summary_parts.append("，但实现难度较高")
        elif positive_count > 0:
            summary_parts.append("，实现相对简单")
        
        # 添加搜索失败说明
        summary_parts.append("。由于搜索服务暂时不可用，此分析基于文本内容进行")
        
        if "rate" in error_message.lower() or "limit" in error_message.lower():
            summary_parts.append("，建议稍后重试获取更详细的验证结果")
        else:
            summary_parts.append("，建议检查网络连接后重试")
        
        summary = "".join(summary_parts)
        
        logger.info(f"🎭 回退分析完成: 可行性{score:.2f}")
        
        return {
            'score': score,
            'summary': summary
        }
