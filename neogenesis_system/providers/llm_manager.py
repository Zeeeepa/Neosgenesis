#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM管理器 - 统一管理多个LLM提供商
LLM Manager - Unified management for multiple LLM providers
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from collections import defaultdict

from .llm_base import BaseLLMClient, LLMConfig, LLMProvider, LLMResponse, LLMMessage
from .impl.deepseek_client import create_llm_client
try:
    from neogenesis_system.config import (
        LLM_PROVIDERS_CONFIG, DEFAULT_LLM_CONFIG, LLM_MANAGER_CONFIG, 
        COST_CONTROL_CONFIG, FEATURE_FLAGS
    )
except ImportError:
    try:
        from ..config import (
            LLM_PROVIDERS_CONFIG, DEFAULT_LLM_CONFIG, LLM_MANAGER_CONFIG, 
            COST_CONTROL_CONFIG, FEATURE_FLAGS
        )
    except ImportError:
        # 提供默认配置
        LLM_PROVIDERS_CONFIG = {}
        DEFAULT_LLM_CONFIG = {}
        LLM_MANAGER_CONFIG = {}
        COST_CONTROL_CONFIG = {}
        FEATURE_FLAGS = {}

logger = logging.getLogger(__name__)


@dataclass
class ProviderStatus:
    """提供商状态"""
    name: str
    enabled: bool
    healthy: bool
    last_check: float
    error_count: int
    success_count: int
    avg_response_time: float
    last_error: Optional[str] = None


class LLMManager:
    """
    LLM管理器 - 统一管理多个LLM提供商
    
    功能：
    - 自动发现和初始化可用的LLM提供商
    - 智能路由和负载均衡
    - 自动回退机制
    - 成本跟踪和控制
    - 健康检查和监控
    """
    
    def __init__(self):
        """初始化LLM管理器"""
        self.providers: Dict[str, BaseLLMClient] = {}
        self.provider_status: Dict[str, ProviderStatus] = {}
        self.config = DEFAULT_LLM_CONFIG.copy()
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'fallback_count': 0,
            'provider_usage': defaultdict(int),
            'cost_tracking': defaultdict(float),
            'request_history': []
        }
        
        # 初始化状态
        self.initialized = False
        self.last_health_check = 0
        
        logger.info("🚀 LLM管理器初始化开始")
        self._initialize_providers()
        
    def _initialize_providers(self):
        """🔥 增强版：初始化可用的提供商（包含备用提供商）"""
        if not FEATURE_FLAGS.get("enable_multi_llm_support", False):
            logger.info("📋 多LLM支持已禁用，仅使用DeepSeek")
            self._initialize_single_provider()
            return
        
        initialized_count = 0
        
        for provider_name, provider_config in LLM_PROVIDERS_CONFIG.items():
            try:
                if not provider_config.get("enabled", False):
                    logger.debug(f"⏭️ 跳过禁用的提供商: {provider_name}")
                    continue
                
                # 检查API密钥
                api_key = ""
                
                # 优先使用硬编码的API密钥
                if provider_config.get("hardcoded_api_key"):
                    api_key = provider_config["hardcoded_api_key"]
                    logger.info(f"🔑 使用硬编码API密钥for {provider_name}")
                else:
                    # 使用环境变量
                    api_key_env = provider_config.get("api_key_env")
                    if api_key_env:
                        api_key = os.getenv(api_key_env, "")
                        if not api_key:
                            logger.warning(f"⚠️ 未找到{provider_name}的API密钥: {api_key_env}")
                            continue
                
                # 创建LLM配置
                llm_config = self._create_llm_config(provider_name, provider_config, api_key)
                
                # 创建客户端
                client = self._create_provider_client(provider_name, llm_config)
                
                # 快速健康检查
                if self._quick_health_check(client, provider_name):
                    self.providers[provider_name] = client
                    self.provider_status[provider_name] = ProviderStatus(
                        name=provider_name,
                        enabled=True,
                        healthy=True,
                        last_check=time.time(),
                        error_count=0,
                        success_count=1,
                        avg_response_time=0.0
                    )
                    initialized_count += 1
                    logger.info(f"✅ {provider_name}提供商初始化成功")
                else:
                    logger.warning(f"❌ {provider_name}提供商健康检查失败")
                    
            except Exception as e:
                logger.error(f"❌ 初始化{provider_name}提供商失败: {e}")
                continue
        
        if initialized_count == 0:
            logger.warning("⚠️ 没有可用的LLM提供商，回退到单一提供商模式")
            self._initialize_single_provider()
        else:
            logger.info(f"🎉 LLM管理器初始化完成，可用提供商: {initialized_count}个")
            self.initialized = True
            
            # 🔥 新增：确保有备用提供商配置
            self._ensure_fallback_configuration()
    
    def _initialize_single_provider(self):
        """初始化单一提供商（DeepSeek）"""
        try:
            from .client_adapter import get_or_create_unified_client
            
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if not api_key:
                logger.error("❌ 未找到DEEPSEEK_API_KEY环境变量")
                return
            
            client = get_or_create_unified_client(api_key)
            self.providers["deepseek"] = client
            self.provider_status["deepseek"] = ProviderStatus(
                name="deepseek",
                enabled=True,
                healthy=True,
                last_check=time.time(),
                error_count=0,
                success_count=1,
                avg_response_time=0.0
            )
            
            logger.info("✅ 单一提供商模式初始化成功 (DeepSeek)")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"❌ 单一提供商初始化失败: {e}")
    
    def _create_provider_client(self, provider_name: str, llm_config: LLMConfig) -> BaseLLMClient:
        """创建特定提供商的客户端"""
        try:
            # 检查配置中的provider_type来决定使用哪个客户端
            provider_config = LLM_PROVIDERS_CONFIG.get(provider_name, {})
            provider_type = provider_config.get("provider_type", provider_name)
            
            if provider_type == "gemini_openai" or (provider_name == "gemini" and provider_type == "gemini_openai"):
                from .impl.gemini_openai_client import GeminiOpenAIClient
                return GeminiOpenAIClient(llm_config)
            elif provider_name == "gemini" or provider_type == "gemini":
                from .impl.gemini_client import GeminiClient
                return GeminiClient(llm_config)
            elif provider_name == "deepseek":
                from .impl.deepseek_client import create_llm_client
                return create_llm_client(llm_config.api_key)
            elif provider_name == "openai":
                from .impl.openai_client import OpenAIClient
                return OpenAIClient(llm_config)
            elif provider_name == "anthropic":
                from .impl.anthropic_client import AnthropicClient
                return AnthropicClient(llm_config)
            elif provider_name == "ollama":
                from .impl.ollama_client import OllamaClient
                return OllamaClient(llm_config)
            else:
                # 默认使用DeepSeek客户端作为回退
                from .impl.deepseek_client import create_llm_client
                return create_llm_client(llm_config.api_key)
        except ImportError as e:
            logger.warning(f"⚠️ 无法导入{provider_name}客户端: {e}")
            # 回退到DeepSeek
            from .impl.deepseek_client import create_llm_client
            return create_llm_client(llm_config.api_key)
    
    def _create_llm_config(self, provider_name: str, provider_config: Dict, api_key: str) -> LLMConfig:
        """创建LLM配置"""
        provider_type = provider_config["provider_type"]
        provider_enum = LLMProvider(provider_type)
        
        # 特殊处理Azure OpenAI
        extra_params = {}
        base_url = provider_config.get("base_url")
        
        # 确保base_url不为None
        if base_url is None:
            if provider_type == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif provider_type == "gemini_openai":
                base_url = "https://hiapi.online"
            elif provider_type == "openai":
                base_url = "https://api.openai.com/v1"
            else:
                base_url = "https://api.deepseek.com/v1"  # 默认使用deepseek
            logger.warning(f"⚠️ {provider_name}的base_url为None，使用默认值: {base_url}")
        
        if provider_type == "azure_openai":
            azure_endpoint = os.getenv(provider_config.get("azure_endpoint_env", ""), "")
            if azure_endpoint:
                base_url = azure_endpoint
                extra_params["api_version"] = provider_config.get("api_version", "2024-02-15-preview")
        
        return LLMConfig(
            provider=provider_enum,
            api_key=api_key,
            model_name=provider_config["default_model"],
            temperature=provider_config.get("temperature", 0.7),
            max_tokens=provider_config.get("max_tokens", 2000),
            base_url=base_url,
            timeout=tuple(provider_config.get("timeout", (30, 120))),
            max_retries=provider_config.get("max_retries", 3),
            retry_delay_base=provider_config.get("retry_delay_base", 2.0),
            request_interval=provider_config.get("request_interval", 1.0),
            extra_params=extra_params
        )
    
    def _quick_health_check(self, client: BaseLLMClient, provider_name: str) -> bool:
        """快速健康检查"""
        try:
            # 简单的配置验证
            return client.validate_config()
        except Exception as e:
            logger.debug(f"🔍 {provider_name}健康检查失败: {e}")
            return False
    
    def call_api(self, prompt: str, 
                 system_message: Optional[str] = None,
                 temperature: Optional[float] = None,
                 **kwargs) -> str:
        """
        简化的API调用接口 - 兼容现有代码
        
        Args:
            prompt: 用户提示
            system_message: 系统消息
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: LLM响应内容
            
        Raises:
            Exception: 调用失败时抛出异常
        """
        try:
            # 构建消息格式
            messages = []
            if system_message:
                messages.append(LLMMessage(role="system", content=system_message))
            messages.append(LLMMessage(role="user", content=prompt))
            
            # 调用chat_completion
            response = self.chat_completion(
                messages=messages,
                temperature=temperature,
                **kwargs
            )
            
            if response.success:
                return response.content
            else:
                raise Exception(f"LLM调用失败: {response.error_message}")
                
        except Exception as e:
            logger.error(f"❌ LLM API调用失败: {e}")
            raise
    
    def chat_completion(self, 
                       messages: Union[str, List[LLMMessage]], 
                       provider_name: Optional[str] = None,
                       temperature: Optional[float] = None,
                       **kwargs) -> LLMResponse:
        """
        聊天完成 - 智能路由到最佳提供商
        
        Args:
            messages: 消息内容
            provider_name: 指定提供商（可选）
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一响应
        """
        self.stats['total_requests'] += 1
        
        if not self.initialized or not self.providers:
            return self._create_error_response("没有可用的LLM提供商")
        
        # 处理直接传入字符串的情况
        if isinstance(messages, str):
            messages = [LLMMessage(role="user", content=messages)]
        
        # 选择提供商
        selected_provider = self._select_provider(provider_name)
        if not selected_provider:
            return self._create_error_response("无法选择合适的提供商")
        
        # 添加temperature到kwargs中
        if temperature is not None:
            kwargs['temperature'] = temperature
        
        # 执行请求（带回退机制）
        return self._execute_with_fallback(selected_provider, messages, **kwargs)
    
    def _select_provider(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        """选择提供商"""
        # 如果指定了提供商且可用，直接使用
        if preferred_provider and preferred_provider in self.providers:
            if self.provider_status[preferred_provider].healthy:
                return preferred_provider
        
        # 检查主要提供商设置
        primary = self.config.get("primary_provider", "auto")
        
        if primary == "auto":
            # 自动选择：按首选顺序选择第一个可用的提供商
            preferred_order = self.config.get("preferred_providers", ["deepseek", "openai", "anthropic"])
            for provider_name in preferred_order:
                if provider_name in self.providers and self.provider_status[provider_name].healthy:
                    return provider_name
        else:
            # 使用指定的主要提供商
            if primary in self.providers and self.provider_status[primary].healthy:
                return primary
        
        # 使用第一个健康的提供商
        for name, status in self.provider_status.items():
            if status.healthy and name in self.providers:
                return name
        
        return None
    
    def _execute_with_fallback(self, provider_name: str, messages: Union[str, List[LLMMessage]], **kwargs) -> LLMResponse:
        """🔥 增强版：执行请求（带智能回退机制）"""
        providers_to_try = [provider_name]
        
        # 🔥 增强版：智能回退策略
        if self.config.get("auto_fallback", True):
            # 获取所有健康的提供商作为回退选项
            healthy_providers = [
                name for name, status in self.provider_status.items() 
                if status.healthy and name != provider_name and name in self.providers
            ]
            
            # 按优先级排序回退提供商
            fallback_providers = self.config.get("fallback_providers", ["openai", "anthropic", "gemini"])
            ordered_fallbacks = []
            
            # 首先添加配置中指定的回退提供商
            for fallback in fallback_providers:
                if fallback in healthy_providers:
                    ordered_fallbacks.append(fallback)
                    healthy_providers.remove(fallback)
            
            # 然后添加其他健康的提供商
            ordered_fallbacks.extend(healthy_providers)
            providers_to_try.extend(ordered_fallbacks)
        
        last_error = None
        network_errors = []
        auth_errors = []
        
        for i, current_provider in enumerate(providers_to_try):
            try:
                # 🔥 增强版：动态健康检查
                if not self.provider_status[current_provider].healthy:
                    # 如果是主要提供商，尝试快速健康检查
                    if i == 0 and hasattr(self.providers[current_provider], 'health_check'):
                        logger.info(f"🔍 对{current_provider}执行快速健康检查...")
                        health_status = self.providers[current_provider].health_check(timeout=10.0)
                        if health_status.get('is_healthy', False):
                            self.provider_status[current_provider].healthy = True
                            logger.info(f"✅ {current_provider}健康检查通过，恢复使用")
                        else:
                            logger.warning(f"⚠️ {current_provider}健康检查失败: {health_status.get('error_message', '未知错误')}")
                            continue
                    else:
                        continue
                
                start_time = time.time()
                client = self.providers[current_provider]
                
                # 🔥 增强版：显示回退信息
                if i == 0:
                    logger.info(f"🤖 使用主要提供商: {current_provider}")
                else:
                    logger.warning(f"🔄 回退到提供商: {current_provider} (第{i+1}选择)")
                
                response = client.chat_completion(messages, **kwargs)
                response_time = time.time() - start_time
                
                if response.success:
                    # 更新统计
                    self._update_provider_stats(current_provider, True, response_time)
                    self.stats['successful_requests'] += 1
                    self.stats['provider_usage'][current_provider] += 1
                    
                    # 🔥 增强版：记录回退成功
                    if i > 0:
                        self.stats['fallback_count'] += 1
                        logger.info(f"✅ 回退成功: {current_provider}处理了请求")
                    
                    # 成本跟踪
                    if response.usage and COST_CONTROL_CONFIG.get("token_usage_tracking", True):
                        self._track_cost(current_provider, response.usage)
                    
                    return response
                else:
                    # 🔥 增强版：分类错误类型
                    self._update_provider_stats(current_provider, False, response_time)
                    error_msg = response.error_message or "未知错误"
                    last_error = error_msg
                    
                    # 分类错误以便更好的诊断
                    if "network" in error_msg.lower() or "connection" in error_msg.lower():
                        network_errors.append(f"{current_provider}: {error_msg}")
                    elif "auth" in error_msg.lower() or "401" in error_msg:
                        auth_errors.append(f"{current_provider}: {error_msg}")
                    
                    logger.warning(f"⚠️ {current_provider}请求失败: {error_msg}")
                    
                    # 继续尝试下一个提供商
                    continue
                        
            except Exception as e:
                self._update_provider_stats(current_provider, False, 0)
                error_msg = str(e)
                last_error = error_msg
                
                # 分类异常
                if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    network_errors.append(f"{current_provider}: {error_msg}")
                
                logger.error(f"❌ {current_provider}执行异常: {e}")
                continue
        
        # 🔥 增强版：所有提供商都失败时的详细错误报告
        self.stats['failed_requests'] += 1
        
        # 生成详细的错误报告
        error_report = f"所有{len(providers_to_try)}个提供商都不可用"
        if network_errors:
            error_report += f"\n网络错误: {len(network_errors)}个"
        if auth_errors:
            error_report += f"\n认证错误: {len(auth_errors)}个"
        if last_error:
            error_report += f"\n最后错误: {last_error}"
        
        logger.error(f"❌ {error_report}")
        
        # 🔥 增强版：提供恢复建议
        logger.error("💡 恢复建议:")
        logger.error("   1. 检查网络连接状态")
        logger.error("   2. 验证API密钥配置")
        logger.error("   3. 检查提供商服务状态")
        logger.error("   4. 考虑增加更多备用提供商")
        
        return self._create_error_response(error_report)
    
    def _update_provider_stats(self, provider_name: str, success: bool, response_time: float):
        """更新提供商统计"""
        if provider_name not in self.provider_status:
            return
        
        status = self.provider_status[provider_name]
        status.last_check = time.time()
        
        if success:
            status.success_count += 1
            status.error_count = 0  # 重置错误计数
            status.healthy = True
            
            # 更新平均响应时间
            if status.avg_response_time == 0:
                status.avg_response_time = response_time
            else:
                status.avg_response_time = (status.avg_response_time + response_time) / 2
        else:
            status.error_count += 1
            
            # 连续错误过多时标记为不健康
            if status.error_count >= 3:
                status.healthy = False
                logger.warning(f"⚠️ {provider_name}被标记为不健康")
    
    def _track_cost(self, provider_name: str, usage):
        """跟踪成本"""
        try:
            provider_config = LLM_PROVIDERS_CONFIG.get(provider_name, {})
            cost_per_1k = provider_config.get("cost_per_1k_tokens", {})
            
            input_cost = (usage.prompt_tokens / 1000) * cost_per_1k.get("input", 0)
            output_cost = (usage.completion_tokens / 1000) * cost_per_1k.get("output", 0)
            total_cost = input_cost + output_cost
            
            self.stats['cost_tracking'][provider_name] += total_cost
            
            logger.debug(f"💰 {provider_name}成本: ${total_cost:.6f}")
            
        except Exception as e:
            logger.debug(f"❌ 成本跟踪失败: {e}")
    
    def _create_error_response(self, error_message: str) -> LLMResponse:
        """创建错误响应"""
        from .llm_base import LLMErrorType, create_error_response
        return create_error_response(
            provider="llm_manager",
            error_type=LLMErrorType.UNKNOWN_ERROR,
            error_message=error_message
        )
    
    def get_provider_status(self) -> Dict[str, Any]:
        """获取提供商状态"""
        return {
            'initialized': self.initialized,
            'total_providers': len(self.providers),
            'healthy_providers': sum(1 for s in self.provider_status.values() if s.healthy),
            'providers': {name: {
                'enabled': status.enabled,
                'healthy': status.healthy,
                'success_count': status.success_count,
                'error_count': status.error_count,
                'avg_response_time': status.avg_response_time,
                'last_error': status.last_error
            } for name, status in self.provider_status.items()},
            'stats': self.stats.copy()
        }
    
    def get_available_models(self, provider_name: Optional[str] = None) -> Dict[str, List[str]]:
        """获取可用模型"""
        if provider_name:
            if provider_name in self.providers:
                return {provider_name: self.providers[provider_name].get_available_models()}
            else:
                return {}
        
        return {
            name: client.get_available_models() 
            for name, client in self.providers.items()
        }
    
    def switch_primary_provider(self, provider_name: str) -> bool:
        """切换主要提供商"""
        if provider_name in self.providers and self.provider_status[provider_name].healthy:
            self.config["primary_provider"] = provider_name
            logger.info(f"🔄 主要提供商已切换到: {provider_name}")
            return True
        return False
    
    def health_check(self, force: bool = False) -> Dict[str, bool]:
        """健康检查"""
        current_time = time.time()
        check_interval = LLM_MANAGER_CONFIG.get("health_check_interval", 300)
        
        if not force and (current_time - self.last_health_check) < check_interval:
            return {name: status.healthy for name, status in self.provider_status.items()}
        
        logger.info("🔍 执行LLM提供商健康检查")
        results = {}
        
        for name, client in self.providers.items():
            try:
                healthy = self._quick_health_check(client, name)
                self.provider_status[name].healthy = healthy
                results[name] = healthy
                logger.debug(f"🔍 {name}: {'✅' if healthy else '❌'}")
            except Exception as e:
                self.provider_status[name].healthy = False
                results[name] = False
                logger.error(f"🔍 {name}健康检查异常: {e}")
        
        self.last_health_check = current_time
        return results
    
    # ==================== 🔥 新增：备用提供商管理方法 ====================
    
    def _ensure_fallback_configuration(self):
        """🔥 新增：确保有合理的备用提供商配置"""
        try:
            available_providers = list(self.providers.keys())
            healthy_providers = [
                name for name, status in self.provider_status.items() 
                if status.healthy
            ]
            
            logger.info(f"🔍 检查备用提供商配置...")
            logger.info(f"   可用提供商: {available_providers}")
            logger.info(f"   健康提供商: {healthy_providers}")
            
            # 如果只有一个提供商，给出建议
            if len(healthy_providers) == 1:
                logger.warning("⚠️ 只有一个健康的LLM提供商，建议配置备用提供商")
                logger.info("💡 备用提供商建议:")
                logger.info("   1. 配置OpenAI作为备用")
                logger.info("   2. 配置Anthropic Claude作为备用")
                logger.info("   3. 配置Google Gemini作为备用")
            
            # 自动配置回退顺序
            if not self.config.get("fallback_providers"):
                # 根据可用提供商自动配置回退顺序
                fallback_order = []
                preferred_fallbacks = ["openai", "anthropic", "gemini", "groq"]
                
                for fallback in preferred_fallbacks:
                    if fallback in healthy_providers:
                        fallback_order.append(fallback)
                
                # 添加其他健康的提供商
                for provider in healthy_providers:
                    if provider not in fallback_order:
                        fallback_order.append(provider)
                
                self.config["fallback_providers"] = fallback_order
                logger.info(f"🔄 自动配置回退顺序: {fallback_order}")
            
            # 确保自动回退已启用
            if not self.config.get("auto_fallback", True):
                self.config["auto_fallback"] = True
                logger.info("✅ 自动回退功能已启用")
                
        except Exception as e:
            logger.error(f"❌ 配置备用提供商失败: {e}")
    
    def add_emergency_fallback(self, provider_name: str, api_key: str) -> bool:
        """
        🔥 新增：添加紧急备用提供商
        
        Args:
            provider_name: 提供商名称 (如 "openai", "anthropic")
            api_key: API密钥
            
        Returns:
            bool: 是否成功添加
        """
        try:
            logger.info(f"🚨 添加紧急备用提供商: {provider_name}")
            
            # 创建基本配置
            from .llm_base import LLMConfig, LLMProvider
            
            provider_enum = None
            base_url = None
            
            if provider_name == "openai":
                provider_enum = LLMProvider.OPENAI
                base_url = "https://api.openai.com/v1"
            elif provider_name == "anthropic":
                provider_enum = LLMProvider.ANTHROPIC
                base_url = "https://api.anthropic.com"
            elif provider_name == "gemini":
                provider_enum = LLMProvider.GEMINI
                base_url = "https://generativelanguage.googleapis.com/v1"
            else:
                logger.error(f"❌ 不支持的紧急备用提供商: {provider_name}")
                return False
            
            # 创建LLM配置
            llm_config = LLMConfig(
                provider=provider_enum,
                api_key=api_key,
                model_name=self._get_default_model(provider_name),
                base_url=base_url,
                timeout=(60, 300),  # 使用较长的超时时间
                max_retries=3
            )
            
            # 创建客户端
            client = self._create_provider_client(provider_name, llm_config)
            
            # 快速健康检查
            if self._quick_health_check(client, provider_name):
                self.providers[provider_name] = client
                self.provider_status[provider_name] = ProviderStatus(
                    name=provider_name,
                    enabled=True,
                    healthy=True,
                    last_check=time.time(),
                    error_count=0,
                    success_count=1,
                    avg_response_time=0.0
                )
                
                # 更新回退配置
                fallback_providers = self.config.get("fallback_providers", [])
                if provider_name not in fallback_providers:
                    fallback_providers.append(provider_name)
                    self.config["fallback_providers"] = fallback_providers
                
                logger.info(f"✅ 紧急备用提供商{provider_name}添加成功")
                return True
            else:
                logger.error(f"❌ 紧急备用提供商{provider_name}健康检查失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 添加紧急备用提供商失败: {e}")
            return False
    
    def _get_default_model(self, provider_name: str) -> str:
        """获取提供商的默认模型"""
        default_models = {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-haiku-20240307",
            "gemini": "gemini-pro",
            "groq": "llama2-70b-4096",
            "deepseek": "deepseek-chat"
        }
        return default_models.get(provider_name, "gpt-3.5-turbo")

    def generate_response(self, query: str, provider: str = 'deepseek', **kwargs) -> str:
        """
        生成响应 - 简化的API调用接口
        
        Args:
            query: 用户查询
            provider: 指定提供商
            **kwargs: 其他参数
            
        Returns:
            str: 生成的响应内容
        """
        try:
            from .llm_base import LLMMessage
            messages = [LLMMessage(role='user', content=query)]
            response = self.chat_completion(
                messages=messages,
                provider_name=provider,
                **kwargs
            )
            return response.content
        except Exception as e:
            logger.error(f"生成响应失败: {e}")
            return f"抱歉，生成响应时遇到错误: {str(e)}"
