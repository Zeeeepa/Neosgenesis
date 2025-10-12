
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量级分析助手 - 专注于快速任务评估和复杂度分析
Lightweight Analysis Assistant - focused on rapid task assessment and complexity analysis

核心职责：
1. 任务复杂度分析 (快速启发式方法)
2. 任务置信度评估 (基于历史数据和模式)
3. 领域推断和统计分析 (辅助决策支持)

"""

import time
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# LLM 相关导入 - 支持多种导入方式
try:
    # 尝试相对导入
    from ..providers.llm_manager import LLMManager
    from ..providers.impl.ollama_client import create_ollama_client, OllamaClient
    from ..providers.llm_base import LLMConfig, LLMProvider, LLMMessage
    LLM_AVAILABLE = True
except ImportError as e1:
    try:
        # 尝试绝对导入
        from neogenesis_system.providers.llm_manager import LLMManager
        from neogenesis_system.providers.impl.ollama_client import create_ollama_client, OllamaClient
        from neogenesis_system.providers.llm_base import LLMConfig, LLMProvider, LLMMessage
        LLM_AVAILABLE = True
    except ImportError as e2:
        try:
            # 尝试直接导入（适用于直接运行的情况）
            import sys
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            
            from providers.llm_manager import LLMManager
            from providers.impl.ollama_client import create_ollama_client, OllamaClient
            from providers.llm_base import LLMConfig, LLMProvider, LLMMessage
            LLM_AVAILABLE = True
        except ImportError as e3:
            logger.debug(f"LLM组件导入失败，将使用纯启发式模式: 相对导入({e1}), 绝对导入({e2}), 直接导入({e3})")
            LLM_AVAILABLE = False
            # 定义空的类型提示
            LLMManager = None
            OllamaClient = None


# ==================== 路由分类数据结构定义 ====================

class TaskComplexity(Enum):
    """任务复杂度枚举"""
    SIMPLE = "simple"         # 简单任务：直接回答或单步操作
    MODERATE = "moderate"     # 中等任务：需要一定分析和多步骤
    COMPLEX = "complex"       # 复杂任务：需要深入分析和系统性方法
    EXPERT = "expert"         # 专家级任务：需要专业知识和复杂推理

class TaskDomain(Enum):
    """任务领域枚举"""
    WEB_DEV = "web_development"          # Web开发
    DATA_SCIENCE = "data_science"        # 数据科学
    API_DEV = "api_development"          # API开发  
    SYSTEM_ADMIN = "system_admin"        # 系统管理
    DATABASE = "database"                # 数据库
    SECURITY = "security"                # 安全
    MOBILE_DEV = "mobile_development"    # 移动开发
    ML_AI = "machine_learning"           # 机器学习/AI
    GENERAL = "general"                  # 通用任务

class TaskIntent(Enum):
    """任务意图枚举"""
    QUESTION = "question"                # 咨询问题
    TASK_EXECUTION = "task_execution"    # 任务执行
    ANALYSIS = "analysis"                # 分析请求
    CREATION = "creation"                # 创建内容
    DEBUGGING = "debugging"              # 调试问题
    OPTIMIZATION = "optimization"        # 优化改进

class TaskUrgency(Enum):
    """任务紧急度枚举"""
    LOW = "low"                         # 低优先级
    MEDIUM = "medium"                   # 中等优先级  
    HIGH = "high"                       # 高优先级
    CRITICAL = "critical"               # 紧急关键

class RouteStrategy(Enum):
    """路由策略枚举"""
    DIRECT_RESPONSE = "direct_response"              # 直接回答
    MULTI_STAGE_PROCESSING = "multi_stage_processing" # 多阶段处理
    WORKFLOW_PLANNING = "workflow_planning"          # 工作流规划
    IDEATION_MODE = "ideation_mode"                 # 创意模式
    DIAGNOSTIC_MODE = "diagnostic_mode"             # 诊断模式
    EXPERT_CONSULTATION = "expert_consultation"      # 专家咨询

@dataclass
class TriageClassification:
    """任务分诊分类结果"""
    complexity: TaskComplexity
    domain: TaskDomain
    intent: TaskIntent
    urgency: TaskUrgency
    route_strategy: RouteStrategy
    confidence: float                    # 分类置信度 (0.0-1.0)
    reasoning: str                       # 分类理由
    key_factors: List[str]              # 关键因素
    estimated_time: Optional[int] = None # 预估处理时间(分钟)
    required_resources: Optional[List[str]] = None  # 所需资源


@dataclass  
class PriorReasoner:
    """
    智能路由网关 - 升级版任务分析器
    
    核心功能：
    1. 快速任务复杂度分析 (启发式 + LLM双重分析)
    2. 智能置信度评估 (基于语义理解)
    3. 输入分类和路由决策 (LLM驱动)
    4. 向后兼容的接口设计
    """
    
    def __init__(self, 
                 api_key: str = "",
                 llm_manager: Optional[LLMManager] = None,
                 ollama_config: Optional[Dict[str, Any]] = None,
                 enable_llm: bool = True):
        """
        初始化智能路由网关
        
        Args:
            api_key: 保留用于向后兼容
            llm_manager: 可选的LLM管理器实例
            ollama_config: Ollama配置参数
            enable_llm: 是否启用LLM功能
        """
        # 保持向后兼容
        self.api_key = api_key
        self.assessment_cache = {}  # 评估缓存
        self.confidence_history = []  # 置信度历史
        
        # LLM 能力集成
        self.enable_llm = enable_llm and LLM_AVAILABLE
        self.llm_manager = None
        self.ollama_client = None
        
        if self.enable_llm:
            try:
                # 尝试初始化LLM能力（优先使用LLMManager，其次Gemini，最后Ollama）
                self._init_llm_capabilities(llm_manager, ollama_config)
            except Exception as e:
                logger.warning(f"⚠️ LLM能力初始化失败，将使用启发式模式: {e}")
                self.enable_llm = False
        
        # 日志信息
        mode = "LLM增强智能分析" if self.enable_llm else "轻量级启发式分析"
        logger.info(f"🧠 PriorReasoner 已初始化 ({mode}模式)")
        
        if self.enable_llm and self.llm_manager:
            logger.info("✅ LLM管理器已集成，支持智能路由功能")
        if self.enable_llm and self.ollama_client:
            logger.info("✅ Ollama客户端已连接，支持本地快速推理")
    
    def _init_llm_capabilities(self, llm_manager: Optional[LLMManager], ollama_config: Optional[Dict[str, Any]]):
        """
        初始化LLM能力 - 优先使用Gemini 2.5 Flash
        
        Args:
            llm_manager: 外部提供的LLM管理器
            ollama_config: Ollama配置参数（保留向后兼容）
        """
        # 方式1：使用外部提供的LLM管理器（推荐）
        if llm_manager:
            self.llm_manager = llm_manager
            logger.info("🔗 使用外部提供的LLM管理器（支持Gemini等多提供商）")
            return
        
        # 方式2：尝试创建内置LLM管理器（优先Gemini）
        try:
            self.llm_manager = LLMManager()
            if self.llm_manager.initialized:
                logger.info("🚀 内置LLM管理器初始化成功，优先使用Gemini 2.5 Flash")
                return
        except Exception as e:
            logger.warning(f"⚠️ 内置LLM管理器创建失败: {e}")
        
        # 方式3：直接尝试创建Gemini客户端
        try:
            import os
            gemini_api_key = os.getenv("GEMINI_API_KEY", "")
            if gemini_api_key:
                try:
                    from ..providers.impl.gemini_client import create_gemini_client
                except ImportError:
                    try:
                        from neogenesis_system.providers.impl.gemini_client import create_gemini_client
                    except ImportError:
                        logger.debug("⚠️ Gemini客户端模块不存在，跳过Gemini初始化")
                        raise ImportError("gemini_client module not found")
                
                gemini_client = create_gemini_client(
                    api_key=gemini_api_key,
                    model="gemini-2.5-flash",
                    temperature=0.1,  # 分类任务需要确定性
                    max_tokens=1000   # 快速响应
                )
                
                # 包装为简单的管理器接口
                class SimpleGeminiManager:
                    def __init__(self, client):
                        self.client = client
                        self.initialized = True
                    
                    def call_api(self, prompt, system_message=None, **kwargs):
                        messages = []
                        if system_message:
                            messages.append({"role": "system", "content": system_message})
                        messages.append({"role": "user", "content": prompt})
                        
                        try:
                            from ..providers.llm_base import LLMMessage
                        except ImportError:
                            try:
                                from neogenesis_system.providers.llm_base import LLMMessage
                            except ImportError:
                                # 定义基本的消息类
                                class LLMMessage:
                                    def __init__(self, role, content):
                                        self.role = role
                                        self.content = content
                        
                        llm_messages = [LLMMessage(role=msg["role"], content=msg["content"]) for msg in messages]
                        response = self.client.chat_completion(llm_messages, **kwargs)
                        
                        if response.success:
                            return response.content
                        else:
                            raise Exception(response.error_message)
                
                self.llm_manager = SimpleGeminiManager(gemini_client)
                logger.info("✅ 直接创建Gemini客户端成功，用于快速任务分析")
                return
                
        except Exception as e:
            logger.warning(f"⚠️ 直接创建Gemini客户端失败: {e}")
        
        # 方式4：回退到Ollama（保留向后兼容）
        default_ollama_config = {
            "model_name": "deepseek-r1:7b",  # 使用已安装的deepseek-r1:7b模型进行快速分类
            "base_url": "http://localhost:11434",
            "temperature": 0.1,             # 分类任务需要确定性
            "max_tokens": 500,              # 快速响应
            "timeout": (5, 30)              # 快速超时
        }
        
        # 合并用户配置
        if ollama_config:
            default_ollama_config.update(ollama_config)
        
        try:
            # 创建Ollama客户端
            self.ollama_client = create_ollama_client(**default_ollama_config)
            logger.info(f"🤖 回退到Ollama客户端: {default_ollama_config['model_name']}")
            
            # 快速健康检查
            if hasattr(self.ollama_client, 'validate_config'):
                is_healthy = self.ollama_client.validate_config()
                if not is_healthy:
                    logger.warning("⚠️ Ollama客户端健康检查失败")
                    self.ollama_client = None
                else:
                    logger.debug("✅ Ollama客户端健康检查通过")
                    
        except Exception as e:
            logger.warning(f"⚠️ 创建Ollama客户端失败: {e}")
            self.ollama_client = None
            
        # 方式5：如果所有LLM都不可用，记录警告
        if not self.ollama_client and not self.llm_manager:
            try:
                self.llm_manager = LLMManager()
                logger.debug("🔧 创建默认LLM管理器作为回退")
            except Exception as e:
                logger.warning(f"⚠️ 创建LLM管理器失败: {e}")
                raise Exception("无法初始化任何LLM能力")
    
    def _call_llm(self, prompt: str, temperature: float = 0.1, max_tokens: int = 500,
                  enable_streaming: bool = False) -> Optional[str]:
        """
        通用LLM调用接口（支持流式）
        
        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大token数
            enable_streaming: 是否启用流式输出
            
        Returns:
            LLM响应内容，失败时返回None
        """
        if not self.enable_llm:
            return None
            
        try:
            # 方式1：优先使用LLM管理器（支持流式）
            if self.llm_manager:
                if enable_streaming and hasattr(self.llm_manager, 'call_api_with_streaming'):
                    response_content = self.llm_manager.call_api_with_streaming(
                        prompt=prompt,
                        temperature=temperature,
                        enable_streaming=True
                    )
                else:
                    response_content = self.llm_manager.call_api(
                        prompt=prompt,
                        temperature=temperature
                    )
                
                if response_content:
                    logger.debug(f"✅ LLM管理器调用成功: {response_content[:50]}...")
                    return response_content
            
            # 方式2：使用Ollama客户端作为回退
            if self.ollama_client:
                messages = [LLMMessage(role="user", content=prompt)]
                response = self.ollama_client.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response.success:
                    logger.debug(f"✅ Ollama调用成功: {response.content[:50]}...")
                    return response.content
                else:
                    logger.warning(f"⚠️ Ollama调用失败: {response.error_message}")
                    
        except Exception as e:
            logger.warning(f"⚠️ LLM调用异常: {e}")
            
        return None
    
    def _call_llm_streaming(self, prompt: str, temperature: float = 0.7, max_tokens: int = 800) -> Optional[str]:
        """
        流式LLM调用 - 实时显示生成过程
        
        Args:
            prompt: 输入提示
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            完整的LLM响应内容，失败时返回None
        """
        if not self.enable_llm:
            return None
            
        try:
            full_response = ""
            
            # 方式1：使用LLM管理器的流式API
            if self.llm_manager and hasattr(self.llm_manager, 'call_api_streaming_generator'):
                try:
                    # 使用流式生成器 - 逐token实时输出
                    print("\n", end="", flush=True)  # 确保在新行开始
                    for chunk in self.llm_manager.call_api_streaming_generator(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    ):
                        if chunk:
                            print(chunk, end="", flush=True)
                            full_response += chunk
                    
                    print()  # 换行
                    logger.debug(f"✅ 流式生成完成，总长度: {len(full_response)}字符")
                    return full_response
                    
                except AttributeError as e:
                    # 如果没有流式生成器，使用普通模式但逐字打印
                    logger.warning(f"⚠️ LLM管理器不支持流式生成器: {e}，使用模拟流式输出")
                    response_content = self.llm_manager.call_api(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    if response_content:
                        # 模拟流式输出
                        import time
                        print("\n", end="", flush=True)
                        for char in response_content:
                            print(char, end="", flush=True)
                            time.sleep(0.01)  # 模拟打字效果
                        print()  # 换行
                        return response_content
                except Exception as e:
                    logger.error(f"❌ 流式生成器调用失败: {e}")
                    # 继续尝试其他方式
            
            # 方式2：使用Ollama客户端（支持真实流式）
            if self.ollama_client:
                messages = [LLMMessage(role="user", content=prompt)]
                
                # 检查是否支持流式
                if hasattr(self.ollama_client, 'chat_completion_stream'):
                    # 真实流式输出
                    for chunk in self.ollama_client.chat_completion_stream(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    ):
                        if chunk and hasattr(chunk, 'content'):
                            print(chunk.content, end="", flush=True)
                            full_response += chunk.content
                    
                    print()  # 换行
                    logger.debug(f"✅ Ollama流式生成完成，总长度: {len(full_response)}字符")
                    return full_response
                else:
                    # 回退到普通模式 + 模拟流式
                    logger.debug("⚠️ Ollama不支持流式，使用模拟流式输出")
                    response = self.ollama_client.chat_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    if response.success:
                        import time
                        for char in response.content:
                            print(char, end="", flush=True)
                            time.sleep(0.01)
                        print()  # 换行
                        return response.content
                        
        except Exception as e:
            logger.warning(f"⚠️ 流式LLM调用异常: {e}")
            print(f"\n⚠️ 流式输出失败，切换到普通模式")
            # 回退到普通调用
            return self._call_llm(prompt, temperature, max_tokens, enable_streaming=False)
            
        return None
    
    def _call_llm_with_fallback(self, prompt: str, fallback_result: Any, **kwargs) -> Any:
        """
        带回退机制的LLM调用
        
        Args:
            prompt: LLM提示
            fallback_result: LLM调用失败时的回退结果
            **kwargs: LLM调用参数
            
        Returns:
            LLM结果或回退结果
        """
        llm_result = self._call_llm(prompt, **kwargs)
        
        if llm_result is not None:
            return llm_result
        else:
            logger.debug("🔧 LLM调用失败，使用启发式回退结果")
            return fallback_result
        
    def assess_task_confidence(self, user_query: str, execution_context: Optional[Dict] = None) -> float:
        """
        评估任务的置信度 - 升级版：支持LLM增强分析
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            置信度分数 (0.0-1.0)
        """
        # 检查缓存
        cache_key = f"confidence_{user_query}_{hash(str(execution_context))}"
        if cache_key in self.assessment_cache:
            logger.debug(f"📋 使用缓存的置信度评估")
            return self.assessment_cache[cache_key]
        
        # 获取启发式分析结果（作为基线和回退）
        heuristic_confidence = self._heuristic_confidence_assessment(user_query, execution_context)
        
        # 尝试LLM增强分析
        if self.enable_llm:
            try:
                llm_confidence = self._llm_confidence_assessment(user_query, execution_context)
                if llm_confidence is not None:
                    # 智能合并：LLM分析为主，启发式分析作为校准
                    final_confidence = self._merge_confidence_scores(heuristic_confidence, llm_confidence)
                    logger.debug(f"🧠 置信度评估 - 启发式:{heuristic_confidence:.3f}, LLM:{llm_confidence:.3f}, 合并:{final_confidence:.3f}")
                else:
                    final_confidence = heuristic_confidence
                    logger.debug(f"🔧 LLM置信度评估失败，使用启发式结果:{final_confidence:.3f}")
            except Exception as e:
                logger.warning(f"⚠️ LLM置信度评估异常: {e}")
                final_confidence = heuristic_confidence
        else:
            final_confidence = heuristic_confidence
            logger.debug(f"📊 启发式置信度评估:{final_confidence:.3f}")
        
        # 缓存结果
        self.assessment_cache[cache_key] = final_confidence
        
        # 限制缓存大小
        if len(self.assessment_cache) > 100:
            oldest_key = next(iter(self.assessment_cache))
            del self.assessment_cache[oldest_key]
        
        logger.info(f"📊 任务置信度评估完成: {final_confidence:.3f}")
        return final_confidence
    
    def _heuristic_confidence_assessment(self, user_query: str, execution_context: Optional[Dict] = None) -> float:
        """
        启发式置信度评估（原有逻辑）
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            启发式置信度分数
        """
        # 基于查询复杂度的评估
        base_confidence = 0.7
        
        # 查询长度影响
        query_length = len(user_query)
        if query_length < 20:
            base_confidence += 0.1
        elif query_length > 100:
            base_confidence -= 0.1
        elif query_length > 200:
            base_confidence -= 0.2
            
        # 技术术语检测
        tech_terms = [
            'API', 'api', '算法', '数据库', '系统', '架构', '优化',
            '机器学习', 'ML', 'AI', '人工智能', '深度学习',
            '网络', '爬虫', '数据分析', '实时', '性能'
        ]
        tech_count = sum(1 for term in tech_terms if term in user_query)
        if tech_count > 0:
            base_confidence += min(0.15, tech_count * 0.05)
        
        # 复杂度关键词检测
        complexity_indicators = [
            '复杂', '困难', '挑战', '高级', '专业',
            '多步骤', '分布式', '并发', '异步', '集成'
        ]
        complexity_count = sum(1 for indicator in complexity_indicators if indicator in user_query)
        if complexity_count > 0:
            base_confidence -= min(0.2, complexity_count * 0.05)
        
        # 明确性关键词检测
        clarity_indicators = [
            '简单', '直接', '基础', '快速', '标准',
            '帮助', '请', '如何', '怎么', '什么'
        ]
        clarity_count = sum(1 for indicator in clarity_indicators if indicator in user_query)
        if clarity_count > 0:
            base_confidence += min(0.1, clarity_count * 0.03)
        
        # 执行上下文影响
        if execution_context:
            context_factors = len(execution_context)
            if context_factors > 3:
                base_confidence += 0.05  # 更多上下文信息提高置信度
            
            # 实时性要求
            if execution_context.get('real_time_requirements'):
                base_confidence -= 0.05
            
            # 性能要求
            if execution_context.get('performance_critical'):
                base_confidence -= 0.03
        
        # 限制在合理范围内
        return min(1.0, max(0.2, base_confidence))
    
    def _llm_confidence_assessment(self, user_query: str, execution_context: Optional[Dict] = None) -> Optional[float]:
        """
        LLM增强的置信度评估
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            LLM评估的置信度分数，失败时返回None
        """
        context_info = ""
        if execution_context:
            context_info = f"\n\n上下文信息:\n{json.dumps(execution_context, ensure_ascii=False, indent=2)}"
            
        prompt = f"""
请分析下面的用户查询，评估我们能成功完成这个任务的置信度。

用户查询: "{user_query}"{context_info}

请从以下维度分析:
1. 任务清晰度 - 需求是否明确
2. 技术可行性 - 技术实现难度
3. 资源需求 - 所需资源是否合理
4. 复杂度评估 - 任务复杂程度
5. 风险因素 - 潜在的失败风险

请返回一个0.0-1.0之间的置信度分数，并简要说明理由。

格式:
置信度: 0.85
理由: 任务需求明确，技术可行性高，复杂度适中
"""
        
        llm_response = self._call_llm(prompt, temperature=0.1, max_tokens=300)
        if llm_response is None:
            return None
            
        # 解析LLM响应，提取置信度分数
        try:
            # 简单的正则解析
            import re
            confidence_match = re.search(r'置信度[：:]\s*([0-9.]+)', llm_response)
            if confidence_match:
                confidence_score = float(confidence_match.group(1))
                # 确保在有效范围内
                confidence_score = min(1.0, max(0.0, confidence_score))
                
                logger.debug(f"🤖 LLM置信度分析: {confidence_score} - {llm_response[:50]}...")
                return confidence_score
            else:
                logger.warning(f"⚠️ 无法从LLM响应中解析置信度: {llm_response[:100]}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ LLM置信度响应解析失败: {e}")
            return None
    
    def _merge_confidence_scores(self, heuristic_score: float, llm_score: float) -> float:
        """
        智能合并启发式和LLM置信度分数
        
        Args:
            heuristic_score: 启发式分析分数
            llm_score: LLM分析分数
            
        Returns:
            合并后的置信度分数
        """
        # 加权平均：LLM权重更高（0.7），启发式作为校准（0.3）
        merged_score = llm_score * 0.7 + heuristic_score * 0.3
        
        # 如果两个分数差异很大，降低置信度（保守策略）
        score_diff = abs(llm_score - heuristic_score)
        if score_diff > 0.3:
            # 差异惩罚
            penalty = min(0.15, score_diff * 0.2)
            merged_score -= penalty
            logger.debug(f"🔍 置信度分数差异较大({score_diff:.3f})，应用惩罚:{penalty:.3f}")
        
        return min(1.0, max(0.1, merged_score))

    # ==================== 核心 LLM 路由分析引擎 ====================

    def _llm_route_analysis(self, user_query: str, execution_context: Optional[Dict] = None) -> Optional[TriageClassification]:
        """
        核心 LLM 路由分析方法 - 取代传统关键词匹配
        
        使用本地 LLM 进行深度语义分析，提供精确的任务分类和路由决策
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            LLM 分析结果，失败时返回 None
        """
        if not self.enable_llm:
            logger.debug("🔧 LLM 未启用，跳过 LLM 路由分析")
            return None
            
        logger.info(f"🧠 启动核心 LLM 路由分析: {user_query[:50]}...")
        
        try:
            # 构建专门的路由分析提示
            route_prompt = self._build_route_analysis_prompt(user_query, execution_context)
            
            # 调用本地 LLM 进行分析
            llm_response = self._call_llm(route_prompt, temperature=0.1, max_tokens=1000)
            
            if llm_response is None:
                logger.warning("⚠️ LLM 路由分析调用失败")
                return None
            
            # 解析 LLM 的决策结果
            classification = self._parse_llm_route_decision(llm_response, user_query)
            
            if classification:
                logger.info(f"✅ LLM 路由分析成功: {classification.domain.value} -> {classification.route_strategy.value}")
                return classification
            else:
                logger.warning("⚠️ LLM 路由决策解析失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ LLM 路由分析异常: {e}")
            return None

    def _build_route_analysis_prompt(self, user_query: str, execution_context: Optional[Dict] = None) -> str:
        """
        构建专门的 LLM 路由分析提示
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            优化的路由分析提示
        """
        # 上下文信息处理
        context_section = ""
        if execution_context:
            context_section = f"\n\n**执行上下文:**\n{json.dumps(execution_context, ensure_ascii=False, indent=2)}"
        
        # 构建专门的路由分析提示
        route_prompt = f"""# 🚦 任务路由分诊系统

## ⚠️ 角色约束 - 极其重要！

**你是一个纯粹的"任务分诊员"，只负责任务分类和路由决策。**

🚫 **严禁行为：**
- 绝对不能回答用户的问题内容
- 不能提供任何技术解决方案
- 不能给出任何建议或指导  
- 不能解释概念或技术原理
- 不能进行任何形式的问答

✅ **唯一职责：**
- 仅对用户查询进行技术维度分类
- 仅判断任务复杂度和处理策略
- 仅输出标准化的路由决策JSON

## 📋 待分析查询

**用户输入:** "{user_query}"{context_section}

## 🎯 分诊维度（仅分类，不解答）

### 复杂度分诊
- **simple**: 问候语、单一概念查询（如"你好"、"什么是HTTP"）
- **moderate**: 需要多步骤分析的技术问题
- **complex**: 系统设计或架构级问题
- **expert**: 需要深度专业知识的高难度问题

### 技术领域分诊
- **web_development**: Web相关技术
- **data_science**: 数据分析/ML相关
- **system_admin**: 系统运维相关
- **database**: 数据库相关
- **general**: 通用或跨领域

### 意图分诊
- **question**: 知识查询类（如"什么是..."、"如何..."）
- **task_execution**: 具体任务执行
- **debugging**: 问题排查修复

### 紧急度分诊
- **low**: 学习性查询
- **medium**: 常规工作任务
- **high**: 重要项目需求
- **critical**: 生产环境紧急情况

### 处理策略分诊
- **direct_response**: 简单问题，快速通道处理
- **multi_stage_processing**: 中等复杂度，标准流程处理
- **workflow_planning**: 复杂任务，需要详细规划
- **expert_consultation**: 高难度，需要专家级处理

## 📄 输出格式（严格JSON，无其他内容）

```json
{{
  "complexity": "simple|moderate|complex|expert",
  "domain": "领域代码",
  "intent": "意图代码", 
  "urgency": "紧急度代码",
  "route_strategy": "处理策略代码",
  "confidence": 0.85,
  "reasoning": "分诊理由（50字内，仅说明分类依据）",
  "key_factors": ["技术维度1", "技术维度2"],
  "estimated_time": 预估分钟数,
  "required_resources": ["资源类型1", "资源类型2"]
}}
```

⚠️ **再次强调：你只是一个分诊员，绝对不能回答问题内容！**"""
        
        return route_prompt

    def _parse_llm_route_decision(self, llm_response: str, user_query: str) -> Optional[TriageClassification]:
        """
        解析 LLM 的路由决策结果
        
        Args:
            llm_response: LLM 的原始响应
            user_query: 原始用户查询
            
        Returns:
            解析后的分类结果，失败时返回 None
        """
        try:
            # 多种方式提取JSON
            import re
            
            # 方式1：提取```json块中的内容
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
            
            if not json_match:
                # 方式2：提取第一个完整的JSON对象
                json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', llm_response, re.DOTALL)
            
            if not json_match:
                # 方式3：尝试更宽松的匹配
                json_match = re.search(r'(\{.*\})', llm_response, re.DOTALL)
            
            if not json_match:
                logger.warning(f"⚠️ 无法从 LLM 响应中提取 JSON 决策结果")
                return None
            
            # 解析JSON决策数据
            decision_data = json.loads(json_match.group(1))
            
            # 验证必要字段
            required_fields = ['complexity', 'domain', 'intent', 'urgency', 'route_strategy']
            missing_fields = [field for field in required_fields if field not in decision_data]
            
            if missing_fields:
                logger.warning(f"⚠️ LLM 决策缺少必要字段: {missing_fields}")
                return None
            
            # 构建分类结果
            classification = TriageClassification(
                complexity=TaskComplexity(decision_data['complexity']),
                domain=TaskDomain(decision_data['domain']),
                intent=TaskIntent(decision_data['intent']),
                urgency=TaskUrgency(decision_data['urgency']),
                route_strategy=RouteStrategy(decision_data['route_strategy']),
                confidence=float(decision_data.get('confidence', 0.8)),
                reasoning=decision_data.get('reasoning', 'LLM 路由分析结果'),
                key_factors=decision_data.get('key_factors', []),
                estimated_time=decision_data.get('estimated_time'),
                required_resources=decision_data.get('required_resources', [])
            )
            
            logger.debug(f"✅ LLM 路由决策解析成功: {classification.complexity.value}/{classification.domain.value}")
            return classification
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ LLM 路由决策 JSON 解析失败: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.warning(f"⚠️ LLM 路由决策数据验证失败: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ LLM 路由决策处理异常: {e}")
            return None

    def _fallback_keyword_analysis(self, user_query: str, execution_context: Optional[Dict] = None) -> TriageClassification:
        """
        回退关键词分析方法 - 封装传统的关键词匹配逻辑
        
        当 LLM 分析失败时使用此方法作为可靠回退
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            基于关键词匹配的分类结果
        """
        logger.info(f"🔧 启动回退关键词分析: {user_query[:50]}...")
        
        # 使用传统的复杂度分析
        complexity_analysis = self.analyze_task_complexity(user_query)
        confidence_score = self._heuristic_confidence_assessment(user_query, execution_context)
        
        # 复杂度到分类的映射
        complexity_score = complexity_analysis.get('complexity_score', 0.5)
        
        if complexity_score < 0.3:
            complexity = TaskComplexity.SIMPLE
            route_strategy = RouteStrategy.DIRECT_RESPONSE
        elif complexity_score < 0.6:
            complexity = TaskComplexity.MODERATE
            route_strategy = RouteStrategy.MULTI_STAGE_PROCESSING
        elif complexity_score < 0.8:
            complexity = TaskComplexity.COMPLEX
            route_strategy = RouteStrategy.WORKFLOW_PLANNING
        else:
            complexity = TaskComplexity.EXPERT
            route_strategy = RouteStrategy.EXPERT_CONSULTATION
        
        # 传统领域推断
        estimated_domain = complexity_analysis.get('estimated_domain', 'general')
        domain_mapping = {
            'web_development': TaskDomain.WEB_DEV,
            'data_science': TaskDomain.DATA_SCIENCE,
            'api_development': TaskDomain.API_DEV,
            'database': TaskDomain.DATABASE,
            'system_admin': TaskDomain.SYSTEM_ADMIN,
            'security': TaskDomain.SECURITY,
            'mobile_development': TaskDomain.MOBILE_DEV,
            'performance': TaskDomain.SYSTEM_ADMIN,
            'automation': TaskDomain.SYSTEM_ADMIN,
        }
        domain = domain_mapping.get(estimated_domain, TaskDomain.GENERAL)
        
        # 传统意图分析（基于关键词）
        intent = self._keyword_intent_analysis(user_query)
        
        # 传统紧急度评估（基于关键词）
        urgency = self._keyword_urgency_analysis(user_query)
        
        # 构建回退分类结果
        fallback_classification = TriageClassification(
            complexity=complexity,
            domain=domain,
            intent=intent,
            urgency=urgency,
            route_strategy=route_strategy,
            confidence=confidence_score * 0.8,  # 关键词分析置信度略低
            reasoning=f"关键词分析：复杂度{complexity_score:.2f}，领域{estimated_domain}",
            key_factors=list(complexity_analysis.get('complexity_factors', {}).keys())[:3],
            estimated_time=self._estimate_processing_time(complexity, domain),
            required_resources=self._estimate_required_resources(domain, complexity)
        )
        
        logger.info(f"✅ 关键词分析完成: {domain.value} -> {route_strategy.value}")
        return fallback_classification

    def _keyword_intent_analysis(self, user_query: str) -> TaskIntent:
        """基于关键词的意图分析"""
        query_lower = user_query.lower()
        
        # 问题咨询关键词
        if any(word in query_lower for word in ['如何', '怎么', '什么是', '请教', '学习', '解释', '介绍']):
            return TaskIntent.QUESTION
        
        # 创建开发关键词
        elif any(word in query_lower for word in ['创建', '生成', '设计', '开发', '写', '构建', '实现']):
            return TaskIntent.CREATION
        
        # 分析评估关键词
        elif any(word in query_lower for word in ['分析', '评估', '比较', '检查', '审查', '测试']):
            return TaskIntent.ANALYSIS
        
        # 调试修复关键词
        elif any(word in query_lower for word in ['修复', '解决', '调试', '错误', '问题', '故障', '异常']):
            return TaskIntent.DEBUGGING
        
        # 优化改进关键词
        elif any(word in query_lower for word in ['优化', '提升', '改进', '加速', '性能', '效率']):
            return TaskIntent.OPTIMIZATION
        
        # 默认为任务执行
        else:
            return TaskIntent.TASK_EXECUTION

    def _keyword_urgency_analysis(self, user_query: str) -> TaskUrgency:
        """基于关键词的紧急度分析"""
        query_lower = user_query.lower()
        
        # 紧急关键词
        if any(word in query_lower for word in ['紧急', '急', '马上', '立即', '现在', 'critical', 'urgent', 'asap']):
            return TaskUrgency.CRITICAL
        
        # 重要关键词
        elif any(word in query_lower for word in ['重要', '尽快', '优先', 'important', 'priority', 'high']):
            return TaskUrgency.HIGH
        
        # 学习探索关键词
        elif any(word in query_lower for word in ['学习', '了解', '探索', '研究', '试试', '看看']):
            return TaskUrgency.LOW
        
        # 默认为中等优先级
        else:
            return TaskUrgency.MEDIUM

    # ==================== 路由专家功能实现 ====================

    def classify_and_route(self, user_query: str, execution_context: Optional[Dict] = None) -> TriageClassification:
        """
        核心路由功能 - 升级版智能任务分诊
        
        新架构：LLM 核心分析 + 关键词回退机制
        - 主要：使用本地 LLM 进行深度语义理解和路由决策
        - 回退：当 LLM 分析失败时，使用关键词匹配作为可靠回退
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            TriageClassification: 完整的智能分类结果
        """
        # 注意：这个日志被简化，详细流程日志由Agent配置控制
        # logger.info(f"🚀 启动智能路由分析: {user_query[:50]}...")
        
        # 第一优先级：LLM 核心路由分析
        llm_result = self._llm_route_analysis(user_query, execution_context)
        if llm_result:
            # logger.info(f"✅ LLM 路由成功: {llm_result.domain.value} -> {llm_result.route_strategy.value} (置信度: {llm_result.confidence:.2f})")
            return llm_result
        
        # 第二优先级：关键词回退分析
        # logger.info("🔧 LLM 分析不可用，启动关键词回退分析")
        fallback_result = self._fallback_keyword_analysis(user_query, execution_context)
        
        # logger.info(f"📊 回退分析完成: {fallback_result.domain.value} -> {fallback_result.route_strategy.value} (置信度: {fallback_result.confidence:.2f})")
        return fallback_result





    def _estimate_processing_time(self, complexity: TaskComplexity, domain: TaskDomain) -> int:
        """估算处理时间（分钟）"""
        base_time = {
            TaskComplexity.SIMPLE: 5,
            TaskComplexity.MODERATE: 15,
            TaskComplexity.COMPLEX: 45,
            TaskComplexity.EXPERT: 120
        }
        
        domain_multiplier = {
            TaskDomain.GENERAL: 1.0,
            TaskDomain.WEB_DEV: 1.2,
            TaskDomain.DATA_SCIENCE: 1.5,
            TaskDomain.ML_AI: 1.8,
            TaskDomain.SYSTEM_ADMIN: 1.3,
            TaskDomain.SECURITY: 1.4
        }
        
        base = base_time.get(complexity, 30)
        multiplier = domain_multiplier.get(domain, 1.0)
        return int(base * multiplier)

    def _estimate_required_resources(self, domain: TaskDomain, complexity: TaskComplexity) -> List[str]:
        """估算所需资源"""
        resources = []
        
        # 基础资源
        if complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
            resources.extend(["专业知识库", "技术文档"])
        
        # 领域特定资源
        domain_resources = {
            TaskDomain.WEB_DEV: ["前端框架", "后端技术栈"],
            TaskDomain.DATA_SCIENCE: ["数据集", "分析工具"],
            TaskDomain.ML_AI: ["计算资源", "模型库"],
            TaskDomain.DATABASE: ["数据库实例", "查询工具"],
            TaskDomain.SYSTEM_ADMIN: ["系统权限", "监控工具"],
            TaskDomain.SECURITY: ["安全工具", "威胁情报"]
        }
        
        resources.extend(domain_resources.get(domain, []))
        return resources[:4]  # 限制最多4个资源
    
    def get_thinking_seed(self, user_query: str, execution_context: Optional[Dict] = None,
                         enable_streaming: bool = False) -> str:
        """
        生成思维种子 - LLM增强版（保留启发式回退）
        
        新策略：
        1. 使用启发式分析提取关键特征（快速且免费）
        2. 基于特征构建专业提示词并调用LLM生成高质量种子
        3. LLM失败时回退到改进的启发式生成
        4. 最终回退到紧急种子生成
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            enable_streaming: 是否启用流式输出
            
        Returns:
            高质量的思维种子
        """
        logger.info(f"🌱 启动LLM增强思维种子生成: {user_query[:30]}...")
        
        try:
            # ========== 第一步：快速启发式分析（提供结构化输入） ==========
            analysis = self.get_quick_analysis_summary(user_query, execution_context)
            confidence = analysis['confidence_score']
            complexity = analysis['complexity_score']
            domain = analysis['domain']
            key_factors = analysis.get('key_factors', [])
            
            logger.debug(f"📊 启发式分析完成: {domain}领域, 复杂度{complexity:.2f}, 置信度{confidence:.2f}")
            
            # ========== 第二步：尝试LLM增强生成 ==========
            if self.enable_llm:
                llm_seed = self._generate_llm_enhanced_seed(
                    user_query=user_query,
                    analysis_context={
                        'domain': domain,
                        'complexity_score': complexity,
                        'confidence_score': confidence,
                        'key_factors': key_factors,
                        'requires_multi_step': analysis.get('requires_multi_step', False)
                    },
                    execution_context=execution_context,
                    enable_streaming=enable_streaming
                )
                
                if llm_seed:
                    logger.info(f"✅ LLM增强种子生成成功 (长度: {len(llm_seed)}字符)")
                    return llm_seed
            
            # ========== 第三步：回退到改进的启发式生成 ==========
            logger.info("🔧 LLM不可用或失败，使用改进的启发式种子生成")
            return self._generate_heuristic_seed(user_query, analysis, execution_context)
            
        except Exception as e:
            logger.error(f"❌ 思维种子生成异常: {e}")
            # 最终回退
            return self._generate_emergency_fallback_seed(user_query)
    
    def _generate_llm_enhanced_seed(self, user_query: str, analysis_context: Dict,
                                    execution_context: Optional[Dict] = None,
                                    enable_streaming: bool = False) -> Optional[str]:
        """
        LLM增强的思维种子生成（核心新方法）
        
        使用高质量提示词调用LLM，结合启发式分析的结构化信息，生成专业的思维种子。
        
        Args:
            user_query: 用户查询
            analysis_context: 启发式分析提供的上下文（领域、复杂度、置信度等）
            execution_context: 执行上下文
            enable_streaming: 是否流式输出
            
        Returns:
            LLM生成的高质量思维种子，失败时返回None
        """
        try:
            # 构建上下文信息
            context_info = ""
            if execution_context:
                context_items = []
                if execution_context.get('real_time_requirements'):
                    context_items.append("⚡ 需要关注实时性")
                if execution_context.get('performance_critical'):
                    context_items.append("🚀 性能优化是关键")
                if execution_context.get('domain_specific'):
                    context_items.append(f"🎯 专业领域: {execution_context.get('domain_specific')}")
                
                if context_items:
                    context_info = "\n\n**执行要求**:\n" + "\n".join(f"- {item}" for item in context_items)
            
            # 构建分析背景
            analysis_background = f"""
**任务特征分析**（基于快速评估）:
- 领域识别: {analysis_context['domain']}
- 复杂度评分: {analysis_context['complexity_score']:.2f} (0-1量级)
- 置信度评分: {analysis_context['confidence_score']:.2f} (0-1量级)
- 关键因素: {', '.join(analysis_context['key_factors'][:3]) if analysis_context['key_factors'] else '通用分析'}
- 多步骤需求: {'是' if analysis_context.get('requires_multi_step') else '否'}
"""
            
            # 🎯 核心提示词：高质量、结构化、专业化、去模板化
            llm_prompt = f"""你是一位资深的问题分析专家，擅长快速理解问题本质并生成高质量的分析思路。

【用户问题】
{user_query}

{analysis_background}
{context_info}

【任务要求】
请生成一个高质量的"思维种子"（初步分析思路），要求：

1. **深度理解**：
   - 准确识别问题的核心意图和关键需求（用户真正想解决什么？）
   - 分析问题所属的技术或知识领域（涉及哪些专业领域？）
   - 判断问题的复杂度和解决难度（需要什么级别的专业知识？）
   - 理解问题的应用场景和实际背景（在什么情境下使用？）
   - 识别隐含的约束条件和前置依赖（有什么限制？需要什么基础？）
   - 评估问题的时效性和紧急程度（是否需要最新信息？是否紧急？）

2. **思路规划**：
   - 提出2-3个可能的解决方向或分析角度
   - 指出需要考虑的关键因素和潜在挑战
   - 如果是多步骤任务，简要说明主要阶段

3. **输出要求**：
   - **开头必须**：用一句话简洁复述用户的核心问题（例如："用户询问的是..."或"用户希望了解..."）
   - 使用自然、专业的语言（不要使用"这是一个...领域的任务"等模板化表达）
   - 长度控制在150-300字
   - 重点突出，逻辑清晰
   - 提供深度分析价值，而不是简单重复问题
   - 避免过于宽泛的建议，要有针对性

【输出格式】
直接输出思维种子内容，不需要JSON格式，不需要标题前缀。用2-4个自然段落组织你的分析。

"""
            
            # 调用LLM（支持流式）
            if enable_streaming:
                # 流式模式：实时显示生成过程
                logger.debug("🔄 开始流式生成思维种子...")
                
                llm_response = self._call_llm_streaming(
                    prompt=llm_prompt,
                    temperature=0.7,
                    max_tokens=800
                )
            else:
                # 非流式模式：一次性返回
                llm_response = self._call_llm(
                    prompt=llm_prompt,
                    temperature=0.7,
                    max_tokens=800,
                    enable_streaming=False
                )
            
            if llm_response:
                # 清理和验证响应
                cleaned_seed = llm_response.strip()
                
                # 基本质量检查
                if len(cleaned_seed) < 50:
                    logger.warning(f"⚠️ LLM生成的种子过短({len(cleaned_seed)}字符)，可能质量不佳")
                    return None
                
                if len(cleaned_seed) > 1000:
                    logger.warning(f"⚠️ LLM生成的种子过长({len(cleaned_seed)}字符)，进行截断")
                    cleaned_seed = cleaned_seed[:800] + "..."
                
                # 验证不是简单的问题复述
                if user_query in cleaned_seed[:100] and len(user_query) > 20:
                    logger.debug("⚠️ LLM可能过多复述问题，但仍可接受")
                
                logger.debug(f"🤖 LLM种子预览: {cleaned_seed[:100]}...")
                return cleaned_seed
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ LLM增强种子生成失败: {e}")
            return None
    
    def _generate_heuristic_seed(self, user_query: str, analysis: Dict,
                                 execution_context: Optional[Dict] = None) -> str:
        """
        启发式种子生成（改进版 - 更自然的表达）
        
        相比旧版的模板化输出，新版使用更自然、更有针对性的语言。
        
        Args:
            user_query: 用户查询
            analysis: 快速分析结果
            execution_context: 执行上下文
            
        Returns:
            基于规则但更自然的思维种子
        """
        seed_parts = []
        
        # 领域识别（更自然的表达）
        domain = analysis.get('domain', 'general')
        domain_descriptions = {
            'web_development': 'Web开发相关',
            'data_science': '数据科学和分析相关',
            'api_development': 'API接口开发相关',
            'database': '数据库设计和操作相关',
            'system_admin': '系统运维和管理相关',
            'machine_learning': '机器学习和AI相关',
            'security': '安全和防护相关',
            'mobile_development': '移动应用开发相关',
            'performance': '性能优化相关',
            'automation': '自动化和脚本相关',
            'general': '通用技术'
        }
        domain_desc = domain_descriptions.get(domain, '技术')
        seed_parts.append(f"这个问题涉及{domain_desc}的内容。")
        
        # 复杂度分析（更有针对性）
        complexity = analysis.get('complexity_score', 0.5)
        if complexity > 0.8:
            seed_parts.append("问题具有较高的技术复杂度，需要深入分析多个技术层面，并综合考虑系统性的解决方案。")
        elif complexity > 0.5:
            seed_parts.append("这是一个中等复杂度的问题，需要结合理论知识和实践经验来制定合理的解决方案。")
        else:
            seed_parts.append("从技术角度看，这个问题有比较清晰的解决路径，可以采用标准的方法来处理。")
        
        # 关键因素（如果有）
        key_factors = analysis.get('key_factors', [])
        if key_factors:
            factors_text = "、".join(key_factors[:3])
            seed_parts.append(f"关键需要关注的技术点包括：{factors_text}。")
        
        # 置信度和建议
        confidence = analysis.get('confidence_score', 0.5)
        if confidence > 0.8:
            seed_parts.append("基于问题的清晰度和常见性，我们有较高把握找到有效的解决方案。")
        elif confidence > 0.5:
            seed_parts.append("需要进一步明确具体需求和技术约束，以便提供更精准的解决方案。")
        else:
            seed_parts.append("建议先澄清问题的具体场景和技术背景，这有助于制定更有针对性的解决策略。")
        
        # 多步骤建议
        if analysis.get('requires_multi_step'):
            seed_parts.append("这个任务需要分步骤来实施，建议采用渐进式的方法逐一验证每个环节。")
        
        # 执行上下文考虑
        if execution_context:
            if execution_context.get('real_time_requirements'):
                seed_parts.append("特别需要注意实时性能的要求。")
            if execution_context.get('performance_critical'):
                seed_parts.append("性能优化应该作为设计的核心考虑因素。")
        
        return " ".join(seed_parts)
    
    def _generate_emergency_fallback_seed(self, user_query: str) -> str:
        """
        紧急回退种子生成（最简单但可用）
        
        当所有其他方法都失败时使用此方法，确保系统始终能返回可用的种子。
        
        Args:
            user_query: 用户查询
            
        Returns:
            基础但可用的思维种子
        """
        return (
            f"针对问题'{user_query}'，需要进行系统性的分析。"
            f"建议首先明确问题的核心需求和技术背景，"
            f"然后探索可行的技术方案并评估其优劣，"
            f"最后制定具体的实施步骤并进行验证。"
        )
    
    def generate_thinking_seed(self, user_query: str, execution_context: Optional[Dict] = None,
                              enable_streaming: bool = False) -> Dict[str, Any]:
        """
        生成思维种子 - NeogenesisPlanner兼容接口（支持流式）
        
        这个方法是为了兼容NeogenesisPlanner中的调用，将get_thinking_seed的结果
        包装成期望的字典格式。
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            enable_streaming: 是否启用流式输出
            
        Returns:
            Dict: 包含thinking_seed、reasoning、confidence的字典
        """
        try:
            logger.info(f"🧠 生成思维种子 (兼容接口): {user_query[:30]}...")
            
            # 调用核心的get_thinking_seed方法（传递流式参数）
            thinking_seed = self.get_thinking_seed(user_query, execution_context, enable_streaming)
            
            # 获取分析信息
            analysis = self.get_quick_analysis_summary(user_query, execution_context)
            confidence = self.assess_task_confidence(user_query, execution_context)
            
            # 构建推理过程描述
            reasoning_parts = [
                f"任务领域: {analysis.get('domain', '通用')}",
                f"复杂度评分: {analysis.get('complexity_score', 0.5):.2f}",
                f"置信度评分: {confidence:.2f}",
                f"推荐策略: {analysis.get('recommendation', '系统性分析')}"
            ]
            
            if analysis.get('key_factors'):
                factors_text = "、".join(analysis['key_factors'][:3])
                reasoning_parts.append(f"关键因素: {factors_text}")
            
            reasoning_process = "; ".join(reasoning_parts)
            
            # 包装成期望的格式
            result = {
                "thinking_seed": thinking_seed,
                "reasoning": reasoning_process,
                "confidence": confidence,
                "generation_method": "prior_reasoner_enhanced",
                "domain": analysis.get('domain', '通用'),
                "complexity_score": analysis.get('complexity_score', 0.5),
                "user_query": user_query
            }
            
            logger.info(f"✅ 思维种子生成完成: {len(thinking_seed)}字符, 置信度: {confidence:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 思维种子生成失败: {e}")
            # 返回基础结果但保持格式一致
            fallback_seed = f"针对查询'{user_query}'的基础思维种子：需要系统性分析和解决方案制定。"
            return {
                "thinking_seed": fallback_seed,
                "reasoning": "使用回退生成方法",
                "confidence": 0.3,
                "generation_method": "fallback",
                "error": str(e)
            }
    
    def analyze_task_complexity(self, user_query: str) -> Dict[str, Any]:
        """
        分析任务复杂度
        
        Args:
            user_query: 用户查询
            
        Returns:
            复杂度分析结果
        """
        complexity_score = 0.5
        complexity_factors = {}
        
        # 关键词复杂度指标
        complexity_keywords = {
            '多步骤': 0.15,
            '集成': 0.12,
            '优化': 0.10,
            '分析': 0.08,
            '设计': 0.08,
            '架构': 0.12,
            '分布式': 0.15,
            '并发': 0.13,
            '实时': 0.10,
            '高性能': 0.11,
            '机器学习': 0.14,
            '深度学习': 0.16,
            '算法': 0.09,
            '数据库': 0.07,
            '网络': 0.06,
            '安全': 0.08
        }
        
        for keyword, weight in complexity_keywords.items():
            if keyword in user_query:
                complexity_score += weight
                complexity_factors[keyword] = weight
                logger.debug(f"🔍 检测到复杂度关键词: {keyword} (+{weight})")
        
        # 句法复杂度
        sentences = user_query.split('。')
        if len(sentences) > 3:
            syntax_complexity = min(0.1, (len(sentences) - 3) * 0.02)
            complexity_score += syntax_complexity
            complexity_factors['多句表达'] = syntax_complexity
        
        # 字符长度复杂度
        if len(user_query) > 150:
            length_complexity = min(0.08, (len(user_query) - 150) / 1000)
            complexity_score += length_complexity
            complexity_factors['表达长度'] = length_complexity
        
        # 技术词汇密度
        tech_words = ['API', 'HTTP', 'JSON', 'SQL', 'Python', 'JavaScript', 'REST', 'GraphQL']
        tech_density = sum(1 for word in tech_words if word in user_query) / max(len(user_query.split()), 1)
        if tech_density > 0.1:
            tech_complexity = min(0.12, tech_density * 2)
            complexity_score += tech_complexity
            complexity_factors['技术词汇密度'] = tech_complexity
        
        # 领域推断
        domain = self._infer_domain(user_query)
        
        # 多步骤检测
        requires_multi_step = any(word in user_query for word in [
            '步骤', '阶段', '分步', '然后', '接下来', '首先', '最后',
            '第一', '第二', '第三', '依次', '顺序'
        ])
        
        # 限制复杂度分数
        final_complexity = min(1.0, complexity_score)
        
        result = {
            'complexity_score': final_complexity,
            'complexity_factors': complexity_factors,
            'estimated_domain': domain,
            'requires_multi_step': requires_multi_step,
            'sentence_count': len(sentences),
            'word_count': len(user_query.split()),
            'tech_density': tech_density
        }
        
        logger.info(f"🧮 复杂度分析完成: {final_complexity:.3f} (因子数:{len(complexity_factors)})")
        return result
    
    def _infer_domain(self, user_query: str) -> str:
        """
        推断任务领域
        
        Args:
            user_query: 用户查询
            
        Returns:
            推断的领域
        """
        query_lower = user_query.lower()
        
        domain_indicators = {
            'web_development': ['网站', 'web', 'html', 'css', 'javascript', '前端', '后端'],
            'data_science': ['数据分析', '数据科学', 'pandas', 'numpy', '机器学习', '模型', '预测'],
            'api_development': ['api', '接口', 'rest', 'restful', 'graphql', 'endpoints'],
            'web_scraping': ['爬虫', 'spider', 'scrapy', '抓取', '爬取', 'crawl'],
            'database': ['数据库', 'sql', 'mysql', 'postgresql', 'mongodb', '查询'],
            'system_admin': ['系统', '服务器', '部署', '运维', 'docker', 'kubernetes'],
            'mobile_development': ['移动', 'app', '安卓', 'android', 'ios', 'react native'],
            'security': ['安全', '加密', '认证', '授权', '防护', 'security'],
            'performance': ['性能', '优化', '速度', '效率', 'benchmark', '负载'],
            'automation': ['自动化', '脚本', '定时', '批处理', 'cron', 'schedule']
        }
        
        domain_scores = {}
        for domain, keywords in domain_indicators.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            inferred_domain = max(domain_scores, key=domain_scores.get)
            logger.debug(f"🏷️ 推断领域: {inferred_domain} (匹配度:{domain_scores[inferred_domain]})")
            return inferred_domain
        
        return 'general'
    
    def get_confidence_statistics(self) -> Dict[str, Any]:
        """
        获取置信度统计信息
        
        Returns:
            置信度统计数据
        """
        if not self.confidence_history:
            return {
                'total_assessments': 0,
                'avg_confidence': 0.0,
                'confidence_trend': 'insufficient_data',
                'cache_size': len(self.assessment_cache)
            }
        
        confidences = [item['predicted_confidence'] for item in self.confidence_history]
        avg_confidence = sum(confidences) / len(confidences)
        
        # 计算趋势
        if len(confidences) >= 5:
            recent_avg = sum(confidences[-5:]) / 5
            earlier_avg = sum(confidences[-10:-5]) / 5 if len(confidences) >= 10 else avg_confidence
            
            if recent_avg > earlier_avg + 0.05:
                trend = 'improving'
            elif recent_avg < earlier_avg - 0.05:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'total_assessments': len(self.confidence_history),
            'avg_confidence': avg_confidence,
            'min_confidence': min(confidences),
            'max_confidence': max(confidences),
            'confidence_trend': trend,
            'cache_size': len(self.assessment_cache),
            'recent_confidences': confidences[-5:] if len(confidences) >= 5 else confidences
        }
    
    def update_confidence_feedback(self, predicted_confidence: float, 
                                 actual_success: bool, execution_time: float):
        """
        更新置信度反馈，用于改进预测准确性
        
        Args:
            predicted_confidence: 预测的置信度
            actual_success: 实际执行是否成功
            execution_time: 执行时间
        """
        feedback_record = {
            'timestamp': time.time(),
            'predicted_confidence': predicted_confidence,
            'actual_success': actual_success,
            'execution_time': execution_time,
            'confidence_accuracy': abs(predicted_confidence - (1.0 if actual_success else 0.0))
        }
        
        self.confidence_history.append(feedback_record)
        
        # 限制历史长度
        if len(self.confidence_history) > 200:
            self.confidence_history = self.confidence_history[-100:]
        
        logger.debug(f"📈 更新置信度反馈: 预测={predicted_confidence:.3f}, 实际={'成功' if actual_success else '失败'}")
    
    def get_quick_analysis_summary(self, user_query: str, execution_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        获取快速分析总结 - PriorReasoner的新核心功能
        
        提供任务的快速概览，包括复杂度、置信度、领域等关键信息
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            快速分析总结
        """
        start_time = time.time()
        
        # 快速分析
        complexity_analysis = self.analyze_task_complexity(user_query)
        confidence_score = self.assess_task_confidence(user_query, execution_context)
        
        analysis_time = time.time() - start_time
        
        summary = {
            'domain': complexity_analysis.get('estimated_domain', 'general'),
            'complexity_score': complexity_analysis.get('complexity_score', 0.5),
            'confidence_score': confidence_score,
            'requires_multi_step': complexity_analysis.get('requires_multi_step', False),
            'key_factors': list(complexity_analysis.get('complexity_factors', {}).keys())[:3],
            'analysis_time': analysis_time,
            'recommendation': self._get_analysis_recommendation(
                complexity_analysis.get('complexity_score', 0.5), 
                confidence_score
            )
        }
        
        logger.info(f"⚡ 快速分析完成: {summary['domain']}领域, 复杂度{summary['complexity_score']:.2f}, 置信度{summary['confidence_score']:.2f}")
        return summary
    
    def _get_analysis_recommendation(self, complexity_score: float, confidence_score: float) -> str:
        """
        基于分析结果提供建议
        
        Args:
            complexity_score: 复杂度分数
            confidence_score: 置信度分数
            
        Returns:
            分析建议
        """
        if complexity_score > 0.8 and confidence_score < 0.4:
            return "高复杂度低置信度任务，建议采用多阶段验证和保守策略"
        elif complexity_score > 0.7:
            return "复杂任务，建议采用系统分析和分步执行"
        elif confidence_score > 0.8:
            return "高置信度任务，可以采用直接执行策略"
        elif confidence_score < 0.3:
            return "低置信度任务，建议寻求额外信息或澄清"
        else:
            return "中等复杂度任务，建议采用平衡的分析和执行策略"
    
    def reset_cache(self):
        """重置评估缓存"""
        self.assessment_cache.clear()
        logger.info("🔄 轻量级分析助手缓存已重置")
