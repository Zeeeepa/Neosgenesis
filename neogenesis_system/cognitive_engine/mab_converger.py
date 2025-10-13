#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
上下文多臂老虎机收敛器 (Contextual MAB Converger)
Contextual Multi-Armed Bandit Converger for intelligent strategy selection

核心升级：
1. 从传统MAB升级为上下文Bandit (LinUCB, Contextual Thompson Sampling)
2. 集成可验证推理系统 (Claim → Evidence → ActionContract)
3. 基于任务上下文特征的智能策略选择
4. 持久化学习参数存储和工具健康监控
5. 可验证的成功信号定义和预算管理
"""

import time
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass

from .data_structures import EnhancedDecisionArm, ReasoningPath
from .contextual_bandit import (
    ContextualBanditManager, ContextFeatures, ActionOutcome, SuccessMetric
)
from .verified_reasoning import (
    VerifiedReasoningEngine, ClaimType, EvidenceType, ContractStatus
)
from .semantic_analyzer import SemanticAnalyzer, AnalysisTaskType

try:
    from neogenesis_system.config import MAB_CONFIG
except ImportError:
    try:
        from ..config import MAB_CONFIG
    except ImportError:
        MAB_CONFIG = {
            "convergence_threshold": 0.05,
            "min_samples": 10,
            "cold_start_threshold": {
                "min_usage_count": 5,
                "min_reliability_score": 0.6,
                "max_idle_hours": 24,
                "min_sample_size": 10,
                "exploration_trigger_threshold": 0.7,
                "detection_weights": {
                    "usage_frequency": 0.3,
                    "reliability": 0.3,
                    "recency": 0.2,
                    "sample_sufficiency": 0.2
                }
            }
        }

logger = logging.getLogger(__name__)


class ContextualMABConverger:
    """上下文多臂老虎机收敛器 - 升级版思维路径选择器"""
    
    def __init__(self, tool_registry=None, algorithm: str = "linucb", 
                 storage_path: str = "contextual_bandit.db",
                 global_budget: Dict[str, float] = None):
        """
        初始化上下文MAB收敛器
        
        Args:
            tool_registry: 工具注册表
            algorithm: 使用的算法 ("linucb" 或 "thompson")
            storage_path: 持久化存储路径
            global_budget: 全局预算配置
        """
        # 🎯 上下文Bandit系统
        self.contextual_bandit = ContextualBanditManager(
            feature_dim=8,
            algorithm=algorithm,
            storage_path=storage_path
        )
        
        # 🔬 可验证推理引擎
        self.reasoning_engine = VerifiedReasoningEngine(
            tool_registry=tool_registry,
            global_budget=global_budget
        )
        
        # 🧠 语义分析器
        self.semantic_analyzer = SemanticAnalyzer()
        logger.info("🧠 语义分析器已初始化")
        
        # 🏆 保留黄金模板系统（升级版）
        self.golden_templates: Dict[str, Dict[str, Any]] = {}
        self.golden_template_config = {
            'success_rate_threshold': 0.90,
            'min_samples_required': 20,
            'confidence_threshold': 0.95,
            'max_golden_templates': 50
        }
        self.template_usage_stats = defaultdict(int)
        
        # 📊 性能统计
        self.selection_history = []
        self.total_selections = 0
        self.context_feature_stats = defaultdict(list)
        
        # 🎭 试炼场系统（保持兼容性）
        self.trial_ground = {
            "learned_paths": {},
            "exploration_boost_active": {},
            "culling_candidates": set(),
            "promotion_candidates": set(),
            "performance_watch_list": {},
            "trial_history": [],
            "culled_paths": []
        }
        
        self.trial_config = {
            "exploration_boost_rounds": 10,
            "learned_path_bonus": 0.2,
            "culling_threshold": 0.3,
            "culling_min_samples": 15,
            "max_culled_history": 100
        }
        
        logger.info("🎭 [试炼场] 试炼场系统已初始化")
        logger.info(f"🎭 [试炼场] 配置: 探索增强{self.trial_config['exploration_boost_rounds']}轮, 学习路径奖励{self.trial_config['learned_path_bonus']:.1%}")
        
        # 🏆 黄金模板系统（保持兼容性）
        self.template_match_history = []
        
        # 📊 反馈来源追踪
        self.feedback_source_tracking = defaultdict(lambda: {
            "count": 0,
            "success_rate": 0.0,
            "avg_reward": 0.0
        })
        
        self.source_weight_config = {
            "user_feedback": 1.0,
            "retrospection": 1.2,
            "auto_evaluation": 0.8,
            "tool_verification": 1.1,
            "contextual_bandit": 1.0
        }
        
        # 🔧 传统MAB兼容性
        self.path_arms = {}  # 路径决策臂
        self.tool_arms = {}  # 工具决策臂
        self.path_selection_history = []
        self.total_path_selections = 0
        self.tool_selection_history = []
        self.total_tool_selections = 0
        self.algorithm_performance = defaultdict(lambda: {'successes': 0, 'total': 0})
        self.tool_algorithm_performance = defaultdict(lambda: {'successes': 0, 'total': 0})
        
        # 🔧 工具健康监控
        self.tool_health_cache = {}
        self.health_check_interval = 300  # 5分钟
        
        # 配置参数
        self.convergence_threshold = MAB_CONFIG.get("convergence_threshold", 0.05)
        self.min_samples = MAB_CONFIG.get("min_samples", 10)
        
        logger.info("🎯 ContextualMABConverger 已初始化")
        logger.info(f"   算法: {algorithm}")
        logger.info(f"   存储路径: {storage_path}")
        logger.info("🔬 可验证推理引擎已启用")
        logger.info("🏆 黄金模板系统已升级")
    
    def extract_context_features(self, user_query: str, execution_context: Optional[Dict] = None,
                                available_tools: List[str] = None) -> ContextFeatures:
        """
        🎯 提取上下文特征向量
        
        构造上下文特征向量 x：
        - 任务签名（意图、领域、复杂度）
        - 工具可达性（健康检查/延迟/速率限制）
        - 输入统计（长度、结构）
        - 历史绩效（该意图下某工具/策略的成功率）
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            available_tools: 可用工具列表
            
        Returns:
            上下文特征对象
        """
        # 1. 任务签名特征
        task_features = self._extract_task_signature(user_query)
        
        # 2. 工具可达性特征
        tool_features = self._extract_tool_availability(available_tools or [])
        
        # 3. 输入统计特征
        input_features = self._extract_input_statistics(user_query, execution_context)
        
        # 4. 历史绩效特征
        history_features = self._extract_historical_performance(user_query, execution_context)
        
        # 5. 环境特征
        env_features = self._extract_environment_features(execution_context)
        
        # 构造完整的上下文特征向量
        context_features = ContextFeatures(
            task_intent=task_features['intent'],
            task_domain=task_features['domain'],
            task_complexity=task_features['complexity'],
            input_length=input_features['length'],
            input_structure_score=input_features['structure'],  # 修复参数名
            # 工具特征映射到正确的字段
            tool_health_scores={tool: tool_features['health_score'] for tool in (available_tools or [])},
            # 历史特征映射到正确的字段
            historical_success_rates={path: history_features['success_rate'] for path in ['default']},
            # 环境特征映射到正确的字段
            network_quality=min(1.0, max(0.0, 1.0 - env_features['network_latency'] / 1000.0)),  # 转换延迟为质量分数
            system_load=env_features['resource_usage'],
            time_budget=env_features.get('time_pressure', 30.0)
        )
        
        logger.debug(f"🎯 提取上下文特征: {context_features}")
        return context_features
    
    def _extract_task_signature(self, user_query: str) -> Dict[str, Any]:
        """
        基于LLM的智能任务签名提取
        
        使用语义分析器进行深度理解，替代简单的关键词匹配
        """
        try:
            # 这里使用语义分析器进行多维度分析
            analysis_tasks = ['intent_detection', 'domain_classification', 'complexity_assessment']
            semantic_response = self.semantic_analyzer.analyze(user_query, analysis_tasks)
            
            # 提取分析结果
            intent = 'general'
            domain = 'general'
            complexity = 0.5
            
            if semantic_response.overall_success:
                # 这里是意图识别结果
                intent_result = semantic_response.analysis_results.get('intent_detection')
                if intent_result and intent_result.success and intent_result.confidence > 0.6:
                    primary_intent = intent_result.result.get('primary_intent', '')
                    intent = self._map_semantic_intent_to_category(primary_intent)
                    logger.debug(f"🧠 语义意图识别: {primary_intent} -> {intent} (置信度: {intent_result.confidence:.3f})")
                
                # 这里是领域分类结果
                domain_result = semantic_response.analysis_results.get('domain_classification')
                if domain_result and domain_result.success and domain_result.confidence > 0.6:
                    primary_domain = domain_result.result.get('primary_domain', '')
                    domain = self._map_semantic_domain_to_category(primary_domain)
                    logger.debug(f"🧠 语义领域分类: {primary_domain} -> {domain} (置信度: {domain_result.confidence:.3f})")
                
                # 这里是复杂度评估结果
                complexity_result = semantic_response.analysis_results.get('complexity_assessment')
                if complexity_result and complexity_result.success and complexity_result.confidence > 0.6:
                    complexity_score = complexity_result.result.get('complexity_score', 0.5)
                    complexity = float(complexity_score)
                    logger.debug(f"🧠 语义复杂度评估: {complexity:.3f} (置信度: {complexity_result.confidence:.3f})")
                
                logger.info(f"🧠 语义分析成功: 意图={intent}, 领域={domain}, 复杂度={complexity:.3f}")
            else:
                logger.warning("⚠️ 语义分析未完全成功，使用回退方案")
                # 回退到简化的关键词匹配
                intent, domain, complexity = self._fallback_keyword_analysis(user_query)
                
        except Exception as e:
            logger.error(f"❌ 语义分析异常: {e}")
            # 异常情况下使用回退方案
            intent, domain, complexity = self._fallback_keyword_analysis(user_query)
        
        return {
            'intent': intent,
            'domain': domain,
            'complexity': complexity
        }
    
    def _map_semantic_intent_to_category(self, semantic_intent: str) -> str:
        """将语义分析的意图映射到标准类别"""
        intent_mapping = {
            # 搜索相关
            '信息查询': 'search',
            '搜索': 'search',
            '查找': 'search',
            '寻找': 'search',
            'information_seeking': 'search',
            'search': 'search',
            
            # 分析相关
            '分析': 'analysis',
            '研究': 'analysis',
            '解析': 'analysis',
            '评估': 'analysis',
            'analysis': 'analysis',
            'research': 'analysis',
            
            # 创建相关
            '创建': 'creation',
            '生成': 'creation',
            '制作': 'creation',
            '设计': 'creation',
            'creation': 'creation',
            'generation': 'creation',
            
            # 修改相关
            '修改': 'modification',
            '更新': 'modification',
            '编辑': 'modification',
            '改进': 'modification',
            'modification': 'modification',
            'update': 'modification',
            
            # 解释相关
            '解释': 'explanation',
            '说明': 'explanation',
            '阐述': 'explanation',
            '教学': 'explanation',
            'explanation': 'explanation',
            'clarification': 'explanation'
        }
        
        # 模糊匹配
        semantic_lower = semantic_intent.lower()
        for key, category in intent_mapping.items():
            if key.lower() in semantic_lower or semantic_lower in key.lower():
                return category
        
        return 'general'
    
    def _map_semantic_domain_to_category(self, semantic_domain: str) -> str:
        """将语义分析的领域映射到标准类别"""
        domain_mapping = {
            # 技术相关
            '技术': 'technical',
            '编程': 'technical',
            '开发': 'technical',
            '计算机': 'technical',
            '软件': 'technical',
            'programming': 'technical',
            'technology': 'technical',
            'software': 'technical',
            'ai': 'technical',
            
            # 商业相关
            '商业': 'business',
            '业务': 'business',
            '管理': 'business',
            '营销': 'business',
            '金融': 'business',
            'business': 'business',
            'management': 'business',
            'marketing': 'business',
            'finance': 'business',
            
            # 学术相关
            '学术': 'academic',
            '研究': 'academic',
            '科学': 'academic',
            '理论': 'academic',
            'academic': 'academic',
            'research': 'academic',
            'science': 'academic',
            
            # 创意相关
            '创意': 'creative',
            '设计': 'creative',
            '艺术': 'creative',
            '写作': 'creative',
            'creative': 'creative',
            'design': 'creative',
            'art': 'creative',
            'writing': 'creative'
        }
        
        # 模糊匹配
        domain_lower = semantic_domain.lower()
        for key, category in domain_mapping.items():
            if key.lower() in domain_lower or domain_lower in key.lower():
                return category
        
        return 'general'
    
    def _fallback_keyword_analysis(self, user_query: str) -> Tuple[str, str, float]:
        """回退的关键词分析方法"""
        logger.debug("🔄 使用回退关键词分析")
        
        query_lower = user_query.lower()
        
        # 简化的意图识别
        if any(word in query_lower for word in ['搜索', '查找', '寻找', 'search', 'find']):
            intent = 'search'
        elif any(word in query_lower for word in ['分析', '研究', 'analyze', 'study']):
            intent = 'analysis'
        elif any(word in query_lower for word in ['创建', '生成', 'create', 'generate']):
            intent = 'creation'
        elif any(word in query_lower for word in ['修改', '更新', 'modify', 'update']):
            intent = 'modification'
        elif any(word in query_lower for word in ['解释', '说明', 'explain', 'describe']):
            intent = 'explanation'
        else:
            intent = 'general'
        
        # 简化的领域识别
        if any(word in query_lower for word in ['代码', '编程', 'code', 'programming']):
            domain = 'technical'
        elif any(word in query_lower for word in ['业务', '商业', 'business']):
            domain = 'business'
        elif any(word in query_lower for word in ['学术', '研究', 'academic', 'research']):
            domain = 'academic'
        elif any(word in query_lower for word in ['创意', '设计', 'creative', 'design']):
            domain = 'creative'
        else:
            domain = 'general'
        
        # 简化的复杂度评估
        complexity_factors = [
            len(user_query) > 200,
            '?' in user_query and user_query.count('?') > 1,
            any(word in query_lower for word in ['复杂', '详细', 'complex', 'detailed']),
            any(word in query_lower for word in ['步骤', '流程', 'steps', 'process'])
        ]
        complexity = sum(complexity_factors) / len(complexity_factors)
        
        return intent, domain, complexity
    
    def _extract_tool_availability(self, available_tools: List[str]) -> Dict[str, float]:
        """提取工具可达性特征"""
        if not available_tools:
            return {'availability_score': 0.0, 'health_score': 0.0}
        
        # 检查工具健康状态
        healthy_tools = 0
        total_health_score = 0.0
        
        for tool in available_tools:
            health_status = self._check_tool_health(tool)
            if health_status['is_healthy']:
                healthy_tools += 1
            total_health_score += health_status['health_score']
        
        availability_score = len(available_tools) / 10.0  # 假设10个工具为满分
        health_score = total_health_score / len(available_tools) if available_tools else 0.0
        
        return {
            'availability_score': min(availability_score, 1.0),
            'health_score': health_score
        }
    
    def _check_tool_health(self, tool_name: str) -> Dict[str, Any]:
        """检查工具健康状态"""
        current_time = time.time()
        
        # 从缓存中获取健康状态
        if tool_name in self.tool_health_cache:
            cached_data = self.tool_health_cache[tool_name]
            if current_time - cached_data['timestamp'] < self.health_check_interval:
                return cached_data['status']
        
        # 执行健康检查
        health_status = {
            'is_healthy': True,
            'health_score': 1.0,
            'latency': 0.0,
            'error_rate': 0.0
        }
        
        # 基于工具使用历史评估健康状态
        if tool_name in self.tool_arms:
            arm = self.tool_arms[tool_name]
            if arm.activation_count > 0:
                health_status['health_score'] = arm.success_rate
                health_status['is_healthy'] = arm.success_rate > 0.5
                
                # 基于最近失败率调整
                if arm.recent_results:
                    recent_failures = sum(1 for r in arm.recent_results[-10:] if not r)
                    health_status['error_rate'] = recent_failures / min(len(arm.recent_results), 10)
        
        # 缓存结果
        self.tool_health_cache[tool_name] = {
            'timestamp': current_time,
            'status': health_status
        }
        
        return health_status
    
    def _extract_input_statistics(self, user_query: str, execution_context: Optional[Dict]) -> Dict[str, Any]:
        """提取输入统计特征"""
        # 查询长度特征
        length_score = min(len(user_query) / 500.0, 1.0)  # 500字符为满分
        
        # 结构复杂度
        structure_factors = [
            user_query.count('\n') > 0,  # 多行
            user_query.count('.') > 2,   # 多句
            user_query.count(',') > 3,   # 复杂句式
            bool(execution_context and len(execution_context) > 3)  # 丰富上下文
        ]
        
        structure_score = sum(structure_factors) / len(structure_factors)
        
        return {
            'length': length_score,
            'structure': structure_score
        }
    
    def _extract_historical_performance(self, user_query: str, execution_context: Optional[Dict]) -> Dict[str, float]:
        """提取历史绩效特征"""
        # 基于查询相似性计算历史成功率
        if not self.path_arms:
            return {'success_rate': 0.5}  # 默认中等成功率
        
        # 简单的相似性匹配
        query_words = set(user_query.lower().split())
        similar_paths = []
        
        for path_id, arm in self.path_arms.items():
            # 基于路径类型匹配
            path_words = set(arm.option.lower().split())
            similarity = len(query_words.intersection(path_words)) / len(query_words.union(path_words)) if query_words.union(path_words) else 0
            
            if similarity > 0.1:  # 有一定相似性
                similar_paths.append((similarity, arm.success_rate))
        
        if similar_paths:
            # 加权平均成功率
            weighted_success = sum(sim * rate for sim, rate in similar_paths)
            total_weight = sum(sim for sim, _ in similar_paths)
            return {'success_rate': weighted_success / total_weight}
        
        return {'success_rate': 0.5}
    
    def _extract_environment_features(self, execution_context: Optional[Dict]) -> Dict[str, float]:
        """提取环境特征"""
        if not execution_context:
            return {
                'network_latency': 0.5,
                'resource_usage': 0.5,
                'time_pressure': 0.5
            }
        
        # 从执行上下文中提取环境信息
        network_latency = execution_context.get('network_latency', 0.5)
        resource_usage = execution_context.get('resource_usage', 0.5)
        time_pressure = execution_context.get('time_pressure', 0.5)
        
        return {
            'network_latency': network_latency,
            'resource_usage': resource_usage,
            'time_pressure': time_pressure
        }

    def _create_strategy_arm_if_missing(self, strategy_id: str, path_type: str = None, 
                                       path_source: str = "unknown", reasoning_path: 'ReasoningPath' = None) -> EnhancedDecisionArm:
        if strategy_id not in self.path_arms:
            if path_type is None:
                # 自动推断路径类型
                path_type = self._infer_path_type_from_strategy_id(strategy_id)
            
            # 🎯 根据路径来源推断类型和初始化参数
            detected_source = self._detect_path_source(strategy_id, path_type, reasoning_path)
            effective_source = path_source if path_source != "unknown" else detected_source
            
            # 创建决策臂
            new_arm = EnhancedDecisionArm(
                path_id=strategy_id,
                option=path_type
            )
            
            # 🌱 新思想特殊初始化：为学习路径提供探索优势
            if effective_source == "learned_exploration":
                # 学习路径获得初始探索奖励
                new_arm.success_count = 1  # 给予初始正向信号
                new_arm.total_reward = 0.3  # 给予适中的初始奖励
                new_arm.rl_reward_history = [0.3]  # 记录初始奖励
                
                # 标记为新学习路径
                self._mark_as_learned_path(strategy_id, reasoning_path)
                
                logger.info(f"🌱 新学习路径进入试炼场: {strategy_id} ({path_type})")
                logger.info(f"   获得探索增强: 初始成功信号 + 0.3奖励")
                
            elif effective_source == "manual_addition":
                # 手动添加的路径获得中等探索优势
                new_arm.success_count = 1
                new_arm.total_reward = 0.2
                new_arm.rl_reward_history = [0.2]
                
                logger.info(f"➕ 手动路径进入试炼场: {strategy_id} ({path_type})")
                
            else:
                # 静态模板或未知来源保持默认初始化
                logger.info(f"🆕 [MAB] 创建策略决策臂: {strategy_id} ({path_type}) [来源: {effective_source}]")
                if effective_source in ["static_template", "unknown"]:
                    logger.info(f"ℹ️  [试炼场] 静态模板路径不进入探索增强期，直接参与正常竞争")
            
            self.path_arms[strategy_id] = new_arm
            
            # 记录到试炼场历史（所有路径都会记录）
            self._record_trial_entry(strategy_id, path_type, effective_source)
        
        return self.path_arms[strategy_id]
    
    def contextual_select_best_path(self, paths: List[ReasoningPath], user_query: str, 
                                   execution_context: Optional[Dict] = None,
                                   available_tools: List[str] = None) -> ReasoningPath:
        """
        🎯 上下文Bandit路径选择 - 核心升级方法
        
        使用上下文特征进行智能路径选择，支持LinUCB和Contextual Thompson Sampling
        
        Args:
            paths: 候选思维路径列表
            user_query: 用户查询
            execution_context: 执行上下文
            available_tools: 可用工具列表
            
        Returns:
            选择的最优思维路径
        """
        if not paths:
            raise ValueError("路径列表不能为空")
        
        if len(paths) == 1:
            logger.info(f"🎯 只有一个路径，直接选择: {paths[0].path_type}")
            return paths[0]
        
        # 🎯 提取上下文特征
        context_features = self.extract_context_features(user_query, execution_context, available_tools)
        
        # 🔬 可验证推理预检查
        verified_paths = self._verify_paths_preconditions(paths, context_features)
        if not verified_paths:
            logger.warning("⚠️ 所有路径都未通过预条件检查，使用原始路径列表")
            verified_paths = paths
        
        # 🏆 黄金模板优先检查
        golden_match = self._check_golden_template_match(verified_paths)
        if golden_match:
            selected_path = golden_match['path']
            template_id = golden_match['template_id']
            
            logger.info(f"🏆 黄金模板匹配成功: {template_id} -> {selected_path.path_type}")
            return selected_path
        
        # 🎯 上下文Bandit选择
        try:
            # 准备动作列表（路径策略ID）
            actions = [path.strategy_id for path in verified_paths]
            strategy_to_path_mapping = {path.strategy_id: path for path in verified_paths}
            
            # 使用上下文Bandit进行选择 - 修复返回值解包问题
            selected_action, confidence, selection_info = self.contextual_bandit.select_action(context_features, actions)
            selected_path = strategy_to_path_mapping[selected_action]
            
            # 更新选择统计
            self.total_selections += 1
            self.selection_history.append({
                'path_id': selected_action,
                'path_type': selected_path.path_type,
                'algorithm': 'contextual_bandit',
                'context_features': context_features.to_dict(),
                'timestamp': time.time(),
                'selection_round': self.total_selections
            })
            
            logger.info(f"🎯 上下文Bandit选择: {selected_path.path_type} (策略ID: {selected_action})")
            logger.debug(f"   上下文特征: 意图={context_features.task_intent}, 领域={context_features.task_domain}")
            
            return selected_path
            
        except Exception as e:
            logger.error(f"❌ 上下文Bandit选择失败: {e}")
            # 回退到传统MAB选择
            return self.select_best_path(verified_paths, 'auto')
    
    def _verify_paths_preconditions(self, paths: List[ReasoningPath], 
                                   context_features: ContextFeatures) -> List[ReasoningPath]:
        """
        🔬 可验证推理：预条件检查
        
        Args:
            paths: 候选路径列表
            context_features: 上下文特征
            
        Returns:
            通过预条件检查的路径列表
        """
        verified_paths = []
        
        for path in paths:
            try:
                # 创建推理声明 - 修复方法名错误
                if not hasattr(self.reasoning_engine, 'reasoning_chains'):
                    # 如果没有推理链，先创建一个
                    chain_id = self.reasoning_engine.create_reasoning_chain(f"路径验证_{int(time.time())}")
                else:
                    # 使用已有的推理链或创建新的
                    chain_id = f"path_verification_{int(time.time())}"
                    if chain_id not in self.reasoning_engine.reasoning_chains:
                        chain_id = self.reasoning_engine.create_reasoning_chain(f"路径验证_{int(time.time())}")
                
                # 使用正确的方法名add_claim
                from neogenesis_system.cognitive_engine.verified_reasoning import ClaimType
                claim_id = self.reasoning_engine.add_claim(
                    chain_id=chain_id,
                    claim_type=ClaimType.PROCEDURAL,
                    statement=f"路径 {path.path_type} 适用于当前任务",
                    confidence=0.8
                )
                
                # 收集证据 - 修复方法名错误和枚举值错误
                evidence_id = self.reasoning_engine.add_evidence(
                    chain_id=chain_id,
                    claim_id=claim_id,
                    evidence_type=EvidenceType.TOOL_OUTPUT,  # 修复：使用存在的枚举值
                    verification_method="historical_performance_analysis",
                    verification_target=f"path_{path.strategy_id}_performance",
                    expected_result={
                        'path_success_rate': self.path_arms.get(path.strategy_id, EnhancedDecisionArm('', '')).success_rate,
                        'context_match': self._calculate_context_match(path, context_features),
                        'tool_compatibility': self._check_tool_compatibility(path, context_features)
                    }
                )
                
                # 创建行动合约 - 修复方法名错误
                # 获取路径性能数据用于合约参数
                path_success_rate = self.path_arms.get(path.strategy_id, EnhancedDecisionArm('', '')).success_rate
                context_match = self._calculate_context_match(path, context_features)
                tool_compatibility = self._check_tool_compatibility(path, context_features)
                
                contract_id = self.reasoning_engine.add_action_contract(
                    chain_id=chain_id,
                    action_name="path_execution",
                    tool_name=f"path_executor_{path.strategy_id}",
                    arguments={
                        'path_id': path.strategy_id,
                        'path_type': path.path_type,
                        'expected_success_rate': path_success_rate
                    },
                    preconditions=[
                        f"工具兼容性 >= 0.5: {tool_compatibility:.2f}",
                        f"上下文匹配度 >= 0.3: {context_match:.2f}"
                    ],
                    expected_outcomes=["任务成功完成", "用户满意度提升"]
                )
                
                # 验证推理链 - 修复方法名错误
                chain_valid, validation_summary = self.reasoning_engine.validate_reasoning_chain(chain_id)
                
                if chain_valid:
                    verified_paths.append(path)
                    logger.debug(f"✅ 路径 {path.path_type} 通过预条件检查")
                else:
                    logger.debug(f"❌ 路径 {path.path_type} 未通过预条件检查: {validation_summary}")
                    
            except Exception as e:
                logger.warning(f"⚠️ 路径 {path.path_type} 预条件检查异常: {e}")
                # 异常情况下仍然包含该路径
                verified_paths.append(path)
        
        return verified_paths
    
    def _calculate_context_match(self, path: ReasoningPath, context_features: ContextFeatures) -> float:
        """计算路径与上下文的匹配度"""
        # 基于路径类型和任务意图的匹配
        path_type_lower = path.path_type.lower()
        intent = context_features.task_intent
        
        # 意图-路径类型匹配规则
        intent_path_match = {
            'search': ['探索', '调研', 'investigative', 'exploratory'],
            'analysis': ['分析', '系统', 'analytical', 'systematic'],
            'creation': ['创新', '创造', 'creative', 'innovative'],
            'modification': ['适应', '灵活', 'adaptive', 'flexible'],
            'explanation': ['整体', '综合', 'comprehensive', 'holistic']
        }
        
        match_score = 0.0
        if intent in intent_path_match:
            keywords = intent_path_match[intent]
            for keyword in keywords:
                if keyword in path_type_lower:
                    match_score += 0.3
                    break
        
        # 复杂度匹配
        if context_features.task_complexity > 0.7 and '系统' in path_type_lower:
            match_score += 0.2
        elif context_features.task_complexity < 0.3 and '实用' in path_type_lower:
            match_score += 0.2
        
        # 历史成功率加权
        if path.strategy_id in self.path_arms:
            historical_success = self.path_arms[path.strategy_id].success_rate
            match_score += historical_success * 0.3
        
        return min(match_score, 1.0)
    
    def _check_tool_compatibility(self, path: ReasoningPath, context_features: ContextFeatures) -> float:
        """检查路径与可用工具的兼容性"""
        # 基于路径类型推断所需工具类型
        path_tool_requirements = {
            '探索调研型': ['search', 'web', 'database'],
            '系统分析型': ['analysis', 'data', 'statistics'],
            '创新突破型': ['generation', 'creative', 'brainstorm'],
            '实用务实型': ['execution', 'automation', 'workflow'],
            '整体综合型': ['integration', 'synthesis', 'summary']
        }
        
        required_tools = path_tool_requirements.get(path.path_type, [])
        if not required_tools:
            return 0.8  # 默认兼容性
        
        # 检查工具可用性
        available_score = context_features.tool_availability
        health_score = context_features.tool_health_score
        
        # 综合兼容性评分
        compatibility = (available_score * 0.6 + health_score * 0.4)
        
        return compatibility
    
    def update_contextual_feedback(self, path_id: str, context_features: ContextFeatures, 
                                  success: bool, reward: float = 0.0, 
                                  execution_result: Optional[Dict] = None):
        """
        🎯 更新上下文Bandit的反馈
        
        Args:
            path_id: 路径ID
            context_features: 上下文特征
            success: 执行是否成功
            reward: 奖励值
            execution_result: 执行结果详情
        """
        try:
            # 🔬 可验证推理：成功信号定义
            verified_success = self._verify_success_signal(success, execution_result)
            adjusted_reward = self._calculate_verified_reward(success, reward, execution_result)
            
            # 创建行动结果
            outcome = ActionOutcome(
                action_id=path_id,  # 修复参数名：action -> action_id
                context_features=context_features,
                success_metrics={SuccessMetric.EXECUTION_SUCCESS: adjusted_reward},  # 修复参数结构
                execution_time=execution_result.get('execution_time', 0.0) if execution_result else 0.0,
                cost=execution_result.get('cost', 0.0) if execution_result else 0.0,  # 添加必需的cost参数
                timestamp=time.time(),  # 添加必需的timestamp参数
                additional_info=execution_result or {}  # 添加额外信息
            )
            
            # 更新上下文Bandit（方法更名：update_reward）
            if hasattr(self.contextual_bandit, 'update_reward'):
                self.contextual_bandit.update_reward(context_features, path_id, outcome)
            else:
                # 兼容旧接口
                self.contextual_bandit.update_feedback(outcome)
            
            # 同时更新传统MAB系统（向后兼容）
            self.update_path_performance(path_id, verified_success, adjusted_reward, "contextual_bandit")
            
            logger.info(f"🎯 上下文反馈更新: {path_id} -> 成功={verified_success}, 奖励={adjusted_reward:.3f}")
            
        except Exception as e:
            logger.error(f"❌ 上下文反馈更新失败: {e}")
            # 回退到传统更新
            self.update_path_performance(path_id, success, reward, "fallback")
    
    def _verify_success_signal(self, raw_success: bool, execution_result: Optional[Dict]) -> bool:
        """
        🔬 可验证的成功信号定义
        
        不依赖LLM自评，而是基于客观指标判断成功
        """
        if not execution_result:
            return raw_success
        
        # 多维度成功验证
        success_indicators = []
        
        # 1. 执行完成度
        completion_rate = execution_result.get('completion_rate', 1.0 if raw_success else 0.0)
        success_indicators.append(completion_rate > 0.8)
        
        # 2. 错误率
        error_rate = execution_result.get('error_rate', 0.0)
        success_indicators.append(error_rate < 0.1)
        
        # 3. 用户满意度（如果有）
        user_satisfaction = execution_result.get('user_satisfaction')
        if user_satisfaction is not None:
            success_indicators.append(user_satisfaction > 0.7)
        
        # 4. 时间效率
        execution_time = execution_result.get('execution_time', 0.0)
        expected_time = execution_result.get('expected_time', execution_time)
        if expected_time > 0:
            time_efficiency = min(expected_time / max(execution_time, 0.1), 1.0)
            success_indicators.append(time_efficiency > 0.5)
        
        # 5. 资源使用效率
        resource_usage = execution_result.get('resource_usage', 0.5)
        success_indicators.append(resource_usage < 0.8)
        
        # 综合判断：至少70%的指标为正面
        verified_success = sum(success_indicators) / len(success_indicators) >= 0.7
        
        if verified_success != raw_success:
            logger.info(f"🔬 成功信号修正: 原始={raw_success} -> 验证后={verified_success}")
        
        return verified_success
    
    def _calculate_verified_reward(self, success: bool, raw_reward: float, 
                                  execution_result: Optional[Dict]) -> float:
        """计算验证后的奖励值"""
        if not execution_result:
            return raw_reward
        
        # 基础奖励
        base_reward = 1.0 if success else -0.5
        
        # 效率奖励
        efficiency_bonus = 0.0
        execution_time = execution_result.get('execution_time', 0.0)
        expected_time = execution_result.get('expected_time', execution_time)
        if expected_time > 0 and execution_time > 0:
            time_ratio = expected_time / execution_time
            if time_ratio > 1.2:  # 比预期快20%以上
                efficiency_bonus += 0.3
            elif time_ratio < 0.8:  # 比预期慢20%以上
                efficiency_bonus -= 0.2
        
        # 质量奖励
        quality_bonus = 0.0
        completion_rate = execution_result.get('completion_rate', 1.0 if success else 0.0)
        quality_bonus += (completion_rate - 0.8) * 0.5  # 超过80%完成度的部分给奖励
        
        # 成本惩罚
        cost_penalty = 0.0
        cost = execution_result.get('cost', 0.0)
        budget = execution_result.get('budget', cost)
        if budget > 0 and cost > budget:
            cost_penalty = -min((cost - budget) / budget, 0.5)  # 最多扣0.5分
        
        # 综合奖励
        final_reward = base_reward + efficiency_bonus + quality_bonus + cost_penalty
        
        return max(-1.0, min(final_reward, 2.0))  # 限制在[-1, 2]范围内
    
    def get_contextual_bandit_stats(self) -> Dict[str, Any]:
        """
        🎯 获取上下文Bandit统计信息
        
        Returns:
            上下文Bandit的详细统计数据
        """
        try:
            bandit_stats = self.contextual_bandit.get_statistics()
            
            # 添加集成统计
            integration_stats = {
                'total_contextual_selections': len([h for h in self.selection_history if h.get('algorithm') == 'contextual_bandit']),
                'contextual_success_rate': self._calculate_contextual_success_rate(),
                'feature_importance': self._analyze_feature_importance(),
                'context_distribution': self._analyze_context_distribution()
            }
            
            return {
                'bandit_core_stats': bandit_stats,
                'integration_stats': integration_stats,
                'verified_reasoning_stats': self.reasoning_engine.get_statistics() if hasattr(self.reasoning_engine, 'get_statistics') else {}
            }
            
        except Exception as e:
            logger.error(f"❌ 获取上下文Bandit统计失败: {e}")
            return {'error': str(e)}
    
    def _calculate_contextual_success_rate(self) -> float:
        """计算上下文Bandit的成功率"""
        contextual_selections = [h for h in self.selection_history if h.get('algorithm') == 'contextual_bandit']
        if not contextual_selections:
            return 0.0
        
        # 基于路径ID查找对应的成功率
        success_rates = []
        for selection in contextual_selections:
            path_id = selection.get('path_id')
            if path_id in self.path_arms:
                success_rates.append(self.path_arms[path_id].success_rate)
        
        return sum(success_rates) / len(success_rates) if success_rates else 0.0
    
    def _analyze_feature_importance(self) -> Dict[str, float]:
        """分析上下文特征的重要性"""
        # 简化的特征重要性分析
        feature_impact = {
            'task_intent': 0.0,
            'task_domain': 0.0,
            'task_complexity': 0.0,
            'tool_availability': 0.0,
            'historical_success_rate': 0.0
        }
        
        # 基于选择历史分析特征影响
        contextual_selections = [h for h in self.selection_history if h.get('context_features')]
        
        if contextual_selections:
            # 简单的相关性分析
            for selection in contextual_selections:
                features = selection.get('context_features', {})
                path_id = selection.get('path_id')
                
                if path_id in self.path_arms:
                    success_rate = self.path_arms[path_id].success_rate
                    
                    # 累积特征与成功率的相关性
                    for feature_name in feature_impact.keys():
                        feature_value = features.get(feature_name, 0.0)
                        if isinstance(feature_value, (int, float)):
                            feature_impact[feature_name] += feature_value * success_rate
            
            # 归一化
            total_impact = sum(feature_impact.values())
            if total_impact > 0:
                feature_impact = {k: v / total_impact for k, v in feature_impact.items()}
        
        return feature_impact
    
    def _analyze_context_distribution(self) -> Dict[str, Any]:
        """分析上下文特征分布"""
        contextual_selections = [h for h in self.selection_history if h.get('context_features')]
        
        if not contextual_selections:
            return {}
        
        # 统计各个特征的分布
        intent_dist = defaultdict(int)
        domain_dist = defaultdict(int)
        complexity_dist = {'low': 0, 'medium': 0, 'high': 0}
        
        for selection in contextual_selections:
            features = selection.get('context_features', {})
            
            # 意图分布
            intent = features.get('task_intent', 'unknown')
            intent_dist[intent] += 1
            
            # 领域分布
            domain = features.get('task_domain', 'unknown')
            domain_dist[domain] += 1
            
            # 复杂度分布
            complexity = features.get('task_complexity', 0.5)
            if complexity < 0.3:
                complexity_dist['low'] += 1
            elif complexity < 0.7:
                complexity_dist['medium'] += 1
            else:
                complexity_dist['high'] += 1
        
        return {
            'intent_distribution': dict(intent_dist),
            'domain_distribution': dict(domain_dist),
            'complexity_distribution': dict(complexity_dist),
            'total_samples': len(contextual_selections)
        }
    
    def get_verified_reasoning_report(self) -> Dict[str, Any]:
        """
        🔬 获取可验证推理报告
        
        Returns:
            可验证推理系统的详细报告
        """
        try:
            # 统计预条件检查结果
            verification_stats = {
                'total_verifications': 0,
                'passed_verifications': 0,
                'failed_verifications': 0,
                'verification_success_rate': 0.0,
                'common_failure_reasons': defaultdict(int),
                'success_signal_corrections': 0
            }
            
            # 从选择历史中统计验证数据
            for selection in self.selection_history:
                if 'verification_result' in selection:
                    verification_stats['total_verifications'] += 1
                    if selection['verification_result'].get('passed', False):
                        verification_stats['passed_verifications'] += 1
                    else:
                        verification_stats['failed_verifications'] += 1
                        reason = selection['verification_result'].get('reason', 'unknown')
                        verification_stats['common_failure_reasons'][reason] += 1
            
            if verification_stats['total_verifications'] > 0:
                verification_stats['verification_success_rate'] = (
                    verification_stats['passed_verifications'] / verification_stats['total_verifications']
                )
            
            # 获取推理引擎统计
            reasoning_engine_stats = {}
            if hasattr(self.reasoning_engine, 'get_statistics'):
                reasoning_engine_stats = self.reasoning_engine.get_statistics()
            
            return {
                'verification_stats': verification_stats,
                'reasoning_engine_stats': reasoning_engine_stats,
                'contract_validation_enabled': True,
                'success_signal_verification_enabled': True
            }
            
        except Exception as e:
            logger.error(f"❌ 获取可验证推理报告失败: {e}")
            return {'error': str(e)}
    
    def get_comprehensive_system_status(self) -> Dict[str, Any]:
        """
        🎯 获取综合系统状态
        
        Returns:
            包含所有子系统状态的综合报告
        """
        try:
            return {
                'timestamp': time.time(),
                'system_mode': 'contextual_bandit_with_verified_reasoning',
                
                # 🎯 上下文Bandit状态
                'contextual_bandit': self.get_contextual_bandit_stats(),
                
                # 🔬 可验证推理状态
                'verified_reasoning': self.get_verified_reasoning_report(),
                
                # 🏆 黄金模板状态
                'golden_templates': self.get_golden_template_stats(),
                
                # 🎭 试炼场状态
                'trial_ground': self.get_trial_ground_analytics(),
                
                # 📊 传统MAB状态（向后兼容）
                'traditional_mab': self.get_system_status(),
                
                # 🔧 工具健康状态
                'tool_health': self._get_tool_health_summary(),
                
                # 📈 性能趋势
                'performance_trends': self._get_performance_trends()
            }
            
        except Exception as e:
            logger.error(f"❌ 获取综合系统状态失败: {e}")
            return {'error': str(e), 'timestamp': time.time()}
    
    def _get_tool_health_summary(self) -> Dict[str, Any]:
        """获取工具健康状态摘要"""
        if not self.tool_health_cache:
            return {'total_tools': 0, 'healthy_tools': 0, 'health_rate': 0.0}
        
        healthy_count = 0
        total_count = len(self.tool_health_cache)
        
        for tool_name, cached_data in self.tool_health_cache.items():
            if cached_data['status']['is_healthy']:
                healthy_count += 1
        
        return {
            'total_tools': total_count,
            'healthy_tools': healthy_count,
            'health_rate': healthy_count / total_count if total_count > 0 else 0.0,
            'last_check_time': max(
                (data['timestamp'] for data in self.tool_health_cache.values()),
                default=0.0
            )
        }
    
    def _get_performance_trends(self) -> Dict[str, Any]:
        """获取性能趋势分析"""
        recent_selections = self.selection_history[-50:] if len(self.selection_history) > 50 else self.selection_history
        
        if not recent_selections:
            return {'trend': 'insufficient_data'}
        
        # 分析最近的成功率趋势
        success_rates = []
        for selection in recent_selections:
            path_id = selection.get('path_id')
            if path_id in self.path_arms:
                success_rates.append(self.path_arms[path_id].success_rate)
        
        if len(success_rates) < 10:
            return {'trend': 'insufficient_data'}
        
        # 简单的趋势分析
        first_half = success_rates[:len(success_rates)//2]
        second_half = success_rates[len(success_rates)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        if second_avg > first_avg + 0.05:
            trend = 'improving'
        elif second_avg < first_avg - 0.05:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'recent_avg_success_rate': second_avg,
            'improvement': second_avg - first_avg,
            'sample_size': len(success_rates)
        }
    
    def export_system_configuration(self) -> Dict[str, Any]:
        """
        🔧 导出系统配置
        
        Returns:
            完整的系统配置数据
        """
        return {
            'contextual_bandit_config': {
                'algorithm': self.contextual_bandit.algorithm if hasattr(self.contextual_bandit, 'algorithm') else 'unknown',
                'feature_dim': self.contextual_bandit.feature_dim if hasattr(self.contextual_bandit, 'feature_dim') else 8,
                'storage_path': self.contextual_bandit.storage_path if hasattr(self.contextual_bandit, 'storage_path') else 'unknown'
            },
            'golden_template_config': self.golden_template_config,
            'trial_config': self.trial_config,
            'source_weight_config': self.source_weight_config,
            'health_check_interval': self.health_check_interval,
            'mab_config': MAB_CONFIG
        }
    
    def demo_contextual_bandit_workflow(self, demo_query: str = "请分析一下人工智能在医疗领域的应用前景"):
        """
        🎯 演示上下文Bandit + 可验证推理的完整工作流程
        
        Args:
            demo_query: 演示用的查询
        """
        logger.info("🎯 开始上下文Bandit + 可验证推理演示")
        logger.info(f"📝 演示查询: {demo_query}")
        
        print("\n" + "="*80)
        print("🎯 上下文多臂老虎机 + 可验证推理系统演示")
        print("="*80)
        
        # 1. 展示语义分析能力
        print("\n🧠 第一步：智能语义分析")
        print("-" * 40)
        
        context_features = self.extract_context_features(demo_query)
        print(f"✅ 任务意图: {context_features.task_intent}")
        print(f"✅ 任务领域: {context_features.task_domain}")
        print(f"✅ 复杂度评分: {context_features.task_complexity:.3f}")
        print(f"✅ 输入长度评分: {context_features.input_length:.3f}")
        
        # 2. 展示上下文Bandit统计
        print("\n🎯 第二步：上下文Bandit状态")
        print("-" * 40)
        
        bandit_stats = self.get_contextual_bandit_stats()
        print(f"✅ 上下文选择次数: {bandit_stats['integration_stats']['total_contextual_selections']}")
        print(f"✅ 上下文成功率: {bandit_stats['integration_stats']['contextual_success_rate']:.3f}")
        
        feature_importance = bandit_stats['integration_stats']['feature_importance']
        print("✅ 特征重要性分析:")
        for feature, importance in feature_importance.items():
            print(f"   - {feature}: {importance:.3f}")
        
        # 3. 展示可验证推理能力
        print("\n🔬 第三步：可验证推理报告")
        print("-" * 40)
        
        reasoning_report = self.get_verified_reasoning_report()
        print(f"✅ 验证成功率: {reasoning_report['verification_stats']['verification_success_rate']:.3f}")
        print(f"✅ 总验证次数: {reasoning_report['verification_stats']['total_verifications']}")
        print("✅ 合约验证: 已启用")
        print("✅ 成功信号验证: 已启用")
        
        # 4. 展示系统综合状态
        print("\n📊 第四步：系统综合状态")
        print("-" * 40)
        
        system_status = self.get_comprehensive_system_status()
        print(f"✅ 系统模式: {system_status['system_mode']}")
        print(f"✅ 工具健康率: {system_status['tool_health']['health_rate']:.1%}")
        print(f"✅ 性能趋势: {system_status['performance_trends']['trend']}")
        print(f"✅ 黄金模板数量: {system_status['golden_templates']['total_templates']}")
        
        # 5. 展示配置导出
        print("\n🔧 第五步：系统配置")
        print("-" * 40)
        
        config = self.export_system_configuration()
        print(f"✅ 上下文Bandit算法: {config['contextual_bandit_config']['algorithm']}")
        print(f"✅ 特征维度: {config['contextual_bandit_config']['feature_dim']}")
        print(f"✅ 语义分析: 已集成")
        print(f"✅ 可验证推理: 已集成")
        
        print("\n" + "="*80)
        print("🎉 演示完成！系统已成功升级为上下文Bandit + 可验证推理")
        print("="*80)
        
        return {
            'demo_query': demo_query,
            'context_features': context_features.to_dict(),
            'bandit_stats': bandit_stats,
            'reasoning_report': reasoning_report,
            'system_status': system_status,
            'configuration': config
        }
    
    def _create_tool_arm_if_missing(self, tool_id: str, tool_name: str = None) -> EnhancedDecisionArm:
        """
        动态创建工具决策臂（如果不存在）
        
        Args:
            tool_id: 工具ID
            tool_name: 工具名称（可选，如果未提供则使用tool_id）
            
        Returns:
            对应的工具决策臂
        """
        if tool_id not in self.tool_arms:
            if tool_name is None:
                tool_name = tool_id  # 默认使用tool_id作为工具名称
            
            self.tool_arms[tool_id] = EnhancedDecisionArm(
                path_id=tool_id,
                option=tool_name
            )
            logger.debug(f"🔧 动态创建工具决策臂: {tool_id} ({tool_name})")
        
        return self.tool_arms[tool_id]
    
    # ==================== 🎭 试炼场系统核心方法 ====================
    
    def _detect_path_source(self, strategy_id: str, path_type: str, reasoning_path: 'ReasoningPath' = None) -> str:
        """
        智能检测路径来源
        
        Args:
            strategy_id: 策略ID
            path_type: 路径类型
            reasoning_path: 推理路径对象
            
        Returns:
            路径来源类型
        """
        # 1. 基于策略ID命名模式检测
        if "learned_" in strategy_id or "explored_" in strategy_id or "generated_" in strategy_id:
            return "learned_exploration"
        
        if "custom_" in strategy_id or "manual_" in strategy_id or "user_" in strategy_id:
            return "manual_addition"
        
        # 2. 基于路径类型检测
        if path_type and ("学习" in path_type or "探索" in path_type or "发现" in path_type):
            return "learned_exploration"
        
        # 3. 基于推理路径对象元数据检测
        if reasoning_path:
            # 检查路径描述中的关键词
            description = getattr(reasoning_path, 'description', '')
            if any(keyword in description for keyword in ["从探索中学习", "知识发现", "外部智慧", "动态生成"]):
                return "learned_exploration"
            
            # 检查是否有学习来源标记
            if hasattr(reasoning_path, 'is_learned') and getattr(reasoning_path, 'is_learned', False):
                return "learned_exploration"
        
        # 4. 默认为静态模板
        return "static_template"
    
    def _mark_as_learned_path(self, strategy_id: str, reasoning_path: 'ReasoningPath' = None):
        """
        标记为学习路径，记录相关元数据
        
        Args:
            strategy_id: 策略ID
            reasoning_path: 推理路径对象
        """
        learned_metadata = {
            "strategy_id": strategy_id,
            "marked_at": time.time(),
            "source": "knowledge_exploration",
            "initial_boost_given": True,
            "promotion_eligible": True,
            "trial_start_time": time.time()
        }
        
        # 从推理路径对象中提取更多元数据
        if reasoning_path:
            learned_metadata.update({
                "path_type": getattr(reasoning_path, 'path_type', ''),
                "description": getattr(reasoning_path, 'description', ''),
                "learning_source": getattr(reasoning_path, 'learning_source', ''),
                "is_learned": getattr(reasoning_path, 'is_learned', True),
                "effectiveness_score": getattr(reasoning_path, 'effectiveness_score', 0.5)
            })
        
        # 注册到试炼场
        self.trial_ground["learned_paths"][strategy_id] = learned_metadata
        
        # 激活探索增强
        self.trial_ground["exploration_boost_active"][strategy_id] = self.trial_config["exploration_boost_rounds"]
        
        logger.info(f"🎭 [试炼场] 路径已标记为学习路径: {strategy_id}")
        logger.info(f"🎭 [试炼场] 探索增强轮数: {self.trial_config['exploration_boost_rounds']}")
        logger.info(f"🎭 [试炼场] 当前试炼场活跃路径数: {len(self.trial_ground['exploration_boost_active'])}")
    
    def _record_trial_entry(self, strategy_id: str, path_type: str, source: str):
        """
        记录试炼场进入历史
        
        Args:
            strategy_id: 策略ID
            path_type: 路径类型
            source: 路径来源
        """
        trial_record = {
            "strategy_id": strategy_id,
            "path_type": path_type,
            "source": source,
            "entry_time": time.time(),
            "entry_round": self.total_path_selections,
            "status": "active_trial"
        }
        
        self.trial_ground["trial_history"].append(trial_record)
        
        # 保持历史记录大小
        if len(self.trial_ground["trial_history"]) > 1000:
            self.trial_ground["trial_history"] = self.trial_ground["trial_history"][-800:]
        
        logger.info(f"🎭 [试炼场] {strategy_id} 开始试炼 (来源: {source})")
        logger.info(f"🎭 [试炼场] 试炼历史记录数: {len(self.trial_ground['trial_history'])}")
    
    def is_learned_path(self, strategy_id: str) -> bool:
        """
        检查是否为学习路径
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            是否为学习路径
        """
        return strategy_id in self.trial_ground["learned_paths"]
    
    def get_exploration_boost(self, strategy_id: str) -> float:
        """
        获取路径的探索增强系数
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            探索增强系数 (1.0 = 无增强, > 1.0 = 有增强)
        """
        boost_factor = 1.0
        
        # 基础增强：新学习路径
        if strategy_id in self.trial_ground["exploration_boost_active"]:
            remaining_rounds = self.trial_ground["exploration_boost_active"][strategy_id]
            if remaining_rounds > 0:
                # 递减的探索增强
                base_bonus = self.trial_config["learned_path_bonus"]
                decay_factor = remaining_rounds / self.trial_config["exploration_boost_rounds"]
                boost_factor += base_bonus * decay_factor
        
        # 特殊增强：学习路径永久小幅增强
        if self.is_learned_path(strategy_id):
            boost_factor += 0.05  # 5%的永久小幅增强
        
        return boost_factor
    
    def _update_exploration_boost(self, strategy_id: str):
        """
        更新探索增强状态（每次选择后调用）
        
        Args:
            strategy_id: 被选择的策略ID
        """
        if strategy_id in self.trial_ground["exploration_boost_active"]:
            remaining = self.trial_ground["exploration_boost_active"][strategy_id]
            if remaining > 0:
                self.trial_ground["exploration_boost_active"][strategy_id] = remaining - 1
                logger.info(f"🎭 [试炼场] 路径 {strategy_id} 探索增强剩余: {remaining - 1} 轮")
                
                if remaining == 1:  # 即将用完
                    logger.info(f"🎯 [试炼场] 路径 {strategy_id} 的探索增强即将结束")
                elif remaining - 1 <= 0:
                    del self.trial_ground["exploration_boost_active"][strategy_id]
                    logger.info(f"✅ [试炼场] 路径 {strategy_id} 完成探索增强期，进入正常竞争")
    
    def _check_culling_candidates(self, strategy_id: str, arm: EnhancedDecisionArm, success: bool):
        """
        🗡️ 检查并管理淘汰候选路径
        
        Args:
            strategy_id: 策略ID
            arm: 决策臂对象
            success: 最新执行结果
        """
        # 只检查有足够样本的路径
        if arm.activation_count < self.trial_config["culling_min_samples"]:
            return
        
        # 获取成功率阈值
        culling_threshold = self.trial_config["culling_threshold"]
        
        # 检查是否应该被加入淘汰候选
        if arm.success_rate < culling_threshold:
            if strategy_id not in self.trial_ground["culling_candidates"]:
                self.trial_ground["culling_candidates"].add(strategy_id)
                
                # 记录进入淘汰候选的原因
                self.trial_ground["performance_watch_list"][strategy_id] = {
                    "reason": "low_success_rate",
                    "success_rate": arm.success_rate,
                    "threshold": culling_threshold,
                    "added_at": time.time(),
                    "sample_count": arm.activation_count,
                    "consecutive_failures": self._calculate_consecutive_failures(arm)
                }
                
                logger.warning(f"⚠️ 路径 {strategy_id} 进入淘汰候选名单")
                logger.warning(f"   成功率: {arm.success_rate:.3f} < 阈值: {culling_threshold}")
                logger.warning(f"   样本数: {arm.activation_count}")
                
                # 如果是学习路径，给予警告但不立即淘汰
                if self.is_learned_path(strategy_id):
                    logger.warning(f"🌱 学习路径 {strategy_id} 表现不佳，将给予额外观察期")
        
        # 如果成功率回升，移出淘汰候选
        elif strategy_id in self.trial_ground["culling_candidates"]:
            if arm.success_rate >= culling_threshold * 1.2:  # 需要超过阈值20%才能移出
                self.trial_ground["culling_candidates"].remove(strategy_id)
                if strategy_id in self.trial_ground["performance_watch_list"]:
                    del self.trial_ground["performance_watch_list"][strategy_id]
                
                logger.info(f"✅ 路径 {strategy_id} 性能回升，移出淘汰候选名单")
                logger.info(f"   当前成功率: {arm.success_rate:.3f} >= 回归阈值: {culling_threshold * 1.2:.3f}")
    
    def _calculate_consecutive_failures(self, arm: EnhancedDecisionArm) -> int:
        """
        计算连续失败次数
        
        Args:
            arm: 决策臂对象
            
        Returns:
            连续失败次数
        """
        if not arm.recent_results:
            return 0
        
        consecutive_count = 0
        # 从最近的结果开始往前数
        for result in reversed(arm.recent_results):
            if not result:  # 如果是失败
                consecutive_count += 1
            else:  # 如果成功了，就停止计数
                break
        
        return consecutive_count
    
    def execute_automatic_culling(self) -> Dict[str, Any]:
        """
        🗡️ 执行自动淘汰机制
        
        Returns:
            淘汰执行结果
        """
        culling_results = {
            "executed_at": time.time(),
            "candidates_reviewed": len(self.trial_ground["culling_candidates"]),
            "paths_culled": [],
            "paths_spared": [],
            "action_summary": {}
        }
        
        if not self.trial_ground["culling_candidates"]:
            culling_results["action_summary"] = {"message": "无需要淘汰的候选路径"}
            return culling_results
        
        logger.info(f"🗡️ 开始自动淘汰检查，候选路径: {len(self.trial_ground['culling_candidates'])} 个")
        
        candidates_to_remove = set()
        
        for strategy_id in list(self.trial_ground["culling_candidates"]):
            if strategy_id not in self.path_arms:
                candidates_to_remove.add(strategy_id)
                continue
            
            arm = self.path_arms[strategy_id]
            watch_data = self.trial_ground["performance_watch_list"].get(strategy_id, {})
            
            # 决定是否真正淘汰
            should_cull, reason = self._should_cull_path(strategy_id, arm, watch_data)
            
            if should_cull:
                # 执行淘汰
                self._cull_path(strategy_id, reason)
                candidates_to_remove.add(strategy_id)
                culling_results["paths_culled"].append({
                    "strategy_id": strategy_id,
                    "reason": reason,
                    "final_success_rate": arm.success_rate,
                    "total_activations": arm.activation_count
                })
                logger.info(f"🗡️ 淘汰路径: {strategy_id} - {reason}")
            else:
                # 暂缓淘汰
                culling_results["paths_spared"].append({
                    "strategy_id": strategy_id,
                    "reason": f"暂缓淘汰 - {reason}",
                    "current_success_rate": arm.success_rate
                })
                logger.info(f"⏳ 暂缓淘汰路径: {strategy_id} - {reason}")
        
        # 清理候选名单
        for strategy_id in candidates_to_remove:
            self.trial_ground["culling_candidates"].discard(strategy_id)
            self.trial_ground["performance_watch_list"].pop(strategy_id, None)
        
        culling_results["action_summary"] = {
            "total_culled": len(culling_results["paths_culled"]),
            "total_spared": len(culling_results["paths_spared"]),
            "remaining_candidates": len(self.trial_ground["culling_candidates"])
        }
        
        logger.info(f"🗡️ 淘汰检查完成: 淘汰 {len(culling_results['paths_culled'])} 个, "
                   f"暂缓 {len(culling_results['paths_spared'])} 个")
        
        return culling_results
    
    def _should_cull_path(self, strategy_id: str, arm: EnhancedDecisionArm, watch_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        判断是否应该淘汰指定路径
        
        Args:
            strategy_id: 策略ID
            arm: 决策臂对象
            watch_data: 监控数据
            
        Returns:
            (是否淘汰, 原因)
        """
        # 1. 学习路径获得额外保护
        if self.is_learned_path(strategy_id):
            # 学习路径需要更差的表现才会被淘汰
            harsh_threshold = self.trial_config["culling_threshold"] * 0.5  # 更严格的阈值
            if arm.success_rate > harsh_threshold:
                return False, "学习路径享受保护期"
            
            # 检查学习路径的试验时间
            learned_meta = self.trial_ground["learned_paths"].get(strategy_id, {})
            trial_time = time.time() - learned_meta.get("trial_start_time", time.time())
            if trial_time < 3600:  # 1小时保护期
                return False, "学习路径仍在保护期内"
        
        # 2. 黄金模板绝不淘汰
        if strategy_id in self.golden_templates:
            return False, "黄金模板不可淘汰"
        
        # 3. 检查连续失败情况
        consecutive_failures = watch_data.get("consecutive_failures", 0)
        if consecutive_failures >= 10:  # 连续10次失败
            return True, f"连续失败{consecutive_failures}次"
        
        # 4. 检查长期表现
        if arm.success_rate < self.trial_config["culling_threshold"] * 0.8:  # 低于阈值的80%
            watch_duration = time.time() - watch_data.get("added_at", time.time())
            if watch_duration > 1800:  # 在观察名单超过30分钟
                return True, f"长期表现不佳 (成功率: {arm.success_rate:.3f})"
        
        # 5. 检查使用频率
        if arm.activation_count > 50 and arm.success_rate < self.trial_config["culling_threshold"]:
            return True, f"大量试验后表现仍不佳 ({arm.activation_count} 次试验)"
        
        return False, "暂不符合淘汰条件"
    
    def _cull_path(self, strategy_id: str, reason: str):
        """
        执行路径淘汰
        
        Args:
            strategy_id: 策略ID
            reason: 淘汰原因
        """
        if strategy_id in self.path_arms:
            # 记录淘汰历史
            culled_arm = self.path_arms[strategy_id]
            cull_record = {
                "strategy_id": strategy_id,
                "culled_at": time.time(),
                "reason": reason,
                "final_stats": {
                    "success_rate": culled_arm.success_rate,
                    "total_activations": culled_arm.activation_count,
                    "total_reward": culled_arm.total_reward
                },
                "was_learned_path": self.is_learned_path(strategy_id)
            }
            
            # 保存到历史记录
            if "culled_paths" not in self.trial_ground:
                self.trial_ground["culled_paths"] = []
            self.trial_ground["culled_paths"].append(cull_record)
            
            # 执行移除
            del self.path_arms[strategy_id]
            
            # 清理相关数据
            self.trial_ground["learned_paths"].pop(strategy_id, None)
            self.trial_ground["exploration_boost_active"].pop(strategy_id, None)
            self.trial_ground["promotion_candidates"].discard(strategy_id)
            
            logger.info(f"🗡️ 路径 {strategy_id} 已被淘汰: {reason}")
            logger.info(f"   最终统计: 成功率 {culled_arm.success_rate:.3f}, 激活 {culled_arm.activation_count} 次")
    
    def get_trial_ground_analytics(self) -> Dict[str, Any]:
        """
        📊 获取试炼场全面分析数据
        
        Returns:
            试炼场统计分析
        """
        analytics = {
            "timestamp": time.time(),
            "overview": self._get_trial_overview(),
            "learned_paths": self._analyze_learned_paths(),
            "exploration_status": self._analyze_exploration_status(),
            "culling_analysis": self._analyze_culling_situation(),
            "performance_trends": self._analyze_performance_trends(),
            "golden_template_candidates": self._analyze_golden_candidates()
        }
        
        return analytics
    
    def _get_trial_overview(self) -> Dict[str, Any]:
        """获取试炼场总体概况"""
        total_paths = len(self.path_arms)
        learned_paths = len(self.trial_ground["learned_paths"])
        
        return {
            "total_active_paths": total_paths,
            "learned_paths_count": learned_paths,
            "static_paths_count": total_paths - learned_paths,
            "exploration_boost_active": len(self.trial_ground["exploration_boost_active"]),
            "culling_candidates": len(self.trial_ground["culling_candidates"]),
            "promotion_candidates": len(self.trial_ground["promotion_candidates"]),
            "golden_templates": len(self.golden_templates),
            "culled_paths_history": len(self.trial_ground.get("culled_paths", []))
        }
    
    def _analyze_learned_paths(self) -> Dict[str, Any]:
        """分析学习路径的详细情况"""
        learned_analysis = {
            "active_learned_paths": [],
            "performance_summary": {
                "excellent": 0,  # > 0.8
                "good": 0,       # 0.6-0.8
                "average": 0,    # 0.4-0.6
                "poor": 0        # < 0.4
            },
            "avg_success_rate": 0.0,
            "total_activations": 0
        }
        
        if not self.trial_ground["learned_paths"]:
            return learned_analysis
        
        success_rates = []
        total_activations = 0
        
        for strategy_id, meta in self.trial_ground["learned_paths"].items():
            if strategy_id not in self.path_arms:
                continue
                
            arm = self.path_arms[strategy_id]
            success_rate = arm.success_rate
            success_rates.append(success_rate)
            total_activations += arm.activation_count
            
            # 性能分类
            if success_rate >= 0.8:
                learned_analysis["performance_summary"]["excellent"] += 1
            elif success_rate >= 0.6:
                learned_analysis["performance_summary"]["good"] += 1
            elif success_rate >= 0.4:
                learned_analysis["performance_summary"]["average"] += 1
            else:
                learned_analysis["performance_summary"]["poor"] += 1
            
            # 详细信息
            trial_duration = time.time() - meta.get("trial_start_time", time.time())
            learned_analysis["active_learned_paths"].append({
                "strategy_id": strategy_id,
                "source": meta.get("source", "unknown"),
                "success_rate": success_rate,
                "activations": arm.activation_count,
                "trial_duration_hours": trial_duration / 3600,
                "has_exploration_boost": strategy_id in self.trial_ground["exploration_boost_active"],
                "is_promotion_candidate": strategy_id in self.trial_ground["promotion_candidates"],
                "is_culling_candidate": strategy_id in self.trial_ground["culling_candidates"]
            })
        
        learned_analysis["avg_success_rate"] = sum(success_rates) / len(success_rates) if success_rates else 0.0
        learned_analysis["total_activations"] = total_activations
        
        return learned_analysis
    
    def _analyze_exploration_status(self) -> Dict[str, Any]:
        """分析探索增强状态"""
        exploration_analysis = {
            "active_boosts": [],
            "total_boost_paths": len(self.trial_ground["exploration_boost_active"]),
            "boost_distribution": {}
        }
        
        for strategy_id, remaining_rounds in self.trial_ground["exploration_boost_active"].items():
            if strategy_id in self.path_arms:
                arm = self.path_arms[strategy_id]
                exploration_analysis["active_boosts"].append({
                    "strategy_id": strategy_id,
                    "remaining_rounds": remaining_rounds,
                    "current_success_rate": arm.success_rate,
                    "activations_during_boost": arm.activation_count,
                    "is_learned_path": self.is_learned_path(strategy_id)
                })
                
                # 分布统计
                if remaining_rounds not in exploration_analysis["boost_distribution"]:
                    exploration_analysis["boost_distribution"][remaining_rounds] = 0
                exploration_analysis["boost_distribution"][remaining_rounds] += 1
        
        return exploration_analysis
    
    def _analyze_culling_situation(self) -> Dict[str, Any]:
        """分析淘汰情况"""
        culling_analysis = {
            "current_candidates": [],
            "recent_culled": [],
            "culling_threshold": self.trial_config["culling_threshold"],
            "protection_summary": {
                "golden_templates": 0,
                "learned_paths_protected": 0,
                "recent_paths": 0
            }
        }
        
        # 当前淘汰候选
        for strategy_id in self.trial_ground["culling_candidates"]:
            if strategy_id in self.path_arms:
                arm = self.path_arms[strategy_id]
                watch_data = self.trial_ground["performance_watch_list"].get(strategy_id, {})
                
                culling_analysis["current_candidates"].append({
                    "strategy_id": strategy_id,
                    "success_rate": arm.success_rate,
                    "activations": arm.activation_count,
                    "watch_reason": watch_data.get("reason", "unknown"),
                    "watch_duration_minutes": (time.time() - watch_data.get("added_at", time.time())) / 60,
                    "is_learned_path": self.is_learned_path(strategy_id),
                    "consecutive_failures": watch_data.get("consecutive_failures", 0)
                })
        
        # 最近淘汰的路径（最后10个）
        recent_culled = self.trial_ground.get("culled_paths", [])[-10:]
        for cull_record in recent_culled:
            culling_analysis["recent_culled"].append({
                "strategy_id": cull_record["strategy_id"],
                "culled_hours_ago": (time.time() - cull_record["culled_at"]) / 3600,
                "reason": cull_record["reason"],
                "final_success_rate": cull_record["final_stats"]["success_rate"],
                "was_learned_path": cull_record["was_learned_path"]
            })
        
        # 保护情况统计
        for strategy_id in self.path_arms:
            if strategy_id in self.golden_templates:
                culling_analysis["protection_summary"]["golden_templates"] += 1
            elif self.is_learned_path(strategy_id):
                learned_meta = self.trial_ground["learned_paths"].get(strategy_id, {})
                trial_time = time.time() - learned_meta.get("trial_start_time", time.time())
                if trial_time < 3600:  # 1小时保护期
                    culling_analysis["protection_summary"]["learned_paths_protected"] += 1
        
        return culling_analysis
    
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """分析性能趋势"""
        trends = {
            "overall_system_health": "healthy",
            "avg_success_rate": 0.0,
            "performance_distribution": {
                "excellent": 0,    # > 0.8
                "good": 0,         # 0.6-0.8
                "average": 0,      # 0.4-0.6
                "poor": 0,         # < 0.4
                "critical": 0      # < 0.2
            },
            "activation_distribution": {
                "highly_used": 0,     # > 100 activations
                "moderately_used": 0, # 20-100 activations
                "lightly_used": 0,    # 5-20 activations
                "rarely_used": 0      # < 5 activations
            },
            "trend_indicators": {
                "paths_improving": 0,
                "paths_declining": 0,
                "stable_paths": 0
            }
        }
        
        if not self.path_arms:
            return trends
        
        success_rates = []
        
        for strategy_id, arm in self.path_arms.items():
            success_rate = arm.success_rate
            success_rates.append(success_rate)
            
            # 性能分布
            if success_rate >= 0.8:
                trends["performance_distribution"]["excellent"] += 1
            elif success_rate >= 0.6:
                trends["performance_distribution"]["good"] += 1
            elif success_rate >= 0.4:
                trends["performance_distribution"]["average"] += 1
            elif success_rate >= 0.2:
                trends["performance_distribution"]["poor"] += 1
            else:
                trends["performance_distribution"]["critical"] += 1
            
            # 使用频率分布
            if arm.activation_count > 100:
                trends["activation_distribution"]["highly_used"] += 1
            elif arm.activation_count >= 20:
                trends["activation_distribution"]["moderately_used"] += 1
            elif arm.activation_count >= 5:
                trends["activation_distribution"]["lightly_used"] += 1
            else:
                trends["activation_distribution"]["rarely_used"] += 1
        
        trends["avg_success_rate"] = sum(success_rates) / len(success_rates)
        
        # 系统健康评估
        poor_performance_ratio = (trends["performance_distribution"]["poor"] + 
                                trends["performance_distribution"]["critical"]) / len(self.path_arms)
        
        if poor_performance_ratio > 0.4:
            trends["overall_system_health"] = "critical"
        elif poor_performance_ratio > 0.2:
            trends["overall_system_health"] = "degraded"
        elif trends["avg_success_rate"] > 0.7:
            trends["overall_system_health"] = "excellent"
        else:
            trends["overall_system_health"] = "healthy"
        
        return trends
    
    def _analyze_golden_candidates(self) -> Dict[str, Any]:
        """分析黄金模板候选情况"""
        golden_analysis = {
            "current_golden_count": len(self.golden_templates),
            "promotion_candidates": [],
            "golden_performance": {
                "avg_success_rate": 0.0,
                "total_activations": 0,
                "stability_score": 0.0
            }
        }
        
        # 分析提升候选
        for strategy_id in self.trial_ground["promotion_candidates"]:
            if strategy_id in self.path_arms:
                arm = self.path_arms[strategy_id]
                golden_analysis["promotion_candidates"].append({
                    "strategy_id": strategy_id,
                    "success_rate": arm.success_rate,
                    "activations": arm.activation_count,
                    "stability": arm.get_stability_score() if hasattr(arm, 'get_stability_score') else 0.0,
                    "is_learned_path": self.is_learned_path(strategy_id),
                    "qualification_score": self._calculate_golden_qualification_score(strategy_id, arm)
                })
        
        # 分析现有黄金模板性能
        if self.golden_templates:
            golden_success_rates = []
            golden_activations = 0
            
            for strategy_id in self.golden_templates:
                if strategy_id in self.path_arms:
                    arm = self.path_arms[strategy_id]
                    golden_success_rates.append(arm.success_rate)
                    golden_activations += arm.activation_count
            
            if golden_success_rates:
                golden_analysis["golden_performance"]["avg_success_rate"] = sum(golden_success_rates) / len(golden_success_rates)
                golden_analysis["golden_performance"]["total_activations"] = golden_activations
                golden_analysis["golden_performance"]["stability_score"] = min(golden_success_rates)  # 最低成功率作为稳定性指标
        
        return golden_analysis
    
    def _calculate_golden_qualification_score(self, strategy_id: str, arm: EnhancedDecisionArm) -> float:
        """
        计算黄金模板资格评分
        
        Args:
            strategy_id: 策略ID
            arm: 决策臂对象
            
        Returns:
            资格评分 (0-1之间)
        """
        # 基础成功率权重 (40%)
        success_score = arm.success_rate * 0.4
        
        # 使用频率权重 (20%)
        frequency_score = min(arm.activation_count / 100, 1.0) * 0.2
        
        # 稳定性权重 (20%) - 基于最近表现的方差
        stability_score = 0.0
        if arm.recent_results and len(arm.recent_results) >= 5:
            recent_success_rate = sum(arm.recent_results[-10:]) / min(len(arm.recent_results), 10)
            # 稳定性 = 1 - |总体成功率 - 最近成功率|
            stability_score = max(0, 1 - abs(arm.success_rate - recent_success_rate)) * 0.2
        
        # 学习路径加分 (10%) - 鼓励从探索中学到的优秀路径
        learning_bonus = 0.1 if self.is_learned_path(strategy_id) and arm.success_rate > 0.7 else 0.0
        
        # 时间衰减 (10%) - 新路径需要更多验证时间
        if strategy_id in self.trial_ground["learned_paths"]:
            learned_meta = self.trial_ground["learned_paths"][strategy_id]
            trial_duration = time.time() - learned_meta.get("trial_start_time", time.time())
            time_score = min(trial_duration / (24 * 3600), 1.0) * 0.1  # 24小时达到满分
        else:
            time_score = 0.1  # 静态路径给满分
        
        return success_score + frequency_score + stability_score + learning_bonus + time_score
    
    # 🎭 试炼场管理和维护方法
    
    def trigger_trial_ground_maintenance(self) -> Dict[str, Any]:
        """
        🔧 触发试炼场维护任务
        
        Returns:
            维护结果摘要
        """
        maintenance_result = {
            "timestamp": time.time(),
            "tasks_executed": [],
            "cleanup_results": {},
            "analytics_snapshot": {}
        }
        
        logger.info("🔧 开始试炼场维护任务...")
        
        # 1. 执行自动淘汰检查
        try:
            culling_results = self.execute_automatic_culling()
            maintenance_result["tasks_executed"].append("automatic_culling")
            maintenance_result["cleanup_results"]["culling"] = culling_results
            logger.info(f"✅ 自动淘汰检查完成: 淘汰 {len(culling_results.get('paths_culled', []))} 个路径")
        except Exception as e:
            logger.error(f"❌ 自动淘汰检查失败: {e}")
            maintenance_result["cleanup_results"]["culling"] = {"error": str(e)}
        
        # 2. 清理过期的探索增强
        try:
            expired_boosts = self._cleanup_expired_exploration_boosts()
            maintenance_result["tasks_executed"].append("boost_cleanup")
            maintenance_result["cleanup_results"]["expired_boosts"] = expired_boosts
            logger.info(f"✅ 探索增强清理完成: 清理 {expired_boosts['cleaned_count']} 个过期增强")
        except Exception as e:
            logger.error(f"❌ 探索增强清理失败: {e}")
            maintenance_result["cleanup_results"]["expired_boosts"] = {"error": str(e)}
        
        # 3. 管理淘汰历史记录大小
        try:
            history_cleanup = self._manage_culled_history()
            maintenance_result["tasks_executed"].append("history_management")
            maintenance_result["cleanup_results"]["history"] = history_cleanup
            if history_cleanup.get("trimmed", 0) > 0:
                logger.info(f"✅ 淘汰历史管理完成: 修剪 {history_cleanup['trimmed']} 条记录")
        except Exception as e:
            logger.error(f"❌ 淘汰历史管理失败: {e}")
            maintenance_result["cleanup_results"]["history"] = {"error": str(e)}
        
        # 4. 生成分析快照
        try:
            analytics_snapshot = self.get_trial_ground_analytics()
            maintenance_result["tasks_executed"].append("analytics_snapshot")
            maintenance_result["analytics_snapshot"] = analytics_snapshot
            logger.info("✅ 分析快照生成完成")
        except Exception as e:
            logger.error(f"❌ 分析快照生成失败: {e}")
            maintenance_result["analytics_snapshot"] = {"error": str(e)}
        
        logger.info(f"🔧 试炼场维护完成，执行了 {len(maintenance_result['tasks_executed'])} 个任务")
        
        return maintenance_result
    
    def _cleanup_expired_exploration_boosts(self) -> Dict[str, Any]:
        """清理过期的探索增强"""
        cleanup_result = {
            "cleaned_count": 0,
            "expired_paths": []
        }
        
        expired_paths = []
        for strategy_id, remaining_rounds in list(self.trial_ground["exploration_boost_active"].items()):
            if remaining_rounds <= 0:
                expired_paths.append(strategy_id)
        
        for strategy_id in expired_paths:
            del self.trial_ground["exploration_boost_active"][strategy_id]
            cleanup_result["expired_paths"].append(strategy_id)
        
        cleanup_result["cleaned_count"] = len(expired_paths)
        return cleanup_result
    
    def _manage_culled_history(self) -> Dict[str, Any]:
        """管理淘汰历史记录大小"""
        history_result = {
            "current_count": len(self.trial_ground["culled_paths"]),
            "max_allowed": self.trial_config["max_culled_history"],
            "trimmed": 0
        }
        
        if history_result["current_count"] > history_result["max_allowed"]:
            # 只保留最新的记录
            excess = history_result["current_count"] - history_result["max_allowed"]
            self.trial_ground["culled_paths"] = self.trial_ground["culled_paths"][-history_result["max_allowed"]:]
            history_result["trimmed"] = excess
            
            logger.info(f"📚 淘汰历史记录修剪: 保留最新 {history_result['max_allowed']} 条, 删除 {excess} 条旧记录")
        
        return history_result
    
    def reset_path_trial_status(self, strategy_id: str) -> Dict[str, Any]:
        """
        🔄 重置指定路径的试炼状态
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            重置结果
        """
        reset_result = {
            "strategy_id": strategy_id,
            "actions_taken": [],
            "success": False
        }
        
        try:
            # 从各种候选名单中移除
            if strategy_id in self.trial_ground["culling_candidates"]:
                self.trial_ground["culling_candidates"].remove(strategy_id)
                reset_result["actions_taken"].append("removed_from_culling_candidates")
            
            if strategy_id in self.trial_ground["promotion_candidates"]:
                self.trial_ground["promotion_candidates"].remove(strategy_id)
                reset_result["actions_taken"].append("removed_from_promotion_candidates")
            
            # 重置监控数据
            if strategy_id in self.trial_ground["performance_watch_list"]:
                del self.trial_ground["performance_watch_list"][strategy_id]
                reset_result["actions_taken"].append("cleared_watch_list_entry")
            
            # 重置探索增强
            if strategy_id in self.trial_ground["exploration_boost_active"]:
                del self.trial_ground["exploration_boost_active"][strategy_id]
                reset_result["actions_taken"].append("cleared_exploration_boost")
            
            # 重置决策臂统计（如果存在）
            if strategy_id in self.path_arms:
                arm = self.path_arms[strategy_id]
                # 保留基本结构，但重置统计
                arm.success_count = 0
                arm.failure_count = 0
                arm.total_reward = 0.0
                arm.recent_results = []
                arm.activation_count = 0
                reset_result["actions_taken"].append("reset_decision_arm_stats")
            
            reset_result["success"] = True
            logger.info(f"🔄 路径 {strategy_id} 试炼状态已重置: {', '.join(reset_result['actions_taken'])}")
            
        except Exception as e:
            reset_result["error"] = str(e)
            logger.error(f"❌ 重置路径 {strategy_id} 试炼状态失败: {e}")
        
        return reset_result
    
    def force_promote_to_golden(self, strategy_id: str, reason: str = "manual_promotion") -> Dict[str, Any]:
        """
        🏆 强制提升路径为黄金模板
        
        Args:
            strategy_id: 策略ID
            reason: 提升原因
            
        Returns:
            提升结果
        """
        promotion_result = {
            "strategy_id": strategy_id,
            "reason": reason,
            "success": False,
            "previous_status": {}
        }
        
        try:
            if strategy_id not in self.path_arms:
                promotion_result["error"] = "策略ID不存在"
                return promotion_result
            
            # 记录之前的状态
            arm = self.path_arms[strategy_id]
            promotion_result["previous_status"] = {
                "success_rate": arm.success_rate,
                "activations": arm.activation_count,
                "was_golden": strategy_id in self.golden_templates
            }
            
            # 执行提升
            if strategy_id not in self.golden_templates:
                self.golden_templates.add(strategy_id)
                logger.info(f"🏆 路径 {strategy_id} 已被强制提升为黄金模板: {reason}")
                
                # 从候选名单中移除
                self.trial_ground["promotion_candidates"].discard(strategy_id)
                self.trial_ground["culling_candidates"].discard(strategy_id)
                
                # 记录提升历史
                if "promotion_history" not in self.trial_ground:
                    self.trial_ground["promotion_history"] = []
                
                self.trial_ground["promotion_history"].append({
                    "strategy_id": strategy_id,
                    "promoted_at": time.time(),
                    "reason": reason,
                    "promotion_type": "manual_force",
                    "stats_at_promotion": {
                        "success_rate": arm.success_rate,
                        "activations": arm.activation_count
                    }
                })
                
                promotion_result["success"] = True
            else:
                promotion_result["error"] = "路径已经是黄金模板"
                logger.warning(f"⚠️ 路径 {strategy_id} 已经是黄金模板，无需重复提升")
        
        except Exception as e:
            promotion_result["error"] = str(e)
            logger.error(f"❌ 强制提升路径 {strategy_id} 失败: {e}")
        
        return promotion_result
    
    def revoke_golden_status(self, strategy_id: str, reason: str = "manual_revocation") -> Dict[str, Any]:
        """
        🔻 撤销黄金模板状态
        
        Args:
            strategy_id: 策略ID
            reason: 撤销原因
            
        Returns:
            撤销结果
        """
        revocation_result = {
            "strategy_id": strategy_id,
            "reason": reason,
            "success": False
        }
        
        try:
            if strategy_id in self.golden_templates:
                self.golden_templates.remove(strategy_id)
                logger.info(f"🔻 路径 {strategy_id} 的黄金模板状态已撤销: {reason}")
                
                # 记录撤销历史
                if "revocation_history" not in self.trial_ground:
                    self.trial_ground["revocation_history"] = []
                
                arm = self.path_arms.get(strategy_id)
                self.trial_ground["revocation_history"].append({
                    "strategy_id": strategy_id,
                    "revoked_at": time.time(),
                    "reason": reason,
                    "stats_at_revocation": {
                        "success_rate": arm.success_rate if arm else 0.0,
                        "activations": arm.activation_count if arm else 0
                    }
                })
                
                revocation_result["success"] = True
            else:
                revocation_result["error"] = "路径不是黄金模板"
                logger.warning(f"⚠️ 路径 {strategy_id} 不是黄金模板，无法撤销")
        
        except Exception as e:
            revocation_result["error"] = str(e)
            logger.error(f"❌ 撤销路径 {strategy_id} 黄金状态失败: {e}")
        
        return revocation_result
    
    def _calculate_path_similarity(self, path1_type: str, path2_type: str) -> float:
        """
        计算两个路径类型之间的相似度
        
        Args:
            path1_type: 第一个路径类型
            path2_type: 第二个路径类型
            
        Returns:
            相似度分数 (0.0-1.0)，1.0表示完全相似
        """
        # 相似度矩阵：定义不同路径类型之间的相似程度
        similarity_matrix = {
            # 系统分析型相似度
            ("系统分析型", "整体综合型"): 0.8,
            ("系统分析型", "探索调研型"): 0.6,
            ("系统分析型", "批判质疑型"): 0.5,
            
            # 创新突破型相似度
            ("创新突破型", "适应灵活型"): 0.7,
            ("创新突破型", "探索调研型"): 0.6,
            
            # 批判质疑型相似度
            ("批判质疑型", "探索调研型"): 0.5,
            ("批判质疑型", "系统分析型"): 0.5,
            
            # 实用务实型相似度
            ("实用务实型", "适应灵活型"): 0.6,
            ("实用务实型", "系统分析型"): 0.4,
            
            # 整体综合型相似度
            ("整体综合型", "协作咨询型"): 0.7,
            ("整体综合型", "系统分析型"): 0.8,
            
            # 探索调研型相似度
            ("探索调研型", "批判质疑型"): 0.5,
            ("探索调研型", "创新突破型"): 0.6,
            
            # 协作咨询型相似度
            ("协作咨询型", "整体综合型"): 0.7,
            ("协作咨询型", "适应灵活型"): 0.5,
            
            # 适应灵活型相似度
            ("适应灵活型", "创新突破型"): 0.7,
            ("适应灵活型", "实用务实型"): 0.6,
        }
        
        # 相同类型完全相似
        if path1_type == path2_type:
            return 1.0
        
        # 查找相似度（支持双向查找）
        key1 = (path1_type, path2_type)
        key2 = (path2_type, path1_type)
        
        similarity = similarity_matrix.get(key1) or similarity_matrix.get(key2)
        
        # 如果没有定义相似度，默认为低相似
        return similarity if similarity is not None else 0.3
    
    def select_top_k_paths(self, paths: List[ReasoningPath], k: int = 2, 
                          algorithm: str = 'auto',
                          diversity_threshold: float = 0.7) -> List[ReasoningPath]:
        """
        🎯 新方案三核心方法：选择Top-K条优质且多样化的路径（分层输出策略）
        
        此方法支持分层输出架构：
        - 选择k条最优路径
        - 确保路径之间具有足够的多样性
        - 支持黄金模板优先机制
        
        Args:
            paths: 候选思维路径列表
            k: 需要选择的路径数量（默认2条：主路径+补充路径）
            algorithm: MAB算法类型 ('thompson_sampling', 'ucb_variant', 'epsilon_greedy', 'auto')
            diversity_threshold: 多样性阈值，相似度超过此值的路径会被过滤 (0.0-1.0)
            
        Returns:
            选择的k条优质路径列表，按置信度降序排列
            - 第一条：主路径（最优）
            - 其余：补充路径（按质量排序）
        """
        if not paths:
            raise ValueError("路径列表不能为空")
        
        # 如果请求的路径数量大于等于候选路径数量，返回所有路径
        if k >= len(paths):
            logger.info(f"🎯 请求{k}条路径，但只有{len(paths)}条候选，返回所有路径")
            return paths
        
        self.total_path_selections += 1
        logger.info(f"🎯 开始分层路径选择（第{self.total_path_selections}次）")
        logger.info(f"   目标: 选择{k}条多样化优质路径")
        logger.info(f"   候选路径: {len(paths)}条")
        logger.info(f"   多样性阈值: {diversity_threshold}")
        
        # 🏆 黄金模板优先检查
        golden_match = self._check_golden_template_match(paths)
        selected_paths = []
        
        if golden_match:
            # 黄金模板路径直接作为主路径
            golden_path = golden_match['path']
            template_id = golden_match['template_id']
            
            selected_paths.append(golden_path)
            
            # 更新黄金模板统计
            self.template_usage_stats[template_id] += 1
            self.template_match_history.append({
                'template_id': template_id,
                'path_id': golden_path.path_id,
                'path_type': golden_path.path_type,
                'match_score': golden_match['match_score'],
                'timestamp': time.time(),
                'selection_round': self.total_path_selections
            })
            
            logger.info(f"🏆 黄金模板作为主路径: {golden_path.path_type}")
            
            # 从候选中移除黄金路径，继续选择补充路径
            remaining_paths = [p for p in paths if p.path_id != golden_path.path_id]
        else:
            remaining_paths = paths
        
        # 🔧 准备MAB决策臂和路径评分
        path_scores = []  # (score, path, arm)
        strategy_to_path_mapping = {}
        
        for path in remaining_paths:
            strategy_id = path.strategy_id
            strategy_to_path_mapping[strategy_id] = path
            
            # 创建或获取决策臂
            arm = self._create_strategy_arm_if_missing(strategy_id, path.path_type)
            
            # 使用MAB算法计算路径评分
            if algorithm == 'auto':
                algorithm = self._select_best_algorithm_for_paths()
            
            try:
                # 计算路径得分（使用各自的MAB算法）
                if algorithm == 'thompson_sampling':
                    score = self._calculate_thompson_score(arm)
                elif algorithm == 'ucb_variant':
                    score = self._calculate_ucb_score(arm)
                elif algorithm == 'epsilon_greedy':
                    score = self._calculate_epsilon_greedy_score(arm)
                else:
                    score = self._calculate_thompson_score(arm)
                
                path_scores.append((score, path, arm))
                
            except Exception as e:
                logger.warning(f"⚠️ 计算路径 {path.path_type} 评分失败: {e}")
                # 使用默认分数
                path_scores.append((0.5, path, arm))
        
        # 按分数降序排序
        path_scores.sort(reverse=True, key=lambda x: x[0])
        
        logger.info(f"📊 路径评分完成，排序结果:")
        for i, (score, path, _) in enumerate(path_scores[:5], 1):  # 只显示前5名
            logger.info(f"   {i}. {path.path_type}: {score:.3f}")
        
        # 🎨 多样性过滤：选择多样化的Top-K路径
        for score, path, arm in path_scores:
            if len(selected_paths) >= k:
                break
            
            # 检查与已选路径的相似度
            is_diverse = True
            for selected_path in selected_paths:
                similarity = self._calculate_path_similarity(
                    path.path_type, 
                    selected_path.path_type
                )
                
                if similarity >= diversity_threshold:
                    is_diverse = False
                    logger.debug(f"   🔄 路径 {path.path_type} 与 {selected_path.path_type} 相似度过高({similarity:.2f})，跳过")
                    break
            
            if is_diverse or len(selected_paths) == 0:
                selected_paths.append(path)
                
                # 更新决策臂统计
                arm.last_used = time.time()
                arm.activation_count += 1
                self._update_exploration_boost(arm.path_id)
                
                logger.info(f"✅ 选中路径 {len(selected_paths)}/{k}: {path.path_type} (评分: {score:.3f})")
        
        # 如果多样性过滤后路径不足k条，补充分数较高的路径
        if len(selected_paths) < k:
            logger.info(f"⚠️ 多样性过滤后仅{len(selected_paths)}条路径，放宽标准补充路径")
            for score, path, arm in path_scores:
                if len(selected_paths) >= k:
                    break
                if path not in selected_paths:
                    selected_paths.append(path)
                    arm.last_used = time.time()
                    arm.activation_count += 1
                    logger.info(f"   补充路径: {path.path_type} (评分: {score:.3f})")
        
        # 记录选择历史
        for i, path in enumerate(selected_paths):
            self.path_selection_history.append({
                'path_id': path.strategy_id,
                'path_type': path.path_type,
                'algorithm': algorithm,
                'rank': i + 1,  # 1=主路径, 2+=补充路径
                'is_primary': (i == 0),
                'timestamp': time.time(),
                'selection_round': self.total_path_selections
            })
        
        logger.info(f"🎯 分层路径选择完成:")
        logger.info(f"   主路径: {selected_paths[0].path_type}")
        if len(selected_paths) > 1:
            supplementary_types = [p.path_type for p in selected_paths[1:]]
            logger.info(f"   补充路径: {', '.join(supplementary_types)}")
        
        return selected_paths
    
    def _calculate_thompson_score(self, arm) -> float:
        """计算Thompson采样得分"""
        alpha = arm.success_count + 1
        beta = arm.failure_count + 1
        return np.random.beta(alpha, beta)
    
    def _calculate_ucb_score(self, arm) -> float:
        """计算UCB得分"""
        if arm.trials == 0:
            return float('inf')
        
        mean_reward = arm.total_reward / arm.trials
        exploration_bonus = np.sqrt(2 * np.log(self.total_path_selections) / arm.trials)
        return mean_reward + exploration_bonus
    
    def _calculate_epsilon_greedy_score(self, arm) -> float:
        """计算ε-贪心得分"""
        if arm.trials == 0:
            return np.random.random()
        
        epsilon = max(0.1, 1.0 / np.sqrt(self.total_path_selections))
        if np.random.random() < epsilon:
            return np.random.random()
        else:
            return arm.total_reward / arm.trials
    
    def select_best_path(self, paths: List[ReasoningPath], algorithm: str = 'auto') -> ReasoningPath:
        """
        🔄 向后兼容方法：选择单一最优路径
        
        ⚠️ 已弃用：此方法保留仅用于向后兼容
        推荐使用: select_top_k_paths() 方法以获得分层输出能力
        
        Args:
            paths: 思维路径列表
            algorithm: 使用的算法 ('thompson_sampling', 'ucb_variant', 'epsilon_greedy', 'auto')
            
        Returns:
            选择的最优思维路径（仅返回第一条）
        """
        logger.debug("⚠️ 调用已弃用的 select_best_path 方法，建议使用 select_top_k_paths")
        
        # 调用新的分层选择方法，只返回第一条（主路径）
        selected_paths = self.select_top_k_paths(paths, k=1, algorithm=algorithm)
        return selected_paths[0]
    
    def select_best_tool(self, available_tools: List[str], algorithm: str = 'auto') -> str:
        """
        🔧 新增：从可用工具列表中选择最优工具
        
        Args:
            available_tools: 可用工具名称列表
            algorithm: 使用的算法 ('thompson_sampling', 'ucb_variant', 'epsilon_greedy', 'auto')
            
        Returns:
            选择的最优工具名称
        """
        if not available_tools:
            raise ValueError("工具列表不能为空")
        
        if len(available_tools) == 1:
            logger.info(f"🔧 只有一个工具，直接选择: {available_tools[0]}")
            return available_tools[0]
        
        self.total_tool_selections += 1
        logger.info(f"🔧 开始第 {self.total_tool_selections} 次工具选择，候选工具: {len(available_tools)}个")
        
        # 🔧 动态创建：确保所有工具的决策臂都存在
        available_arms = []
        tool_to_arm_mapping = {}  # 工具名称到决策臂的映射
        
        for tool_name in available_tools:
            tool_id = tool_name  # 使用工具名称作为ID
            tool_to_arm_mapping[tool_name] = tool_id
            
            # 🔧 动态创建：确保工具决策臂存在
            arm = self._create_tool_arm_if_missing(tool_id, tool_name)
            available_arms.append(arm)
            
            logger.debug(f"✅ 工具决策臂就绪: {tool_id} ({tool_name})")
        
        # 自动选择算法
        if algorithm == 'auto':
            algorithm = self._select_best_algorithm_for_tools()
        
        # 根据选择的算法进行决策
        try:
            if algorithm == 'thompson_sampling':
                best_arm = self._thompson_sampling_for_tools(available_arms)
            elif algorithm == 'ucb_variant':
                best_arm = self._ucb_variant_for_tools(available_arms)
            elif algorithm == 'epsilon_greedy':
                best_arm = self._epsilon_greedy_for_tools(available_arms)
            else:
                logger.warning(f"⚠️ 未知算法 {algorithm}，使用Thompson采样")
                best_arm = self._thompson_sampling_for_tools(available_arms)
            
            # 更新使用时间和激活次数
            best_arm.last_used = time.time()
            best_arm.activation_count += 1
            
            # 🎯 找到对应的工具名称
            selected_tool = best_arm.option  # 工具名称存储在option字段中
            
            # 记录选择历史
            self.tool_selection_history.append({
                'tool_id': best_arm.path_id,
                'tool_name': selected_tool,
                'algorithm': algorithm,
                'timestamp': time.time(),
                'selection_round': self.total_tool_selections
            })
            
            logger.info(f"🔧 使用 {algorithm} 选择工具: {selected_tool} (ID: {best_arm.path_id})")
            return selected_tool
            
        except Exception as e:
            logger.error(f"❌ MAB工具选择算法执行失败: {e}")
            # 回退到随机选择
            selected_tool = np.random.choice(available_tools)
            logger.info(f"🔄 回退到随机选择工具: {selected_tool}")
            return selected_tool
    
    def is_tool_cold(self, tool_name: str) -> Dict[str, any]:
        """
        🔍 判断工具是否处于冷启动状态
        
        这个方法是MABConverger的"自我认知"能力，当MainController询问时，
        它能明确回答："我推荐的这个工具，我自己熟不熟？"
        
        Args:
            tool_name: 工具名称
            
        Returns:
            Dict包含详细的冷启动分析结果:
            {
                'is_cold_start': bool,      # 是否处于冷启动状态
                'cold_score': float,        # 冷启动得分 (0-1, 越高越"冷")
                'confidence': float,        # 经验可信度 (0-1, 越高越可信)
                'analysis': {
                    'usage_count': int,     # 使用次数
                    'reliability_score': float,  # 可靠性分数
                    'idle_hours': float,    # 空闲时间(小时)
                    'sample_size': int      # 样本数量
                },
                'recommendation': str,      # 推荐模式 ('experience'/'exploration')
                'reason': str              # 判断理由
            }
        """
        logger.debug(f"🔍 开始冷启动检测: 工具 '{tool_name}'")
        
        # 获取冷启动配置
        cold_start_config = MAB_CONFIG["cold_start_threshold"]
        detection_weights = cold_start_config["detection_weights"]
        
        # 获取工具的决策臂
        tool_arm = self.tool_arms.get(tool_name)
        
        if not tool_arm:
            # 完全未使用的工具 - 绝对冷启动
            logger.debug(f"🆕 工具 '{tool_name}' 从未使用过，判定为冷启动")
            return {
                'is_cold_start': True,
                'cold_score': 1.0,
                'confidence': 0.0,
                'analysis': {
                    'usage_count': 0,
                    'reliability_score': 0.0,
                    'idle_hours': float('inf'),
                    'sample_size': 0
                },
                'recommendation': 'exploration',
                'reason': '工具从未被使用过，无任何经验数据'
            }
        
        # 计算各个冷启动因子
        analysis = self._calculate_cold_start_factors(tool_arm, cold_start_config)
        
        # 计算加权冷启动得分
        cold_score = (
            analysis['usage_factor'] * detection_weights['usage_frequency'] +
            analysis['reliability_factor'] * detection_weights['reliability'] +
            analysis['recency_factor'] * detection_weights['recency'] +
            analysis['sample_factor'] * detection_weights['sample_sufficiency']
        )
        
        # 判定是否冷启动
        exploration_threshold = cold_start_config["exploration_trigger_threshold"]
        is_cold = cold_score > exploration_threshold
        
        # 生成判断理由
        reason = self._generate_cold_start_reason(analysis, cold_score, exploration_threshold)
        
        result = {
            'is_cold_start': is_cold,
            'cold_score': round(cold_score, 3),
            'confidence': round(1.0 - cold_score, 3),
            'analysis': {
                'usage_count': analysis['usage_count'],
                'reliability_score': round(analysis['reliability_score'], 3),
                'idle_hours': round(analysis['idle_hours'], 2),
                'sample_size': analysis['sample_size']
            },
            'recommendation': 'exploration' if is_cold else 'experience',
            'reason': reason
        }
        
        logger.info(f"🔍 冷启动检测完成: {tool_name} -> "
                   f"{'冷启动' if is_cold else '经验丰富'} "
                   f"(得分: {cold_score:.3f}, 置信度: {result['confidence']:.3f})")
        
        return result
    
    def _calculate_cold_start_factors(self, tool_arm: EnhancedDecisionArm, 
                                    cold_start_config: Dict[str, any]) -> Dict[str, any]:
        """
        计算冷启动各个因子
        
        Args:
            tool_arm: 工具决策臂
            cold_start_config: 冷启动配置
            
        Returns:
            包含各个因子的分析结果
        """
        current_time = time.time()
        
        # 1. 使用频率因子 (使用次数越少，分数越高)
        usage_count = tool_arm.activation_count
        min_usage = cold_start_config["min_usage_count"]
        usage_factor = max(0.0, 1.0 - usage_count / max(min_usage, 1))
        
        # 2. 可靠性因子 (成功率不稳定或样本少时分数高)
        total_samples = tool_arm.success_count + tool_arm.failure_count
        if total_samples >= 3:
            reliability_score = tool_arm.success_rate
            # 样本数调整：样本越少，可靠性越低
            sample_adjustment = min(1.0, total_samples / 10.0)  # 10个样本视为充足
            adjusted_reliability = reliability_score * sample_adjustment
        else:
            adjusted_reliability = 0.0  # 样本太少，不可靠
        
        min_reliability = cold_start_config["min_reliability_score"]
        reliability_factor = max(0.0, 1.0 - adjusted_reliability / max(min_reliability, 0.1))
        
        # 3. 最近使用因子 (时间越久，分数越高)
        if tool_arm.last_used > 0:
            idle_hours = (current_time - tool_arm.last_used) / 3600
        else:
            idle_hours = float('inf')
        
        max_idle = cold_start_config["max_idle_hours"]
        recency_factor = min(1.0, idle_hours / max(max_idle, 1))
        
        # 4. 样本充足性因子 (样本越少，分数越高)
        min_samples = cold_start_config["min_sample_size"]
        sample_factor = max(0.0, 1.0 - total_samples / max(min_samples, 1))
        
        return {
            'usage_count': usage_count,
            'usage_factor': usage_factor,
            'reliability_score': adjusted_reliability,
            'reliability_factor': reliability_factor,
            'idle_hours': idle_hours if idle_hours != float('inf') else -1,
            'recency_factor': recency_factor,
            'sample_size': total_samples,
            'sample_factor': sample_factor
        }
    
    def _generate_cold_start_reason(self, analysis: Dict[str, any], 
                                   cold_score: float, threshold: float) -> str:
        """
        生成冷启动判断的详细理由
        
        Args:
            analysis: 分析结果
            cold_score: 冷启动得分
            threshold: 判定阈值
            
        Returns:
            判断理由字符串
        """
        reasons = []
        
        # 使用频率分析
        if analysis['usage_factor'] > 0.7:
            reasons.append(f"使用次数过少({analysis['usage_count']}次)")
        elif analysis['usage_factor'] > 0.3:
            reasons.append(f"使用经验有限({analysis['usage_count']}次)")
        
        # 可靠性分析
        if analysis['reliability_factor'] > 0.6:
            reasons.append(f"性能数据不可靠(可靠性:{analysis['reliability_score']:.2f})")
        elif analysis['reliability_factor'] > 0.3:
            reasons.append(f"性能数据不够稳定")
        
        # 最近使用分析
        if analysis['idle_hours'] > 72:
            reasons.append(f"长时间未使用({analysis['idle_hours']:.1f}小时)")
        elif analysis['idle_hours'] > 24:
            reasons.append(f"较长时间未使用")
        
        # 样本数分析
        if analysis['sample_factor'] > 0.7:
            reasons.append(f"样本数据不足({analysis['sample_size']}个)")
        
        if not reasons:
            if cold_score > threshold:
                reasons.append("综合评估显示缺乏足够经验")
            else:
                reasons.append("具有充足的使用经验和可靠数据")
        
        # 组合理由
        if cold_score > threshold:
            return f"冷启动状态: {'; '.join(reasons)} (得分:{cold_score:.3f} > {threshold})"
        else:
            return f"经验丰富: {'; '.join(reasons)} (得分:{cold_score:.3f} ≤ {threshold})"
    
    def _thompson_sampling_for_paths(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对思维路径的Thompson采样算法 - 🌟 增强版：支持探索增强"""
        if not arms:
            raise ValueError("没有可用的路径决策臂")
        
        best_arm = None
        best_score = -1
        
        logger.debug(f"🎲 Thompson采样路径选择，候选路径: {len(arms)}个")
        
        for arm in arms:
            # 使用Beta分布进行Thompson采样
            alpha = arm.success_count + 1
            beta = arm.failure_count + 1
            
            # 从Beta分布中采样
            sampled_value = np.random.beta(alpha, beta)
            
            # 路径级别的奖励考虑
            if arm.rl_reward_history:
                avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                # 将奖励调整到0-1范围
                normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                sampled_value = sampled_value * 0.8 + normalized_reward * 0.2
            
            # 🌟 探索增强：为新学习路径提供额外机会
            exploration_boost = self.get_exploration_boost(arm.path_id)
            if exploration_boost > 1.0:
                sampled_value *= exploration_boost
                logger.debug(f"   🚀 路径 {arm.path_id} 获得探索增强: {exploration_boost:.3f}x")
            
            # 路径多样性考虑：减少过度依赖单一路径
            usage_penalty = min(0.1, arm.activation_count / (self.total_path_selections + 1) * 0.2)
            sampled_value = max(0, sampled_value - usage_penalty)
            
            logger.debug(f"   路径 {arm.path_id}: sampled={sampled_value:.3f}, α={alpha}, β={beta}, boost={exploration_boost:.3f}")
            
            if sampled_value > best_score:
                best_score = sampled_value
                best_arm = arm
        
        logger.debug(f"🏆 Thompson采样选择: {best_arm.path_id} (得分: {best_score:.3f})")
        return best_arm
    
    def _ucb_variant_for_paths(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对思维路径的UCB (Upper Confidence Bound) 变种算法 - 🌟 增强版：支持探索增强"""
        if not arms:
            raise ValueError("没有可用的路径决策臂")
        
        total_rounds = sum(arm.activation_count for arm in arms)
        if total_rounds == 0:
            # 第一轮随机选择
            selected_arm = np.random.choice(arms)
            logger.debug(f"🎲 UCB首轮随机选择路径: {selected_arm.path_id}")
            return selected_arm
        
        best_arm = None
        best_ucb_value = -float('inf')
        
        logger.debug(f"📊 UCB路径选择，总轮数: {total_rounds}")
        
        for arm in arms:
            if arm.activation_count == 0:
                # 未尝试过的路径优先选择，学习路径享有更高优先级
                exploration_boost = self.get_exploration_boost(arm.path_id)
                if exploration_boost > 1.0:
                    logger.debug(f"🆕🚀 优先选择未使用的学习路径: {arm.path_id} (增强: {exploration_boost:.3f}x)")
                else:
                    logger.debug(f"🆕 优先选择未使用路径: {arm.path_id}")
                return arm
            
            # 计算UCB值
            confidence_bound = np.sqrt(2 * np.log(total_rounds) / arm.activation_count)
            
            # 基础成功率
            base_value = arm.success_rate
            
            # 路径级别的RL奖励考虑
            if arm.rl_reward_history:
                avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                base_value = base_value * 0.7 + normalized_reward * 0.3
            
            # 🌟 探索增强：为新学习路径提供额外UCB奖励
            exploration_boost = self.get_exploration_boost(arm.path_id)
            if exploration_boost > 1.0:
                base_value *= exploration_boost
                logger.debug(f"   🚀 路径 {arm.path_id} 获得UCB探索增强: {exploration_boost:.3f}x")
            
            # 路径探索奖励：鼓励尝试不同思维方式
            exploration_bonus = confidence_bound * 1.2  # 增强探索
            ucb_value = base_value + exploration_bonus
            
            logger.debug(f"   路径 {arm.path_id}: UCB={ucb_value:.3f}, base={base_value:.3f}, conf={confidence_bound:.3f}, boost={exploration_boost:.3f}")
            
            if ucb_value > best_ucb_value:
                best_ucb_value = ucb_value
                best_arm = arm
        
        logger.debug(f"🏆 UCB选择路径: {best_arm.path_id} (UCB值: {best_ucb_value:.3f})")
        return best_arm
    
    def _epsilon_greedy_for_paths(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对思维路径的Epsilon-Greedy算法 - 🌟 增强版：支持探索增强"""
        if not arms:
            raise ValueError("没有可用的路径决策臂")
        
        # 路径级别的动态epsilon值，鼓励思维多样性
        total_activations = sum(arm.activation_count for arm in arms)
        epsilon = max(0.1, 0.4 / (1 + total_activations * 0.008))  # 比传统更高的探索率
        
        # 🌟 学习路径增强：如果有学习路径，适当提高探索率
        has_boosted_paths = any(self.get_exploration_boost(arm.path_id) > 1.0 for arm in arms)
        if has_boosted_paths:
            epsilon = min(0.6, epsilon * 1.3)  # 增强探索，给学习路径更多机会
        
        logger.debug(f"🎯 Epsilon-Greedy路径选择，ε={epsilon:.3f} {'(学习增强)' if has_boosted_paths else ''}")
        
        # 使用epsilon决定是否探索
        if np.random.random() < epsilon:
            # 🌟 智能探索：优先选择有探索增强的路径
            boosted_arms = [arm for arm in arms if self.get_exploration_boost(arm.path_id) > 1.0]
            if boosted_arms and np.random.random() < 0.7:  # 70%概率选择增强路径
                selected_arm = np.random.choice(boosted_arms)
                boost = self.get_exploration_boost(selected_arm.path_id)
                logger.debug(f"🔍🚀 智能探索选择增强路径: {selected_arm.path_id} (增强: {boost:.3f}x)")
            else:
                # 常规随机探索
                selected_arm = np.random.choice(arms)
                logger.debug(f"🔍 探索模式选择路径: {selected_arm.path_id}")
            return selected_arm
        else:
            # 利用：选择当前最好的路径
            best_arm = None
            best_score = -float('inf')
            
            for arm in arms:
                # 路径级别的综合评分
                score = arm.success_rate
                
                # RL奖励权重
                if arm.rl_reward_history:
                    avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                    normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                    score = score * 0.6 + normalized_reward * 0.4
                
                # 🌟 探索增强：即使在利用模式下，也给予学习路径一定优势
                exploration_boost = self.get_exploration_boost(arm.path_id)
                if exploration_boost > 1.0:
                    # 在利用模式下给学习路径一个小的额外分数
                    score += (exploration_boost - 1.0) * 0.1  # 轻微增强，避免过度偏向
                    logger.debug(f"   🚀 路径 {arm.path_id} 获得利用模式增强: +{(exploration_boost - 1.0) * 0.1:.3f}")
                
                # 路径使用频率平衡：避免过度依赖单一思维模式
                usage_ratio = arm.activation_count / (total_activations + 1)
                if usage_ratio > 0.5:  # 如果某路径使用过于频繁，稍微降低评分
                    score *= 0.95
                
                logger.debug(f"   路径 {arm.path_id}: score={score:.3f}, usage_ratio={usage_ratio:.3f}, boost={exploration_boost:.3f}")
                
                if score > best_score:
                    best_score = score
                    best_arm = arm
            
            logger.debug(f"🏆 利用模式选择路径: {best_arm.path_id} (得分: {best_score:.3f})")
            return best_arm if best_arm else arms[0]
    
    def _select_best_algorithm_for_paths(self) -> str:
        """
        为路径选择选择最佳算法
        
        Returns:
            最佳算法名称
        """
        # 如果样本太少，使用Thompson采样进行探索
        if self.total_path_selections < 15:
            logger.debug("📊 样本较少，选择Thompson采样")
            return 'thompson_sampling'
        
        # 计算路径级别的收敛水平
        if not self.path_arms:
            return 'thompson_sampling'
        
        arms_list = list(self.path_arms.values())
        convergence_level = self._calculate_path_convergence_level(arms_list)
        
        # 考虑思维多样性：路径选择需要更多探索
        if convergence_level < 0.4:
            # 低收敛，使用探索性强的算法
            logger.debug(f"📊 低收敛({convergence_level:.3f})，选择Thompson采样")
            return 'thompson_sampling'
        elif convergence_level < 0.7:
            # 中等收敛，使用平衡的算法
            logger.debug(f"📊 中等收敛({convergence_level:.3f})，选择UCB")
            return 'ucb_variant'
        else:
            # 高收敛，但仍需保持一定探索（思维多样性重要）
            logger.debug(f"📊 高收敛({convergence_level:.3f})，选择Epsilon-Greedy")
            return 'epsilon_greedy'
    
    def _calculate_path_convergence_level(self, arms: List[EnhancedDecisionArm]) -> float:
        """
        计算路径级别的收敛水平
        
        Args:
            arms: 路径决策臂列表
            
        Returns:
            收敛水平 (0.0-1.0)
        """
        if len(arms) < 2:
            return 0.0
        
        # 计算路径成功率方差
        success_rates = []
        for arm in arms:
            total = arm.success_count + arm.failure_count
            if total > 0:
                success_rates.append(arm.success_count / total)
        
        if len(success_rates) < 2:
            return 0.0
        
        variance = np.var(success_rates)
        # 将方差转换为收敛水平（方差越小，收敛水平越高）
        # 对于思维路径，我们希望保持一定的多样性，所以收敛标准稍微宽松
        convergence_level = max(0.0, 1.0 - variance * 3.5)
        
        return convergence_level
    
    # ==================== 🔧 工具选择MAB算法实现 ====================
    
    def _select_best_algorithm_for_tools(self) -> str:
        """
        为工具选择选择最佳算法
        
        Returns:
            最佳算法名称
        """
        # 如果样本太少，使用Thompson采样进行探索
        if self.total_tool_selections < 10:
            logger.debug("📊 工具选择样本较少，选择Thompson采样")
            return 'thompson_sampling'
        
        # 计算工具级别的收敛水平
        if not self.tool_arms:
            return 'thompson_sampling'
        
        arms_list = list(self.tool_arms.values())
        convergence_level = self._calculate_tool_convergence_level(arms_list)
        
        # 工具选择倾向于更快收敛到最优工具
        if convergence_level < 0.3:
            # 低收敛，使用探索性强的算法
            logger.debug(f"📊 工具选择低收敛({convergence_level:.3f})，选择Thompson采样")
            return 'thompson_sampling'
        elif convergence_level < 0.6:
            # 中等收敛，使用平衡的算法
            logger.debug(f"📊 工具选择中等收敛({convergence_level:.3f})，选择UCB")
            return 'ucb_variant'
        else:
            # 高收敛，使用利用型算法
            logger.debug(f"📊 工具选择高收敛({convergence_level:.3f})，选择Epsilon-Greedy")
            return 'epsilon_greedy'
    
    def _calculate_tool_convergence_level(self, arms: List[EnhancedDecisionArm]) -> float:
        """
        计算工具级别的收敛水平
        
        Args:
            arms: 工具决策臂列表
            
        Returns:
            收敛水平 (0.0-1.0)
        """
        if len(arms) < 2:
            return 0.0
        
        # 计算工具成功率方差
        success_rates = []
        for arm in arms:
            total = arm.success_count + arm.failure_count
            if total > 0:
                success_rates.append(arm.success_count / total)
        
        if len(success_rates) < 2:
            return 0.0
        
        variance = np.var(success_rates)
        # 工具选择可以更快收敛，收敛标准相对严格
        convergence_level = max(0.0, 1.0 - variance * 2.5)
        
        return convergence_level
    
    def _thompson_sampling_for_tools(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对工具选择的Thompson采样算法"""
        if not arms:
            raise ValueError("没有可用的工具决策臂")
        
        best_arm = None
        best_score = -1
        
        logger.debug(f"🔧 Thompson采样工具选择，候选工具: {len(arms)}个")
        
        for arm in arms:
            # 使用Beta分布进行Thompson采样
            alpha = arm.success_count + 1
            beta = arm.failure_count + 1
            
            # 从Beta分布中采样
            sampled_value = np.random.beta(alpha, beta)
            
            # 工具级别的奖励考虑
            if arm.rl_reward_history:
                avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                # 将奖励调整到0-1范围
                normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                sampled_value = sampled_value * 0.7 + normalized_reward * 0.3
            
            logger.debug(f"   工具 {arm.path_id}: sampled={sampled_value:.3f}, α={alpha}, β={beta}")
            
            if sampled_value > best_score:
                best_score = sampled_value
                best_arm = arm
        
        logger.debug(f"🏆 Thompson采样选择工具: {best_arm.path_id} (得分: {best_score:.3f})")
        return best_arm
    
    def _ucb_variant_for_tools(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对工具选择的UCB (Upper Confidence Bound) 变种算法"""
        if not arms:
            raise ValueError("没有可用的工具决策臂")
        
        total_rounds = sum(arm.activation_count for arm in arms)
        if total_rounds == 0:
            # 第一轮随机选择
            selected_arm = np.random.choice(arms)
            logger.debug(f"🔧 UCB首轮随机选择工具: {selected_arm.path_id}")
            return selected_arm
        
        best_arm = None
        best_ucb_value = -float('inf')
        
        logger.debug(f"📊 UCB工具选择，总轮数: {total_rounds}")
        
        for arm in arms:
            if arm.activation_count == 0:
                # 未尝试过的工具优先选择
                logger.debug(f"🆕 优先选择未使用工具: {arm.path_id}")
                return arm
            
            # 计算UCB值
            confidence_bound = np.sqrt(2 * np.log(total_rounds) / arm.activation_count)
            
            # 基础成功率
            base_value = arm.success_rate
            
            # 工具级别的RL奖励考虑
            if arm.rl_reward_history:
                avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                base_value = base_value * 0.6 + normalized_reward * 0.4
            
            # 工具探索奖励
            exploration_bonus = confidence_bound * 1.0  # 标准探索
            ucb_value = base_value + exploration_bonus
            
            logger.debug(f"   工具 {arm.path_id}: UCB={ucb_value:.3f}, base={base_value:.3f}, conf={confidence_bound:.3f}")
            
            if ucb_value > best_ucb_value:
                best_ucb_value = ucb_value
                best_arm = arm
        
        logger.debug(f"🏆 UCB选择工具: {best_arm.path_id} (UCB值: {best_ucb_value:.3f})")
        return best_arm
    
    def _epsilon_greedy_for_tools(self, arms: List[EnhancedDecisionArm]) -> EnhancedDecisionArm:
        """针对工具选择的Epsilon-Greedy算法"""
        if not arms:
            raise ValueError("没有可用的工具决策臂")
        
        # 工具级别的动态epsilon值
        total_activations = sum(arm.activation_count for arm in arms)
        epsilon = max(0.05, 0.3 / (1 + total_activations * 0.01))  # 比路径选择更低的探索率
        
        logger.debug(f"🔧 Epsilon-Greedy工具选择，ε={epsilon:.3f}")
        
        # 使用epsilon决定是否探索
        if np.random.random() < epsilon:
            # 探索：随机选择工具
            selected_arm = np.random.choice(arms)
            logger.debug(f"🔍 探索模式选择工具: {selected_arm.path_id}")
            return selected_arm
        else:
            # 利用：选择当前最好的工具
            best_arm = None
            best_score = -float('inf')
            
            for arm in arms:
                # 工具级别的综合评分
                score = arm.success_rate
                
                # RL奖励权重
                if arm.rl_reward_history:
                    avg_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history)
                    normalized_reward = max(0, min(1, (avg_reward + 1) / 2))
                    score = score * 0.5 + normalized_reward * 0.5
                
                logger.debug(f"   工具 {arm.path_id}: score={score:.3f}")
                
                if score > best_score:
                    best_score = score
                    best_arm = arm
            
            logger.debug(f"🏆 利用模式选择工具: {best_arm.path_id} (得分: {best_score:.3f})")
            return best_arm if best_arm else arms[0]
    
    # ==================== 📊 更新性能反馈方法 ====================
    
    def update_path_performance(self, path_id: str, success: bool, reward: float = 0.0, source: str = "user_feedback"):
        """
        🔧 双层学习：更新路径或工具的性能反馈 - 通用性反馈更新方法（增强版）
        
        增强功能：
        - 新增source参数，支持追踪反馈来源
        - 支持回溯分析("retrospection")和用户反馈("user_feedback")的区分
        - 针对不同来源的反馈，使用不同的权重和处理策略
        
        Args:
            path_id: 路径ID或工具ID（由调用方决定是路径还是工具）
            success: 执行是否成功
            reward: RL奖励值
            source: 反馈来源 ("user_feedback", "retrospection", "auto_evaluation", "tool_verification")
        """
        # 🎯 智能识别：检查是路径反馈还是工具反馈
        if path_id in self.path_arms:
            # 路径反馈处理
            target_arm = self.path_arms[path_id]
            
            # 更新路径算法性能统计
            if self.path_selection_history:
                last_selection = self.path_selection_history[-1]
                if last_selection['path_id'] == path_id:
                    algorithm = last_selection['algorithm']
                    self.algorithm_performance[algorithm]['total'] += 1
                    if success:
                        self.algorithm_performance[algorithm]['successes'] += 1
                        
        elif path_id in self.tool_arms:
            # 工具反馈处理
            target_arm = self.tool_arms[path_id]
            
            # 更新工具算法性能统计
            if self.tool_selection_history:
                last_selection = self.tool_selection_history[-1]
                if last_selection['tool_id'] == path_id:
                    algorithm = last_selection['algorithm']
                    self.tool_algorithm_performance[algorithm]['total'] += 1
                    if success:
                        self.tool_algorithm_performance[algorithm]['successes'] += 1
                        
        else:
            # 动态创建决策臂（默认作为路径处理，保持向后兼容）
            target_arm = self._create_strategy_arm_if_missing(path_id)
            logger.debug(f"🔧 为未知ID {path_id} 创建路径决策臂（向后兼容）")
        
        # ✅ 增强版性能更新：根据来源调整处理策略
        adjusted_reward = self._adjust_reward_by_source(reward, source, success)
        target_arm.update_performance(success, adjusted_reward)
        
        # 📊 记录来源追踪信息
        self._record_feedback_source(path_id, source, success, reward)
        
        # 记录更新日志
        arm_type = "工具" if path_id in self.tool_arms else "路径"
        logger.info(f"📊 更新{arm_type}性能: {path_id} -> 成功率:{target_arm.success_rate:.3f}, 奖励:{reward:.3f}, 来源:{source}")
        logger.debug(f"   详细: 成功{target_arm.success_count}次, 失败{target_arm.failure_count}次, 激活{target_arm.activation_count}次")
        
        # 🏆 黄金模板识别逻辑：检查是否符合黄金模板条件（仅对路径应用）
        if path_id in self.path_arms:
            self._check_and_promote_to_golden_template(path_id, target_arm)
            
            # 🎭 试炼场管理：检查淘汰候选
            self._check_culling_candidates(path_id, target_arm, success)
    
    def update_path_feedback(self, path_id: str, success: bool, reward: float = 0.0, source: str = "user_feedback"):
        """
        🔥 修复：添加update_path_feedback方法（与update_path_performance功能相同，提供兼容性）
        
        Args:
            path_id: 路径ID或工具ID
            success: 执行是否成功
            reward: RL奖励值
            source: 反馈来源
        """
        return self.update_path_performance(path_id, success, reward, source)
    
    def _adjust_reward_by_source(self, reward: float, source: str, success: bool) -> float:
        """
        根据反馈来源调整奖励值
        
        Args:
            reward: 原始奖励值
            source: 反馈来源
            success: 执行是否成功
            
        Returns:
            调整后的奖励值
        """
        # 获取来源权重
        weight = self.source_weight_config.get(source, 1.0)
        
        # 特殊处理：回溯分析的初始探索奖励
        if source == "retrospection":
            if success and reward > 0:
                # 回溯分析成功的创新想法给予额外奖励
                adjusted_reward = reward * weight + 0.1
            else:
                # 回溯分析失败时仍给予小幅正向奖励鼓励探索
                adjusted_reward = max(reward * weight, 0.05)
        else:
            # 其他来源按权重调整
            adjusted_reward = reward * weight
        
        return adjusted_reward
    
    def _record_feedback_source(self, path_id: str, source: str, success: bool, reward: float):
        """
        记录反馈来源追踪信息
        
        Args:
            path_id: 路径ID
            source: 反馈来源
            success: 执行是否成功
            reward: 奖励值
        """
        if source in self.feedback_source_tracking:
            tracking = self.feedback_source_tracking[source]
            
            # 更新统计信息
            old_count = tracking["count"]
            new_count = old_count + 1
            
            # 增量更新成功率
            old_success_rate = tracking["success_rate"]
            new_success_rate = (old_success_rate * old_count + (1 if success else 0)) / new_count
            
            # 增量更新平均奖励
            old_avg_reward = tracking["avg_reward"]
            new_avg_reward = (old_avg_reward * old_count + reward) / new_count
            
            # 更新追踪记录
            tracking.update({
                "count": new_count,
                "success_rate": new_success_rate,
                "avg_reward": new_avg_reward
            })
            
            logger.debug(f"📊 来源追踪更新: {source} -> 次数:{new_count}, 成功率:{new_success_rate:.3f}, 平均奖励:{new_avg_reward:.3f}")
    
    def get_feedback_source_stats(self) -> Dict[str, Any]:
        """
        获取反馈来源统计信息
        
        Returns:
            详细的来源追踪统计
        """
        return {
            "source_tracking": self.feedback_source_tracking.copy(),
            "source_weights": self.source_weight_config.copy(),
            "total_feedback_by_source": {
                source: data["count"] 
                for source, data in self.feedback_source_tracking.items()
            },
            "retrospection_contribution": {
                "total_retrospection_feedback": self.feedback_source_tracking["retrospection"]["count"],
                "retrospection_success_rate": self.feedback_source_tracking["retrospection"]["success_rate"],
                "retrospection_avg_reward": self.feedback_source_tracking["retrospection"]["avg_reward"]
            }
        }
    
    # 保留向后兼容的方法（标记为过时）
    def update_arm_performance(self, dimension_name: str, option: str, 
                             success: bool, reward: float = 0.0):
        """
        更新决策臂的性能 - 已过时，请使用 update_path_performance
        
        Args:
            dimension_name: 维度名称
            option: 选项名称
            success: 是否成功
            reward: RL奖励值
        """
        logger.warning("⚠️ update_arm_performance 已过时，请使用 update_path_performance")
        path_id = f"{dimension_name}_{option}"  # 临时转换
        self.update_path_performance(path_id, success, reward)
    
    def check_path_convergence(self) -> bool:
        """
        检查路径选择是否收敛
        
        Returns:
            是否收敛
        """
        if len(self.path_arms) < 2:
            return False
            
        # 检查是否有足够的样本
        total_samples = sum(arm.success_count + arm.failure_count for arm in self.path_arms.values())
        if total_samples < self.min_samples:
            return False
            
        # 计算路径成功率方差，判断是否收敛
        success_rates = []
        for arm in self.path_arms.values():
            total = arm.success_count + arm.failure_count
            if total > 0:
                success_rates.append(arm.success_count / total)
                
        if len(success_rates) < 2:
            return False
            
        variance = np.var(success_rates)
        # 对于思维路径，使用稍微宽松的收敛标准，保持多样性
        adjusted_threshold = self.convergence_threshold * 1.2
        is_converged = variance < adjusted_threshold
        
        if is_converged:
            logger.info(f"✅ 路径选择已收敛 (方差:{variance:.4f}, 阈值:{adjusted_threshold:.4f})")
        
        return is_converged
    
    # 保留向后兼容的方法（标记为过时）
    def check_convergence(self, dimension_name: str) -> bool:
        """
        检查指定维度是否收敛 - 已过时，请使用 check_path_convergence
        """
        logger.warning("⚠️ check_convergence 已过时，请使用 check_path_convergence")
        return self.check_path_convergence()
    
    def get_path_statistics(self) -> Dict[str, Dict[str, any]]:
        """
        获取所有路径的统计信息（包含黄金模板状态）
        
        Returns:
            路径统计数据
        """
        statistics = {}
        
        for path_id, arm in self.path_arms.items():
            # 检查是否为黄金模板
            is_golden_template = path_id in self.golden_templates
            golden_template_info = None
            
            if is_golden_template:
                template_data = self.golden_templates[path_id]
                golden_template_info = {
                    'created_timestamp': template_data['created_timestamp'],
                    'last_updated': template_data['last_updated'],
                    'stability_score': template_data['stability_score'],
                    'usage_as_template': self.template_usage_stats.get(path_id, 0),
                    'promotion_reason': template_data['promotion_reason']
                }
            
            # 计算路径特定的统计
            statistics[path_id] = {
                'path_type': arm.option,  # 路径类型
                'path_id': path_id,
                'activation_count': arm.activation_count,
                'success_count': arm.success_count,
                'failure_count': arm.failure_count,
                'success_rate': arm.success_rate,
                'total_reward': arm.total_reward,
                'average_reward': sum(arm.rl_reward_history) / len(arm.rl_reward_history) if arm.rl_reward_history else 0.0,
                'last_used': arm.last_used,
                'recent_trend': self._calculate_recent_trend(arm),
                'consecutive_successes': self._calculate_consecutive_successes(arm),
                'usage_ratio': arm.activation_count / max(self.total_path_selections, 1),
                
                # 🏆 黄金模板相关信息
                'is_golden_template': is_golden_template,
                'golden_template_info': golden_template_info,
                'meets_golden_criteria': self._check_golden_criteria(arm),
                'stability_score': self._calculate_stability_score(arm) if arm.activation_count >= 10 else 0.0
            }
        
        return statistics
    
    def _check_golden_criteria(self, arm: EnhancedDecisionArm) -> bool:
        """
        检查路径是否符合黄金模板的基本条件（不包括稳定性检查）
        
        Args:
            arm: 决策臂对象
            
        Returns:
            是否符合基本条件
        """
        config = self.golden_template_config
        return (arm.success_rate >= config['success_rate_threshold'] and 
                arm.activation_count >= config['min_samples_required'])
    
    def get_system_path_summary(self) -> Dict[str, any]:
        """
        获取路径选择系统的整体摘要
        
        Returns:
            系统摘要数据
        """
        if not self.path_arms:
            return {
                'total_paths': 0,
                'total_selections': self.total_path_selections,
                'is_converged': False,
                'convergence_level': 0.0,
                'most_used_path': None,
                'best_performing_path': None
            }
        
        # 最常用路径
        most_used_arm = max(self.path_arms.values(), key=lambda a: a.activation_count)
        
        # 最佳性能路径
        best_performing_arm = max(self.path_arms.values(), key=lambda a: a.success_rate)
        
        # 算法性能统计
        algorithm_stats = {}
        for algo, stats in self.algorithm_performance.items():
            if stats['total'] > 0:
                algorithm_stats[algo] = {
                    'success_rate': stats['successes'] / stats['total'],
                    'total_uses': stats['total']
                }
        
        return {
            'total_paths': len(self.path_arms),
            'total_selections': self.total_path_selections,
            'is_converged': self.check_path_convergence(),
            'convergence_level': self._calculate_path_convergence_level(list(self.path_arms.values())),
            'most_used_path': {
                'path_id': most_used_arm.path_id,
                'path_type': most_used_arm.option,
                'usage_count': most_used_arm.activation_count
            },
            'best_performing_path': {
                'path_id': best_performing_arm.path_id,
                'path_type': best_performing_arm.option,
                'success_rate': best_performing_arm.success_rate
            },
            'algorithm_performance': algorithm_stats,
            'total_samples': sum(arm.success_count + arm.failure_count for arm in self.path_arms.values())
        }
    
    # 保留向后兼容的方法（标记为过时）
    def get_dimension_statistics(self) -> Dict[str, Dict[str, any]]:
        """
        获取所有维度的统计信息 - 已过时，请使用 get_path_statistics
        """
        logger.warning("⚠️ get_dimension_statistics 已过时，请使用 get_path_statistics")
        return self.get_path_statistics()
    
    def get_path_details(self, path_id: str = None) -> Dict[str, any]:
        """
        获取指定路径的详细信息
        
        Args:
            path_id: 路径ID，如果为None则返回所有路径的详细信息
            
        Returns:
            路径详细信息
        """
        if path_id is not None:
            if path_id not in self.path_arms:
                logger.warning(f"⚠️ 路径 {path_id} 不存在")
                return {}
            
            arm = self.path_arms[path_id]
            return {
                'path_id': path_id,
                'path_type': arm.option,
                'success_count': arm.success_count,
                'failure_count': arm.failure_count,
                'success_rate': arm.success_rate,
                'total_reward': arm.total_reward,
                'average_reward': sum(arm.rl_reward_history) / len(arm.rl_reward_history) if arm.rl_reward_history else 0.0,
                'activation_count': arm.activation_count,
                'last_used': arm.last_used,
                'recent_trend': self._calculate_recent_trend(arm),
                'consecutive_successes': self._calculate_consecutive_successes(arm),
                'rl_reward_history': arm.rl_reward_history.copy(),
                'recent_results': arm.recent_results.copy()
            }
        else:
            # 返回所有路径的详细信息
            all_details = {}
            for pid, arm in self.path_arms.items():
                all_details[pid] = self.get_path_details(pid)
            
            # 按成功率排序
            sorted_paths = sorted(all_details.items(), 
                                key=lambda x: x[1]['success_rate'], 
                                reverse=True)
            return dict(sorted_paths)
    
    def get_selection_history(self, limit: int = 10) -> List[Dict[str, any]]:
        """
        获取路径选择历史
        
        Args:
            limit: 返回的历史记录数量限制
            
        Returns:
            选择历史列表
        """
        return self.path_selection_history[-limit:] if self.path_selection_history else []
    
    # 保留向后兼容的方法（标记为过时）
    def get_arm_details(self, dimension_name: str) -> List[Dict[str, any]]:
        """
        获取指定维度的所有决策臂详细信息 - 已过时，请使用 get_path_details
        """
        logger.warning("⚠️ get_arm_details 已过时，请使用 get_path_details")
        return list(self.get_path_details().values())
    
    def reset_path(self, path_id: str):
        """
        重置指定路径的所有数据
        
        Args:
            path_id: 路径ID
        """
        if path_id in self.path_arms:
            del self.path_arms[path_id]
            logger.info(f"🔄 路径 {path_id} 已重置")
        
        # 清理选择历史中的相关记录
        self.path_selection_history = [
            record for record in self.path_selection_history 
            if record['path_id'] != path_id
        ]
    
    def reset_all_paths(self):
        """
        重置所有路径数据，完全清空学习历史
        """
        self.path_arms.clear()
        self.path_selection_history.clear()
        self.total_path_selections = 0
        self.algorithm_performance.clear()
        logger.info("🔄 所有路径数据已重置")
    
    def get_system_status(self) -> Dict[str, any]:
        """
        获取MAB路径选择系统的整体状态
        
        Returns:
            系统状态信息
        """
        total_paths = len(self.path_arms)
        is_converged = self.check_path_convergence()
        
        # 计算活跃路径数（最近使用过的）
        current_time = time.time()
        active_paths = sum(
            1 for arm in self.path_arms.values() 
            if arm.last_used > 0 and (current_time - arm.last_used) < 3600  # 1小时内使用过
        )
        
        # 最受欢迎的路径类型
        path_type_usage = {}
        for arm in self.path_arms.values():
            path_type = arm.option
            path_type_usage[path_type] = path_type_usage.get(path_type, 0) + arm.activation_count
        
        most_popular_type = max(path_type_usage.items(), key=lambda x: x[1])[0] if path_type_usage else None
        
        # 获取黄金模板统计
        golden_stats = self.get_golden_template_stats()
        
        return {
            'mode': 'path_selection',  # 新增：标识当前为路径选择模式
            'total_paths': total_paths,
            'active_paths': active_paths,
            'total_selections': self.total_path_selections,
            'is_converged': is_converged,
            'convergence_level': self._calculate_path_convergence_level(list(self.path_arms.values())) if self.path_arms else 0.0,
            'convergence_threshold': self.convergence_threshold,
            'min_samples': self.min_samples,
            'most_popular_path_type': most_popular_type,
            'path_type_distribution': path_type_usage,
            'algorithm_performance': dict(self.algorithm_performance),
            
            # 🏆 黄金模板系统状态
            'golden_template_system': {
                'enabled': True,
                'total_templates': golden_stats['total_templates'],
                'avg_success_rate': golden_stats['avg_success_rate'],
                'total_usage_count': golden_stats['total_usage_count'],
                'most_used_template': golden_stats['most_used_template'],
                'match_history_count': golden_stats['match_history_count'],
                'config': self.golden_template_config
            }
        }
    
    # 保留向后兼容的方法（标记为过时）
    def reset_dimension(self, dimension_name: str):
        """
        重置指定维度的所有数据 - 已过时，请使用 reset_path 或 reset_all_paths
        """
        logger.warning("⚠️ reset_dimension 已过时，请使用 reset_path 或 reset_all_paths")
        # 不执行任何操作，避免意外清除路径数据
    
    # ==================== 🏆 黄金决策模板系统实现 ====================
    
    def _check_golden_template_match(self, paths: List[ReasoningPath]) -> Optional[Dict[str, any]]:
        """
        检查当前路径列表是否与已有黄金模板匹配 - 🎯 修复版：基于策略ID匹配
        
        Args:
            paths: 候选思维路径列表
            
        Returns:
            匹配结果字典，包含匹配的模板和路径信息，如果无匹配则返回None
        """
        if not self.golden_templates:
            return None
        
        best_match = None
        best_score = 0.0
        match_threshold = 0.85  # 匹配阈值
        
        logger.debug(f"🏆 检查 {len(self.golden_templates)} 个黄金模板")
        
        for template_id, template_data in self.golden_templates.items():
            template_path_type = template_data['path_type']
            
            # 🎯 根源修复：直接使用路径的策略ID，无需推导
            for path in paths:
                # 直接使用路径的策略ID
                path_strategy_id = path.strategy_id
                
                # 检查是否匹配：策略ID匹配或路径类型匹配
                is_strategy_match = (template_id == path_strategy_id)
                is_type_match = (template_path_type == path.path_type)
                
                if is_strategy_match or is_type_match:
                    # 计算匹配分数
                    match_score = self._calculate_template_match_score(template_data, path)
                    
                    # 策略ID匹配给额外分数
                    if is_strategy_match:
                        match_score += 0.1  # 策略ID匹配奖励
                    
                    logger.debug(f"   模板 {template_id} vs 路径策略 {path_strategy_id}: 匹配分数 {match_score:.3f}")
                    logger.debug(f"      策略匹配: {is_strategy_match}, 类型匹配: {is_type_match}")
                    
                    if match_score > match_threshold and match_score > best_score:
                        best_match = {
                            'template_id': template_id,
                            'path': path,
                            'match_score': match_score,
                            'template_data': template_data,
                            'strategy_match': is_strategy_match
                        }
                        best_score = match_score
        
        if best_match:
            match_type = "策略ID" if best_match['strategy_match'] else "路径类型"
            logger.debug(f"🏆 找到最佳匹配: 模板 {best_match['template_id']} (分数: {best_score:.3f}, 匹配类型: {match_type})")
        else:
            logger.debug("🏆 未找到符合条件的黄金模板匹配")
        
        return best_match
    
    def _calculate_template_match_score(self, template_data: Dict[str, any], path: ReasoningPath) -> float:
        """
        计算模板与路径的匹配分数 - 🎯 修复版：基于策略ID匹配
        
        Args:
            template_data: 黄金模板数据
            path: 候选路径
            
        Returns:
            匹配分数 (0.0-1.0)
        """
        score = 0.0
        
        # 🎯 根源修复：直接使用路径的策略ID
        path_strategy_id = path.strategy_id
        
        # 1. 策略ID完全匹配 (基础分数60%)
        template_strategy_id = template_data.get('strategy_id', template_data.get('path_id', ''))
        if template_strategy_id == path_strategy_id:
            score += 0.6
        # 1b. 路径类型匹配作为备选 (基础分数40%)
        elif template_data['path_type'] == path.path_type:
            score += 0.4
        
        # 2. 描述相似性 (额外20%)
        desc_similarity = self._calculate_description_similarity(
            template_data.get('description', ''), path.description
        )
        score += desc_similarity * 0.2
        
        # 3. 历史性能奖励 (额外20%)
        performance_bonus = min(template_data['success_rate'] - 0.8, 0.2) * 1.0  # 超过80%的部分转换为奖励
        score += performance_bonus
        
        logger.debug(f"🎯 匹配分数详情:")
        logger.debug(f"   模板策略ID: {template_strategy_id}")
        logger.debug(f"   路径策略ID: {path_strategy_id}")
        logger.debug(f"   策略匹配: {template_strategy_id == path_strategy_id}")
        logger.debug(f"   描述相似性: {desc_similarity:.3f}")
        logger.debug(f"   性能奖励: {performance_bonus:.3f}")
        logger.debug(f"   总分: {score:.3f}")
        
        return min(score, 1.0)
    
    def _calculate_description_similarity(self, desc1: str, desc2: str) -> float:
        """
        计算两个描述文本的相似度（简单实现）
        
        Args:
            desc1: 描述文本1
            desc2: 描述文本2
            
        Returns:
            相似度分数 (0.0-1.0)
        """
        if not desc1 or not desc2:
            return 0.0
        
        # 简单的关键词匹配算法
        words1 = set(desc1.lower().split())
        words2 = set(desc2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _check_and_promote_to_golden_template(self, path_id: str, arm: EnhancedDecisionArm):
        """
        检查路径是否符合黄金模板条件，如果符合则提升为黄金模板
        
        Args:
            path_id: 路径ID
            arm: 决策臂对象
        """
        config = self.golden_template_config
        
        # 检查基本条件
        if (arm.success_rate >= config['success_rate_threshold'] and 
            arm.activation_count >= config['min_samples_required']):
            
            # 检查稳定性（最近N次的表现）
            if self._check_path_stability(arm):
                # 检查是否已经是黄金模板
                if path_id not in self.golden_templates:
                    self._promote_to_golden_template(path_id, arm)
                else:
                    # 更新已有黄金模板
                    self._update_golden_template(path_id, arm)
    
    def _check_path_stability(self, arm: EnhancedDecisionArm) -> bool:
        """
        检查路径的稳定性（最近表现是否持续良好）
        
        Args:
            arm: 决策臂对象
            
        Returns:
            是否稳定
        """
        window_size = self.golden_template_config['stability_check_window']
        
        # 获取最近的结果
        recent_results = arm.recent_results[-window_size:] if len(arm.recent_results) >= window_size else arm.recent_results
        
        if len(recent_results) < window_size:
            return False  # 样本不足
        
        # 计算最近窗口的成功率
        recent_successes = sum(1 for result in recent_results if result)
        recent_success_rate = recent_successes / len(recent_results)
        
        # 稳定性要求：最近表现不低于整体表现的95%
        stability_threshold = arm.success_rate * 0.95
        
        return recent_success_rate >= stability_threshold
    
    def _promote_to_golden_template(self, strategy_id: str, arm: EnhancedDecisionArm):
        """
        将策略提升为黄金模板 - 🎯 修复版：基于策略ID
        
        Args:
            strategy_id: 策略ID（而非实例ID）
            arm: 决策臂对象
        """
        # 检查模板数量限制
        if len(self.golden_templates) >= self.golden_template_config['max_golden_templates']:
            # 移除表现最差的模板
            self._remove_worst_golden_template()
        
        # 🎯 修复：基于策略ID创建黄金模板
        template_data = {
            'strategy_id': strategy_id,        # 策略ID（用于匹配）
            'path_id': strategy_id,           # 兼容性字段
            'path_type': arm.option,          # 路径类型
            'description': getattr(arm, 'description', ''),
            'success_rate': arm.success_rate,
            'total_activations': arm.activation_count,
            'average_reward': sum(arm.rl_reward_history) / len(arm.rl_reward_history) if arm.rl_reward_history else 0.0,
            'created_timestamp': time.time(),
            'last_updated': time.time(),
            'promotion_reason': 'high_performance',
            'stability_score': self._calculate_stability_score(arm),
            'usage_count': 0  # 作为模板被使用的次数
        }
        
        # 使用策略ID作为模板键
        self.golden_templates[strategy_id] = template_data
        
        logger.info(f"🏆 新黄金模板诞生！")
        logger.info(f"   策略ID: {strategy_id}")
        logger.info(f"   路径类型: {arm.option}")
        logger.info(f"   成功率: {arm.success_rate:.1%}")
        logger.info(f"   激活次数: {arm.activation_count}")
        avg_rl_reward = sum(arm.rl_reward_history) / len(arm.rl_reward_history) if arm.rl_reward_history else 0.0
        logger.info(f"   平均奖励: {avg_rl_reward:.3f}")
        logger.info(f"   当前黄金模板总数: {len(self.golden_templates)}")
    
    def _update_golden_template(self, strategy_id: str, arm: EnhancedDecisionArm):
        """
        更新已有的黄金模板数据 - 🎯 修复版：基于策略ID
        
        Args:
            strategy_id: 策略ID（而非实例ID）
            arm: 决策臂对象
        """
        if strategy_id in self.golden_templates:
            template = self.golden_templates[strategy_id]
            template.update({
                'success_rate': arm.success_rate,
                'total_activations': arm.activation_count,
                'average_reward': sum(arm.rl_reward_history) / len(arm.rl_reward_history) if arm.rl_reward_history else 0.0,
                'last_updated': time.time(),
                'stability_score': self._calculate_stability_score(arm)
            })
            
            logger.debug(f"🏆 更新黄金模板: {strategy_id} -> 成功率:{arm.success_rate:.1%}")
    
    def _calculate_stability_score(self, arm: EnhancedDecisionArm) -> float:
        """
        计算路径的稳定性分数
        
        Args:
            arm: 决策臂对象
            
        Returns:
            稳定性分数 (0.0-1.0)
        """
        if arm.activation_count < 10:
            return 0.0
        
        # 计算成功率的方差（越小越稳定）
        recent_results = arm.recent_results[-20:] if len(arm.recent_results) >= 20 else arm.recent_results
        
        if len(recent_results) < 5:
            return 0.5  # 样本不足，给中等分数
        
        # 计算滑动窗口成功率的方差
        window_size = 5
        success_rates = []
        
        for i in range(len(recent_results) - window_size + 1):
            window = recent_results[i:i + window_size]
            window_success_rate = sum(window) / len(window)
            success_rates.append(window_success_rate)
        
        if len(success_rates) < 2:
            return 0.5
        
        # 方差越小，稳定性越高
        variance = np.var(success_rates)
        stability_score = max(0.0, 1.0 - variance * 4)  # 将方差转换为稳定性分数
        
        return stability_score
    
    def _remove_worst_golden_template(self):
        """
        移除表现最差的黄金模板
        """
        if not self.golden_templates:
            return
        
        # 按综合分数排序，移除最差的
        worst_template_id = min(self.golden_templates.keys(), 
                               key=lambda tid: self._calculate_template_quality_score(self.golden_templates[tid]))
        
        removed_template = self.golden_templates.pop(worst_template_id)
        
        logger.info(f"🗑️ 移除表现较差的黄金模板: {worst_template_id}")
        logger.info(f"   原因: 为新模板腾出空间")
        logger.info(f"   被移除模板成功率: {removed_template['success_rate']:.1%}")
    
    def _calculate_template_quality_score(self, template_data: Dict[str, any]) -> float:
        """
        计算模板的质量分数
        
        Args:
            template_data: 模板数据
            
        Returns:
            质量分数
        """
        # 综合考虑成功率、使用次数、稳定性等因素
        success_score = template_data['success_rate'] * 0.4
        usage_score = min(template_data.get('usage_count', 0) / 10, 1.0) * 0.3  # 使用次数标准化
        stability_score = template_data.get('stability_score', 0.5) * 0.2
        recency_score = self._calculate_recency_score(template_data) * 0.1
        
        return success_score + usage_score + stability_score + recency_score
    
    def _calculate_recency_score(self, template_data: Dict[str, any]) -> float:
        """
        计算模板的新近性分数
        
        Args:
            template_data: 模板数据
            
        Returns:
            新近性分数 (0.0-1.0)
        """
        current_time = time.time()
        last_updated = template_data.get('last_updated', template_data.get('created_timestamp', current_time))
        
        # 计算距离上次更新的时间（小时）
        hours_since_update = (current_time - last_updated) / 3600
        
        # 24小时内更新得满分，超过7天开始衰减
        if hours_since_update <= 24:
            return 1.0
        elif hours_since_update <= 168:  # 7天
            return 1.0 - (hours_since_update - 24) / 144  # 线性衰减
        else:
            return 0.0
    
    # ==================== 🏆 黄金模板管理接口 ====================
    
    def get_golden_templates(self) -> Dict[str, Dict[str, any]]:
        """
        获取所有黄金模板
        
        Returns:
            黄金模板字典
        """
        return self.golden_templates.copy()
    
    def get_golden_template_stats(self) -> Dict[str, any]:
        """
        获取黄金模板系统统计信息
        
        Returns:
            统计信息字典
        """
        if not self.golden_templates:
            return {
                'total_templates': 0,
                'avg_success_rate': 0.0,
                'total_usage_count': 0,
                'most_used_template': None,
                'template_usage_stats': {},
                'match_history_count': len(self.template_match_history) if hasattr(self, 'template_match_history') else 0
            }
        
        success_rates = [t['success_rate'] for t in self.golden_templates.values()]
        usage_counts = [self.template_usage_stats.get(tid, 0) for tid in self.golden_templates.keys()]
        
        most_used_template_id = max(self.template_usage_stats.keys(), 
                                   key=self.template_usage_stats.get) if self.template_usage_stats else None
        
        return {
            'total_templates': len(self.golden_templates),
            'avg_success_rate': sum(success_rates) / len(success_rates),
            'total_usage_count': sum(usage_counts),
            'most_used_template': {
                'template_id': most_used_template_id,
                'usage_count': self.template_usage_stats.get(most_used_template_id, 0),
                'template_data': self.golden_templates.get(most_used_template_id)
            } if most_used_template_id else None,
            'template_usage_stats': dict(self.template_usage_stats),
            'match_history_count': len(self.template_match_history)
        }
    
    def remove_golden_template(self, template_id: str) -> bool:
        """
        手动移除指定的黄金模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            是否成功移除
        """
        if template_id in self.golden_templates:
            removed_template = self.golden_templates.pop(template_id)
            logger.info(f"🗑️ 手动移除黄金模板: {template_id}")
            logger.info(f"   模板类型: {removed_template['path_type']}")
            return True
        else:
            logger.warning(f"⚠️ 黄金模板 {template_id} 不存在")
            return False
    
    def clear_golden_templates(self):
        """
        清空所有黄金模板
        """
        count = len(self.golden_templates)
        self.golden_templates.clear()
        self.template_usage_stats.clear()
        self.template_match_history.clear()
        
        logger.info(f"🗑️ 已清空所有黄金模板 (共 {count} 个)")
    
    def export_golden_templates(self) -> str:
        """
        导出黄金模板数据（JSON格式）
        
        Returns:
            JSON字符串
        """
        import json
        export_data = {
            'golden_templates': self.golden_templates,
            'template_usage_stats': dict(self.template_usage_stats),
            'template_match_history': self.template_match_history[-50:],  # 只导出最近50条匹配历史
            'export_timestamp': time.time(),
            'config': self.golden_template_config
        }
        
        return json.dumps(export_data, indent=2, ensure_ascii=False)
    
    def import_golden_templates(self, json_data: str) -> bool:
        """
        导入黄金模板数据
        
        Args:
            json_data: JSON字符串
            
        Returns:
            是否成功导入
        """
        try:
            import json
            data = json.loads(json_data)
            
            # 验证数据格式
            if 'golden_templates' not in data:
                logger.error("❌ 导入数据格式错误：缺少golden_templates字段")
                return False
            
            # 导入模板
            imported_count = 0
            for template_id, template_data in data['golden_templates'].items():
                if len(self.golden_templates) < self.golden_template_config['max_golden_templates']:
                    self.golden_templates[template_id] = template_data
                    imported_count += 1
                else:
                    break
            
            # 导入使用统计
            if 'template_usage_stats' in data:
                for template_id, count in data['template_usage_stats'].items():
                    if template_id in self.golden_templates:
                        self.template_usage_stats[template_id] = count
            
            logger.info(f"✅ 成功导入 {imported_count} 个黄金模板")
            return True
            
        except Exception as e:
            logger.error(f"❌ 导入黄金模板失败: {e}")
            return False
    
    # ==================== 🏆 黄金模板使用示例 ====================
    
    def demo_golden_template_workflow(self):
        """
        演示黄金模板系统的完整工作流程
        
        这是一个示例方法，展示了黄金模板系统的核心功能
        """
        logger.info("🏆 开始黄金模板系统演示")
        
        # 1. 显示当前状态
        stats = self.get_golden_template_stats()
        logger.info(f"当前黄金模板数量: {stats['total_templates']}")
        
        # 2. 显示配置
        config = self.golden_template_config
        logger.info(f"黄金模板配置:")
        logger.info(f"  - 成功率阈值: {config['success_rate_threshold']:.1%}")
        logger.info(f"  - 最小样本数: {config['min_samples_required']}")
        logger.info(f"  - 最大模板数: {config['max_golden_templates']}")
        
        # 3. 显示现有黄金模板
        if self.golden_templates:
            logger.info("🏆 现有黄金模板:")
            for template_id, template_data in self.golden_templates.items():
                logger.info(f"  - {template_id}: {template_data['path_type']} "
                           f"(成功率: {template_data['success_rate']:.1%}, "
                           f"使用次数: {self.template_usage_stats.get(template_id, 0)})")
        else:
            logger.info("📝 暂无黄金模板")
        
        # 4. 显示候选路径
        candidate_paths = []
        for path_id, arm in self.path_arms.items():
            if self._check_golden_criteria(arm) and path_id not in self.golden_templates:
                candidate_paths.append((path_id, arm))
        
        if candidate_paths:
            logger.info("⭐ 符合黄金模板条件的候选路径:")
            for path_id, arm in candidate_paths:
                stability = self._calculate_stability_score(arm)
                logger.info(f"  - {path_id}: {arm.option} "
                           f"(成功率: {arm.success_rate:.1%}, "
                           f"样本: {arm.activation_count}, "
                           f"稳定性: {stability:.2f})")
        else:
            logger.info("📝 暂无符合条件的候选路径")
        
        logger.info("🏆 黄金模板系统演示完成")
    
    # ==================== 💡 Aha-Moment决策支持系统 ====================
    
    def get_path_confidence(self, strategy_id: str) -> float:
        """
        获取指定策略的置信度分数
        
        Args:
            strategy_id: 策略ID（注意：这里应该传递strategy_id而不是path_id实例ID）
            
        Returns:
            置信度分数 (0.0-1.0)，1.0表示非常有信心，0.0表示完全没有信心
        """
        # 🔧 动态创建：如果策略不存在，则动态创建（置信度为最低）
        arm = self._create_strategy_arm_if_missing(strategy_id)
        
        # 如果样本数不足，置信度较低
        if arm.activation_count < 5:
            base_confidence = 0.2  # 基础信心很低
        elif arm.activation_count < 10:
            base_confidence = 0.4
        elif arm.activation_count < 20:
            base_confidence = 0.6
        else:
            base_confidence = 0.8  # 充足样本的基础信心
        
        # 基于成功率调整置信度
        success_factor = arm.success_rate
        
        # 基于稳定性调整置信度
        stability_factor = self._calculate_stability_score(arm) if arm.activation_count >= 10 else 0.5
        
        # 基于最近表现调整置信度
        recent_performance_factor = self._calculate_recent_performance_factor(arm)
        
        # 综合计算置信度
        confidence = (
            base_confidence * 0.3 +          # 样本量贡献30%
            success_factor * 0.4 +           # 成功率贡献40%
            stability_factor * 0.2 +         # 稳定性贡献20%
            recent_performance_factor * 0.1  # 最近表现贡献10%
        )
        
        return min(max(confidence, 0.0), 1.0)  # 确保在[0,1]范围内
    
    def _calculate_recent_performance_factor(self, arm: EnhancedDecisionArm) -> float:
        """
        计算最近表现因子
        
        Args:
            arm: 决策臂对象
            
        Returns:
            最近表现因子 (0.0-1.0)
        """
        if not arm.recent_results or len(arm.recent_results) < 3:
            return 0.5  # 默认中等
        
        # 计算最近5次的成功率
        recent_window = arm.recent_results[-5:]
        recent_success_rate = sum(recent_window) / len(recent_window)
        
        return recent_success_rate
    
    def get_all_paths_confidence(self) -> Dict[str, float]:
        """
        获取所有路径的置信度
        
        Returns:
            路径ID到置信度的映射
        """
        confidence_map = {}
        for path_id in self.path_arms.keys():
            confidence_map[path_id] = self.get_path_confidence(path_id)
        
        return confidence_map
    
    def check_low_confidence_scenario(self, threshold: float = 0.3) -> bool:
        """
        检查是否处于低置信度场景（所有路径表现都很差）
        
        Args:
            threshold: 置信度阈值，低于此值认为是低置信度
            
        Returns:
            是否所有路径都处于低置信度状态
        """
        if not self.path_arms:
            return True  # 没有路径数据，认为是低置信度场景
        
        confidence_scores = self.get_all_paths_confidence()
        
        if not confidence_scores:
            return True
        
        # 检查是否所有路径的置信度都低于阈值
        max_confidence = max(confidence_scores.values())
        avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        
        logger.debug(f"💡 置信度检查: 最高置信度={max_confidence:.3f}, 平均置信度={avg_confidence:.3f}, 阈值={threshold}")
        
        # 如果最高置信度都低于阈值，则认为需要绕道思考
        return max_confidence < threshold
    
    def get_confidence_analysis(self) -> Dict[str, any]:
        """
        获取置信度分析报告
        
        Returns:
            置信度分析数据
        """
        confidence_scores = self.get_all_paths_confidence()
        
        if not confidence_scores:
            return {
                'total_paths': 0,
                'max_confidence': 0.0,
                'min_confidence': 0.0,
                'avg_confidence': 0.0,
                'low_confidence_paths': 0,
                'high_confidence_paths': 0,
                'confidence_distribution': {}
            }
        
        values = list(confidence_scores.values())
        low_confidence_count = sum(1 for conf in values if conf < 0.3)
        high_confidence_count = sum(1 for conf in values if conf > 0.7)
        
        # 置信度分布统计
        distribution = {
            'very_low (0.0-0.2)': sum(1 for conf in values if 0.0 <= conf < 0.2),
            'low (0.2-0.4)': sum(1 for conf in values if 0.2 <= conf < 0.4),
            'medium (0.4-0.6)': sum(1 for conf in values if 0.4 <= conf < 0.6),
            'high (0.6-0.8)': sum(1 for conf in values if 0.6 <= conf < 0.8),
            'very_high (0.8-1.0)': sum(1 for conf in values if 0.8 <= conf <= 1.0)
        }
        
        return {
            'total_paths': len(confidence_scores),
            'max_confidence': max(values),
            'min_confidence': min(values),
            'avg_confidence': sum(values) / len(values),
            'low_confidence_paths': low_confidence_count,
            'high_confidence_paths': high_confidence_count,
            'confidence_distribution': distribution,
            'detailed_scores': confidence_scores
        }
    
    # ==================== 🔧 辅助计算方法 ====================
    
    def _calculate_recent_trend(self, arm: EnhancedDecisionArm) -> str:
        """
        计算路径的最近性能趋势
        
        Args:
            arm: 决策臂对象
            
        Returns:
            趋势字符串: 'improving', 'declining', 'stable', 'insufficient_data'
        """
        if len(arm.recent_results) < 4:
            return 'insufficient_data'
        
        # 取最近的结果，分为两半进行比较
        recent = arm.recent_results[-10:] if len(arm.recent_results) >= 10 else arm.recent_results
        mid_point = len(recent) // 2
        
        if mid_point < 2:
            return 'insufficient_data'
        
        # 计算前半段和后半段的成功率
        earlier_half = recent[:mid_point]
        later_half = recent[mid_point:]
        
        earlier_rate = sum(earlier_half) / len(earlier_half)
        later_rate = sum(later_half) / len(later_half)
        
        # 判断趋势
        if later_rate > earlier_rate + 0.1:  # 10%的改善视为improving
            return 'improving'
        elif later_rate < earlier_rate - 0.1:  # 10%的下降视为declining
            return 'declining'
        else:
            return 'stable'
    
    def _calculate_consecutive_successes(self, arm: EnhancedDecisionArm) -> int:
        """
        计算连续成功次数
        
        Args:
            arm: 决策臂对象
            
        Returns:
            连续成功次数
        """
        if not arm.recent_results:
            return 0
        
        consecutive_count = 0
        # 从最近的结果开始往前数
        for result in reversed(arm.recent_results):
            if result:  # 如果是成功
                consecutive_count += 1
            else:  # 如果失败了，就停止计数
                break
        
        return consecutive_count
    
    # ==================== 🎯 根源修复完成：移除复杂解析逻辑 ====================
    # 注意：_resolve_strategy_id 方法已移除，因为数据源头现在直接提供正确的策略ID
    
    def _infer_path_type_from_strategy_id(self, strategy_id: str) -> str:
        """
        从策略ID推断路径类型
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            推断的路径类型
        """
        # 策略ID到路径类型的映射表
        strategy_to_type_mapping = {
            'systematic_analytical': '系统分析型',
            'creative_innovative': '创新突破型',
            'critical_questioning': '批判质疑型',
            'practical_pragmatic': '实用务实型',
            'holistic_comprehensive': '整体综合型',
            'exploratory_investigative': '探索调研型',
            'collaborative_consultative': '协作咨询型',
            'adaptive_flexible': '适应灵活型',
            
            # 兼容性映射（中文路径类型）
            '系统分析': '系统分析型',
            '创新突破': '创新突破型',
            '批判质疑': '批判质疑型',
            '实用务实': '实用务实型',
            '整体综合': '整体综合型',
            '探索调研': '探索调研型',
            '协作咨询': '协作咨询型',
            '适应灵活': '适应灵活型'
        }
        
        # 直接匹配
        if strategy_id in strategy_to_type_mapping:
            return strategy_to_type_mapping[strategy_id]
        
        # 模糊匹配
        strategy_lower = strategy_id.lower()
        for key, value in strategy_to_type_mapping.items():
            if key.lower() in strategy_lower or strategy_lower in key.lower():
                logger.debug(f"🔍 模糊匹配策略类型: {strategy_id} -> {value}")
                return value
        
        # 基于关键词推断
        if 'systematic' in strategy_lower or 'analytical' in strategy_lower or '系统' in strategy_id:
            return '系统分析型'
        elif 'creative' in strategy_lower or 'innovative' in strategy_lower or '创新' in strategy_id:
            return '创新突破型'
        elif 'critical' in strategy_lower or 'questioning' in strategy_lower or '批判' in strategy_id:
            return '批判质疑型'
        elif 'practical' in strategy_lower or 'pragmatic' in strategy_lower or '实用' in strategy_id:
            return '实用务实型'
        elif 'holistic' in strategy_lower or 'comprehensive' in strategy_lower or '整体' in strategy_id:
            return '整体综合型'
        elif 'exploratory' in strategy_lower or 'investigative' in strategy_lower or '探索' in strategy_id:
            return '探索调研型'
        elif 'collaborative' in strategy_lower or 'consultative' in strategy_lower or '协作' in strategy_id:
            return '协作咨询型'
        elif 'adaptive' in strategy_lower or 'flexible' in strategy_lower or '适应' in strategy_id:
            return '适应灵活型'
        
        # 默认返回
        logger.debug(f"⚠️ 无法推断路径类型，使用默认: {strategy_id} -> 通用方法型")
        return '通用方法型'


# 🔄 向后兼容性：保持原有的MABConverger类名
MABConverger = ContextualMABConverger

# 为了完全向后兼容，我们也可以创建一个简单的工厂函数
def create_mab_converger(algorithm: str = "linucb", **kwargs) -> ContextualMABConverger:
    """
    创建MAB收敛器的工厂函数
    
    Args:
        algorithm: 使用的算法
        **kwargs: 其他参数
        
    Returns:
        ContextualMABConverger实例
    """
    return ContextualMABConverger(algorithm=algorithm, **kwargs)
