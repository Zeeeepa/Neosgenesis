#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自主知识探勘模块 - Knowledge Explorer
Agent连接外部智慧的桥梁

这个模块实现了认知飞轮的"探索触角"，负责：
1. 主动探勘外部世界的新知识和智慧
2. 多源信息的获取、整合和质量评估
3. 基于探索结果生成新的思维种子
4. 为认知飞轮提供持续的"营养输入"

核心理念：让AI从内向型思维扩展为外向型认知探索者
"""

import time
import random
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

try:
    from .search_tools import WebSearchClient
except ImportError:
    WebSearchClient = None

logger = logging.getLogger(__name__)

try:
    from cognitive_engine.semantic_analyzer import SemanticAnalyzer, AnalysisTaskType
except ImportError:
    try:
        # 尝试相对导入作为回退
        from ..cognitive_engine.semantic_analyzer import SemanticAnalyzer, AnalysisTaskType
    except ImportError:
        SemanticAnalyzer = None
        AnalysisTaskType = None
        logger.warning("⚠️ SemanticAnalyzer 导入失败，KnowledgeExplorer将使用默认策略运行")


class ExplorationStrategy(Enum):
    """探索策略枚举"""
    DOMAIN_EXPANSION = "domain_expansion"           # 领域扩展探索
    TREND_MONITORING = "trend_monitoring"           # 趋势监控探索
    GAP_ANALYSIS = "gap_analysis"                   # 知识缺口分析
    CROSS_DOMAIN_LEARNING = "cross_domain_learning" # 跨域学习探索
    SERENDIPITY_DISCOVERY = "serendipity_discovery" # 偶然发现探索
    EXPERT_KNOWLEDGE = "expert_knowledge"           # 专家知识获取
    COMPETITIVE_INTELLIGENCE = "competitive_intelligence" # 竞争情报分析


class KnowledgeQuality(Enum):
    """知识质量等级"""
    EXCELLENT = "excellent"     # 优秀：高可信度、高创新性
    GOOD = "good"              # 良好：中等质量，有一定价值
    FAIR = "fair"              # 一般：基础信息，参考价值
    POOR = "poor"              # 较差：质量存疑，需要验证
    UNRELIABLE = "unreliable"   # 不可靠：不建议使用


@dataclass
class ExplorationTarget:
    """探索目标数据结构"""
    target_id: str
    target_type: str  # "concept", "trend", "technology", "methodology", "domain"
    description: str
    keywords: List[str] = field(default_factory=list)
    priority: float = 0.5  # 0-1, 1为最高优先级
    exploration_depth: int = 1  # 探索深度层级
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeItem:
    """知识项数据结构"""
    knowledge_id: str
    content: str
    source: str
    source_type: str  # "web_search", "api_call", "database", "expert_system"
    quality: KnowledgeQuality
    confidence_score: float = 0.5  # 0-1, 置信度分数
    relevance_score: float = 0.5   # 0-1, 相关性分数
    novelty_score: float = 0.5     # 0-1, 新颖性分数
    
    # 元数据
    extraction_method: str = ""
    language: str = "zh"
    discovered_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    
    # 验证状态
    is_verified: bool = False
    verification_method: str = ""
    verification_score: float = 0.0


@dataclass
class ThinkingSeed:
    """思维种子数据结构"""
    seed_id: str
    seed_content: str
    source_knowledge: List[str] = field(default_factory=list)  # 来源知识项ID列表
    creativity_level: str = "medium"  # "low", "medium", "high"
    potential_applications: List[str] = field(default_factory=list)
    generated_strategy: str = ""
    confidence: float = 0.5
    
    # 认知路径相关
    suggested_reasoning_paths: List[str] = field(default_factory=list)
    cross_domain_connections: List[str] = field(default_factory=list)
    
    # 元数据
    generated_at: float = field(default_factory=time.time)
    generation_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExplorationResult:
    """探索结果数据结构"""
    exploration_id: str
    strategy: ExplorationStrategy
    targets: List[ExplorationTarget]
    
    # 探索成果
    discovered_knowledge: List[KnowledgeItem] = field(default_factory=list)
    generated_seeds: List[ThinkingSeed] = field(default_factory=list)
    identified_trends: List[Dict[str, Any]] = field(default_factory=list)
    cross_domain_insights: List[Dict[str, Any]] = field(default_factory=list)
    
    # 执行统计
    execution_time: float = 0.0
    success_rate: float = 0.0
    quality_score: float = 0.0
    
    # 元数据
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


class KnowledgeExplorer:
    """
    🌐 自主知识探勘模块 - Agent的"外部智慧连接器"
    
    核心职责：
    1. 主动探勘外部世界的新知识和趋势
    2. 多源信息获取：网络搜索、API调用、专家系统
    3. 智能知识质量评估和过滤机制
    4. 基于探索发现生成高质量思维种子
    5. 为认知飞轮提供持续的知识"营养输入"
    
    设计原则：
    - 主动性：不等待指令，主动发现机会
    - 多样性：支持多种探索策略和信息源
    - 质量优先：严格的知识质量评估体系
    - 适应性：根据探索效果动态调整策略
    """
    
    def __init__(self, 
                 llm_client=None,
                 web_search_client=None,
                 semantic_analyzer=None,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化知识探勘模块
        
        Args:
            llm_client: LLM客户端（用于智能分析）
            web_search_client: 网络搜索客户端
            semantic_analyzer: 语义分析器（用于智能意图理解和策略选择）
            config: 探勘配置参数
        """
        self.llm_client = llm_client
        self.web_search_client = web_search_client
        self.semantic_analyzer = semantic_analyzer
        
        # 配置参数
        self.config = {
            # 探索策略配置
            "exploration_strategies": {
                "default_strategy": ExplorationStrategy.DOMAIN_EXPANSION,
                "strategy_rotation": True,              # 是否轮换策略
                "max_parallel_explorations": 3,        # 最大并行探索数
                "exploration_timeout": 120.0           # 探索超时时间
            },
            
            # 质量控制配置
            "quality_control": {
                "min_confidence_threshold": 0.4,       # 最小置信度阈值
                "min_relevance_threshold": 0.3,        # 最小相关性阈值
                "enable_cross_validation": True,       # 启用交叉验证
                "quality_decay_factor": 0.1            # 质量衰减因子
            },
            
            # 种子生成配置
            "seed_generation": {
                "max_seeds_per_exploration": 5,        # 每次探索最大种子数
                "creativity_boost_factor": 1.2,        # 创意提升因子
                "cross_domain_bonus": 0.3,            # 跨域连接奖励
                "enable_serendipity": True             # 启用偶然发现
            },
            
            # 信息源配置
            "information_sources": {
                "enable_web_search": True,             # 启用网络搜索
                "enable_api_calls": False,             # 启用API调用
                "enable_database_query": False,       # 启用数据库查询
                "max_results_per_source": 10          # 每个信息源最大结果数
            }
        }
        
        # 合并用户配置
        if config:
            self._merge_config(self.config, config)
        
        # 初始化信息源客户端
        if not self.web_search_client and self.config["information_sources"]["enable_web_search"]:
            try:
                if WebSearchClient:
                    self.web_search_client = WebSearchClient(
                        max_results=self.config["information_sources"]["max_results_per_source"]
                    )
                    logger.info("🌐 网络搜索客户端已初始化")
                else:
                    logger.warning("⚠️ WebSearchClient 不可用，网络搜索功能将被禁用")
            except Exception as e:
                logger.warning(f"⚠️ 网络搜索客户端初始化失败: {e}")
        
        # 探索历史和统计
        self.exploration_history: List[ExplorationResult] = []
        self.knowledge_cache: Dict[str, KnowledgeItem] = {}
        self.seed_cache: Dict[str, ThinkingSeed] = {}
        
        # 策略性能统计
        self.strategy_performance: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"success_rate": 0.0, "avg_quality": 0.0, "total_seeds": 0}
        )
        
        # 探索目标管理
        self.active_targets: List[ExplorationTarget] = []
        self.completed_targets: List[ExplorationTarget] = []
        
        # 性能统计
        self.stats = {
            "total_explorations": 0,
            "successful_explorations": 0,
            "total_knowledge_discovered": 0,
            "total_seeds_generated": 0,
            "average_quality_score": 0.0,
            "average_execution_time": 0.0
        }
        
        logger.info("🌐 KnowledgeExplorer 初始化完成")
        logger.info(f"   网络搜索: {'启用' if self.web_search_client else '禁用'}")
        logger.info(f"   LLM分析: {'启用' if self.llm_client else '禁用'}")
        logger.info("🔍 外部智慧连接器已就绪 - 主动探索模式启动")
    
    def explore_knowledge(self, 
                         targets: List[ExplorationTarget],
                         strategy: Optional[ExplorationStrategy] = None,
                         user_context: Optional[Dict[str, Any]] = None) -> ExplorationResult:
        """
        执行知识探勘任务 - 双轨探索系统核心入口
        
        Args:
            targets: 探索目标列表
            strategy: 探索策略（可选）
            user_context: 用户上下文（用于用户指令驱动模式）
            
        Returns:
            完整的探索结果
        """
        start_time = time.time()
        exploration_id = f"exploration_{int(time.time() * 1000)}"
        
        # 🎯 检测探索模式
        is_user_directed = user_context and user_context.get("exploration_mode") == "user_directed"
        exploration_mode = "用户指令驱动" if is_user_directed else "系统自主探索"
        
        # 确定探索策略
        if not strategy:
            if is_user_directed:
                strategy = self._select_user_directed_strategy(targets, user_context)
            else:
                strategy = self._select_optimal_strategy(targets)
        
        logger.info(f"🌐 开始知识探勘: {exploration_id} ({exploration_mode})")
        logger.info(f"   策略: {strategy.value}")
        logger.info(f"   目标数量: {len(targets)}")
        
        if is_user_directed:
            user_query = user_context.get("user_query", "")
            logger.info(f"   🎯 用户查询: {user_query[:50]}...")
        
        try:
            # 创建探索结果对象
            result = ExplorationResult(
                exploration_id=exploration_id,
                strategy=strategy,
                targets=targets
            )
            
            # 执行探索流程
            self._execute_exploration_pipeline(result)
            
            # 计算执行统计
            result.execution_time = time.time() - start_time
            result.success_rate = self._calculate_success_rate(result)
            result.quality_score = self._calculate_quality_score(result)
            
            # 更新缓存和统计
            self._update_caches_and_stats(result)
            
            logger.info(f"✅ 知识探勘完成: {exploration_id}")
            logger.info(f"   执行时间: {result.execution_time:.2f}s")
            logger.info(f"   发现知识: {len(result.discovered_knowledge)} 项")
            logger.info(f"   生成种子: {len(result.generated_seeds)} 个")
            logger.info(f"   质量评分: {result.quality_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 知识探勘失败: {exploration_id} - {e}")
            # 返回空结果但包含错误信息
            return ExplorationResult(
                exploration_id=exploration_id,
                strategy=strategy,
                targets=targets,
                execution_time=time.time() - start_time,
                context={"error": str(e)}
            )
    
    def _execute_exploration_pipeline(self, result: ExplorationResult):
        """执行完整的探索流水线"""
        logger.info("🔄 执行探索流水线...")
        
        # 阶段1: 信息收集
        logger.info("📡 阶段1: 信息收集")
        raw_information = self._collect_information(result.targets, result.strategy)
        
        # 阶段2: 知识提取和质量评估
        logger.info("🔍 阶段2: 知识提取和质量评估")
        result.discovered_knowledge = self._extract_and_evaluate_knowledge(
            raw_information, result.targets
        )
        
        # 阶段3: 思维种子生成
        logger.info("🌱 阶段3: 思维种子生成")
        result.generated_seeds = self._generate_thinking_seeds(
            result.discovered_knowledge, result.strategy
        )
        
        # 阶段4: 趋势分析
        logger.info("📈 阶段4: 趋势分析")
        result.identified_trends = self._analyze_trends(
            result.discovered_knowledge, result.targets
        )
        
        # 阶段5: 跨域洞察发现
        logger.info("🔗 阶段5: 跨域洞察发现")
        result.cross_domain_insights = self._discover_cross_domain_insights(
            result.discovered_knowledge, result.generated_seeds
        )
        
        logger.info("✅ 探索流水线执行完成")
    
    def _collect_information(self, 
                           targets: List[ExplorationTarget], 
                           strategy: ExplorationStrategy) -> List[Dict[str, Any]]:
        """信息收集阶段 - 从多个信息源获取原始信息"""
        raw_information = []
        
        for target in targets[:self.config["exploration_strategies"]["max_parallel_explorations"]]:
            logger.debug(f"🎯 收集目标信息: {target.target_id}")
            
            # 网络搜索
            if (self.web_search_client and 
                self.config["information_sources"]["enable_web_search"]):
                web_results = self._search_web_information(target, strategy)
                raw_information.extend(web_results)
            
            # API调用（预留接口）
            if self.config["information_sources"]["enable_api_calls"]:
                api_results = self._query_api_sources(target, strategy)
                raw_information.extend(api_results)
            
            # 数据库查询（预留接口）
            if self.config["information_sources"]["enable_database_query"]:
                db_results = self._query_database_sources(target, strategy)
                raw_information.extend(db_results)
        
        logger.info(f"📡 信息收集完成: 获取 {len(raw_information)} 条原始信息")
        return raw_information
    
    def _search_web_information(self, 
                              target: ExplorationTarget, 
                              strategy: ExplorationStrategy) -> List[Dict[str, Any]]:
        """执行网络搜索"""
        if not self.web_search_client:
            return []
        
        try:
            # 构建搜索查询
            search_queries = self._build_search_queries(target, strategy)
            web_results = []
            
            for query in search_queries[:3]:  # 限制查询数量
                logger.debug(f"🔍 搜索查询: {query}")
                
                results = self.web_search_client.search(query)
                for result in results:
                    web_results.append({
                        "content": result.get("snippet", ""),
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "source": "web_search",
                        "query": query,
                        "target_id": target.target_id,
                        "collected_at": time.time()
                    })
            
            logger.debug(f"🌐 网络搜索完成: {len(web_results)} 条结果")
            return web_results
            
        except Exception as e:
            logger.error(f"❌ 网络搜索失败: {e}")
            return []
    
    def _build_search_queries(self, 
                            target: ExplorationTarget, 
                            strategy: ExplorationStrategy) -> List[str]:
        """🔍 构建语义增强的搜索查询 - 优先使用语义理解，回退到关键词构建"""
        base_keywords = target.keywords + [target.description]
        queries = []
        
        # 🎯 根据探索模式和优先级调整搜索策略
        is_user_directed = target.metadata.get("exploration_mode") == "user_directed"
        priority_level = target.priority
        target_type = target.metadata.get("target_type", "general")
        user_query = target.metadata.get("user_query", "")
        
        logger.debug(f"🔍 构建搜索查询: 模式={target.metadata.get('exploration_mode')}, "
                    f"优先级={priority_level}, 查询='{user_query[:30]}...'")
        
        # 🧠 优先尝试语义增强的查询构建
        if is_user_directed and self.semantic_analyzer and user_query:
            try:
                semantic_queries = self._build_semantic_enhanced_queries(user_query, target, strategy, base_keywords)
                if semantic_queries:
                    queries.extend(semantic_queries)
                    logger.debug(f"✅ 使用语义增强查询: 生成 {len(semantic_queries)} 个查询")
                else:
                    # 语义增强失败，使用传统方法
                    queries.extend(self._build_traditional_queries(target, strategy, base_keywords))
                    logger.debug("🔄 语义增强失败，使用传统查询构建")
            except Exception as e:
                logger.warning(f"⚠️ 语义增强查询构建失败: {e}")
                queries.extend(self._build_traditional_queries(target, strategy, base_keywords))
        else:
            # 使用传统查询构建方法
            queries.extend(self._build_traditional_queries(target, strategy, base_keywords))
        
        # 根据优先级限制查询数量
        if priority_level == ExplorationPriority.HIGH:
            max_queries = 8  # 高优先级允许更多查询
        elif priority_level == ExplorationPriority.MEDIUM:
            max_queries = 6
        else:
            max_queries = 4  # 低优先级限制查询数量
        
        final_queries = queries[:max_queries]
        logger.debug(f"🔍 最终生成 {len(final_queries)} 个搜索查询 (最大: {max_queries})")
        return final_queries
    
    def _build_semantic_enhanced_queries(self, user_query: str, target: ExplorationTarget, 
                                       strategy: ExplorationStrategy, base_keywords: List[str]) -> List[str]:
        """🧠 基于语义分析构建智能搜索查询"""
        try:
            # 执行语义分析
            analysis_tasks = ['intent_detection', 'domain_classification', 'keyword_extraction']
            response = self.semantic_analyzer.analyze(user_query, analysis_tasks)
            
            if not response.overall_success:
                logger.warning("⚠️ 语义分析失败，无法构建语义增强查询")
                return []
            
            # 提取分析结果
            intent_result = response.analysis_results.get('intent_detection')
            domain_result = response.analysis_results.get('domain_classification')
            keyword_result = response.analysis_results.get('keyword_extraction')
            
            intent = None
            domain = None
            semantic_keywords = []
            
            confidence_threshold = 0.7
            
            if intent_result and intent_result.success and intent_result.confidence > confidence_threshold:
                intent = intent_result.result.get('primary_intent')
                
            if domain_result and domain_result.success and domain_result.confidence > confidence_threshold:
                domain = domain_result.result.get('domain')
                
            if keyword_result and keyword_result.success:
                semantic_keywords = keyword_result.result.get('keywords', [])[:5]
            
            logger.debug(f"🧠 语义分析提取: intent={intent}, domain={domain}, keywords={semantic_keywords}")
            
            # 基于语义分析结果生成查询
            semantic_queries = self._generate_queries_from_semantics(
                user_query, intent, domain, semantic_keywords, strategy, target.metadata
            )
            
            return semantic_queries
            
        except Exception as e:
            logger.error(f"❌ 语义增强查询构建异常: {e}")
            return []
    
    def _generate_queries_from_semantics(self, user_query: str, intent: Optional[str], 
                                       domain: Optional[str], semantic_keywords: List[str],
                                       strategy: ExplorationStrategy, metadata: Dict[str, Any]) -> List[str]:
        """🎯 基于语义要素生成搜索查询"""
        queries = []
        
        # 使用原始查询作为基础
        queries.append(user_query)
        
        # 基于意图生成专门化查询
        if intent:
            intent_queries = self._get_intent_specific_queries(user_query, intent, semantic_keywords)
            queries.extend(intent_queries)
        
        # 基于领域生成专业化查询
        if domain:
            domain_queries = self._get_domain_specific_queries(user_query, domain, semantic_keywords)
            queries.extend(domain_queries)
        
        # 基于策略生成增强查询
        strategy_queries = self._get_strategy_enhanced_queries(user_query, strategy, semantic_keywords)
        queries.extend(strategy_queries)
        
        # 去重并保持顺序
        unique_queries = []
        seen = set()
        for query in queries:
            if query and query not in seen:
                unique_queries.append(query)
                seen.add(query)
        
        logger.debug(f"🧠 语义生成查询: {len(unique_queries)} 个")
        return unique_queries
    
    def _get_intent_specific_queries(self, user_query: str, intent: str, keywords: List[str]) -> List[str]:
        """🎯 基于意图生成特定查询"""
        queries = []
        main_keywords = keywords[:3] if keywords else user_query.split()[:3]
        
        intent_templates = {
            'solution_seeking': [
                "{} 解决方案", "{} 最佳实践", "{} 实现方法", 
                "{} 专业指南", "{} 详细教程"
            ],
            'comparison_analysis': [
                "{} 对比分析", "{} 优劣比较", "{} 选择指南",
                "{} vs 替代方案", "{} 性能对比"
            ],
            'trend_monitoring': [
                "{} 最新趋势", "{} 2024发展", "{} 未来方向",
                "{} 创新动态", "{} 技术演进"
            ],
            'learning_request': [
                "{} 基础知识", "{} 学习指南", "{} 入门教程",
                "{} 深入理解", "{} 核心概念"
            ],
            'problem_diagnosis': [
                "{} 常见问题", "{} 故障排除", "{} 问题分析",
                "{} 诊断方法", "{} 解决方案"
            ]
        }
        
        templates = intent_templates.get(intent, ["{} 详细信息"])
        
        # 为每个主要关键词生成查询
        for keyword in main_keywords:
            for template in templates[:2]:  # 限制每个意图的查询数量
                query = template.format(keyword)
                queries.append(query)
        
        return queries[:4]  # 限制总数
    
    def _get_domain_specific_queries(self, user_query: str, domain: str, keywords: List[str]) -> List[str]:
        """🎯 基于领域生成特定查询"""
        queries = []
        main_keywords = keywords[:3] if keywords else user_query.split()[:3]
        
        domain_templates = {
            'technology': [
                "{} 技术原理", "{} 架构设计", "{} 性能优化",
                "{} 实现细节", "{} 最新技术"
            ],
            'business': [
                "{} 商业模式", "{} 市场分析", "{} 投资价值",
                "{} 商业案例", "{} 盈利策略"
            ],
            'academic': [
                "{} 研究现状", "{} 学术观点", "{} 理论基础",
                "{} 研究方法", "{} 前沿研究"
            ],
            'health': [
                "{} 健康影响", "{} 医疗应用", "{} 安全性",
                "{} 临床研究", "{} 专业建议"
            ]
        }
        
        templates = domain_templates.get(domain, ["{} 专业分析"])
        
        # 为每个关键词生成领域特定查询
        for keyword in main_keywords:
            for template in templates[:2]:
                query = template.format(keyword)
                queries.append(query)
        
        return queries[:3]  # 限制数量
    
    def _get_strategy_enhanced_queries(self, user_query: str, strategy: ExplorationStrategy, keywords: List[str]) -> List[str]:
        """🎯 基于探索策略生成增强查询"""
        queries = []
        main_keywords = keywords[:2] if keywords else user_query.split()[:2]
        
        strategy_templates = {
            ExplorationStrategy.EXPERT_KNOWLEDGE: [
                "{} 专家观点", "{} 权威指南", "{} 专业方法论"
            ],
            ExplorationStrategy.TREND_MONITORING: [
                "{} 最新趋势", "{} 发展动态", "{} 未来展望"
            ],
            ExplorationStrategy.COMPETITIVE_INTELLIGENCE: [
                "{} 竞争分析", "{} 市场对比", "{} 优势评估"
            ],
            ExplorationStrategy.CROSS_DOMAIN_LEARNING: [
                "{} 跨领域应用", "{} 创新融合", "{} 跨界案例"
            ],
            ExplorationStrategy.DOMAIN_EXPANSION: [
                "{} 应用领域", "{} 相关技术", "{} 扩展应用"
            ],
            ExplorationStrategy.GAP_ANALYSIS: [
                "{} 技术瓶颈", "{} 挑战问题", "{} 解决方案"
            ]
        }
        
        templates = strategy_templates.get(strategy, ["{} 深入分析"])
        
        for keyword in main_keywords:
            for template in templates:
                query = template.format(keyword)
                queries.append(query)
        
        return queries[:3]  # 限制数量
    
    def _build_traditional_queries(self, target: ExplorationTarget, strategy: ExplorationStrategy, 
                                 base_keywords: List[str]) -> List[str]:
        """🔄 传统查询构建方法（回退机制）"""
        is_user_directed = target.metadata.get("exploration_mode") == "user_directed"
        
        if is_user_directed:
            # 用户指令驱动：深入、多样化、高质量搜索
            return self._build_user_directed_queries(target, strategy, base_keywords)
        else:
            # 系统自主探索：宽泛、发散、探索性搜索
            return self._build_autonomous_queries(target, strategy, base_keywords)
    
    def _build_user_directed_queries(self, target: ExplorationTarget, 
                                   strategy: ExplorationStrategy, 
                                   base_keywords: List[str]) -> List[str]:
        """🎯 构建用户指令驱动的深入、多样化搜索查询"""
        queries = []
        search_depth = target.metadata.get("search_depth", "comprehensive")
        target_type = target.metadata.get("target_type", "primary_focus")
        
        # 获取用户查询原文
        user_query = target.metadata.get("user_query", "")
        core_keywords = base_keywords[:4]  # 使用前4个关键词
        
        if target_type == "primary_focus":
            # 🎯 主要目标：最深入、最全面的搜索
            queries.extend(self._build_comprehensive_queries(core_keywords, strategy, user_query))
            
        elif target_type == "contextual_expansion":
            # 🎯 上下文目标：相关背景和扩展信息
            queries.extend(self._build_contextual_queries(core_keywords, strategy))
            
        elif target_type == "verification_focused":
            # 🎯 验证目标：可行性和风险评估
            queries.extend(self._build_verification_queries(core_keywords, strategy))
        
        return queries
    
    def _build_autonomous_queries(self, target: ExplorationTarget, 
                                strategy: ExplorationStrategy, 
                                base_keywords: List[str]) -> List[str]:
        """🔄 构建系统自主的宽泛、探索性搜索查询"""
        queries = []
        target_type = target.metadata.get("target_type", "general")
        core_keywords = base_keywords[:3]  # 自主探索使用较少关键词
        
        if target_type == "knowledge_gap_filling":
            # 🔄 知识缺口：广泛收集基础信息
            queries.extend(self._build_gap_filling_queries(core_keywords, strategy))
            
        elif target_type == "serendipitous_discovery":
            # 🔄 偶然发现：最大化搜索多样性
            queries.extend(self._build_serendipity_queries(core_keywords, strategy))
            
        elif target_type == "trend_monitoring":
            # 🔄 趋势监控：关注最新发展
            queries.extend(self._build_trend_queries(core_keywords, strategy))
        
        return queries
    
    def _build_comprehensive_queries(self, keywords: List[str], 
                                   strategy: ExplorationStrategy, 
                                   user_query: str) -> List[str]:
        """🎯 构建全面深入的查询 - 用户主要目标"""
        queries = []
        
        # 直接使用用户查询
        if user_query:
            queries.append(user_query)
        
        # 根据策略生成精确查询
        if strategy == ExplorationStrategy.EXPERT_KNOWLEDGE:
            for keyword in keywords[:2]:
                queries.extend([
                    f"{keyword} 专家深度分析",
                    f"{keyword} 权威指南详解",
                    f"{keyword} 专业实践方案",
                    f"{keyword} 行业最佳实践案例"
                ])
        
        elif strategy == ExplorationStrategy.TREND_MONITORING:
            for keyword in keywords[:2]:
                queries.extend([
                    f"{keyword} 2024最新发展趋势",
                    f"{keyword} 未来发展方向预测",
                    f"{keyword} 技术演进路线图",
                    f"{keyword} 创新突破进展"
                ])
        
        elif strategy == ExplorationStrategy.COMPETITIVE_INTELLIGENCE:
            for keyword in keywords[:2]:
                queries.extend([
                    f"{keyword} 竞争对手分析",
                    f"{keyword} 市场格局对比",
                    f"{keyword} 优势劣势评估",
                    f"{keyword} 竞争策略研究"
                ])
        
        else:
            # 默认深度查询
            for keyword in keywords[:3]:
                queries.extend([
                    f"{keyword} 详细说明",
                    f"{keyword} 深入分析",
                    f"{keyword} 完整指南"
                ])
        
        return queries
    
    def _build_contextual_queries(self, keywords: List[str], 
                                strategy: ExplorationStrategy) -> List[str]:
        """🎯 构建上下文相关查询 - 用户扩展目标"""
        queries = []
        
        for keyword in keywords[:2]:
                queries.extend([
                f"{keyword} 相关背景知识",
                f"{keyword} 应用场景案例",
                f"{keyword} 实施前提条件",
                f"{keyword} 相关技术栈"
            ])
        
        return queries
    
    def _build_verification_queries(self, keywords: List[str], 
                                  strategy: ExplorationStrategy) -> List[str]:
        """🎯 构建验证相关查询 - 用户验证目标"""
        queries = []
        
        for keyword in keywords[:2]:
            queries.extend([
                f"{keyword} 可行性评估报告",
                f"{keyword} 技术风险分析",
                f"{keyword} 实施挑战与对策",
                f"{keyword} 成功失败案例对比"
            ])
        
        return queries
    
    def _build_gap_filling_queries(self, keywords: List[str], 
                                 strategy: ExplorationStrategy) -> List[str]:
        """🔄 构建知识缺口查询 - 系统自主学习"""
        queries = []
        
        # 更广泛的探索性查询
        for keyword in keywords[:2]:
            queries.extend([
                f"{keyword} 基础概念",
                f"{keyword} 相关领域",
                f"{keyword} 应用实例"
            ])
        
        return queries
    
    def _build_serendipity_queries(self, keywords: List[str], 
                                 strategy: ExplorationStrategy) -> List[str]:
        """🔄 构建偶然发现查询 - 系统创新探索"""
        queries = []
        
        # 最大化多样性的探索性查询
        for keyword in keywords[:2]:
            queries.extend([
                f"{keyword} 意想不到的应用",
                f"{keyword} 创新突破",
                f"{keyword} 跨界融合",
                f"{keyword} 未来可能性"
            ])
        
        return queries
    
    def _build_trend_queries(self, keywords: List[str], 
                           strategy: ExplorationStrategy) -> List[str]:
        """🔄 构建趋势监控查询 - 系统趋势跟踪"""
        queries = []
        
        # 关注最新发展的查询
        for keyword in keywords[:2]:
            queries.extend([
                f"{keyword} 最新动态",
                f"{keyword} 发展趋势",
                f"{keyword} 新兴方向"
            ])
        
        return queries
    
    def _query_api_sources(self, 
                         target: ExplorationTarget, 
                         strategy: ExplorationStrategy) -> List[Dict[str, Any]]:
        """查询API信息源（预留接口）"""
        # 这里可以集成各种API：
        # - 学术论文API (arXiv, PubMed等)
        # - 新闻API (News API等)
        # - 技术文档API (GitHub, Stack Overflow等)
        # - 专业数据库API
        
        return []  # 当前为空实现
    
    def _query_database_sources(self, 
                              target: ExplorationTarget, 
                              strategy: ExplorationStrategy) -> List[Dict[str, Any]]:
        """查询数据库信息源（预留接口）"""
        # 这里可以集成：
        # - 内部知识库
        # - 行业数据库
        # - 历史探索缓存
        
        return []  # 当前为空实现
    
    def _extract_and_evaluate_knowledge(self, 
                                      raw_information: List[Dict[str, Any]], 
                                      targets: List[ExplorationTarget]) -> List[KnowledgeItem]:
        """知识提取和质量评估"""
        knowledge_items = []
        
        for info in raw_information:
            try:
                # 提取知识内容
                knowledge_item = self._extract_knowledge_from_info(info, targets)
                if knowledge_item:
                    # 评估知识质量
                    self._evaluate_knowledge_quality(knowledge_item)
                    
                    # 质量过滤
                    if self._passes_quality_filter(knowledge_item):
                        knowledge_items.append(knowledge_item)
                        logger.debug(f"✅ 知识提取成功: {knowledge_item.knowledge_id}")
                    else:
                        logger.debug(f"❌ 知识质量不合格: {knowledge_item.knowledge_id}")
            
            except Exception as e:
                logger.debug(f"⚠️ 知识提取失败: {e}")
                continue
        
        logger.info(f"🔍 知识提取完成: {len(knowledge_items)} 项高质量知识")
        return knowledge_items
    
    def _extract_knowledge_from_info(self, 
                                   info: Dict[str, Any], 
                                   targets: List[ExplorationTarget]) -> Optional[KnowledgeItem]:
        """从原始信息中提取知识项"""
        content = info.get("content", "")
        if not content or len(content.strip()) < 10:
            return None
        
        # 生成知识ID
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        knowledge_id = f"knowledge_{content_hash}_{int(time.time())}"
        
        # 创建知识项
        knowledge_item = KnowledgeItem(
            knowledge_id=knowledge_id,
            content=content,
            source=info.get("url", info.get("source", "unknown")),
            source_type=info.get("source", "unknown"),
            quality=KnowledgeQuality.FAIR,  # 初始质量等级
            extraction_method="automatic_extraction",
            tags=self._extract_tags_from_content(content),
            related_concepts=self._extract_concepts_from_content(content, targets)
        )
        
        return knowledge_item
    
    def _evaluate_knowledge_quality(self, knowledge_item: KnowledgeItem):
        """评估知识质量 - 多维度评估体系"""
        
        # 1. 置信度评估（基于来源可信度）
        confidence_score = self._assess_source_credibility(knowledge_item.source_type)
        
        # 2. 相关性评估（基于内容相关度）
        relevance_score = self._assess_content_relevance(knowledge_item.content)
        
        # 3. 新颖性评估（基于内容独特性）
        novelty_score = self._assess_content_novelty(knowledge_item.content)
        
        # 4. 综合质量评估
        overall_score = (confidence_score * 0.4 + 
                        relevance_score * 0.4 + 
                        novelty_score * 0.2)
        
        # 更新知识项评分
        knowledge_item.confidence_score = confidence_score
        knowledge_item.relevance_score = relevance_score
        knowledge_item.novelty_score = novelty_score
        
        # 确定质量等级
        if overall_score >= 0.8:
            knowledge_item.quality = KnowledgeQuality.EXCELLENT
        elif overall_score >= 0.6:
            knowledge_item.quality = KnowledgeQuality.GOOD
        elif overall_score >= 0.4:
            knowledge_item.quality = KnowledgeQuality.FAIR
        elif overall_score >= 0.2:
            knowledge_item.quality = KnowledgeQuality.POOR
        else:
            knowledge_item.quality = KnowledgeQuality.UNRELIABLE
        
        logger.debug(f"📊 质量评估完成: {knowledge_item.knowledge_id} - {knowledge_item.quality.value}")
    
    def _assess_source_credibility(self, source_type: str) -> float:
        """评估信息源可信度"""
        credibility_scores = {
            "web_search": 0.6,
            "academic_paper": 0.9,
            "expert_system": 0.8,
            "database": 0.7,
            "api_call": 0.6,
            "unknown": 0.3
        }
        return credibility_scores.get(source_type, 0.3)
    
    def _assess_content_relevance(self, content: str) -> float:
        """评估内容相关性（简化实现）"""
        # 基于内容长度和关键词密度的简单评估
        content_length = len(content)
        if content_length < 50:
            return 0.3
        elif content_length < 200:
            return 0.5
        elif content_length < 500:
            return 0.7
        else:
            return 0.8
    
    def _assess_content_novelty(self, content: str) -> float:
        """评估内容新颖性"""
        # 检查是否与已有知识重复
        for cached_item in list(self.knowledge_cache.values())[-10:]:  # 检查最近10项
            if self._calculate_content_similarity(content, cached_item.content) > 0.8:
                return 0.2  # 高度相似，新颖性低
        
        return 0.6  # 默认中等新颖性
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """计算内容相似性（简化实现）"""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _passes_quality_filter(self, knowledge_item: KnowledgeItem) -> bool:
        """知识质量过滤器"""
        min_confidence = self.config["quality_control"]["min_confidence_threshold"]
        min_relevance = self.config["quality_control"]["min_relevance_threshold"]
        
        return (knowledge_item.confidence_score >= min_confidence and
                knowledge_item.relevance_score >= min_relevance and
                knowledge_item.quality != KnowledgeQuality.UNRELIABLE)
    
    def _generate_thinking_seeds(self, 
                               knowledge_items: List[KnowledgeItem], 
                               strategy: ExplorationStrategy) -> List[ThinkingSeed]:
        """基于发现的知识生成思维种子"""
        thinking_seeds = []
        max_seeds = self.config["seed_generation"]["max_seeds_per_exploration"]
        
        # 按质量排序知识项
        sorted_knowledge = sorted(knowledge_items, 
                                key=lambda k: (k.confidence_score + k.relevance_score + k.novelty_score) / 3, 
                                reverse=True)
        
        # 为高质量知识生成种子
        for knowledge_item in sorted_knowledge[:max_seeds]:
            seed = self._create_thinking_seed_from_knowledge(knowledge_item, strategy)
            if seed:
                thinking_seeds.append(seed)
        
        # 生成跨知识融合种子
        if len(knowledge_items) >= 2:
            fusion_seeds = self._create_fusion_thinking_seeds(knowledge_items[:3], strategy)
            thinking_seeds.extend(fusion_seeds)
        
        # 限制种子数量
        thinking_seeds = thinking_seeds[:max_seeds]
        
        logger.info(f"🌱 思维种子生成完成: {len(thinking_seeds)} 个")
        return thinking_seeds
    
    def _create_thinking_seed_from_knowledge(self, 
                                           knowledge_item: KnowledgeItem, 
                                           strategy: ExplorationStrategy) -> Optional[ThinkingSeed]:
        """从单个知识项创建思维种子"""
        
        # 基于策略调整种子内容
        if strategy == ExplorationStrategy.TREND_MONITORING:
            seed_content = f"基于趋势监控发现：{knowledge_item.content[:100]}..."
            creativity_level = "medium"
        
        elif strategy == ExplorationStrategy.CROSS_DOMAIN_LEARNING:
            seed_content = f"跨域学习洞察：{knowledge_item.content[:100]}..."
            creativity_level = "high"
        
        elif strategy == ExplorationStrategy.GAP_ANALYSIS:
            seed_content = f"缺口分析发现：{knowledge_item.content[:100]}..."
            creativity_level = "medium"
        
        elif strategy == ExplorationStrategy.EXPERT_KNOWLEDGE:
            seed_content = f"专家知识洞察：{knowledge_item.content[:100]}..."
            creativity_level = "high"
        
        else:
            seed_content = f"探索发现：{knowledge_item.content[:100]}..."
            creativity_level = "medium"
        
        # 生成种子ID
        seed_id = f"seed_{knowledge_item.knowledge_id}_{int(time.time())}"
        
        # 创建思维种子
        thinking_seed = ThinkingSeed(
            seed_id=seed_id,
            seed_content=seed_content,
            source_knowledge=[knowledge_item.knowledge_id],
            creativity_level=creativity_level,
            potential_applications=self._suggest_applications(knowledge_item),
            generated_strategy=strategy.value,
            confidence=min(knowledge_item.confidence_score * 1.1, 1.0),  # 轻微提升
            suggested_reasoning_paths=self._suggest_reasoning_paths(knowledge_item, strategy),
            generation_context={
                "strategy": strategy.value,
                "source_quality": knowledge_item.quality.value,
                "generated_from": "single_knowledge_item"
            }
        )
        
        return thinking_seed
    
    def _create_fusion_thinking_seeds(self, 
                                    knowledge_items: List[KnowledgeItem], 
                                    strategy: ExplorationStrategy) -> List[ThinkingSeed]:
        """创建融合思维种子 - 整合多个知识项的创新种子"""
        fusion_seeds = []
        
        if len(knowledge_items) < 2:
            return fusion_seeds
        
        # 创建知识融合种子
        fusion_content = self._fuse_knowledge_contents(knowledge_items)
        fusion_id = f"fusion_seed_{int(time.time())}"
        
        fusion_seed = ThinkingSeed(
            seed_id=fusion_id,
            seed_content=f"融合洞察：{fusion_content}",
            source_knowledge=[k.knowledge_id for k in knowledge_items],
            creativity_level="high",  # 融合种子通常更有创意
            potential_applications=self._suggest_fusion_applications(knowledge_items),
            generated_strategy=strategy.value,
            confidence=sum(k.confidence_score for k in knowledge_items) / len(knowledge_items),
            cross_domain_connections=self._identify_cross_domain_connections(knowledge_items),
            generation_context={
                "strategy": strategy.value,
                "generated_from": "knowledge_fusion",
                "fusion_count": len(knowledge_items)
            }
        )
        
        fusion_seeds.append(fusion_seed)
        return fusion_seeds
    
    def _fuse_knowledge_contents(self, knowledge_items: List[KnowledgeItem]) -> str:
        """融合多个知识项的内容"""
        contents = [k.content[:50] for k in knowledge_items[:3]]  # 取前50字符
        return "、".join(contents) + " 的综合创新思路"
    
    def _suggest_applications(self, knowledge_item: KnowledgeItem) -> List[str]:
        """建议知识应用领域"""
        base_applications = [
            "问题解决策略",
            "创新思维路径",
            "决策优化方案"
        ]
        
        # 基于知识标签增加特定应用
        specific_applications = []
        for tag in knowledge_item.tags[:2]:
            specific_applications.append(f"{tag}相关应用")
        
        return base_applications + specific_applications
    
    def _suggest_reasoning_paths(self, 
                               knowledge_item: KnowledgeItem, 
                               strategy: ExplorationStrategy) -> List[str]:
        """建议推理路径"""
        base_paths = ["analytical_reasoning", "creative_synthesis"]
        
        strategy_specific_paths = {
            ExplorationStrategy.TREND_MONITORING: ["trend_analysis_path", "predictive_reasoning"],
            ExplorationStrategy.CROSS_DOMAIN_LEARNING: ["analogical_reasoning", "cross_domain_transfer"],
            ExplorationStrategy.GAP_ANALYSIS: ["problem_solving_path", "systematic_analysis"],
            ExplorationStrategy.DOMAIN_EXPANSION: ["exploratory_reasoning", "domain_bridging"],
            ExplorationStrategy.EXPERT_KNOWLEDGE: ["expert_reasoning_path", "professional_methodology"]
        }
        
        specific_paths = strategy_specific_paths.get(strategy, [])
        return base_paths + specific_paths
    
    def _suggest_fusion_applications(self, knowledge_items: List[KnowledgeItem]) -> List[str]:
        """建议融合知识的应用"""
        return [
            "跨领域创新解决方案",
            "综合决策优化策略",
            "多维度问题分析方法",
            "系统性思维升级路径"
        ]
    
    def _identify_cross_domain_connections(self, knowledge_items: List[KnowledgeItem]) -> List[str]:
        """识别跨域连接"""
        connections = []
        domains = set()
        
        # 从标签中提取领域信息
        for item in knowledge_items:
            domains.update(item.tags[:2])  # 取前2个标签作为领域
        
        # 生成跨域连接描述
        domain_list = list(domains)
        for i in range(len(domain_list)):
            for j in range(i+1, len(domain_list)):
                connections.append(f"{domain_list[i]}与{domain_list[j]}的融合创新")
        
        return connections[:3]  # 限制连接数量
    
    def _analyze_trends(self, 
                       knowledge_items: List[KnowledgeItem], 
                       targets: List[ExplorationTarget]) -> List[Dict[str, Any]]:
        """分析识别的趋势"""
        trends = []
        
        # 基于知识内容识别趋势关键词
        trend_keywords = self._extract_trend_keywords(knowledge_items)
        
        for keyword in trend_keywords[:3]:  # 限制趋势数量
            trend = {
                "trend_id": f"trend_{keyword}_{int(time.time())}",
                "trend_name": f"{keyword}相关趋势",
                "confidence": 0.6,
                "supporting_knowledge": [k.knowledge_id for k in knowledge_items 
                                       if keyword.lower() in k.content.lower()],
                "time_horizon": "short_term",
                "impact_prediction": f"{keyword}将在相关领域产生重要影响",
                "identified_at": time.time()
            }
            trends.append(trend)
        
        logger.info(f"📈 趋势分析完成: 识别 {len(trends)} 个趋势")
        return trends
    
    def _extract_trend_keywords(self, knowledge_items: List[KnowledgeItem]) -> List[str]:
        """提取趋势关键词"""
        keyword_frequency = defaultdict(int)
        
        for item in knowledge_items:
            words = item.content.lower().split()
            for word in words:
                if len(word) > 3:  # 过滤短词
                    keyword_frequency[word] += 1
        
        # 返回频次最高的关键词
        sorted_keywords = sorted(keyword_frequency.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_keywords[:5] if freq > 1]
    
    def _discover_cross_domain_insights(self, 
                                      knowledge_items: List[KnowledgeItem], 
                                      thinking_seeds: List[ThinkingSeed]) -> List[Dict[str, Any]]:
        """发现跨域洞察"""
        insights = []
        
        # 基于思维种子的跨域连接
        for seed in thinking_seeds:
            if seed.cross_domain_connections:
                insight = {
                    "insight_id": f"cross_domain_{seed.seed_id}",
                    "insight_type": "cross_domain_connection",
                    "description": f"发现{seed.cross_domain_connections[0]}的创新机会",
                    "supporting_seeds": [seed.seed_id],
                    "potential_impact": "high",
                    "confidence": seed.confidence,
                    "discovered_at": time.time()
                }
                insights.append(insight)
        
        logger.info(f"🔗 跨域洞察发现完成: {len(insights)} 个洞察")
        return insights
    
    
    # ==================== 策略选择与优化 ====================
    
    def _select_optimal_strategy(self, targets: List[ExplorationTarget]) -> ExplorationStrategy:
        """基于目标和历史表现选择最优探索策略"""
        
        # 如果没有历史数据，使用默认策略
        if not self.strategy_performance:
            return self.config["exploration_strategies"]["default_strategy"]
        
        # 基于历史表现选择策略
        best_strategy = None
        best_score = 0.0
        
        for strategy_name, performance in self.strategy_performance.items():
            # 综合评分：成功率 * 0.6 + 平均质量 * 0.4
            score = (performance["success_rate"] * 0.6 + 
                    performance["avg_quality"] * 0.4)
            
            if score > best_score:
                best_score = score
                try:
                    best_strategy = ExplorationStrategy(strategy_name)
                except ValueError:
                    continue
        
        return best_strategy or self.config["exploration_strategies"]["default_strategy"]
    
    def _select_user_directed_strategy(self, targets: List[ExplorationTarget], 
                                     user_context: Dict[str, Any]) -> ExplorationStrategy:
        """🎯 为用户指令驱动模式选择最优策略 - 优先使用语义分析"""
        user_query = user_context.get("user_query", "")
        
        logger.debug(f"🎯 为用户查询选择探索策略: {user_query[:50]}...")
        
        # 🧠 优先尝试使用语义分析器
        if self.semantic_analyzer and user_query:
            try:
                semantic_strategy = self._get_strategy_from_semantic_analysis(user_query, user_context)
                if semantic_strategy:
                    logger.info(f"✅ 语义分析选择策略: {semantic_strategy.value}")
                    return semantic_strategy
            except Exception as e:
                logger.warning(f"⚠️ 语义分析失败，使用默认策略: {e}")
        
        # 🚨 语义分析失败，使用默认策略
        logger.warning("⚠️ 语义分析不可用或失败，使用默认专家知识策略")
        return ExplorationStrategy.EXPERT_KNOWLEDGE
    
    def _get_strategy_from_semantic_analysis(self, user_query: str, user_context: Dict[str, Any]) -> Optional[ExplorationStrategy]:
        """🧠 基于语义分析选择探索策略"""
        if not self.semantic_analyzer:
            return None
            
        try:
            # 执行多维度语义分析
            analysis_tasks = ['intent_detection', 'domain_classification']
            response = self.semantic_analyzer.analyze(user_query, analysis_tasks)
            
            if not response.overall_success:
                logger.warning("⚠️ 语义分析未成功完成")
                return None
            
            # 提取分析结果
            intent_result = response.analysis_results.get('intent_detection')
            domain_result = response.analysis_results.get('domain_classification')
            
            intent = None
            domain = None
            confidence_threshold = 0.7
            
            if intent_result and intent_result.success and intent_result.confidence > confidence_threshold:
                intent = intent_result.result.get('primary_intent')
                
            if domain_result and domain_result.success and domain_result.confidence > confidence_threshold:
                domain = domain_result.result.get('domain')
            
            logger.debug(f"🧠 语义分析结果: intent={intent}, domain={domain}")
            
            # 基于语义分析结果映射策略
            strategy = self._map_semantic_analysis_to_strategy(intent, domain, user_query, user_context)
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ 语义分析过程异常: {e}")
            return None
    
    def _map_semantic_analysis_to_strategy(self, intent: Optional[str], domain: Optional[str], 
                                         user_query: str, user_context: Dict[str, Any]) -> Optional[ExplorationStrategy]:
        """🎯 将语义分析结果映射到探索策略"""
        
        # 基于意图的策略映射
        intent_strategy_mapping = {
            # 解决方案寻求 - 专家知识优先
            'solution_seeking': ExplorationStrategy.EXPERT_KNOWLEDGE,
            'problem_solving': ExplorationStrategy.EXPERT_KNOWLEDGE,
            'how_to_query': ExplorationStrategy.EXPERT_KNOWLEDGE,
            
            # 比较分析 - 竞争情报
            'comparison_analysis': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            'evaluation_request': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            'selection_help': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            
            # 趋势和最新信息
            'trend_monitoring': ExplorationStrategy.TREND_MONITORING,
            'latest_information': ExplorationStrategy.TREND_MONITORING,
            'news_seeking': ExplorationStrategy.TREND_MONITORING,
            
            # 学习和了解
            'learning_request': ExplorationStrategy.DOMAIN_EXPANSION,
            'knowledge_acquisition': ExplorationStrategy.DOMAIN_EXPANSION,
            'understanding_seeking': ExplorationStrategy.DOMAIN_EXPANSION,
            
            # 跨领域整合
            'integration_query': ExplorationStrategy.CROSS_DOMAIN_LEARNING,
            'synthesis_request': ExplorationStrategy.CROSS_DOMAIN_LEARNING,
            
            # 问题诊断
            'problem_diagnosis': ExplorationStrategy.GAP_ANALYSIS,
            'issue_identification': ExplorationStrategy.GAP_ANALYSIS,
        }
        
        # 优先基于意图选择策略
        if intent and intent in intent_strategy_mapping:
            strategy = intent_strategy_mapping[intent]
            logger.debug(f"🎯 基于意图 '{intent}' 选择策略: {strategy.value}")
            return strategy
        
        # 基于领域的策略映射（作为补充）
        domain_strategy_mapping = {
            # 技术领域 - 专家知识和趋势监控
            '技术': ExplorationStrategy.EXPERT_KNOWLEDGE,
            'technology': ExplorationStrategy.EXPERT_KNOWLEDGE,
            'artificial_intelligence': ExplorationStrategy.TREND_MONITORING,
            
            # 商业领域 - 竞争情报和趋势监控  
            '商业': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            'business': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            'marketing': ExplorationStrategy.COMPETITIVE_INTELLIGENCE,
            
            # 学术研究 - 领域扩展和跨域学习
            '学术': ExplorationStrategy.DOMAIN_EXPANSION,
            'academic': ExplorationStrategy.DOMAIN_EXPANSION,
            'research': ExplorationStrategy.CROSS_DOMAIN_LEARNING,
            
            # 创新和创意 - 跨域学习和偶然发现
            '创新': ExplorationStrategy.CROSS_DOMAIN_LEARNING,
            'innovation': ExplorationStrategy.SERENDIPITY_DISCOVERY,
        }
        
        if domain and domain in domain_strategy_mapping:
            strategy = domain_strategy_mapping[domain]
            logger.debug(f"🎯 基于领域 '{domain}' 选择策略: {strategy.value}")
            return strategy
        
        # 基于查询长度和复杂度的启发式策略
        query_length = len(user_query.split())
        if query_length > 10:  # 复杂查询，可能需要专家知识
            logger.debug("🎯 复杂查询，选择专家知识策略")
            return ExplorationStrategy.EXPERT_KNOWLEDGE
        elif query_length < 5:  # 简单查询，领域扩展
            logger.debug("🎯 简单查询，选择领域扩展策略")
            return ExplorationStrategy.DOMAIN_EXPANSION
        
        # 如果都没匹配到，返回默认策略
        logger.debug("🎯 语义分析未匹配到明确策略，使用默认专家知识策略")
        return ExplorationStrategy.EXPERT_KNOWLEDGE
    
    
    def create_exploration_targets_from_context(self, context: Dict[str, Any]) -> List[ExplorationTarget]:
        """🎯 从认知调度器上下文创建探索目标 - 双轨探索增强版"""
        targets = []
        
        # 检测是否为用户指令驱动模式
        is_user_directed = context.get("exploration_mode") == "user_directed"
        
        if is_user_directed:
            # 🎯 用户指令驱动模式 - 精确聚焦，高质量探索
            targets.extend(self._create_user_directed_targets(context))
        else:
            # 🔄 系统自主探索模式 - 宽泛探索，弥补知识缺口
            targets.extend(self._create_autonomous_targets(context))
        
        logger.info(f"🎯 已创建 {len(targets)} 个探索目标 ({'用户指令驱动' if is_user_directed else '系统自主'})")
        
        # 显示目标详情
        for target in targets:
            priority_str = "🔴高优先级" if target.priority == ExplorationPriority.HIGH else "🟡中优先级"
            logger.debug(f"   {priority_str}: {target.description[:60]}...")
        
        return targets
    
    def _create_user_directed_targets(self, context: Dict[str, Any]) -> List[ExplorationTarget]:
        """🎯 创建用户指令驱动的高优先级、精确聚焦的探索目标"""
        targets = []
        user_query = context.get("user_query", "")
        user_context = context.get("user_context", {})
        
        if not user_query:
            logger.warning("⚠️ 用户指令驱动模式但缺少user_query")
            return targets
        
        # 🎯 主要目标：精确聚焦用户查询核心
        core_keywords = self._extract_core_keywords_advanced(user_query)
        query_intent = self._analyze_user_query_intent(user_query)
        
        primary_target = ExplorationTarget(
            target_id=f"user_primary_{int(time.time())}",
            description=f"用户核心查询深度探索: {user_query}",
            keywords=core_keywords,
            priority=ExplorationPriority.HIGH,
            domain=self._identify_query_domain(user_query),
            expected_quality=KnowledgeQuality.HIGH,
            metadata={
                "user_query": user_query,
                "exploration_mode": "user_directed",
                "target_type": "primary_focus",
                "query_intent": query_intent,
                "search_depth": "comprehensive",
                "search_diversity": "high",
                "immediate_priority": True,
                "urgency_level": user_context.get("urgency_level", "high"),
                "expected_depth": user_context.get("expected_depth", "detailed")
            }
        )
        targets.append(primary_target)
        
        # 🎯 扩展目标：相关上下文探索
        if query_intent.get("requires_context", False):
            context_target = ExplorationTarget(
                target_id=f"user_context_{int(time.time())}",
                description=f"用户查询相关上下文探索: {query_intent.get('context_topics', [])}",
                keywords=self._generate_contextual_keywords(user_query, core_keywords),
                priority=ExplorationPriority.MEDIUM,
                domain=self._identify_query_domain(user_query),
                expected_quality=KnowledgeQuality.HIGH,
                metadata={
                    "user_query": user_query,
                    "exploration_mode": "user_directed",
                    "target_type": "contextual_expansion",
                    "search_depth": "moderate",
                    "search_diversity": "medium",
                    "parent_target": primary_target.target_id
                }
            )
            targets.append(context_target)
        
        # 🎯 验证目标：如果查询涉及可行性或决策
        if query_intent.get("requires_verification", False):
            verification_target = ExplorationTarget(
                target_id=f"user_verify_{int(time.time())}",
                description=f"用户查询可行性验证探索: {user_query}",
                keywords=self._generate_verification_keywords(user_query, core_keywords),
                priority=ExplorationPriority.MEDIUM,
                domain=self._identify_query_domain(user_query),
                expected_quality=KnowledgeQuality.HIGH,
                metadata={
                    "user_query": user_query,
                    "exploration_mode": "user_directed",
                    "target_type": "verification_focused",
                    "search_depth": "targeted",
                    "search_diversity": "focused",
                    "verification_aspects": ["feasibility", "risks", "alternatives"]
                }
            )
            targets.append(verification_target)
        
        logger.debug(f"🎯 用户指令目标创建完成: {len(targets)} 个精确聚焦目标")
        return targets
    
    def _create_autonomous_targets(self, context: Dict[str, Any]) -> List[ExplorationTarget]:
        """🔄 创建系统自主的低优先级、宽泛探索目标"""
        targets = []
        exploration_opportunities = context.get("exploration_opportunities", [])
        knowledge_gaps = context.get("current_knowledge_gaps", [])
        
        # 🔄 知识缺口目标：弥补系统认知盲区
        for i, gap in enumerate(knowledge_gaps[:2]):  # 限制数量，避免资源过载
            gap_target = ExplorationTarget(
                target_id=f"autonomous_gap_{int(time.time())}_{i}",
                description=f"知识缺口弥补探索: {gap.get('gap_description', '未知领域')}",
                keywords=gap.get('related_keywords', [])[:8],
                priority=ExplorationPriority.LOW,  # 自主探索使用低优先级
                domain=gap.get('domain', '通用'),
                expected_quality=KnowledgeQuality.MEDIUM,
                metadata={
                    "exploration_mode": "autonomous",
                    "target_type": "knowledge_gap_filling",
                    "search_depth": "broad",
                    "search_diversity": "high",
                    "gap_type": gap.get('gap_type', 'unknown'),
                    "discovery_focus": True
                }
            )
            targets.append(gap_target)
        
        # 🔄 机会探索目标：发现意想不到的知识
        for i, opportunity in enumerate(exploration_opportunities[:2]):
            serendipity_target = ExplorationTarget(
                target_id=f"autonomous_serendipity_{int(time.time())}_{i}",
                description=f"偶然发现探索: {opportunity.get('description', '探索未知')}",
                keywords=opportunity.get('keywords', [])[:6],
                priority=ExplorationPriority.LOW,
                domain=opportunity.get('domain', '通用'),
                expected_quality=KnowledgeQuality.MEDIUM,
                metadata={
                    "exploration_mode": "autonomous",
                    "target_type": "serendipitous_discovery",
                    "search_depth": "exploratory",
                    "search_diversity": "maximum",
                    "opportunity_type": opportunity.get('type', 'general'),
                    "creativity_boost": True
                }
            )
            targets.append(serendipity_target)
        
        # 🔄 趋势监控目标：跟踪领域发展
        if len(targets) < 3:  # 确保至少有趋势监控目标
            trend_target = ExplorationTarget(
                target_id=f"autonomous_trend_{int(time.time())}",
                description="系统自主趋势监控探索",
                keywords=["最新发展", "技术趋势", "创新应用", "未来方向"],
                priority=ExplorationPriority.LOW,
                domain="技术",
                expected_quality=KnowledgeQuality.MEDIUM,
                metadata={
                    "exploration_mode": "autonomous",
                    "target_type": "trend_monitoring",
                    "search_depth": "surface",
                    "search_diversity": "wide",
                    "temporal_focus": "recent",
                    "future_oriented": True
                }
            )
            targets.append(trend_target)
        
        logger.debug(f"🔄 自主探索目标创建完成: {len(targets)} 个宽泛探索目标")
        return targets
    
    
    def _identify_query_domain(self, user_query: str) -> str:
        """🧠 智能识别用户查询的领域 - 优先使用语义分析，回退到关键词匹配"""
        
        # 🧠 优先尝试语义分析
        if self.semantic_analyzer and user_query:
            try:
                response = self.semantic_analyzer.analyze(user_query, ['domain_classification'])
                
                if response.overall_success:
                    domain_result = response.analysis_results.get('domain_classification')
                    
                    if domain_result and domain_result.success and domain_result.confidence > 0.7:
                        semantic_domain = domain_result.result.get('domain', '').lower()
                        
                        # 映射语义分析结果到我们的领域分类
                        domain_mapping = {
                            'technology': '技术',
                            'technical': '技术',
                            'programming': '技术',
                            'business': '商业',
                            'commercial': '商业',
                            'marketing': '商业',
                            'academic': '学术',
                            'research': '学术',
                            'scientific': '学术',
                            'health': '健康',
                            'medical': '健康',
                            'healthcare': '健康',
                            'education': '教育',
                            'educational': '教育',
                            'learning': '教育',
                        }
                        
                        if semantic_domain in domain_mapping:
                            mapped_domain = domain_mapping[semantic_domain]
                            logger.debug(f"🧠 语义分析识别领域: {semantic_domain} → {mapped_domain}")
                            return mapped_domain
                
            except Exception as e:
                logger.warning(f"⚠️ 领域识别语义分析失败: {e}")
        
        # 🚨 语义分析失败，使用默认领域
        logger.warning("⚠️ 语义分析不可用或失败，使用默认通用领域")
        return "通用"
    
    
    def _extract_core_keywords_advanced(self, user_query: str) -> List[str]:
        """🎯 高级关键词提取 - 针对用户查询优化"""
        import re
        
        # 专业术语权重提升
        technical_terms = ['API', 'api', '算法', '架构', '系统', '框架', '模型', '优化', '机器学习', 'AI', 
                          '人工智能', '深度学习', '数据分析', '云计算', '微服务', '容器', '分布式']
        
        # 提取所有词汇
        words = re.findall(r'\b\w+\b', user_query)
        
        # 按重要性分类
        high_priority_keywords = []
        medium_priority_keywords = []
        
        for word in words:
            if len(word) > 2:
                # 专业术语优先级最高
                if any(term.lower() == word.lower() for term in technical_terms):
                    high_priority_keywords.append(word)
                # 长词汇通常更具体
                elif len(word) > 5:
                    high_priority_keywords.append(word)
                # 其他有效词汇
                elif word.lower() not in {'的', '是', '在', '有', '和', '与', '或', '但', '如何', '什么', '哪里', '为什么', 
                                        'the', 'is', 'in', 'and', 'or', 'but', 'how', 'what', 'where', 'why', 'when'}:
                    medium_priority_keywords.append(word)
        
        # 组合并去重，优先级高的在前
        core_keywords = list(dict.fromkeys(high_priority_keywords + medium_priority_keywords))
        return core_keywords[:12]  # 返回前12个核心关键词
    
    def _analyze_user_query_intent(self, user_query: str) -> Dict[str, Any]:
        """🎯 分析用户查询意图 - 指导探索策略"""
        query_lower = user_query.lower()
        intent = {
            "primary_intent": "information_seeking",
            "requires_context": False,
            "requires_verification": False,
            "complexity_level": "medium",
            "temporal_focus": "current",
            "context_topics": [],
            "verification_aspects": []
        }
        
        # 意图分类
        if any(word in query_lower for word in ['如何', '怎么', '方法', 'how', 'method', '实现']):
            intent["primary_intent"] = "solution_seeking"
            intent["requires_context"] = True
            intent["context_topics"] = ["最佳实践", "实现方法", "案例研究"]
            
        elif any(word in query_lower for word in ['比较', '对比', '选择', '哪个好', 'compare', 'vs', 'versus']):
            intent["primary_intent"] = "comparison_analysis"
            intent["requires_verification"] = True
            intent["verification_aspects"] = ["优劣对比", "适用场景", "性能差异"]
            
        elif any(word in query_lower for word in ['可行', '可行性', '能否', '是否可能', 'feasible', 'possible']):
            intent["primary_intent"] = "feasibility_assessment"
            intent["requires_verification"] = True
            intent["verification_aspects"] = ["技术可行性", "实施难度", "风险评估"]
            
        elif any(word in query_lower for word in ['最新', '趋势', '发展', '动态', 'latest', 'trend', 'recent']):
            intent["primary_intent"] = "trend_monitoring"
            intent["temporal_focus"] = "recent"
            intent["requires_context"] = True
            intent["context_topics"] = ["发展趋势", "未来方向", "技术演进"]
        
        # 复杂度评估
        if len(user_query) > 50 or len(user_query.split()) > 10:
            intent["complexity_level"] = "high"
        elif len(user_query) < 20 or len(user_query.split()) < 5:
            intent["complexity_level"] = "low"
            
        return intent
    
    def _generate_contextual_keywords(self, user_query: str, core_keywords: List[str]) -> List[str]:
        """🎯 生成上下文相关关键词"""
        contextual_keywords = core_keywords.copy()
        
        # 基于查询内容添加上下文词汇
        query_lower = user_query.lower()
        
        if any(tech in query_lower for tech in ['api', '系统', '架构', '技术']):
            contextual_keywords.extend(["技术背景", "实现原理", "应用场景"])
            
        elif any(biz in query_lower for biz in ['商业', '市场', '业务', '营销']):
            contextual_keywords.extend(["商业模式", "市场分析", "竞争格局"])
            
        elif any(academic in query_lower for academic in ['研究', '学术', '理论', '方法论']):
            contextual_keywords.extend(["研究现状", "理论基础", "方法论"])
        
        return list(dict.fromkeys(contextual_keywords))[:10]
    
    def _generate_verification_keywords(self, user_query: str, core_keywords: List[str]) -> List[str]:
        """🎯 生成验证相关关键词"""
        verification_keywords = core_keywords.copy()
        
        # 添加验证导向的关键词
        verification_keywords.extend([
            "可行性分析", "技术评估", "风险评价", "实施难度", 
            "成功案例", "失败教训", "挑战与障碍", "解决方案"
        ])
        
        # 基于查询类型添加特定验证词汇
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in ['技术', '系统', 'api', '架构']):
            verification_keywords.extend(["技术风险", "性能瓶颈", "扩展性", "维护成本"])
            
        elif any(word in query_lower for word in ['商业', '项目', '投资']):
            verification_keywords.extend(["投资回报", "市场风险", "竞争威胁", "盈利能力"])
        
        return list(dict.fromkeys(verification_keywords))[:12]
    
    def _calculate_success_rate(self, result: ExplorationResult) -> float:
        """计算探索成功率"""
        if not result.targets:
            return 0.0
        
        successful_targets = 0
        for target in result.targets:
            # 如果目标产生了知识或种子，视为成功
            target_knowledge = [k for k in result.discovered_knowledge 
                              if target.target_id in k.related_concepts]
            target_seeds = [s for s in result.generated_seeds 
                          if any(target.target_id in s.generation_context.get("related_targets", []))]
            
            if target_knowledge or target_seeds:
                successful_targets += 1
        
        return successful_targets / len(result.targets)
    
    def _calculate_quality_score(self, result: ExplorationResult) -> float:
        """计算整体质量评分"""
        if not result.discovered_knowledge:
            return 0.0
        
        total_score = 0.0
        for knowledge in result.discovered_knowledge:
            knowledge_score = (knowledge.confidence_score + 
                             knowledge.relevance_score + 
                             knowledge.novelty_score) / 3
            total_score += knowledge_score
        
        return total_score / len(result.discovered_knowledge)
    
    def _update_caches_and_stats(self, result: ExplorationResult):
        """更新缓存和统计信息"""
        # 更新探索历史
        self.exploration_history.append(result)
        
        # 更新知识缓存
        for knowledge in result.discovered_knowledge:
            self.knowledge_cache[knowledge.knowledge_id] = knowledge
        
        # 更新种子缓存
        for seed in result.generated_seeds:
            self.seed_cache[seed.seed_id] = seed
        
        # 更新策略性能
        strategy_name = result.strategy.value
        self.strategy_performance[strategy_name]["success_rate"] = (
            (self.strategy_performance[strategy_name]["success_rate"] + result.success_rate) / 2
        )
        self.strategy_performance[strategy_name]["avg_quality"] = (
            (self.strategy_performance[strategy_name]["avg_quality"] + result.quality_score) / 2
        )
        self.strategy_performance[strategy_name]["total_seeds"] += len(result.generated_seeds)
        
        # 更新全局统计
        self.stats["total_explorations"] += 1
        if result.success_rate > 0.5:
            self.stats["successful_explorations"] += 1
        self.stats["total_knowledge_discovered"] += len(result.discovered_knowledge)
        self.stats["total_seeds_generated"] += len(result.generated_seeds)
        
        # 更新平均值
        total_explorations = self.stats["total_explorations"]
        self.stats["average_quality_score"] = (
            (self.stats["average_quality_score"] * (total_explorations - 1) + result.quality_score) / 
            total_explorations
        )
        self.stats["average_execution_time"] = (
            (self.stats["average_execution_time"] * (total_explorations - 1) + result.execution_time) / 
            total_explorations
        )
        
        # 清理过期缓存
        self._cleanup_caches()
    
    def _cleanup_caches(self):
        """清理过期缓存"""
        max_history = 100
        max_knowledge_cache = 500
        max_seed_cache = 300
        
        # 清理探索历史
        if len(self.exploration_history) > max_history:
            self.exploration_history = self.exploration_history[-max_history//2:]
        
        # 清理知识缓存（保留最新的）
        if len(self.knowledge_cache) > max_knowledge_cache:
            sorted_knowledge = sorted(
                self.knowledge_cache.items(),
                key=lambda x: x[1].discovered_at,
                reverse=True
            )
            self.knowledge_cache = dict(sorted_knowledge[:max_knowledge_cache//2])
        
        # 清理种子缓存（保留最新的）
        if len(self.seed_cache) > max_seed_cache:
            sorted_seeds = sorted(
                self.seed_cache.items(),
                key=lambda x: x[1].generated_at,
                reverse=True
            )
            self.seed_cache = dict(sorted_seeds[:max_seed_cache//2])
    
    # ==================== 公共接口方法 ====================
    
    def create_exploration_targets_from_context(self, 
                                              context: Dict[str, Any]) -> List[ExplorationTarget]:
        """基于上下文创建探索目标"""
        targets = []
        
        # 从上下文提取关键信息
        session_insights = context.get("session_insights", {})
        knowledge_gaps = context.get("current_knowledge_gaps", [])
        
        # 基于知识缺口创建目标
        for gap in knowledge_gaps[:3]:  # 限制目标数量
            target = ExplorationTarget(
                target_id=f"gap_target_{gap.get('gap_id', 'unknown')}",
                target_type="knowledge_gap",
                description=gap.get("description", "知识缺口探索"),
                keywords=gap.get("keywords", [gap.get("area", "")]),
                priority=gap.get("exploration_priority", 0.5)
            )
            targets.append(target)
        
        # 如果没有明确的缺口，创建通用探索目标
        if not targets:
            general_target = ExplorationTarget(
                target_id=f"general_target_{int(time.time())}",
                target_type="general_exploration",
                description="通用知识探索",
                keywords=["技术趋势", "创新方法", "最佳实践"],
                priority=0.6
            )
            targets.append(general_target)
        
        return targets
    
    def get_exploration_stats(self) -> Dict[str, Any]:
        """获取探索统计信息"""
        return {
            **self.stats,
            "strategy_performance": dict(self.strategy_performance),
            "cache_status": {
                "knowledge_cache_size": len(self.knowledge_cache),
                "seed_cache_size": len(self.seed_cache),
                "exploration_history_size": len(self.exploration_history)
            },
            "recent_explorations": len([r for r in self.exploration_history 
                                      if time.time() - r.timestamp < 3600])  # 最近1小时
        }
    
    def _merge_config(self, base_config: Dict, user_config: Dict):
        """递归合并配置"""
        for key, value in user_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
