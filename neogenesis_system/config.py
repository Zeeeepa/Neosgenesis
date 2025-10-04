#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置文件 - 存放所有系统配置
Configuration file - stores all system configurations
"""

# ==================== 传统DeepSeek API配置（向后兼容） ====================
# 注意：这些常量保留用于向后兼容，新代码应使用LLM_PROVIDERS_CONFIG
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_CHAT_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"

# API调用配置 - 针对并发调用优化
API_CONFIG = {
    "temperature": 0.7,
    "max_tokens": 2000,
    "timeout": (15, 60),  # 🔧 增加超时时间 - 连接15秒，读取60秒（应对并发压力）
    "max_retries": 3,     # 🔧 增加重试次数到3次
    "retry_delay_base": 2,  # 🔧 增加退避基数到2
    "proxies": {'http': None, 'https': None},  # 禁用代理
    "concurrent_requests": True,  # 启用并发请求
    "connection_pool_size": 5,   # 🔧 减少连接池大小，避免过度并发
    "enable_keep_alive": True,   # 启用连接复用
    "request_interval": 1.0      # 🔧 新增：请求间隔1秒，避免过于频繁
}

# MAB算法配置
MAB_CONFIG = {
    "convergence_threshold": 0.05,  # 收敛阈值
    "min_samples": 10,  # 最小样本数
    "base_exploration_rate": 0.1,  # 基础探索率
    "exploration_decay": 0.99,  # 探索率衰减
    "min_exploration_rate": 0.05  # 最小探索率
}

# 系统限制配置
SYSTEM_LIMITS = {
    "max_decision_history": 1000,
    "max_performance_history": 50,
    "max_dimension_cache": 100,
    "max_failure_analysis_history": 20,
    "max_alternative_thinking_signals": 5,
    "max_retry_strategies": 10
}

# 评估配置
EVALUATION_CONFIG = {
    "task_completion_thresholds": {
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    },
    "confidence_adjustment_factors": {
        "complexity": 0.1,
        "frequency": 0.2,
        "quality": 0.2,
        "option_match": 0.15
    }
}

# DeepSeek提示模板
PROMPT_TEMPLATES = {
    "dimension_creation": """
作为一个专业的任务分析和决策维度设计专家，请对以下任务进行深度分析并创建合适的决策维度。

📋 **任务描述**: {user_query}
{context_info}

📊 **历史学习信息**: 
{historical_insights}

🎯 **任务要求**:
1. 深度分析任务的核心挑战和决策点
2. 基于任务特性智能创建3-6个关键决策维度
3. 每个维度包含2-4个具体可行的选项
4. 选项之间要互斥且覆盖主要决策空间
5. 考虑技术实现、性能、可靠性、用户体验等多个角度

📝 **输出要求**:
请以JSON格式输出，确保格式严格正确，不要包含任何额外的文本或解释。

**JSON结构**:
{{
    "task_analysis": {{
        "complexity": 0.7,
        "domain": "任务领域",
        "key_challenges": ["挑战1", "挑战2", "挑战3"]
    }},
    "suggested_dimensions": {{
        "维度名称1": {{
            "选项1": "选项1的详细描述，说明适用场景和优势",
            "选项2": "选项2的详细描述，说明适用场景和优势",
            "选项3": "选项3的详细描述，说明适用场景和优势"
        }},
        "维度名称2": {{
            "选项A": "选项A的详细描述",
            "选项B": "选项B的详细描述"
        }}
    }},
    "reasoning": "详细说明为什么选择这些维度，每个维度解决什么问题，以及维度之间的关系"
}}

💡 **设计原则**:
- 维度名称要准确反映决策要点
- 选项描述要具体可操作
- 考虑实际应用场景的复杂性
- 平衡技术可行性和效果优化
- 体现对任务深度理解和专业判断

请基于你的专业知识和分析能力，为这个任务创建最合适的决策维度组合。
""",

    "self_analysis": """
作为DeepSeek AI模型，请对您自身在处理以下特定任务时的能力局限性进行深度自我分析：

## 任务特征分析：
- 涉及领域：{domain_tags}
- 复杂度指标：{complexity_indicators}
- 创新性要求：{creativity_requirement:.2f} (0-1 scale)
- 歧义程度：{ambiguity_level:.2f} (0-1 scale)
- 实时性要求：{real_time_requirements}
- 技术术语密度：{technical_terms_count}

## 请从以下维度进行自我局限性分析：

1. **知识边界局限**：在上述领域中，您认为自己的知识可能存在哪些盲点或不足？

2. **推理能力局限**：对于该复杂度和创新性要求，您的逻辑推理可能遇到什么挑战？

3. **实时性局限**：考虑API调用延迟，您在实时响应方面有何限制？

4. **上下文理解局限**：对于该歧义程度的任务，您可能误解哪些方面？

5. **创新性局限**：在高创新性要求下，您可能难以提供什么类型的创新解决方案？

6. **技术实现局限**：在具体代码生成或技术实现方面，您可能存在哪些不足？

7. **动态适应局限**：在任务需求变化时，您的适应能力可能受到什么制约？

请按以下JSON格式返回分析结果：
{{
    "limitations": [
        {{
            "type": "具体局限性类型",
            "severity": 0.0-1.0的严重程度评分,
            "description": "详细描述这个局限性",
            "specific_context": "在当前任务场景下的具体表现",
            "impact": "对任务执行可能产生的影响",
            "confidence": 0.0-1.0的评估置信度,
            "mitigation_suggestions": ["补偿策略建议1", "补偿策略建议2"]
        }}
    ],
    "overall_capability_assessment": {{
        "task_suitability": 0.0-1.0的任务适配度评分,
        "key_strengths": ["在此任务中的主要优势"],
        "critical_weaknesses": ["最需要注意的弱点"],
        "recommended_approach": "建议的任务处理方式"
    }}
}}

请基于您对自身能力的真实理解，诚实、准确地进行分析。
""",

    # Gemini优化的Prompt模板
    "gemini_task_analysis": """
You are an expert task analysis specialist. Analyze the following task and provide a structured assessment.

**Task**: {user_query}
**Context**: {context_info}

**Analysis Requirements**:
1. Assess task complexity (0.0-1.0 scale)
2. Identify key challenges and requirements
3. Determine optimal approach strategy
4. Evaluate resource needs and constraints

**Response Format**:
Provide your analysis in valid JSON format only, with no additional text:

{{
    "complexity_score": 0.7,
    "domain": "task_domain",
    "key_challenges": ["challenge1", "challenge2", "challenge3"],
    "approach_strategy": "recommended_strategy",
    "resource_requirements": ["requirement1", "requirement2"],
    "estimated_effort": "effort_level",
    "success_factors": ["factor1", "factor2"],
    "potential_risks": ["risk1", "risk2"]
}}
""",

    "gemini_dimension_creation": """
You are a decision framework architect. Create optimal decision dimensions for the given task.

**Task**: {user_query}
**Historical Insights**: {historical_insights}

**Requirements**:
- Create 3-6 key decision dimensions
- Each dimension should have 2-4 mutually exclusive options
- Options must be actionable and cover the decision space
- Consider technical feasibility, performance, and user experience

**Output only valid JSON**:

{{
    "task_analysis": {{
        "complexity": 0.7,
        "domain": "domain_name",
        "key_challenges": ["challenge1", "challenge2"]
    }},
    "dimensions": {{
        "dimension_1": {{
            "option_a": "detailed description of option A with use cases",
            "option_b": "detailed description of option B with use cases"
        }},
        "dimension_2": {{
            "option_x": "detailed description of option X",
            "option_y": "detailed description of option Y",
            "option_z": "detailed description of option Z"
        }}
    }},
    "reasoning": "explanation of dimension choices and relationships"
}}
""",

    "gemini_path_verification": """
You are a solution validation expert. Evaluate the feasibility and quality of the proposed reasoning path.

**Task**: {user_query}
**Proposed Path**: {reasoning_path}
**Context**: {context}

**Evaluation Criteria**:
- Technical feasibility (0.0-1.0)
- Implementation complexity (0.0-1.0)
- Expected effectiveness (0.0-1.0)
- Resource requirements
- Potential risks and mitigation strategies

**Output valid JSON only**:

{{
    "feasibility_score": 0.8,
    "complexity_score": 0.6,
    "effectiveness_score": 0.9,
    "overall_rating": 0.77,
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "risks": ["risk1", "risk2"],
    "recommendations": ["recommendation1", "recommendation2"],
    "implementation_notes": "specific guidance for implementation"
}}
"""
}

# 日志配置
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": ["console", "file"],
    "file_path": "neogenesis_system.log"
}

# 性能优化配置
PERFORMANCE_CONFIG = {
    "enable_parallel_path_verification": True,  # 启用并行路径验证
    "enable_intelligent_caching": True,         # 启用智能缓存
    "enable_adaptive_path_count": True,         # 启用自适应路径数量
    "enable_early_termination": True,           # 启用早期终止
    "max_concurrent_verifications": 2,          # 🔧 减少并发验证数，降低API调用压力
    "cache_ttl_seconds": 3600,                  # 缓存过期时间(秒)
    "path_consistency_threshold": 0.8,          # 路径一致性阈值
    "min_verification_paths": 2,                # 最小验证路径数
    "max_verification_paths": 6,                # 最大验证路径数
    "confidence_path_mapping": {                # 置信度-路径数映射
        0.9: 2,  # 高置信度：验证2条路径
        0.7: 3,  # 中高置信度：验证3条路径
        0.5: 4,  # 中等置信度：验证4条路径
        0.3: 5,  # 低置信度：验证5条路径
        0.0: 6   # 极低置信度：验证6条路径
    }
}

# RAG配置
RAG_CONFIG = {
    "max_search_results": 8,                    # 最大搜索结果数量
    "search_timeout": 30,                       # 搜索超时时间(秒)
    "information_synthesis_timeout": 60,        # 信息综合超时时间(秒)
    "cache_expiry_hours": 24,                   # 缓存过期时间(小时)
    "min_seed_quality_threshold": 50,           # 最小种子质量阈值(字符数)
    "rag_enhancement_score_threshold": 2,       # RAG增强判断阈值
    "enable_intelligent_caching": True,         # 启用智能缓存
    "enable_multi_source_verification": True,   # 启用多源验证
    "enable_contextual_relevance_scoring": True, # 启用上下文相关性评分
    "search_engines": ["tavily", "firecrawl"],           # 支持的搜索引擎
    "default_search_engine": "tavily",        # 默认搜索引擎
    "tavily_api_key": "",   # Tavily API密钥（请从环境变量TAVILY_API_KEY设置）
    "firecrawl_api_key": "",   # Firecrawl API密钥（请从环境变量FIRECRAWL_API_KEY设置）
    "max_search_queries_per_request": 2,        # 🚨 减少搜索查询数 - 降低请求压力
    "information_diversity_weight": 0.3,        # 信息多样性权重
    "source_reliability_weight": 0.4,           # 来源可靠性权重
    "contextual_relevance_weight": 0.3,         # 上下文相关性权重
    # 🚀 并行搜索优化配置
    "enable_parallel_search": False,            # 🚨 临时禁用并行搜索 - 避免请求风暴触发速率限制
    "max_search_workers": 3,                    # 最大并行搜索工作线程数
    "parallel_search_timeout": 45,              # 并行搜索总超时时间(秒)
    "enable_search_result_streaming": False,    # 启用搜索结果流式返回
    "enable_real_web_search": True,             # ✅ 启用真实Firecrawl搜索
    # 🛡️ 搜索稳定性优化配置
    "search_rate_limit_interval": 3.0,          # 🚨 增加搜索请求间隔（秒） - 降低触发速率限制风险
    "search_max_retries": 2,                     # 🚨 减少重试次数 - 避免过度请求
    "search_retry_base_delay": 2.0,              # 🚨 增加重试基础延迟（秒）
    "search_use_fallback_on_ratelimit": False    # 遇到速率限制时的处理策略（已移除模拟搜索）
}

# 特性开关
FEATURE_FLAGS = {
    "enable_llm_self_assessment": True,
    "enable_alternative_thinking": True,
    "enable_performance_tracking": True,
    "enable_cache": True,
    "enable_fallback_dimensions": True,
    "enable_performance_optimization": True,    # 启用性能优化
    "enable_rag_enhancement": True,             # 新增：启用RAG增强思维种子生成
    "enable_hybrid_seed_generation": False,     # 新增：启用混合种子生成策略
    "enable_real_time_information": True,       # 新增：启用实时信息获取
    "enable_information_verification": True,    # 新增：启用信息验证
    "enable_multi_llm_support": True,          # 新增：启用多LLM支持
    "prefer_gemini_for_analysis": True,        # 新增：分析任务优先使用Gemini
    "enable_gemini_json_mode": True            # 新增：启用Gemini JSON模式
}

# ==================== 多LLM配置系统 ====================

# LLM提供商配置
LLM_PROVIDERS_CONFIG = {
    "deepseek": {
        "display_name": "DeepSeek",
        "provider_type": "deepseek",
        "api_key_env": "DEEPSEEK_API_KEY",
        "hardcoded_api_key": "",  # DeepSeek API密钥（请从环境变量DEEPSEEK_API_KEY设置）
        "default_model": "deepseek-chat",
        "available_models": ["deepseek-v3", "deepseek-chat", "deepseek-coder"],
        "base_url": "https://api.deepseek.com/v1",
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": (30, 180),
        "max_retries": 3,
        "retry_delay_base": 2.0,
        "request_interval": 1.0,
        "features": ["chat", "coding", "chinese", "reasoning"],
        "cost_per_1k_tokens": {"input": 0.00014, "output": 0.00028},
        "context_window": 32768,
        "enabled": True
    },
    
    "openai": {
        "display_name": "OpenAI GPT (via DeepSeek)",
        "provider_type": "openai", 
        "api_key_env": "OPENAI_API_KEY",
        "hardcoded_api_key": "",  # 不再使用硬编码密钥，改用环境变量
        "default_model": "deepseek-v3",  # 修改为使用deepseek-v3
        "available_models": [
            "deepseek-v3", "gemini-2.5-flash", "gemini-2.5-pro",
            "gpt-3.5-turbo", "gpt-3.5-turbo-16k",
            "gpt-4", "gpt-4-turbo-preview", "gpt-4o", "gpt-4o-mini"
        ],
        "base_url": "https://api.deepseek.com/v1",  # 修改为DeepSeek官方API地址
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": (30, 120),
        "max_retries": 3,
        "retry_delay_base": 2.0,
        "request_interval": 0.5,
        "features": ["chat", "function_calling", "vision", "json_mode"],
        "cost_per_1k_tokens": {"input": 0.0015, "output": 0.002},
        "context_window": 16384,
        "enabled": False  # 禁用OpenAI配置，改用DeepSeek
    },
    
    "anthropic": {
        "display_name": "Anthropic Claude",
        "provider_type": "anthropic",
        "api_key_env": "ANTHROPIC_API_KEY", 
        "default_model": "claude-3-sonnet-20240229",
        "available_models": [
            "claude-3-opus-20240229", "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307", "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022"
        ],
        "base_url": None,  # 使用默认
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": (30, 180),
        "max_retries": 3,
        "retry_delay_base": 2.0,
        "request_interval": 1.0,
        "features": ["chat", "long_context", "reasoning", "analysis"],
        "cost_per_1k_tokens": {"input": 0.003, "output": 0.015},
        "context_window": 200000,  # Claude支持长上下文
        "enabled": False  # 默认禁用，需要API密钥
    },
    
    "azure_openai": {
        "display_name": "Azure OpenAI",
        "provider_type": "azure_openai",
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "azure_endpoint_env": "AZURE_OPENAI_ENDPOINT",
        "api_version": "2024-02-15-preview",
        "default_model": "gpt-35-turbo",
        "available_models": ["gpt-35-turbo", "gpt-4", "gpt-4-32k"],
        "max_tokens": 4000,
        "temperature": 0.7,
        "timeout": (30, 120),
        "max_retries": 3,
        "retry_delay_base": 2.0,
        "request_interval": 0.5,
        "features": ["chat", "function_calling", "enterprise"],
        "cost_per_1k_tokens": {"input": 0.0015, "output": 0.002},
        "context_window": 16384,
        "enabled": False  # 默认禁用，需要API密钥和端点
    },
    
    "gemini": {
        "display_name": "Google Gemini",
        "provider_type": "gemini",
        "api_key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "available_models": [
            "gemini-2.5-flash", "gemini-2.5-pro"
        ],
        "base_url": "https://generativelanguage.googleapis.com",
        "max_tokens": 8192,
        "temperature": 0.7,
        "timeout": (30, 120),
        "max_retries": 3,
        "retry_delay_base": 2.0,
        "request_interval": 0.5,
        "features": ["chat", "function_calling", "multimodal", "json_mode", "fast_inference"],
        "cost_per_1k_tokens": {"input": 0.000075, "output": 0.0003},  # Gemini 2.5 Flash pricing
        "context_window": 1048576,  # 1M tokens context window
        "enabled": True  # 默认启用，推荐使用
    },
    
    "ollama": {
        "display_name": "Ollama (本地)",
        "provider_type": "ollama",
        "api_key_env": None,  # 本地服务不需要API密钥
        "default_model": "deepseek-r1:7b",
        "available_models": ["deepseek-r1:7b", "llama2", "mistral", "codellama", "phi"],
        "base_url": "http://localhost:11434",
        "max_tokens": 2000,
        "temperature": 0.7,
        "timeout": (10, 300),  # 本地推理可能较慢
        "max_retries": 2,
        "retry_delay_base": 1.0,
        "request_interval": 0.1,
        "features": ["chat", "local", "offline", "privacy"],
        "cost_per_1k_tokens": {"input": 0.0, "output": 0.0},  # 本地免费
        "context_window": 4096,
        "enabled": False  # 默认禁用，需要本地Ollama服务
    }
}

# 默认LLM配置
DEFAULT_LLM_CONFIG = {
    "primary_provider": "auto",          # 主要提供商（auto=自动检测可用的提供商）
    "preferred_providers": [             # 首选提供商顺序（按优先级）
        "gemini", "deepseek", "openai", "anthropic", "ollama"
    ],
    "fallback_providers": [              # 回退提供商（按优先级）
        "deepseek", "openai", "anthropic", "ollama", "gemini"
    ],
    "auto_fallback": True,               # 是否自动回退
    "fallback_on_error": True,          # 错误时是否回退
    "fallback_on_rate_limit": True,     # 速率限制时是否回退
    "load_balancing": False,             # 是否启用负载均衡
    "provider_selection_strategy": "priority",  # 选择策略: priority, round_robin, random
    "health_check_interval": 300,       # 健康检查间隔（秒）
    "performance_tracking": True,       # 是否跟踪性能
    "cost_tracking": True,              # 是否跟踪成本
    "usage_logging": True               # 是否记录使用情况
}

# LLM管理器配置
LLM_MANAGER_CONFIG = {
    "max_concurrent_requests": 3,       # 最大并发请求数
    "request_queue_size": 100,          # 请求队列大小
    "timeout_buffer": 5,                # 超时缓冲（秒）
    "health_check_timeout": 10,         # 健康检查超时（秒）
    "stats_retention_days": 30,         # 统计数据保留天数
    "enable_request_caching": True,     # 启用请求缓存
    "cache_ttl_seconds": 300,           # 缓存过期时间（秒）
    "enable_response_validation": True, # 启用响应验证
    "log_all_interactions": False,      # 是否记录所有交互（调试用）
    "enable_provider_metrics": True     # 启用提供商指标
}

# 成本控制配置
COST_CONTROL_CONFIG = {
    "enable_cost_limits": True,         # 启用成本限制
    "daily_cost_limit_usd": 10.0,      # 每日成本限制（美元）
    "monthly_cost_limit_usd": 100.0,   # 每月成本限制（美元）
    "cost_alert_threshold": 0.8,       # 成本警告阈值（比例）
    "enable_cost_optimization": True,  # 启用成本优化
    "prefer_cheaper_models": True,     # 优先使用便宜的模型
    "token_usage_tracking": True,      # 跟踪token使用量
    "detailed_cost_breakdown": True    # 详细的成本分解
}
