#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一LLM客户端接口 - 所有LLM客户端的基类和数据结构定义
Unified LLM Client Interface - Base classes and data structures for all LLM clients

设计理念：
- 提供统一的接口抽象，支持多种LLM提供商
- 定义标准的响应格式和错误处理
- 支持异步操作和流式响应
- 兼容现有DeepSeek实现的同时支持扩展
"""

import time
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Callable, AsyncIterator, Awaitable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """支持的LLM提供商枚举"""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    HUGGINGFACE = "huggingface"
    OLLAMA = "ollama"
    TOGETHER_AI = "together"
    COHERE = "cohere"
    GOOGLE = "google"
    GEMINI = "gemini"
    GEMINI_OPENAI = "gemini_openai"
    GROQ = "groq"


class LLMErrorType(Enum):
    """LLM错误类型枚举"""
    AUTHENTICATION = "authentication_error"
    RATE_LIMIT = "rate_limit_error"
    SERVER_ERROR = "server_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    PARSE_ERROR = "parse_error"
    MODEL_ERROR = "model_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class LLMMessage:
    """标准化的消息格式"""
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMUsage:
    """Token使用情况"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost_estimate(self) -> float:
        """估算成本（基于通用定价，可被子类覆盖）"""
        # 基础估算：输入0.001/1K tokens，输出0.002/1K tokens
        return (self.prompt_tokens * 0.001 + self.completion_tokens * 0.002) / 1000


@dataclass
class LLMResponse:
    """统一的LLM响应格式"""
    # 基础字段
    success: bool
    content: str = ""
    
    # 元数据
    provider: str = ""
    model: str = ""
    response_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    # Token使用情况
    usage: Optional[LLMUsage] = None
    
    # 错误信息
    error_type: Optional[LLMErrorType] = None
    error_message: str = ""
    error_details: Optional[Dict[str, Any]] = None
    
    # 原始响应（用于调试）
    raw_response: Optional[Dict[str, Any]] = None
    
    # 扩展字段
    finish_reason: Optional[str] = None
    choices: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        """响应后处理"""
        if not self.timestamp:
            self.timestamp = time.time()
    
    @property
    def is_error(self) -> bool:
        """是否为错误响应"""
        return not self.success or self.error_type is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "response_time": self.response_time,
            "timestamp": self.timestamp,
            "usage": self.usage.__dict__ if self.usage else None,
            "error_type": self.error_type.value if self.error_type else None,
            "error_message": self.error_message,
            "finish_reason": self.finish_reason
        }


@dataclass
class LLMConfig:
    """统一的LLM配置基类"""
    # 基础配置
    provider: LLMProvider
    api_key: str
    model_name: str = ""
    
    # 生成参数
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # 网络配置
    base_url: Optional[str] = None
    timeout: tuple = (30, 180)  # (connect_timeout, read_timeout)
    max_retries: int = 3
    retry_delay_base: float = 2.0
    proxies: Optional[Dict[str, str]] = None
    
    # 性能配置
    enable_cache: bool = True
    cache_ttl: int = 300
    request_interval: float = 1.0
    
    # 🔥 新增：网络错误处理配置
    network_retry_multiplier: float = 2.0  # 网络错误重试时间倍数
    max_network_retry_delay: float = 120.0  # 最大网络重试延迟
    enable_metrics: bool = True  # 是否启用指标收集
    
    # 扩展配置
    extra_headers: Optional[Dict[str, str]] = None
    extra_params: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """配置后处理"""
        if not self.model_name:
            # 如果没有指定模型，使用默认模型
            default_models = {
                LLMProvider.DEEPSEEK: "deepseek-chat",
                LLMProvider.OPENAI: "gpt-3.5-turbo",
                LLMProvider.ANTHROPIC: "claude-3-sonnet-20240229",
                LLMProvider.AZURE_OPENAI: "gpt-35-turbo",
                LLMProvider.HUGGINGFACE: "gpt2",
                LLMProvider.OLLAMA: "llama2",
                LLMProvider.TOGETHER_AI: "togethercomputer/llama-2-7b-chat",
                LLMProvider.COHERE: "command",
                LLMProvider.GOOGLE: "gemini-pro",
                LLMProvider.GROQ: "llama2-70b-4096"
            }
            self.model_name = default_models.get(self.provider, "unknown")


class BaseLLMClient(ABC):
    """
    统一LLM客户端抽象基类
    
    所有LLM客户端都应该继承此类并实现其抽象方法。
    这个设计受到了LangChain和unified-llm-client的启发，
    但针对Meta MAB系统的特定需求进行了优化。
    """
    
    def __init__(self, config: LLMConfig):
        """
        初始化LLM客户端
        
        Args:
            config: LLM配置对象
        """
        self.config = config
        self.provider = config.provider
        self.model_name = config.model_name
        
        # 性能统计
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "total_tokens": 0,
            "error_counts": {},
            "last_request_time": 0.0
        }
        
        logger.info(f"🤖 初始化{self.provider.value}客户端: {self.model_name}")
    
    @abstractmethod
    def chat_completion(self, 
                       messages: Union[str, List[LLMMessage]], 
                       temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None,
                       **kwargs) -> LLMResponse:
        """
        聊天完成接口 - 核心抽象方法
        
        Args:
            messages: 消息内容，可以是字符串或消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一的响应对象
        """
        pass
    
    @abstractmethod
    async def achat_completion(self, 
                              messages: Union[str, List[LLMMessage]], 
                              temperature: Optional[float] = None,
                              max_tokens: Optional[int] = None,
                              **kwargs) -> LLMResponse:
        """
        🚀 异步聊天完成接口 - 核心异步抽象方法
        
        Args:
            messages: 消息内容，可以是字符串或消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一的响应对象
        """
        pass
    
    def call_api(self, prompt: str, 
                 system_message: Optional[str] = None,
                 temperature: Optional[float] = None,
                 **kwargs) -> str:
        """
        简化的API调用接口 - 兼容现有代码
        
        这个方法为了保持与现有代码的兼容性而存在。
        内部调用chat_completion方法。
        
        Args:
            prompt: 用户提示
            system_message: 系统消息
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 响应内容
            
        Raises:
            ConnectionError: 当所有重试都失败时
        """
        # 构建消息列表
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
        
        # 兼容性处理
        if response.success:
            return response.content
        else:
            error_msg = f"{self.provider.value} API调用失败: {response.error_message}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    async def acall_api(self, prompt: str, 
                       system_message: Optional[str] = None,
                       temperature: Optional[float] = None,
                       **kwargs) -> str:
        """
        🚀 异步简化的API调用接口 - 兼容现有代码
        
        这个方法为了保持与现有代码的兼容性而存在。
        内部调用achat_completion方法。
        
        Args:
            prompt: 用户提示
            system_message: 系统消息
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 响应内容
            
        Raises:
            ConnectionError: 当所有重试都失败时
        """
        # 构建消息列表
        messages = []
        if system_message:
            messages.append(LLMMessage(role="system", content=system_message))
        messages.append(LLMMessage(role="user", content=prompt))
        
        # 使用achat_completion执行
        response = await self.achat_completion(messages, temperature=temperature, **kwargs)
        
        if response.success:
            return response.content
        else:
            error_msg = f"{self.provider.value} 异步API调用失败: {response.error_message}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        获取可用模型列表
        
        Returns:
            List[str]: 可用的模型名称列表
        """
        pass
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        获取提供商信息
        
        Returns:
            Dict[str, Any]: 提供商信息
        """
        return {
            "provider": self.provider.value,
            "model": self.model_name,
            "base_url": self.config.base_url,
            "supported_features": self.get_supported_features(),
            "stats": self.get_stats()
        }
    
    def get_supported_features(self) -> List[str]:
        """
        获取支持的功能列表
        
        Returns:
            List[str]: 支持的功能
        """
        # 基础功能
        features = ["chat_completion", "text_generation"]
        
        # 子类可以覆盖此方法添加更多功能
        return features
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = self.stats.copy()
        
        # 计算衍生指标
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["average_response_time"] = stats["total_response_time"] / stats["successful_requests"] if stats["successful_requests"] > 0 else 0
        else:
            stats["success_rate"] = 0.0
            stats["average_response_time"] = 0.0
        
        return stats
    
    def _update_stats(self, response: LLMResponse):
        """
        更新性能统计
        
        Args:
            response: LLM响应对象
        """
        self.stats["total_requests"] += 1
        self.stats["last_request_time"] = time.time()
        
        if response.success:
            self.stats["successful_requests"] += 1
            self.stats["total_response_time"] += response.response_time
            
            if response.usage:
                self.stats["total_tokens"] += response.usage.total_tokens
        else:
            self.stats["failed_requests"] += 1
            
            if response.error_type:
                error_key = response.error_type.value
                self.stats["error_counts"][error_key] = self.stats["error_counts"].get(error_key, 0) + 1
    
    def _prepare_messages(self, messages: Union[str, List[LLMMessage]]) -> List[LLMMessage]:
        """
        准备消息格式
        
        Args:
            messages: 输入消息
            
        Returns:
            List[LLMMessage]: 标准化的消息列表
        """
        if isinstance(messages, str):
            return [LLMMessage(role="user", content=messages)]
        elif isinstance(messages, list):
            # 确保都是LLMMessage对象
            result = []
            for msg in messages:
                if isinstance(msg, LLMMessage):
                    result.append(msg)
                elif isinstance(msg, dict):
                    result.append(LLMMessage(
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                        name=msg.get("name"),
                        metadata=msg.get("metadata")
                    ))
                else:
                    # 假设是字符串
                    result.append(LLMMessage(role="user", content=str(msg)))
            return result
        else:
            raise ValueError(f"不支持的消息格式: {type(messages)}")
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "total_tokens": 0,
            "error_counts": {},
            "last_request_time": 0.0
        }
        logger.info(f"🔄 {self.provider.value}客户端统计已重置")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.provider.value}Client(model={self.model_name})"
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"{self.__class__.__name__}(provider={self.provider.value}, model={self.model_name})"


# 工具函数

def create_llm_config(provider: str, api_key: str, **kwargs) -> LLMConfig:
    """
    便捷的配置创建函数
    
    Args:
        provider: 提供商名称
        api_key: API密钥
        **kwargs: 其他配置参数
        
    Returns:
        LLMConfig: 配置对象
    """
    provider_enum = LLMProvider(provider.lower())
    
    return LLMConfig(
        provider=provider_enum,
        api_key=api_key,
        **kwargs
    )


def create_error_response(provider: str, error_type: LLMErrorType, 
                         error_message: str, **kwargs) -> LLMResponse:
    """
    创建错误响应的便捷函数
    
    Args:
        provider: 提供商名称
        error_type: 错误类型
        error_message: 错误消息
        **kwargs: 其他参数
        
    Returns:
        LLMResponse: 错误响应对象
    """
    return LLMResponse(
        success=False,
        provider=provider,
        error_type=error_type,
        error_message=error_message,
        **kwargs
    )


def create_success_response(provider: str, model: str, content: str,
                           usage: Optional[LLMUsage] = None,
                           response_time: float = 0.0,
                           **kwargs) -> LLMResponse:
    """
    创建成功响应的便捷函数
    
    Args:
        provider: 提供商名称
        model: 模型名称
        content: 响应内容
        usage: Token使用情况
        response_time: 响应时间
        **kwargs: 其他参数
        
    Returns:
        LLMResponse: 成功响应对象
    """
    return LLMResponse(
        success=True,
        provider=provider,
        model=model,
        content=content,
        usage=usage,
        response_time=response_time,
        **kwargs
    )


def parse_messages_from_dict(messages_data: List[Dict[str, Any]]) -> List[LLMMessage]:
    """
    从字典列表解析消息
    
    Args:
        messages_data: 字典格式的消息列表
        
    Returns:
        List[LLMMessage]: 解析后的消息列表
    """
    return [
        LLMMessage(
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            name=msg.get("name"),
            metadata=msg.get("metadata")
        )
        for msg in messages_data
    ]
