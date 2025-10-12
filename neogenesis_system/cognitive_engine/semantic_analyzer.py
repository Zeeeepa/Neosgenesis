#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
语义分析器 - 基于LLM的智能文本分析
Semantic Analyzer - LLM-based intelligent text analysis

核心职责：
1. 替换硬编码关键词判断，使用LLM进行语义理解
2. 支持多任务并行分析（意图识别、情感分析、复杂度评估等）
3. 返回结构化的JSON分析结果
4. 提供可扩展的分析任务框架

设计理念：
- 智能而非死板：理解同义词、上下文和复杂句式
- 可配置任务：支持自定义分析任务和输出格式
- 高效可靠：内置缓存、错误处理和降级机制
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)

class AnalysisTaskType(Enum):
    """分析任务类型枚举"""
    INTENT_DETECTION = "intent_detection"           # 意图识别
    SENTIMENT_ANALYSIS = "sentiment_analysis"       # 情感分析
    COMPLEXITY_ASSESSMENT = "complexity_assessment" # 复杂度评估
    DOMAIN_CLASSIFICATION = "domain_classification" # 领域分类
    URGENCY_EVALUATION = "urgency_evaluation"       # 紧急程度评估
    KEYWORD_EXTRACTION = "keyword_extraction"       # 关键词提取
    TOPIC_MODELING = "topic_modeling"               # 主题建模
    LANGUAGE_DETECTION = "language_detection"       # 语言检测
    VISUAL_NEED_DETECTION = "visual_need_detection" # 视觉需求识别
    OUTPUT_FORMAT_ANALYSIS = "output_format_analysis" # 输出形态分析（已弃用）
    VISUAL_ENHANCEMENT_OPPORTUNITY = "visual_enhancement_opportunity" # 🎨 视觉增强机会评估
    INTERACTION_CONTEXT_ANALYSIS = "interaction_context_analysis" # 🧠 交互情境分析
    AESTHETIC_PREFERENCE_INFERENCE = "aesthetic_preference_inference" # 🎭 审美偏好推断
    CUSTOM_ANALYSIS = "custom_analysis"             # 自定义分析

@dataclass
class AnalysisTask:
    """单个分析任务定义"""
    task_type: AnalysisTaskType
    description: str
    expected_output_format: Dict[str, Any]
    prompt_template: Optional[str] = None
    confidence_threshold: float = 0.7
    
@dataclass 
class AnalysisResult:
    """单个分析结果"""
    task_type: AnalysisTaskType
    result: Dict[str, Any]
    confidence: float
    processing_time: float
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class SemanticAnalysisResponse:
    """完整的语义分析响应"""
    input_text: str
    analysis_results: Dict[str, AnalysisResult]
    total_processing_time: float
    overall_success: bool
    cache_hit: bool = False
    llm_provider: Optional[str] = None
    
class SemanticAnalyzer:
    """语义分析器 - 基于LLM的智能文本分析引擎"""
    
    def __init__(self, llm_manager=None, config: Optional[Dict] = None):
        """
        初始化语义分析器
        
        Args:
            llm_manager: LLM管理器实例，如果为None则自动创建
            config: 配置字典，包含分析参数和LLM设置
        """
        self.config = config or self._get_default_config()
        
        # 🔥 修复：如果没有提供LLM管理器，尝试自动创建
        if llm_manager is not None:
            self.llm_manager = llm_manager
            logger.info("🔗 使用外部提供的LLM管理器")
        else:
            # 尝试自动创建LLM管理器
            self.llm_manager = self._create_llm_manager()
        
        # 分析结果缓存
        self.analysis_cache = {}
        self.cache_ttl = self.config.get('cache_ttl', 300)  # 5分钟缓存
        
        # 统计信息
        self.stats = {
            'total_analyses': 0,
            'cache_hits': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'total_processing_time': 0.0
        }
        
        # 预定义分析任务模板
        self.builtin_tasks = self._initialize_builtin_tasks()
        
        logger.info("🔍 SemanticAnalyzer 已初始化")
    
    def _create_llm_manager(self):
        """创建LLM管理器"""
        try:
            from ..providers.llm_manager import LLMManager
            llm_manager = LLMManager()
            logger.info("🤖 自动创建LLM管理器成功")
            return llm_manager
        except ImportError as e:
            logger.warning(f"⚠️ 无法导入LLMManager: {e}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ LLM管理器创建失败: {e}")
            return None
        
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'cache_ttl': 300,  # 缓存时间
            'max_retries': 3,  # 最大重试次数
            'timeout': 30,     # 请求超时时间
            'batch_size': 5,   # 批处理大小
            'confidence_threshold': 0.7,  # 默认置信度阈值
            'model_name': None,  # 默认模型（None表示使用LLM管理器的默认模型）
            'temperature': 0.1,  # 低温度保证结果稳定性
        }
        
    def _initialize_builtin_tasks(self) -> Dict[str, AnalysisTask]:
        """初始化内置分析任务"""
        tasks = {}
        
        # 意图识别任务
        tasks['intent_detection'] = AnalysisTask(
            task_type=AnalysisTaskType.INTENT_DETECTION,
            description="识别用户输入的意图和目的",
            expected_output_format={
                "primary_intent": "string",  # 主要意图
                "secondary_intents": ["string"],  # 次要意图
                "confidence": "float",  # 置信度
                "intent_category": "string",  # 意图类别
                "action_required": "boolean"  # 是否需要行动
            },
            prompt_template="""请分析以下文本的意图：

文本: "{text}"

请识别用户的意图并返回JSON格式结果：
{{
    "primary_intent": "主要意图（如：信息查询、问题解决、任务执行等）",
    "secondary_intents": ["次要意图列表"],
    "confidence": 0.0-1.0之间的置信度分数,
    "intent_category": "意图类别（如：question, request, command, greeting等）",
    "action_required": true/false 是否需要具体行动
}}

请仅返回JSON，不要其他内容。"""
        )
        
        # 情感分析任务
        tasks['sentiment_analysis'] = AnalysisTask(
            task_type=AnalysisTaskType.SENTIMENT_ANALYSIS,
            description="分析文本的情感倾向和情绪状态",
            expected_output_format={
                "overall_sentiment": "string",  # 总体情感
                "sentiment_score": "float",     # 情感分数
                "emotions": {"emotion": "float"},  # 具体情绪
                "emotional_intensity": "string"   # 情感强度
            },
            prompt_template="""请分析以下文本的情感和情绪：

文本: "{text}"

请返回JSON格式的情感分析结果：
{{
    "overall_sentiment": "positive/negative/neutral",
    "sentiment_score": -1.0到1.0之间的分数（-1最负面，1最正面），
    "emotions": {{
        "joy": 0.0-1.0,
        "anger": 0.0-1.0,
        "fear": 0.0-1.0,
        "sadness": 0.0-1.0,
        "surprise": 0.0-1.0,
        "trust": 0.0-1.0
    }},
    "emotional_intensity": "low/medium/high"
}}

请仅返回JSON，不要其他内容。"""
        )
        
        # 复杂度评估任务
        tasks['complexity_assessment'] = AnalysisTask(
            task_type=AnalysisTaskType.COMPLEXITY_ASSESSMENT,
            description="评估任务或问题的复杂程度",
            expected_output_format={
                "complexity_level": "string",      # 复杂度等级
                "complexity_score": "float",       # 复杂度分数
                "complexity_factors": ["string"],  # 复杂度因素
                "estimated_effort": "string",      # 预估工作量
                "requires_expertise": "boolean"    # 是否需要专业知识
            },
            prompt_template="""请评估以下任务或问题的复杂程度：

文本: "{text}"

请返回JSON格式的复杂度评估结果：
{{
    "complexity_level": "low/medium/high/expert",
    "complexity_score": 0.0-1.0之间的复杂度分数,
    "complexity_factors": ["导致复杂的具体因素列表"],
    "estimated_effort": "minimal/moderate/substantial/extensive",
    "requires_expertise": true/false
}}

评估标准：
- Low: 简单直接的任务，几分钟内可完成
- Medium: 需要一些思考和步骤的任务
- High: 复杂的多步骤任务，需要深入分析
- Expert: 需要专业知识和大量时间的任务

请仅返回JSON，不要其他内容。"""
        )
        
        # 领域分类任务
        tasks['domain_classification'] = AnalysisTask(
            task_type=AnalysisTaskType.DOMAIN_CLASSIFICATION,
            description="识别文本所属的专业领域或主题域",
            expected_output_format={
                "primary_domain": "string",        # 主要领域
                "secondary_domains": ["string"],   # 次要领域  
                "domain_confidence": "float",      # 领域置信度
                "is_interdisciplinary": "boolean", # 是否跨领域
                "technical_level": "string"        # 技术水平
            },
            prompt_template="""请识别以下文本所属的专业领域：

文本: "{text}"

请返回JSON格式的领域分类结果：
{{
    "primary_domain": "主要专业领域",
    "secondary_domains": ["相关的次要领域"],
    "domain_confidence": 0.0-1.0之间的置信度,
    "is_interdisciplinary": true/false,
    "technical_level": "basic/intermediate/advanced/expert"
}}

领域包括但不限于：
技术（programming, ai, database, system），商业（marketing, finance, strategy），
学术（research, theory, analysis），生活（health, travel, education），
创意（design, art, writing）等

请仅返回JSON，不要其他内容。"""
        )
        
        # 紧急程度评估任务
        tasks['urgency_evaluation'] = AnalysisTask(
            task_type=AnalysisTaskType.URGENCY_EVALUATION,
            description="评估任务的紧急程度和优先级",
            expected_output_format={
                "urgency_level": "string",         # 紧急程度
                "urgency_score": "float",          # 紧急度分数
                "time_sensitivity": "string",      # 时间敏感度
                "consequences": "string",          # 延迟后果
                "priority_rank": "integer"         # 优先级排名
            },
            prompt_template="""请评估以下任务的紧急程度：

文本: "{text}"

请返回JSON格式的紧急程度评估：
{{
    "urgency_level": "low/medium/high/critical",
    "urgency_score": 0.0-1.0之间的紧急度分数,
    "time_sensitivity": "flexible/moderate/strict/immediate",
    "consequences": "延迟处理的后果描述",
    "priority_rank": 1-10之间的优先级排名（10最高）
}}

评估标准：
- Low: 可以稍后处理，无明确时间限制
- Medium: 建议及时处理，有一定时间要求
- High: 需要尽快处理，有明确期限
- Critical: 需要立即处理，延迟会有严重后果

请仅返回JSON，不要其他内容。"""
        )
        
        # 🔑 关键词提取任务
        tasks['keyword_extraction'] = AnalysisTask(
            task_type=AnalysisTaskType.KEYWORD_EXTRACTION,
            description="从文本中提取关键词和技术术语",
            expected_output_format={
                "keywords": ["string"],           # 主要关键词
                "technical_terms": ["string"],   # 技术术语
                "key_phrases": ["string"],       # 关键短语
                "entities": ["string"],          # 实体名称
                "confidence": "float"            # 提取置信度
            },
            prompt_template="""请从以下文本中提取关键词和技术术语：

文本: "{text}"

请返回JSON格式的关键词提取结果：
{{
    "keywords": ["主要关键词列表，3-5个最重要的词汇"],
    "technical_terms": ["技术术语列表，包括专业名词、技术概念等"],
    "key_phrases": ["关键短语列表，2-4个词的重要短语"],
    "entities": ["实体名称，如人名、地名、产品名、公司名等"],
    "confidence": 0.0-1.0之间的提取置信度分数
}}

提取要求：
- 关键词应该是最能代表文本核心内容的词汇
- 技术术语包括API、算法、框架、工具等专业概念
- 关键短语应该是有意义的词组合
- 实体应该是具体的名称
- 去除停用词和无意义的词汇

请仅返回JSON，不要其他内容。"""
        )
        
        # 视觉需求识别任务
        tasks['visual_need_detection'] = AnalysisTask(
            task_type=AnalysisTaskType.VISUAL_NEED_DETECTION,
            description="识别用户查询是否需要视觉化表达或图像生成",
            expected_output_format={
                "needs_visual": "boolean",       # 是否需要视觉化
                "visual_type": "string",         # 视觉化类型
                "confidence": "float",           # 置信度
                "visual_purpose": "string",      # 视觉化目的
                "suggested_elements": ["string"] # 建议元素
            },
            prompt_template="""请分析以下文本是否需要视觉化表达或图像生成：

文本: "{text}"

请识别用户是否需要视觉内容并返回JSON格式结果：
{{
    "needs_visual": true/false - 是否需要生成或展示视觉内容,
    "visual_type": "设计类型（如：logo, illustration, diagram, photo, art, ui_mockup, infographic等）",
    "confidence": 0.0-1.0之间的置信度分数,
    "visual_purpose": "视觉化的目的（如：展示概念、辅助说明、艺术创作、设计原型等）",
    "suggested_elements": ["建议包含的视觉元素或特征列表"]
}}

判断标准：
- 直接请求："画", "设计", "生成图片", "创作", "制作"等
- 隐含需求："想象一下...", "展示...", "什么样子？", "如何看起来？"
- 描述性内容：详细的外观、场景、风格描述
- 设计相关：界面、logo、插图、原型等需求

请仅返回JSON，不要其他内容。"""
        )
        
        # 🎨 视觉增强机会评估任务 - 从"判断需求"升级为"评估机会"
        tasks['visual_enhancement_opportunity'] = AnalysisTask(
            task_type=AnalysisTaskType.VISUAL_ENHANCEMENT_OPPORTUNITY,
            description="评估视觉内容增强用户体验的机会和潜力，不仅限于明确的图像请求",
            expected_output_format={
                # 基本判断
                "has_visual_opportunity": "boolean",    # 是否存在视觉增强机会
                "opportunity_strength": "float",       # 机会强度 (0.0-1.0)
                "opportunity_type": "string",          # 机会类型
                
                # 情境分析
                "context_analysis": {
                    "conversation_tone": "string",     # 对话调性
                    "user_emotional_state": "string",  # 用户情绪状态
                    "content_complexity": "string",    # 内容复杂度
                    "interaction_phase": "string"      # 交互阶段
                },
                
                # 视觉建议
                "visual_recommendations": {
                    "primary_visual_type": "string",   # 主要视觉类型
                    "style_suggestions": ["string"],   # 风格建议
                    "mood_alignment": "string",        # 情绪匹配
                    "aesthetic_direction": "string"    # 审美方向
                },
                
                # 时机判断
                "timing_assessment": {
                    "generation_timing": "string",     # 生成时机
                    "user_readiness": "float",         # 用户准备度
                    "context_appropriateness": "float" # 情境适宜度
                },
                
                # 个性化建议
                "personalization": {
                    "suggested_elements": ["string"],  # 建议元素
                    "avoid_elements": ["string"],      # 需要避免的元素
                    "cultural_considerations": "string" # 文化考量
                }
            },
            prompt_template="""作为一名具备深度审美理解和情商的AI助手，请评估以下内容的视觉增强机会：

用户输入: "{text}"

请以一名经验丰富的交互设计师和情绪智能专家的视角，综合分析并返回JSON结果：

{{
    "has_visual_opportunity": true/false,
    "opportunity_strength": 0.0-1.0之间的机会强度分数,
    "opportunity_type": "机会类型（如：explicit_request, implicit_enhancement, educational_support, emotional_resonance, creative_inspiration）",
    
    "context_analysis": {{
        "conversation_tone": "对话调性（如：formal, casual, playful, serious, creative, professional）",
        "user_emotional_state": "用户情绪（如：curious, frustrated, excited, focused, overwhelmed, inspired）",
        "content_complexity": "内容复杂度（如：simple, moderate, complex, highly_technical）",
        "interaction_phase": "交互阶段（如：initial_inquiry, deep_exploration, problem_solving, creative_brainstorming）"
    }},
    
    "visual_recommendations": {{
        "primary_visual_type": "主要视觉类型（如：illustration, diagram, infographic, artistic_concept, ui_mockup, photo_realistic）",
        "style_suggestions": ["风格建议列表、如：minimalist, vibrant, professional, whimsical, modern, classic"],
        "mood_alignment": "情绪匹配（如：calm_and_focused, energetic_and_inspiring, warm_and_friendly, sleek_and_modern）",
        "aesthetic_direction": "审美方向（如：clean_and_simple, rich_and_detailed, bold_and_dramatic, subtle_and_elegant）"
    }},
    
    "timing_assessment": {{
        "generation_timing": "生成时机（如：immediate, after_text_response, on_request, contextually_appropriate）",
        "user_readiness": 0.0-1.0之间的用户准备度分数,
        "context_appropriateness": 0.0-1.0之间的情境适宜度分数
    }},
    
    "personalization": {{
        "suggested_elements": ["建议包含的视觉元素列表"],
        "avoid_elements": ["应避免的元素列表"],
        "cultural_considerations": "文化敏感性考量和建议"
    }}
}}

评估标准：
1. **机会识别**：不仅识别明确的图像请求，更要挖掘隐含的视觉增强机会
2. **情境敏感**：理解对话氛围、用户情绪和交互阶段
3. **审美判断**：提供符合情境和用户需求的视觉风格建议
4. **时机智能**：判断何时生成视觉内容最适宜
5. **个性化适应**：基于内容和情境提供个性化建议

请仅返回JSON，不要其他内容。"""
        )
        
        # 🧠 交互情境分析任务 - 深度理解对话情境
        tasks['interaction_context_analysis'] = AnalysisTask(
            task_type=AnalysisTaskType.INTERACTION_CONTEXT_ANALYSIS,
            description="分析当前交互的情境、氛围和用户状态，为视觉决策提供情境支持",
            expected_output_format={
                "interaction_context": {
                    "session_continuity": "string",   # 会话连续性
                    "topic_evolution": "string",      # 话题演化
                    "user_engagement_level": "float"  # 用户参与度
                },
                "emotional_intelligence": {
                    "detected_emotions": ["string"],  # 检测到的情绪
                    "emotional_trajectory": "string", # 情绪轨迹
                    "empathy_opportunities": ["string"] # 共情机会
                },
                "cognitive_load_assessment": {
                    "information_density": "float",   # 信息密度
                    "mental_effort_required": "string", # 所需心智努力
                    "attention_span_match": "float"   # 注意力匹配度
                }
            },
            prompt_template="""作为一名交互心理学和情绪智能专家，请分析以下交互情境：

用户输入: "{text}"

请返回JSON格式的情境分析：

{{
    "interaction_context": {{
        "session_continuity": "会话连续性（new_topic, topic_deepening, follow_up, context_switch）",
        "topic_evolution": "话题演化（introduction, exploration, refinement, conclusion）",
        "user_engagement_level": 0.0-1.0之间的参与度分数
    }},
    
    "emotional_intelligence": {{
        "detected_emotions": ["检测到的情绪列表，如：curiosity, excitement, frustration, confidence"],
        "emotional_trajectory": "情绪轨迹（如：steady_positive, growing_enthusiasm, initial_confusion_to_clarity）",
        "empathy_opportunities": ["可以表达共情的机会列表"]
    }},
    
    "cognitive_load_assessment": {{
        "information_density": 0.0-1.0之间的信息密度分数,
        "mental_effort_required": "所需心智努力级别（low, moderate, high, very_high）",
        "attention_span_match": 0.0-1.0之间的注意力匹配度分数
    }}
}}

分析重点：
- 识别用户的情绪状态和参与程度
- 评估当前交互的认知负荷
- 找到共情和情绪连接的机会

请仅返回JSON，不要其他内容。"""
        )
        
        # 🎭 审美偏好推断任务 - 理解用户的视觉品味
        tasks['aesthetic_preference_inference'] = AnalysisTask(
            task_type=AnalysisTaskType.AESTHETIC_PREFERENCE_INFERENCE,
            description="基于用户的表达方式、内容偏好和交互风格，推断其审美偏好",
            expected_output_format={
                "aesthetic_profile": {
                    "style_preference": "string",     # 风格偏好
                    "complexity_tolerance": "string", # 复杂度耐受度
                    "color_personality": "string",    # 颜色个性
                    "cultural_context": "string"      # 文化背景
                },
                "inferred_preferences": {
                    "visual_elements": ["string"],    # 偏好的视觉元素
                    "avoided_elements": ["string"],   # 可能不喜欢的元素
                    "mood_preferences": ["string"]    # 情绪调性偏好
                },
                "confidence_metrics": {
                    "preference_certainty": "float",  # 偏好确定性
                    "cultural_accuracy": "float",     # 文化准确性
                    "personalization_potential": "float" # 个性化潜力
                }
            },
            prompt_template="""作为一名跨文化审美心理学和设计人类学专家，请分析用户的潜在审美偏好：

用户输入: "{text}"

请基于语言风格、表达方式、内容类型等线索，推断用户的审美偏好并返回JSON：

{{
    "aesthetic_profile": {{
        "style_preference": "风格偏好（如：minimalist, maximalist, classic, modern, artistic, functional）",
        "complexity_tolerance": "复杂度耐受度（low, moderate, high, very_high）",
        "color_personality": "颜色个性（warm, cool, neutral, vibrant, muted, monochrome）",
        "cultural_context": "文化背景推断（如：eastern, western, contemporary, traditional）"
    }},
    
    "inferred_preferences": {{
        "visual_elements": ["可能喜欢的视觉元素列表，如：clean_lines, organic_shapes, geometric_patterns"],
        "avoided_elements": ["可能不喜欢的元素列表，如：clutter, harsh_contrasts, overly_decorative"],
        "mood_preferences": ["情绪调性偏好，如：calm, energetic, sophisticated, playful"]
    }},
    
    "confidence_metrics": {{
        "preference_certainty": 0.0-1.0之间的偏好确定性分数,
        "cultural_accuracy": 0.0-1.0之间的文化背景准确性分数,
        "personalization_potential": 0.0-1.0之间的个性化潜力分数
    }}
}}

推断依据：
- 语言风格：正式/非正式、技术性/创意性等
- 内容偏好：简洁/详细、抽象/具象等
- 交互方式：直接/委婉、快速/深入等
- 文化线索：表达习惯、价值观等

请仅返回JSON，不要其他内容。"""
        )
        
        return tasks
    
    def analyze(self, 
                text: str, 
                tasks: Union[List[str], List[AnalysisTask], str],
                **kwargs) -> SemanticAnalysisResponse:
        """
        执行语义分析
        
        Args:
            text: 要分析的文本
            tasks: 分析任务列表，可以是任务名称字符串列表、AnalysisTask对象列表或单个任务名
            **kwargs: 额外的分析参数
            
        Returns:
            SemanticAnalysisResponse: 分析结果
        """
        start_time = time.time()
        self.stats['total_analyses'] += 1
        
        try:
            # 统一任务格式
            task_list = self._prepare_tasks(tasks)
            
            # 检查缓存
            cache_key = self._generate_cache_key(text, task_list)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self.stats['cache_hits'] += 1
                logger.debug(f"🎯 缓存命中: {cache_key}")
                return cached_result
                
            # 执行分析
            results = {}
            overall_success = True
            llm_provider = None
            
            for task in task_list:
                try:
                    result = self._execute_single_task(text, task, **kwargs)
                    results[task.task_type.value] = result
                    
                    if not result.success:
                        overall_success = False
                        
                    # 记录使用的LLM提供商
                    if llm_provider is None and hasattr(self.llm_manager, 'last_used_provider'):
                        llm_provider = getattr(self.llm_manager, 'last_used_provider', None)
                        
                except Exception as e:
                    logger.error(f"❌ 任务执行失败 {task.task_type.value}: {e}")
                    results[task.task_type.value] = AnalysisResult(
                        task_type=task.task_type,
                        result={},
                        confidence=0.0,
                        processing_time=0.0,
                        success=False,
                        error_message=str(e)
                    )
                    overall_success = False
            
            # 创建响应对象
            total_time = time.time() - start_time
            response = SemanticAnalysisResponse(
                input_text=text,
                analysis_results=results,
                total_processing_time=total_time,
                overall_success=overall_success,
                cache_hit=False,
                llm_provider=llm_provider
            )
            
            # 缓存结果
            self._cache_result(cache_key, response)
            
            # 更新统计
            if overall_success:
                self.stats['successful_analyses'] += 1
            else:
                self.stats['failed_analyses'] += 1
            self.stats['total_processing_time'] += total_time
            
            logger.info(f"🔍 语义分析完成: {len(results)}项任务, 耗时{total_time:.2f}s")
            return response
            
        except Exception as e:
            logger.error(f"❌ 语义分析失败: {e}")
            self.stats['failed_analyses'] += 1
            
            return SemanticAnalysisResponse(
                input_text=text,
                analysis_results={},
                total_processing_time=time.time() - start_time,
                overall_success=False,
                cache_hit=False,
                llm_provider=None
            )
    
    def _prepare_tasks(self, tasks: Union[List[str], List[AnalysisTask], str]) -> List[AnalysisTask]:
        """准备分析任务列表"""
        if isinstance(tasks, str):
            # 单个任务名称
            if tasks in self.builtin_tasks:
                return [self.builtin_tasks[tasks]]
            else:
                raise ValueError(f"未知的内置任务: {tasks}")
                
        elif isinstance(tasks, list):
            task_list = []
            for task in tasks:
                if isinstance(task, str):
                    # 任务名称字符串
                    if task in self.builtin_tasks:
                        task_list.append(self.builtin_tasks[task])
                    else:
                        raise ValueError(f"未知的内置任务: {task}")
                elif isinstance(task, AnalysisTask):
                    # AnalysisTask对象
                    task_list.append(task)
                else:
                    raise ValueError(f"不支持的任务类型: {type(task)}")
            return task_list
        else:
            raise ValueError(f"不支持的任务格式: {type(tasks)}")
    
    def _execute_single_task(self, text: str, task: AnalysisTask, **kwargs) -> AnalysisResult:
        """执行单个分析任务"""
        start_time = time.time()
        
        try:
            # 准备提示词
            prompt = task.prompt_template.format(text=text) if task.prompt_template else f"请分析: {text}"
            
            # 调用LLM (这里需要实现LLM调用逻辑)
            llm_response = self._call_llm(prompt, task, **kwargs)
            
            # 解析响应 - 使用改进的JSON解析
            try:
                if isinstance(llm_response, str):
                    # 使用改进的JSON解析函数
                    from ..providers.rag_seed_generator import parse_json_response
                    result_data = parse_json_response(llm_response)
                    if not result_data:
                        # 如果解析失败，尝试标准JSON解析作为回退
                        result_data = json.loads(llm_response)
                else:
                    result_data = llm_response
                    
                confidence = result_data.get('confidence', task.confidence_threshold)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON解析失败，使用降级处理: {e}")
                result_data = {"raw_response": llm_response, "parse_error": str(e)}
                confidence = 0.5
            except Exception as e:
                logger.warning(f"⚠️ 响应解析异常，使用降级处理: {e}")
                result_data = {"raw_response": llm_response, "parse_error": str(e)}
                confidence = 0.5
            
            processing_time = time.time() - start_time
            
            return AnalysisResult(
                task_type=task.task_type,
                result=result_data,
                confidence=confidence,
                processing_time=processing_time,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ 任务执行异常 {task.task_type.value}: {e}")
            
            return AnalysisResult(
                task_type=task.task_type,
                result={},
                confidence=0.0,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
    
    def _call_llm(self, prompt: str, task: AnalysisTask, **kwargs) -> str:
        """调用LLM进行分析"""
        if not self.llm_manager:
            # 如果没有LLM管理器，尝试创建一个
            try:
                from ..providers.llm_manager import LLMManager
                self.llm_manager = LLMManager()
                logger.info("🤖 自动创建LLM管理器")
            except ImportError:
                logger.error("❌ 无法导入LLMManager，SemanticAnalyzer需要LLM支持")
                raise RuntimeError("SemanticAnalyzer requires LLM support")
        
        try:
            # 构建系统消息
            system_message = "你是一个专业的语义分析助手，专门负责分析文本并返回结构化的JSON结果。请严格按照要求的JSON格式返回，不要包含其他文字说明。"
            
            # 准备消息列表
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
            
            # 使用LLM管理器调用
            # 如果model为None，LLM管理器会自动使用当前提供商的默认模型
            model_to_use = kwargs.get('model') or self.config.get('model_name')
            response = self.llm_manager.chat_completion(
                messages=messages,
                model=model_to_use,  # None会让LLM管理器自动选择
                temperature=kwargs.get('temperature', self.config.get('temperature', 0.1)),
                max_tokens=kwargs.get('max_tokens', 2000),
                timeout=kwargs.get('timeout', self.config.get('timeout', 30))
            )
            
            if response and response.success:
                # 记录使用的提供商
                if hasattr(response, 'provider'):
                    self.llm_manager.last_used_provider = response.provider
                return response.content.strip()
            else:
                error_msg = response.error_message if response else "LLM调用无响应"
                logger.error(f"❌ LLM调用失败: {error_msg}")
                raise RuntimeError(f"LLM调用失败: {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ LLM调用异常: {e}")
            raise
    
    def _generate_cache_key(self, text: str, tasks: List[AnalysisTask]) -> str:
        """生成缓存键"""
        task_signatures = [f"{task.task_type.value}:{task.description[:50]}" for task in tasks]
        combined = f"{text}|{','.join(task_signatures)}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[SemanticAnalysisResponse]:
        """获取缓存结果"""
        if cache_key in self.analysis_cache:
            cached_data, timestamp = self.analysis_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                cached_data.cache_hit = True
                return cached_data
            else:
                # 缓存已过期
                del self.analysis_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: SemanticAnalysisResponse):
        """缓存分析结果"""
        self.analysis_cache[cache_key] = (result, time.time())
        
        # 简单的缓存清理：如果缓存过多，清理一半
        if len(self.analysis_cache) > 1000:
            keys_to_remove = list(self.analysis_cache.keys())[:500]
            for key in keys_to_remove:
                del self.analysis_cache[key]
            logger.info("🧹 缓存清理完成")
    
    def add_custom_task(self, task: AnalysisTask) -> None:
        """添加自定义分析任务"""
        self.builtin_tasks[task.task_type.value] = task
        logger.info(f"✅ 已添加自定义任务: {task.task_type.value}")
    
    def get_available_tasks(self) -> Dict[str, str]:
        """获取可用的分析任务列表"""
        return {task_id: task.description for task_id, task in self.builtin_tasks.items()}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        stats = self.stats.copy()
        stats['cache_hit_rate'] = (
            self.stats['cache_hits'] / max(self.stats['total_analyses'], 1)
        )
        stats['success_rate'] = (
            self.stats['successful_analyses'] / max(self.stats['total_analyses'], 1)  
        )
        stats['average_processing_time'] = (
            self.stats['total_processing_time'] / max(self.stats['total_analyses'], 1)
        )
        return stats
    
    def clear_cache(self):
        """清空分析缓存"""
        self.analysis_cache.clear()
        logger.info("🧹 分析缓存已清空")
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_analyses': 0,
            'cache_hits': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'total_processing_time': 0.0
        }
        logger.info("📊 统计信息已重置")


# 便捷函数
def create_semantic_analyzer(llm_manager=None, config=None) -> SemanticAnalyzer:
    """创建语义分析器实例"""
    return SemanticAnalyzer(llm_manager=llm_manager, config=config)

def quick_analyze(text: str, tasks: Union[List[str], str] = "intent_detection", 
                 llm_manager=None) -> Dict[str, Any]:
    """快速语义分析 - 便捷方法"""
    analyzer = create_semantic_analyzer(llm_manager)
    response = analyzer.analyze(text, tasks)
    
    # 返回简化的结果字典
    results = {}
    for task_type, result in response.analysis_results.items():
        if result.success:
            results[task_type] = result.result
        else:
            results[task_type] = {"error": result.error_message}
    
    return results


if __name__ == "__main__":
    # 简单测试
    print("🔍 SemanticAnalyzer 测试")
    
    # 创建分析器
    analyzer = create_semantic_analyzer()
    
    # 测试分析
    test_text = "我急需一个高性能的机器学习API解决方案"
    test_tasks = ['intent_detection', 'sentiment_analysis', 'complexity_assessment', 'domain_classification']
    
    print(f"测试文本: {test_text}")
    print(f"分析任务: {test_tasks}")
    
    # 注意：这个测试需要有LLM管理器支持才能正常运行
    try:
        response = analyzer.analyze(test_text, test_tasks)
        print(f"分析结果: {response}")
        print(f"统计信息: {analyzer.get_stats()}")
    except Exception as e:
        print(f"测试失败（正常，需要LLM支持）: {e}")
    
    print("✅ SemanticAnalyzer 模块加载成功")
