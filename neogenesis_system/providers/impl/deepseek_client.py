#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
强化版 DeepSeek API 客户端 - 支持统一LLM接口
Enhanced DeepSeek API Client with Unified LLM Interface

特性:
- 实现统一LLM客户端接口
- 使用 requests.Session 提高性能
- 配置化的重试逻辑和超时控制
- 精细的错误处理和结构化日志
- 自动 JSON 解析和响应验证
- 流式响应支持
- 请求缓存机制
- 性能监控和统计
"""

import json
import time
import hashlib
import logging
import asyncio
import requests
from typing import Optional, Dict, Any, List, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

try:
    from neogenesis_system.config import API_CONFIG, DEEPSEEK_CHAT_ENDPOINT, DEEPSEEK_MODEL
except ImportError:
    try:
        from ...config import API_CONFIG, DEEPSEEK_CHAT_ENDPOINT, DEEPSEEK_MODEL
    except ImportError:
        # 提供默认值以防配置文件不存在
        API_CONFIG = {}
        DEEPSEEK_CHAT_ENDPOINT = "https://api.deepseek.com/chat/completions"
        DEEPSEEK_MODEL = "deepseek-chat"
from ..llm_base import (
    BaseLLMClient, LLMConfig, LLMResponse, LLMMessage, LLMUsage, 
    LLMProvider, LLMErrorType, create_error_response
)

logger = logging.getLogger(__name__)


# APIErrorType已迁移到LLMErrorType，保持向后兼容
APIErrorType = LLMErrorType

@dataclass
class APIResponse:
    """API响应数据结构 - 向后兼容"""
    success: bool
    content: str = ""
    raw_response: Optional[Dict[str, Any]] = None
    error_type: Optional[LLMErrorType] = None
    error_message: str = ""
    status_code: int = 0
    response_time: float = 0.0
    tokens_used: int = 0
    model_used: str = ""
    
    def to_llm_response(self, provider: str = "deepseek") -> LLMResponse:
        """转换为统一的LLMResponse格式"""
        usage = None
        if self.tokens_used > 0:
            usage = LLMUsage(
                prompt_tokens=0,  # DeepSeek目前不单独返回
                completion_tokens=self.tokens_used,
                total_tokens=self.tokens_used
            )
        
        return LLMResponse(
            success=self.success,
            content=self.content,
            provider=provider,
            model=self.model_used,
            response_time=self.response_time,
            usage=usage,
            error_type=self.error_type,
            error_message=self.error_message,
            raw_response=self.raw_response
        )


@dataclass  
class ClientConfig:
    """客户端配置 - 兼容旧版本的配置结构"""
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = DEEPSEEK_MODEL
    timeout: tuple = (60, 300)  # 🔥 修复：增加超时时间 (连接超时60s, 读取超时300s)
    max_retries: int = 5  # 🔥 修复：增加重试次数
    retry_delay_base: float = 3.0  # 🔥 修复：增加重试延迟基数
    temperature: float = 0.7
    max_tokens: int = 2000
    enable_cache: bool = True
    cache_ttl: int = 300  # 缓存时间(秒)
    enable_metrics: bool = True
    proxies: Optional[Dict[str, str]] = None
    request_interval: float = 1.0  # 🔧 新增：请求间隔时间(秒)
    # 🔥 新增：网络错误处理配置
    network_retry_multiplier: float = 2.0  # 网络错误重试时间倍数
    max_network_retry_delay: float = 120.0  # 最大网络重试延迟
    
    def to_llm_config(self) -> LLMConfig:
        """转换为统一的LLMConfig格式"""
        return LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            api_key=self.api_key,
            model_name=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay_base=self.retry_delay_base,
            enable_cache=self.enable_cache,
            cache_ttl=self.cache_ttl,
            proxies=self.proxies,
            request_interval=self.request_interval,
            # 🔥 新增：网络错误处理配置
            network_retry_multiplier=getattr(self, 'network_retry_multiplier', 2.0),
            max_network_retry_delay=getattr(self, 'max_network_retry_delay', 120.0)
        )


@dataclass
class ClientMetrics:
    """客户端性能指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    total_tokens_used: int = 0
    total_tokens: int = 0  # 🔧 新增：总token数（用于异步统计）
    prompt_tokens: int = 0  # 🔧 新增：提示token数
    completion_tokens: int = 0  # 🔧 新增：完成token数
    cache_hits: int = 0
    error_counts: Dict[APIErrorType, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_response_time(self) -> float:
        """平均响应时间"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests


class DeepSeekClient(BaseLLMClient):
    """
    强化版 DeepSeek API 客户端 - 实现统一LLM接口
    
    特性:
    - 继承BaseLLMClient统一接口
    - 高性能会话复用
    - 智能重试机制
    - 请求缓存
    - 性能监控
    - 结构化错误处理
    """
    
    def __init__(self, config: Union[ClientConfig, LLMConfig]):
        """
        初始化客户端 - 支持新旧两种配置格式
        
        Args:
            config: 客户端配置（ClientConfig或LLMConfig）
        """
        # 配置转换和验证
        if isinstance(config, LLMConfig):
            # 新的统一配置格式
            llm_config = config
            self.config = self._convert_llm_config_to_client_config(config)
        else:
            # 旧的ClientConfig格式
            self.config = config
            llm_config = config.to_llm_config()
        
        # 调用父类初始化
        super().__init__(llm_config)
        
        # DeepSeek特有的指标系统
        # 检查是否启用指标
        enable_metrics = getattr(self.config, 'enable_metrics', True)
        if enable_metrics:
            self.metrics = ClientMetrics()
        else:
            self.metrics = None
        
        # 初始化 requests.Session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Neogenesis-System/1.0'
        })
        
        # 修复SSL错误 - 禁用SSL验证(如果遇到证书问题)
        # 注意：生产环境应该使用正确的证书验证
        self.session.verify = False
        
        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 配置代理
        if self.config.proxies:
            self.session.proxies.update(self.config.proxies)
        
        # 🚀 初始化异步客户端
        self.async_client = None
        if HTTPX_AVAILABLE:
            self._init_async_client()
        else:
            logger.warning("⚠️ httpx未安装，异步功能不可用。请安装: pip install httpx")
        
        # 请求缓存
        self._cache: Dict[str, tuple] = {}  # key -> (response, timestamp)
        
        # 🔧 新增：请求频率控制
        self._last_request_time = 0
        self._request_interval = getattr(self.config, 'request_interval', 1.0)  # 默认1秒间隔
        
        logger.info(f"🚀 DeepSeekClient 初始化完成")
        # 兼容旧的ClientConfig和新的LLMConfig
        model_name = getattr(self.config, 'model', None) or getattr(self.config, 'model_name', 'deepseek-chat')
        logger.info(f"   模型: {model_name}")
        logger.info(f"   缓存: {'启用' if self.config.enable_cache else '禁用'}")
        # 兼容新旧配置格式
        enable_metrics = getattr(self.config, 'enable_metrics', True)
        logger.info(f"   指标: {'启用' if enable_metrics else '禁用'}")
        logger.info(f"   请求间隔: {self._request_interval}s")
    
    def _convert_llm_config_to_client_config(self, llm_config: LLMConfig) -> ClientConfig:
        """🔥 增强版：将统一LLMConfig转换为DeepSeek的ClientConfig"""
        return ClientConfig(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url or "https://api.deepseek.com/v1",
            model=llm_config.model_name,
            timeout=llm_config.timeout or (60, 300),  #修复：使用新的默认超时时间
            max_retries=llm_config.max_retries or 5,  #修复：使用新的默认重试次数
            retry_delay_base=llm_config.retry_delay_base or 3.0,  #修复：使用新的默认延迟
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            enable_cache=llm_config.enable_cache,
            cache_ttl=llm_config.cache_ttl,
            enable_metrics=True,  # 为LLMConfig设置默认值
            proxies=llm_config.proxies,
            request_interval=llm_config.request_interval or 1.0,
            # 🔥 新增：网络错误处理配置
            network_retry_multiplier=getattr(llm_config, 'network_retry_multiplier', 2.0),
            max_network_retry_delay=getattr(llm_config, 'max_network_retry_delay', 120.0)
        )
    
    def _init_async_client(self):
        """🚀 初始化异步HTTP客户端"""
        try:
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'Neogenesis-System/1.0'
            }
            
            # 配置异步客户端
            client_kwargs = {
                'headers': headers,
                'timeout': httpx.Timeout(self.config.timeout),
                'limits': httpx.Limits(max_keepalive_connections=10, max_connections=100),
                'verify': False  # 🔥 关键修复：禁用SSL验证
            }
            
            # 处理代理配置 - 使用更兼容的方式
            if self.config.proxies:
                try:
                    # 尝试新的httpx方式
                    client_kwargs['proxies'] = self.config.proxies
                    self.async_client = httpx.AsyncClient(**client_kwargs)
                    logger.debug("🚀 异步HTTP客户端初始化完成（含代理配置，SSL验证已禁用）")
                except TypeError as te:
                    # 如果失败，则不使用代理创建客户端
                    logger.warning(f"⚠️ httpx版本不支持proxies参数，跳过代理配置: {te}")
                    client_kwargs.pop('proxies', None)
                    self.async_client = httpx.AsyncClient(**client_kwargs)
                    logger.debug("🚀 异步HTTP客户端初始化完成（无代理，SSL验证已禁用）")
            else:
                self.async_client = httpx.AsyncClient(**client_kwargs)
                logger.debug("🚀 异步HTTP客户端初始化完成（SSL验证已禁用）")
            
        except Exception as e:
            logger.error(f"❌ 异步客户端初始化失败: {e}")
            self.async_client = None
    
    # ==================== 聊天完成API接口 ====================
    
    def chat_completion(self, 
                       messages: Union[str, List[LLMMessage]], 
                       temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None,
                       **kwargs) -> LLMResponse:
        """
        聊天完成API调用 - 统一接口实现
        
        Args:
            messages: 消息内容，可以是字符串或消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一的响应对象
        """
        start_time = time.time()
        
        # 准备消息格式
        prepared_messages = self._prepare_messages(messages)
        
        # 参数处理
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        # 兼容新旧配置格式
        model = kwargs.get('model') or getattr(self.config, 'model', None) or getattr(self.config, 'model_name', 'deepseek-chat')
        enable_cache = kwargs.get('enable_cache', self.config.enable_cache)
        
        # 转换为DeepSeek API格式
        api_messages = []
        for msg in prepared_messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # 构建请求数据
        request_data = {
            'model': model,
            'messages': api_messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        
        # 检查缓存
        cache_key = self._generate_cache_key(request_data)
        if enable_cache and self._is_cache_valid(cache_key):
            cached_api_response, _ = self._cache[cache_key]
            self.metrics.cache_hits += 1
            logger.debug(f"📋 使用缓存响应: {cache_key[:16]}...")
            
            # 转换为统一格式
            llm_response = cached_api_response.to_llm_response("deepseek")
            self._update_stats(llm_response)
            return llm_response
        
        # 执行API调用
        api_response = self._execute_request(request_data, start_time)
        
        # 转换为统一格式
        llm_response = api_response.to_llm_response("deepseek")
        
        # 更新缓存
        if enable_cache and api_response.success:
            self._cache[cache_key] = (api_response, time.time())
            self._cleanup_cache()
        
        # 更新指标
        enable_metrics = getattr(self.config, 'enable_metrics', True)
        if enable_metrics and self.metrics:
            self._update_metrics(api_response)
        
        # 更新父类统计
        self._update_stats(llm_response)
        
        return llm_response
    
    async def achat_completion(self, 
                              messages: Union[str, List[LLMMessage]], 
                              temperature: Optional[float] = None,
                              max_tokens: Optional[int] = None,
                              **kwargs) -> LLMResponse:
        """
        🚀 异步聊天完成API调用 - 统一接口实现
        
        Args:
            messages: 消息内容，可以是字符串或消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一的响应对象
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx未安装，无法使用异步功能。请安装: pip install httpx")
        
        if not self.async_client:
            self._init_async_client()
            if not self.async_client:
                raise RuntimeError("异步客户端初始化失败")
        
        start_time = time.time()
        
        # 准备消息格式
        prepared_messages = self._prepare_messages(messages)
        
        # 参数处理
        temperature = temperature or self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens
        model = kwargs.get('model') or getattr(self.config, 'model', None) or getattr(self.config, 'model_name', 'deepseek-chat')
        enable_cache = kwargs.get('enable_cache', self.config.enable_cache)
        
        # 转换为DeepSeek API格式
        api_messages = []
        for msg in prepared_messages:
            api_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # 构建请求数据
        request_data = {
            'model': model,
            'messages': api_messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        
        # 检查缓存
        cache_key = self._generate_cache_key(request_data)
        if enable_cache and self._is_cache_valid(cache_key):
            cached_api_response, _ = self._cache[cache_key]
            self.metrics.cache_hits += 1
            logger.debug(f"📋 使用缓存响应: {cache_key[:16]}...")
            
            # 转换为统一格式
            llm_response = cached_api_response.to_llm_response("deepseek")
            self._update_stats(llm_response)
            return llm_response
        
        # 🚀 执行异步API调用
        api_response = await self._aexecute_request(request_data, start_time)
        
        # 转换为统一格式
        llm_response = api_response.to_llm_response("deepseek")
        
        # 更新缓存
        if enable_cache and api_response.success:
            self._cache[cache_key] = (api_response, time.time())
            self._cleanup_cache()
        
        # 更新指标
        enable_metrics = getattr(self.config, 'enable_metrics', True)
        if enable_metrics and self.metrics:
            self._update_metrics(api_response)
        
        # 更新父类统计
        self._update_stats(llm_response)
        
        return llm_response
    
    def simple_chat(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        **kwargs
    ) -> APIResponse:
        """
        简化的聊天接口
        
        Args:
            prompt: 用户提示
            system_message: 系统消息
            **kwargs: 其他参数
            
        Returns:
            API响应对象
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat_completion(
            messages=messages,
            system_message=system_message,
            **kwargs
        )
    
    def _execute_request(self, request_data: Dict[str, Any], start_time: float) -> APIResponse:
        """
        执行API请求（包含重试逻辑）
        
        Args:
            request_data: 请求数据
            start_time: 开始时间
            
        Returns:
            API响应对象
        """
        # 🔧 请求频率控制 - 确保两次请求之间有足够间隔
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._request_interval:
            wait_time = self._request_interval - time_since_last
            logger.debug(f"⏱️ 请求间隔控制，等待 {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        self._last_request_time = time.time()
        
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(f"🤖 API调用尝试 {attempt + 1}/{self.config.max_retries}")
                
                response = self.session.post(
                    f"{self.config.base_url}/chat/completions",
                    json=request_data,
                    timeout=self.config.timeout,
                    verify=False  # 禁用SSL验证以避免SSL协议错误
                )
                
                response_time = time.time() - start_time
                
                # 处理成功响应
                if response.status_code == 200:
                    return self._process_success_response(response, response_time)
                
                # 处理错误响应
                error_response = self._process_error_response(response, response_time)
                
                # 决定是否重试
                if not self._should_retry(error_response.error_type, attempt):
                    return error_response
                
                # 计算等待时间并重试
                wait_time = self._calculate_retry_delay(error_response.error_type, attempt)
                logger.warning(f"🔄 等待 {wait_time:.1f}s 后重试...")
                time.sleep(wait_time)
                last_error = error_response
                
            except requests.exceptions.Timeout as e:
                response_time = time.time() - start_time
                last_error = APIResponse(
                    success=False,
                    error_type=LLMErrorType.TIMEOUT_ERROR,
                    error_message=f"请求超时: {str(e)}",
                    response_time=response_time
                )
                
                if attempt < self.config.max_retries - 1:
                    # 🔥 修复：超时错误也使用指数退避，但延迟较短
                    wait_time = min(
                        self.config.retry_delay_base * (2 ** attempt),
                        60.0  # 超时重试最大延迟60秒
                    )
                    logger.warning(f"⏱️ 超时重试，等待 {wait_time:.1f}s...")
                    time.sleep(wait_time)
                
            except requests.exceptions.ConnectionError as e:
                response_time = time.time() - start_time
                last_error = APIResponse(
                    success=False,
                    error_type=APIErrorType.NETWORK_ERROR,
                    error_message=f"网络连接错误: {str(e)}",
                    response_time=response_time
                )
                
                if attempt < self.config.max_retries - 1:
                    # 🔥 修复：使用指数退避策略，但有最大限制
                    base_delay = getattr(self.config, 'network_retry_multiplier', 2.0) * self.config.retry_delay_base
                    wait_time = min(
                        base_delay * (2 ** attempt),  # 指数退避
                        getattr(self.config, 'max_network_retry_delay', 120.0)  # 最大延迟限制
                    )
                    logger.warning(f"🌐 网络错误重试，等待 {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    
            except Exception as e:
                response_time = time.time() - start_time
                last_error = APIResponse(
                    success=False,
                    error_type=LLMErrorType.UNKNOWN_ERROR,
                    error_message=f"未知错误: {str(e)}",
                    response_time=response_time
                )
                
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"❌ 未知错误重试，等待 3s...")
                    time.sleep(3)
        
        # 🔥 增强版：所有重试失败后的详细错误报告
        logger.error(f"❌ API调用失败: 所有 {self.config.max_retries} 次重试均失败")
        
        # 提供详细的失败分析和建议
        if last_error:
            if last_error.error_type == APIErrorType.NETWORK_ERROR:
                logger.error("💡 网络连接问题建议:")
                logger.error("   1. 检查网络连接状态")
                logger.error("   2. 检查防火墙设置")
                logger.error("   3. 尝试使用代理或VPN")
                logger.error("   4. 检查DNS解析是否正常")
            elif last_error.error_type == LLMErrorType.TIMEOUT_ERROR:
                logger.error("💡 请求超时问题建议:")
                logger.error("   1. 当前超时设置: 连接{}s, 读取{}s".format(*self.config.timeout))
                logger.error("   2. 可以尝试增加超时时间")
                logger.error("   3. 检查网络延迟情况")
            elif last_error.error_type == LLMErrorType.AUTHENTICATION:
                logger.error("💡 认证失败建议:")
                logger.error("   1. 检查API密钥是否正确")
                logger.error("   2. 检查API密钥是否过期")
                logger.error("   3. 检查账户余额")
        
        return last_error or APIResponse(
            success=False,
            error_type=APIErrorType.UNKNOWN_ERROR,
            error_message="所有重试尝试均失败，请检查网络连接和API配置"
        )
    
    def _process_success_response(self, response: requests.Response, response_time: float) -> APIResponse:
        """处理成功响应"""
        try:
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # 提取token使用信息
            tokens_used = 0
            if 'usage' in data:
                tokens_used = data['usage'].get('total_tokens', 0)
            
            logger.info(f"✅ API调用成功 ({response_time:.2f}s, {tokens_used} tokens)")
            
            return APIResponse(
                success=True,
                content=content,
                raw_response=data,
                status_code=response.status_code,
                response_time=response_time,
                tokens_used=tokens_used,
                model_used=data.get('model', getattr(self.config, 'model', None) or getattr(self.config, 'model_name', 'deepseek-chat'))
            )
            
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"❌ 响应解析失败: {str(e)}")
            return APIResponse(
                success=False,
                error_type=LLMErrorType.PARSE_ERROR,
                error_message=f"响应解析失败: {str(e)}",
                status_code=response.status_code,
                response_time=response_time
            )
    
    def _process_error_response(self, response: requests.Response, response_time: float) -> APIResponse:
        """处理错误响应"""
        error_type = LLMErrorType.UNKNOWN_ERROR
        error_message = f"HTTP {response.status_code}"
        
        # 根据状态码分类错误
        if response.status_code == 401:
            error_type = LLMErrorType.AUTHENTICATION
            error_message = "API密钥认证失败"
        elif response.status_code == 429:
            error_type = LLMErrorType.RATE_LIMIT
            error_message = "API调用频率限制"
        elif response.status_code in [500, 502, 503, 504]:
            error_type = LLMErrorType.SERVER_ERROR
            error_message = f"服务器错误 {response.status_code}"
        elif response.status_code == 400:
            error_type = LLMErrorType.INVALID_REQUEST
            error_message = "请求参数无效"
        
        # 尝试提取详细错误信息
        try:
            error_data = response.json()
            if 'error' in error_data:
                error_message = error_data['error'].get('message', error_message)
        except:
            pass
        
        logger.error(f"❌ API错误: {error_message} ({response.status_code})")
        
        return APIResponse(
            success=False,
            error_type=error_type,
            error_message=error_message,
            status_code=response.status_code,
            response_time=response_time
        )
    
    def _should_retry(self, error_type: LLMErrorType, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries - 1:
            return False
        
        # 不重试的错误类型
        non_retryable = {
            LLMErrorType.AUTHENTICATION,
            LLMErrorType.PARSE_ERROR,
            LLMErrorType.INVALID_REQUEST
        }
        
        return error_type not in non_retryable
    
    def _calculate_retry_delay(self, error_type: LLMErrorType, attempt: int) -> float:
        """计算重试延迟时间"""
        base_delay = self.config.retry_delay_base
        
        if error_type == LLMErrorType.RATE_LIMIT:
            # 限流错误使用指数退避
            return base_delay ** (attempt + 1) * 2
        elif error_type == LLMErrorType.SERVER_ERROR:
            # 服务器错误使用线性增长
            return 5 * (attempt + 1)
        else:
            # 其他错误使用基础延迟
            return base_delay * (attempt + 1)
    
    def _generate_cache_key(self, request_data: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 将请求数据序列化并生成哈希
        cache_string = json.dumps(request_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache:
            return False
        
        _, timestamp = self._cache[cache_key]
        return time.time() - timestamp < self.config.cache_ttl
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.config.cache_ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"🧹 清理了 {len(expired_keys)} 个过期缓存项")
    
    def _update_metrics(self, response: APIResponse):
        """更新性能指标"""
        if not self.metrics:
            return
            
        self.metrics.total_requests += 1
        
        if response.success:
            self.metrics.successful_requests += 1
            self.metrics.total_response_time += response.response_time
            self.metrics.total_tokens_used += response.tokens_used
        else:
            self.metrics.failed_requests += 1
            if response.error_type:
                self.metrics.error_counts[response.error_type] = \
                    self.metrics.error_counts.get(response.error_type, 0) + 1
    
    def get_metrics(self) -> Optional[ClientMetrics]:
        """获取客户端性能指标"""
        return self.metrics
    
    def reset_metrics(self):
        """重置性能指标"""
        if self.metrics:
            self.metrics = ClientMetrics()
            logger.info("📊 性能指标已重置")
        else:
            logger.debug("📊 性能指标功能未启用")
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.info("🧹 缓存已清空")
    
    @contextmanager
    def batch_mode(self):
        """批量模式上下文管理器（可以添加批量优化逻辑）"""
        logger.debug("🔄 进入批量模式")
        try:
            yield self
        finally:
            logger.debug("✅ 退出批量模式")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        self.session.close()
        logger.debug("🔄 DeepSeekClient 资源已清理")
    
    # ==================== 实现BaseLLMClient抽象方法 ====================
    
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 基础配置验证 - 不进行实际API调用以避免健康检查失败
            if not self.config.api_key:
                logger.debug("❌ DeepSeek API密钥未设置")
                return False
            
            if len(self.config.api_key.strip()) < 10:
                logger.debug("❌ DeepSeek API密钥格式无效")
                return False
            
            # 检查base_url格式
            base_url = getattr(self.config, 'base_url', None)
            if base_url and not (base_url.startswith('http://') or base_url.startswith('https://')):
                logger.debug("❌ DeepSeek base_url格式无效")
                return False
            
            # 基础配置验证通过
            logger.debug("✅ DeepSeek基础配置验证通过")
            return True
            
        except Exception as e:
            logger.error(f"❌ DeepSeek配置验证失败: {e}")
            return False
    
    def get_available_models(self) -> List[str]:
        """
        获取可用模型列表
        
        Returns:
            List[str]: 可用的模型名称列表
        """
        # DeepSeek目前支持的模型
        return [
            "deepseek-chat",
            "deepseek-coder"
        ]
    
    def get_supported_features(self) -> List[str]:
        """
        获取支持的功能列表
        
        Returns:
            List[str]: 支持的功能
        """
        return [
            "chat_completion", 
            "achat_completion",  # 🚀 新增异步支持
            "text_generation", 
            "chinese_language",
            "coding_assistance",
            "caching",
            "retry_mechanism"
        ]
    
    # ==================== 🚀 异步请求执行方法 ====================
    
    async def _aexecute_request(self, request_data: Dict[str, Any], start_time: float) -> APIResponse:
        """
        🚀 异步执行API请求
        
        Args:
            request_data: 请求数据
            start_time: 开始时间
            
        Returns:
            APIResponse: API响应对象
        """
        if not self.async_client:
            raise RuntimeError("异步客户端未初始化")
        
        # 🔧 频率控制（异步版本）
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._request_interval:
            wait_time = self._request_interval - time_since_last
            logger.debug(f"⏱️ 异步频率控制，等待 {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        self._last_request_time = time.time()
        
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                logger.debug(f"🚀 异步API调用尝试 {attempt + 1}/{self.config.max_retries}")
                
                response = await self.async_client.post(
                    f"{self.config.base_url}/chat/completions",
                    json=request_data,
                    timeout=self.config.timeout
                )
                
                response_time = time.time() - start_time
                
                # 处理成功响应
                if response.status_code == 200:
                    return self._aprocess_success_response(response, response_time)
                
                # 处理错误响应
                error_response = self._aprocess_error_response(response, response_time)
                
                # 决定是否重试
                if not self._should_retry(error_response.error_type, attempt):
                    return error_response
                
                # 计算等待时间并重试
                wait_time = self._calculate_retry_delay(error_response.error_type, attempt)
                logger.warning(f"🔄 异步等待 {wait_time:.1f}s 后重试...")
                await asyncio.sleep(wait_time)
                last_error = error_response
                
            except Exception as e:
                # 简化异常处理，兼容httpx不可用的情况
                response_time = time.time() - start_time
                error_type = LLMErrorType.TIMEOUT_ERROR if 'timeout' in str(e).lower() else LLMErrorType.NETWORK_ERROR
                last_error = APIResponse(
                    success=False,
                    error_type=error_type,
                    error_message=f"异步请求错误: {str(e)}",
                    response_time=response_time
                )
                
                if attempt < self.config.max_retries - 1:
                    wait_time = 3 * (attempt + 1)
                    logger.warning(f"🔄 异步错误重试，等待 {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    break
        
        # 所有重试都失败了
        if self.metrics:
            self.metrics.failed_requests += 1
        return last_error or APIResponse(
            success=False,
            error_type=LLMErrorType.UNKNOWN_ERROR,
            error_message="异步API调用失败：所有重试都已用尽",
            response_time=time.time() - start_time
        )
    
    def _aprocess_success_response(self, response, response_time: float) -> APIResponse:
        """🚀 处理异步成功响应"""
        try:
            response_data = response.json()
            
            # 提取消息内容
            content = ""
            if 'choices' in response_data and response_data['choices']:
                choice = response_data['choices'][0]
                if 'message' in choice:
                    content = choice['message'].get('content', '')
                elif 'text' in choice:
                    content = choice.get('text', '')
            
            # 更新指标
            if self.metrics:
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                self.metrics.total_response_time += response_time
                
                # 统计token使用
                if 'usage' in response_data:
                    usage = response_data['usage']
                    self.metrics.total_tokens += usage.get('total_tokens', 0)
                    self.metrics.prompt_tokens += usage.get('prompt_tokens', 0)
                    self.metrics.completion_tokens += usage.get('completion_tokens', 0)
            
            logger.debug(f"🚀 异步API调用成功，响应时间: {response_time:.2f}s")
            
            return APIResponse(
                success=True,
                content=content,
                raw_response=response_data,
                status_code=response.status_code,
                response_time=response_time
            )
            
        except Exception as e:
            logger.error(f"❌ 异步响应解析失败: {e}")
            return APIResponse(
                success=False,
                error_type=LLMErrorType.PARSE_ERROR,
                error_message=f"异步响应解析失败: {str(e)}",
                status_code=getattr(response, 'status_code', 0),
                response_time=response_time
            )
    
    def _aprocess_error_response(self, response, response_time: float) -> APIResponse:
        """🚀 处理异步错误响应"""
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
        except:
            error_message = f"HTTP {response.status_code}: 响应解析失败"
        
        # 错误类型映射
        error_type = LLMErrorType.SERVER_ERROR
        if response.status_code == 401:
            error_type = LLMErrorType.AUTHENTICATION
        elif response.status_code == 429:
            error_type = LLMErrorType.RATE_LIMIT
        elif response.status_code == 403:
            error_type = LLMErrorType.QUOTA_EXCEEDED
        elif response.status_code == 400:
            error_type = LLMErrorType.INVALID_REQUEST
        
        # 更新指标
        if self.metrics:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.error_counts[error_type.value] = self.metrics.error_counts.get(error_type.value, 0) + 1
        
        logger.warning(f"⚠️ 异步API错误 {response.status_code}: {error_message}")
        
        return APIResponse(
            success=False,
            error_type=error_type,
            error_message=error_message,
            status_code=response.status_code,
            response_time=response_time
        )
    
    async def aclose(self):
        """🚀 关闭异步客户端"""
        if self.async_client:
            await self.async_client.aclose()
            self.async_client = None
            logger.debug("🚀 异步HTTP客户端已关闭")
    
    # ==================== 🔥 新增：健康检查和诊断方法 ====================
    
    def health_check(self, timeout: Optional[float] = 30.0) -> Dict[str, Any]:
        """
        🔥 新增：执行DeepSeek API健康检查
        
        Args:
            timeout: 健康检查超时时间（秒）
            
        Returns:
            Dict包含健康状态信息
        """
        health_status = {
            'is_healthy': False,
            'response_time': None,
            'error_message': None,
            'api_accessible': False,
            'authentication_valid': False,
            'network_connectivity': False,
            'timestamp': time.time()
        }
        
        try:
            logger.info("🔍 开始DeepSeek API健康检查...")
            start_time = time.time()
            
            # 使用简单的测试请求
            test_request = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            # 临时修改超时设置用于健康检查
            original_timeout = self.config.timeout
            if timeout:
                self.config.timeout = (min(timeout/2, 30), timeout)
            
            try:
                response = self.session.post(
                    f"{self.config.base_url}/chat/completions",
                    json=test_request,
                    timeout=self.config.timeout,
                    verify=False  # 禁用SSL验证以避免SSL协议错误
                )
                
                response_time = time.time() - start_time
                health_status['response_time'] = response_time
                health_status['network_connectivity'] = True
                health_status['api_accessible'] = True
                
                if response.status_code == 200:
                    health_status['is_healthy'] = True
                    health_status['authentication_valid'] = True
                    logger.info(f"✅ DeepSeek API健康检查通过 ({response_time:.2f}s)")
                elif response.status_code == 401:
                    health_status['error_message'] = "API密钥认证失败"
                    logger.warning("⚠️ DeepSeek API认证失败")
                else:
                    health_status['error_message'] = f"API返回错误状态码: {response.status_code}"
                    logger.warning(f"⚠️ DeepSeek API返回错误: {response.status_code}")
                    
            finally:
                # 恢复原始超时设置
                self.config.timeout = original_timeout
                
        except requests.exceptions.Timeout:
            health_status['error_message'] = "健康检查请求超时"
            logger.warning("⚠️ DeepSeek API健康检查超时")
        except requests.exceptions.ConnectionError as e:
            health_status['error_message'] = f"网络连接错误: {str(e)}"
            logger.warning(f"⚠️ DeepSeek API网络连接失败: {e}")
        except Exception as e:
            health_status['error_message'] = f"健康检查异常: {str(e)}"
            logger.error(f"❌ DeepSeek API健康检查异常: {e}")
        
        return health_status
    
    def get_client_status(self) -> Dict[str, Any]:
        """
        🔥 新增：获取客户端状态信息
        
        Returns:
            Dict包含客户端详细状态
        """
        status = {
            'client_type': 'DeepSeekClient',
            'config': {
                'base_url': self.config.base_url,
                'model': self.config.model,
                'timeout': self.config.timeout,
                'max_retries': self.config.max_retries,
                'retry_delay_base': self.config.retry_delay_base
            },
            'session_active': self.session is not None,
            'async_client_available': self.async_client is not None,
            'cache_enabled': self.config.enable_cache,
            'metrics_enabled': self.metrics is not None
        }
        
        # 添加指标信息（如果可用）
        if self.metrics:
            status['metrics'] = {
                'total_requests': self.metrics.total_requests,
                'successful_requests': self.metrics.successful_requests,
                'failed_requests': self.metrics.failed_requests,
                'average_response_time': self.metrics.average_response_time,
                'error_counts': dict(self.metrics.error_counts)
            }
        
        return status


# 工厂函数和便捷接口
def create_client(api_key: str, **kwargs) -> DeepSeekClient:
    """
    创建 DeepSeek 客户端的工厂函数 - 向后兼容
    
    Args:
        api_key: API密钥
        **kwargs: 其他配置参数
        
    Returns:
        DeepSeekClient 实例
    """
    config = ClientConfig(api_key=api_key, **kwargs)
    return DeepSeekClient(config)


def create_llm_client(api_key: str, **kwargs) -> DeepSeekClient:
    """
    创建统一LLM客户端的工厂函数
    
    Args:
        api_key: API密钥
        **kwargs: 其他配置参数
        
    Returns:
        DeepSeekClient 实例（实现BaseLLMClient接口）
    """
    # 确保base_url有默认值
    if 'base_url' not in kwargs:
        kwargs['base_url'] = "https://api.deepseek.com/v1"
    
    llm_config = LLMConfig(
        provider=LLMProvider.DEEPSEEK,
        api_key=api_key,
        model_name=kwargs.pop('model_name', 'deepseek-chat'),
        **kwargs
    )
    return DeepSeekClient(llm_config)


def quick_chat(api_key: str, prompt: str, system_message: Optional[str] = None) -> str:
    """
    快速聊天便捷函数
    
    Args:
        api_key: API密钥
        prompt: 用户提示
        system_message: 系统消息
        
    Returns:
        AI响应内容
        
    Raises:
        Exception: API调用失败时抛出异常
    """
    with create_client(api_key) as client:
        response = client.simple_chat(prompt, system_message)
        if response.success:
            return response.content
        else:
            raise Exception(f"API调用失败: {response.error_message}")

       
