#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM客户端实现包 - LLM Client Implementations Package

包含各种LLM提供商的具体实现：
- DeepSeek客户端
- OpenAI客户端  
- Anthropic客户端
- Gemini客户端
- Ollama客户端
"""

__version__ = "1.0.0"
__author__ = "Neogenesis Team"

# 导入所有可用的客户端实现
try:
    from .deepseek_client import create_llm_client as create_deepseek_client
except ImportError:
    create_deepseek_client = None

try:
    from .gemini_client import create_gemini_client, GeminiClient
except ImportError:
    create_gemini_client = None
    GeminiClient = None

try:
    from .openai_client import create_openai_client, OpenAIClient
except ImportError:
    create_openai_client = None
    OpenAIClient = None

try:
    from .anthropic_client import create_anthropic_client, AnthropicClient
except ImportError:
    create_anthropic_client = None
    AnthropicClient = None

try:
    from .ollama_client import create_ollama_client, OllamaClient
except ImportError:
    create_ollama_client = None
    OllamaClient = None

__all__ = [
    # 创建函数
    "create_deepseek_client",
    "create_gemini_client", 
    "create_openai_client",
    "create_anthropic_client",
    "create_ollama_client",
    
    # 客户端类
    "GeminiClient",
    "OpenAIClient", 
    "AnthropicClient",
    "OllamaClient",
]
