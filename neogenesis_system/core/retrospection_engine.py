#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务回溯引擎 - Task Retrospection Engine
Agent的"记忆回放"和经验提取核心大脑

这个引擎实现了从"被动应激"到"主动认知"的关键转换：
- 选择阶段 (Select): 智能挑选有价值的历史任务进行复盘
- 创想阶段 (Ideate): 主动激活LLMDrivenDimensionCreator和Aha-Moment机制
- 沉淀阶段 (Assimilate): 将新知识融入MAB系统，形成进化闭环

核心创新：让Agent主动从过往经验中学习，而不是被动等待危机触发
"""

import time
import random
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from ..shared.state_manager import StateManager, ConversationTurn, TaskPhase, GoalStatus
from ..cognitive_engine.data_structures import ReasoningPath, TaskComplexity
from ..cognitive_engine.path_generator import PathGenerator, LLMDrivenDimensionCreator
from ..cognitive_engine.mab_converger import MABConverger

logger = logging.getLogger(__name__)


class RetrospectionStrategy(Enum):
    """回溯策略枚举"""
    RANDOM_SAMPLING = "random_sampling"           # 随机采样
    FAILURE_FOCUSED = "failure_focused"           # 专注失败任务
    COMPLEXITY_BASED = "complexity_based"         # 基于复杂度选择
    LOW_SATISFACTION = "low_satisfaction"         # 低满意度优先
    TOOL_FAILURE = "tool_failure"                 # 工具调用失败
    RECENT_TASKS = "recent_tasks"                 # 最近任务优先


@dataclass
class RetrospectionTask:
    """回溯任务数据结构"""
    task_id: str
    original_turn: ConversationTurn
    selection_reason: str
    selection_strategy: RetrospectionStrategy
    complexity_score: float = 0.0
    priority_score: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class RetrospectionResult:
    """回溯结果数据结构"""
    retrospection_id: str
    task: RetrospectionTask
    
    # 创想结果
    llm_dimensions: List[Dict[str, Any]] = field(default_factory=list)
    aha_moment_paths: List[ReasoningPath] = field(default_factory=list)
    
    # 分析洞察
    insights: Dict[str, Any] = field(default_factory=dict)
    success_patterns: List[str] = field(default_factory=list)
    failure_causes: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # 工具复盘结果
    tool_retrospection: Dict[str, Any] = field(default_factory=dict)
    
    # 沉淀状态
    assimilated_strategies: List[str] = field(default_factory=list)
    mab_updates: List[Dict[str, Any]] = field(default_factory=list)
    
    # 元数据
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)


class TaskRetrospectionEngine:
    """
    🔍 任务回溯引擎 - Agent的"记忆回放"与智慧萃取器
    
    核心职责：
    1. 智能任务选择：从历史中挑选最有价值的复盘对象
    2. 双重创想激活：主动调用LLMDrivenDimensionCreator + Aha-Moment
    3. 知识沉淀融合：将新思路注入MAB系统，形成学习闭环
    
    设计哲学：
    - 从"被动等待危机"升级为"主动挖掘潜能"
    - 让每个历史任务都成为未来决策的智慧源泉
    - 构建Agent的"内在独白"和"自我进化"能力
    """
    
    def __init__(self, 
                 path_generator: Optional[PathGenerator] = None,
                 mab_converger: Optional[MABConverger] = None,
                 llm_client=None,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化任务回溯引擎
        
        Args:
            path_generator: 路径生成器实例（用于Aha-Moment激活）
            mab_converger: MAB收敛器实例（用于知识沉淀）
            llm_client: LLM客户端（用于深度分析）
            config: 引擎配置参数
        """
        self.path_generator = path_generator
        self.mab_converger = mab_converger
        self.llm_client = llm_client
        
        # 配置参数
        self.config = {
            # 任务选择配置
            "task_selection": {
                "default_strategy": RetrospectionStrategy.RANDOM_SAMPLING,
                "max_task_age_hours": 24.0,        # 最大任务年龄（小时）
                "min_complexity_threshold": 0.3,   # 最小复杂度阈值
                "failure_priority_boost": 2.0,     # 失败任务优先级加权
                "max_tasks_per_session": 5         # 每次会话最大回溯任务数
            },
            
            # 创想激活配置
            "ideation": {
                "enable_llm_dimensions": True,      # 启用LLM维度创想
                "enable_aha_moment": True,          # 启用Aha-Moment机制
                "max_new_dimensions": 3,            # 最大新维度数量
                "max_creative_paths": 4,            # 最大创意路径数量
                "creative_prompt_temperature": 0.8  # 创意提示词温度
            },
            
            # 知识沉淀配置
            "assimilation": {
                "enable_mab_injection": True,       # 启用MAB注入
                "initial_exploration_reward": 0.1,  # 初始探索奖励
                "knowledge_decay_factor": 0.95,     # 知识衰减因子
                "max_assimilated_strategies": 10    # 最大沉淀策略数
            },
            
            # 分析深度配置
            "analysis": {
                "enable_pattern_recognition": True,  # 启用模式识别
                "enable_failure_analysis": True,     # 启用失败分析
                "enable_insight_extraction": True,   # 启用洞察提取
                "min_pattern_confidence": 0.6       # 最小模式置信度
            }
        }
        
        # 合并用户配置
        if config:
            self._merge_config(self.config, config)
        
        # 创建LLM维度创建器
        self.llm_dimension_creator = None
        if self.llm_client:
            try:
                self.llm_dimension_creator = LLMDrivenDimensionCreator(
                    llm_client=self.llm_client
                )
                logger.info("🧠 LLM维度创建器已集成")
            except Exception as e:
                logger.warning(f"⚠️ LLM维度创建器初始化失败: {e}")
        
        # 回溯历史和统计
        self.retrospection_history: List[RetrospectionResult] = []
        self.selected_tasks_cache: Dict[str, RetrospectionTask] = {}
        
        # 性能统计
        self.stats = {
            "total_retrospections": 0,
            "total_tasks_analyzed": 0,
            "total_insights_generated": 0,
            "total_strategies_assimilated": 0,
            "average_execution_time": 0.0,
            "success_rate": 0.0
        }
        
        logger.info("🔍 TaskRetrospectionEngine 初始化完成")
        logger.info(f"   任务选择策略: {self.config['task_selection']['default_strategy'].value}")
        logger.info(f"   LLM创想: {'启用' if self.config['ideation']['enable_llm_dimensions'] else '禁用'}")
        logger.info(f"   Aha-Moment: {'启用' if self.config['ideation']['enable_aha_moment'] else '禁用'}")
        logger.info("💡 从'被动应激'升级为'主动认知' - 记忆回放引擎就绪")
    
    def perform_retrospection(self, 
                            state_manager: StateManager,
                            strategy: Optional[RetrospectionStrategy] = None,
                            target_task_id: Optional[str] = None) -> RetrospectionResult:
        """
        执行完整的任务回溯流程
        
        这是回溯引擎的主入口方法，实现完整的四阶段流程：
        1. Select: 智能选择回溯任务
        2. Ideate: 双重创想激活
        3. Assimilate: 知识沉淀融合
        4. Analyze: 深度分析 (包括专门的工具复盘分析)
        
        Args:
            state_manager: 状态管理器实例
            strategy: 回溯策略（可选，默认使用配置策略）
            target_task_id: 目标任务ID（可选，指定特定任务）
            
        Returns:
            完整的回溯结果，包括工具复盘分析
        """
        start_time = time.time()
        retrospection_id = f"retro_{int(time.time() * 1000)}"
        
        logger.info(f"🔍 开始任务回溯流程: {retrospection_id}")
        
        try:
            # ==================== 阶段一：选择 (Select) ====================
            logger.info("📋 阶段一：智能任务选择")
            
            if target_task_id:
                # 指定任务回溯
                selected_task = self._get_task_by_id(state_manager, target_task_id)
                if not selected_task:
                    raise ValueError(f"指定的任务ID不存在: {target_task_id}")
            else:
                # 智能任务选择
                used_strategy = strategy or self.config["task_selection"]["default_strategy"]
                selected_task = self.select_task_for_review(state_manager, used_strategy)
                
                if not selected_task:
                    logger.warning("🤷 未找到合适的回溯任务")
                    return self._create_empty_result(retrospection_id, start_time)
            
            logger.info(f"✅ 选中回溯任务: {selected_task.task_id}")
            logger.info(f"   选择原因: {selected_task.selection_reason}")
            logger.info(f"   原始问题: {selected_task.original_turn.user_input[:50]}...")
            
            # ==================== 阶段二：创想 (Ideate) ====================
            logger.info("💡 阶段二：双重创想激活")
            
            llm_dimensions = []
            aha_paths = []
            
            # 2a) 主动激活LLMDrivenDimensionCreator
            if (self.config["ideation"]["enable_llm_dimensions"] and 
                self.llm_dimension_creator):
                
                logger.info("🧠 激活LLM维度创想...")
                llm_dimensions = self._activate_llm_dimension_creation(selected_task)
                logger.info(f"   生成LLM维度: {len(llm_dimensions)} 个")
            
            # 2b) 主动激活Aha-Moment机制
            if (self.config["ideation"]["enable_aha_moment"] and 
                self.path_generator):
                
                logger.info("💥 激活Aha-Moment创意突破...")
                aha_paths = self._activate_aha_moment_creation(selected_task)
                logger.info(f"   生成创意路径: {len(aha_paths)} 条")
            
            # ==================== 阶段三：沉淀 (Assimilate) ====================
            logger.info("🧩 阶段三：知识沉淀融合")
            
            assimilated_strategies = []
            mab_updates = []
            
            if self.config["assimilation"]["enable_mab_injection"] and self.mab_converger:
                assimilated_strategies, mab_updates = self._assimilate_new_knowledge(
                    llm_dimensions, aha_paths
                )
                logger.info(f"   沉淀策略: {len(assimilated_strategies)} 个")
            
            # ==================== 深度分析与洞察提取 ====================
            logger.info("🔬 执行深度分析...")
            
            # 执行工具复盘分析
            tool_retrospection = self._perform_tool_retrospection(selected_task)
            
            insights = self._extract_insights(selected_task)
            success_patterns = self._identify_success_patterns(selected_task)
            failure_causes = self._analyze_failure_causes(selected_task)
            improvements = self._generate_improvement_suggestions(
                selected_task, llm_dimensions, aha_paths
            )
            
            # 构建回溯结果
            execution_time = time.time() - start_time
            result = RetrospectionResult(
                retrospection_id=retrospection_id,
                task=selected_task,
                llm_dimensions=llm_dimensions,
                aha_moment_paths=aha_paths,
                insights=insights,
                success_patterns=success_patterns,
                failure_causes=failure_causes,
                improvement_suggestions=improvements,
                tool_retrospection=tool_retrospection,
                assimilated_strategies=assimilated_strategies,
                mab_updates=mab_updates,
                execution_time=execution_time
            )
            
            # 更新统计
            self._update_stats(result)
            
            # 记录回溯历史
            self.retrospection_history.append(result)
            
            logger.info(f"✅ 回溯流程完成 (耗时: {execution_time:.2f}s)")
            logger.info(f"   生成洞察: {len(insights)} 项")
            logger.info(f"   识别模式: {len(success_patterns)} 个成功模式, {len(failure_causes)} 个失败原因")
            logger.info(f"   改进建议: {len(improvements)} 条")
            logger.info(f"   工具复盘: {tool_retrospection.get('analysis_status', 'unknown')} "
                       f"({tool_retrospection.get('tools_analyzed', 0)} 个工具)")
            if tool_retrospection.get('tool_optimization_suggestions'):
                logger.info(f"   工具优化: {len(tool_retrospection['tool_optimization_suggestions'])} 条建议")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ 回溯流程失败: {e} (耗时: {execution_time:.2f}s)")
            return self._create_error_result(retrospection_id, str(e), start_time)
    
    def select_task_for_review(self, 
                             state_manager: StateManager,
                             strategy: RetrospectionStrategy) -> Optional[RetrospectionTask]:
        """
        🎯 阶段一：智能任务选择
        
        从Agent的"记忆宫殿"中智能挑选最有价值的历史任务进行回溯
        
        Args:
            state_manager: 状态管理器实例
            strategy: 选择策略
            
        Returns:
            选中的回溯任务，如果没有合适任务则返回None
        """
        conversation_history = state_manager.conversation_history
        
        if not conversation_history:
            logger.warning("📭 对话历史为空，无法进行任务回溯")
            return None
        
        # 过滤候选任务
        candidates = self._filter_candidate_tasks(conversation_history)
        
        if not candidates:
            logger.warning("🚫 没有合适的候选任务")
            return None
        
        # 根据策略选择任务
        selected_turn = None
        selection_reason = ""
        
        if strategy == RetrospectionStrategy.RANDOM_SAMPLING:
            selected_turn = random.choice(candidates)
            selection_reason = "随机采样策略选择"
            
        elif strategy == RetrospectionStrategy.FAILURE_FOCUSED:
            failed_tasks = [turn for turn in candidates if not turn.success]
            if failed_tasks:
                selected_turn = random.choice(failed_tasks)
                selection_reason = "专注失败任务策略 - 从失败中学习"
            else:
                selected_turn = random.choice(candidates)
                selection_reason = "无失败任务，回退到随机选择"
                
        elif strategy == RetrospectionStrategy.COMPLEXITY_BASED:
            # 按复杂度排序（这里简化为按工具调用数量）
            complex_tasks = sorted(candidates, 
                                 key=lambda t: len(t.tool_calls), 
                                 reverse=True)
            selected_turn = complex_tasks[0] if complex_tasks else random.choice(candidates)
            selection_reason = f"高复杂度任务策略 - 工具调用数: {len(selected_turn.tool_calls)}"
            
        elif strategy == RetrospectionStrategy.RECENT_TASKS:
            # 选择最近的任务
            recent_tasks = sorted(candidates, key=lambda t: t.timestamp, reverse=True)
            selected_turn = recent_tasks[0]
            selection_reason = "最近任务优先策略"
            
        elif strategy == RetrospectionStrategy.TOOL_FAILURE:
            # 选择工具调用失败的任务
            tool_failed_tasks = []
            for turn in candidates:
                for tool_call in turn.tool_calls:
                    if not tool_call.get('success', True):
                        tool_failed_tasks.append(turn)
                        break
            
            if tool_failed_tasks:
                selected_turn = random.choice(tool_failed_tasks)
                selection_reason = "工具失败任务策略 - 分析工具调用问题"
            else:
                selected_turn = random.choice(candidates)
                selection_reason = "无工具失败任务，回退到随机选择"
        
        else:
            # 默认随机选择
            selected_turn = random.choice(candidates)
            selection_reason = "默认随机选择策略"
        
        # 构建回溯任务
        task = RetrospectionTask(
            task_id=selected_turn.turn_id,
            original_turn=selected_turn,
            selection_reason=selection_reason,
            selection_strategy=strategy,
            complexity_score=self._calculate_task_complexity(selected_turn),
            priority_score=self._calculate_priority_score(selected_turn, strategy)
        )
        
        # 缓存选择的任务
        self.selected_tasks_cache[task.task_id] = task
        
        logger.debug(f"🎯 任务选择详情:")
        logger.debug(f"   策略: {strategy.value}")
        logger.debug(f"   候选数量: {len(candidates)}")
        logger.debug(f"   选中任务: {task.task_id}")
        logger.debug(f"   复杂度: {task.complexity_score:.2f}")
        logger.debug(f"   优先级: {task.priority_score:.2f}")
        
        return task
    
    def _activate_llm_dimension_creation(self, 
                                       task: RetrospectionTask) -> List[Dict[str, Any]]:
        """
        🧠 激活LLM维度创想
        
        主动调用LLMDrivenDimensionCreator，为历史任务构思全新解决方案
        
        Args:
            task: 回溯任务
            
        Returns:
            LLM生成的新维度列表
        """
        if not self.llm_dimension_creator:
            logger.warning("⚠️ LLM维度创建器未可用")
            return []
        
        try:
            # 构建回顾性Prompt - 这是关键创新
            retrospective_prompt = self._build_retrospective_prompt(task)
            
            logger.debug(f"🧠 LLM回顾性提示词: {retrospective_prompt[:100]}...")
            
            # 调用维度创建器的核心方法
            # 注意：这里我们传入特殊的回顾性上下文，让LLM理解这是一个"重新思考"任务
            dimensions = self.llm_dimension_creator.create_dynamic_dimensions(
                task_description=retrospective_prompt,
                num_dimensions=self.config["ideation"]["max_new_dimensions"],
                creativity_level="high",
                context={
                    "mode": "retrospective_analysis",
                    "original_task": task.original_turn.user_input,
                    "original_response": task.original_turn.llm_response,
                    "task_metadata": {
                        "success": task.original_turn.success,
                        "tool_calls": len(task.original_turn.tool_calls),
                        "complexity": task.complexity_score
                    }
                }
            )
            
            logger.info(f"🧠 LLM维度创想完成: {len(dimensions)} 个新维度")
            
            return dimensions
            
        except Exception as e:
            logger.error(f"❌ LLM维度创想失败: {e}")
            return []
    
    def _activate_aha_moment_creation(self, 
                                    task: RetrospectionTask) -> List[ReasoningPath]:
        """
        💥 激活Aha-Moment创意突破
        
        强制系统使用creative_bypass模式，寻找非传统解决方案
        
        Args:
            task: 回溯任务
            
        Returns:
            生成的创意路径列表
        """
        if not self.path_generator:
            logger.warning("⚠️ 路径生成器未可用")
            return []
        
        try:
            # 构建创意种子 - 引导非传统思维
            creative_seed = f"为'{task.original_turn.user_input}'寻找突破性的、非传统的解决方案"
            
            logger.debug(f"💥 Aha-Moment创意种子: {creative_seed}")
            
            # 关键：使用creative_bypass模式强制激活创新思维
            creative_paths = self.path_generator.generate_paths(
                thinking_seed=creative_seed,
                task=task.original_turn.user_input,
                max_paths=self.config["ideation"]["max_creative_paths"],
                mode='creative_bypass'  # 🔑 这是关键参数！
            )
            
            # 过滤和优化创意路径
            filtered_paths = self._filter_creative_paths(creative_paths, task)
            
            logger.info(f"💥 Aha-Moment创意突破完成: {len(filtered_paths)} 条创意路径")
            
            return filtered_paths
            
        except Exception as e:
            logger.error(f"❌ Aha-Moment创意激活失败: {e}")
            return []
    
    def _assimilate_new_knowledge(self, 
                                llm_dimensions: List[Dict[str, Any]],
                                aha_paths: List[ReasoningPath]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        🧩 知识沉淀融合
        
        将回溯产生的新思路注入MAB系统，形成学习闭环
        
        Args:
            llm_dimensions: LLM生成的维度
            aha_paths: Aha-Moment路径
            
        Returns:
            (沉淀的策略ID列表, MAB更新记录列表)
        """
        if not self.mab_converger:
            logger.warning("⚠️ MAB收敛器未可用，无法进行知识沉淀")
            return [], []
        
        assimilated_strategies = []
        mab_updates = []
        
        try:
            # 处理LLM维度
            for dim in llm_dimensions:
                # 修复：ReasoningPath对象使用属性访问而非.get()方法
                dimension_id = getattr(dim, 'path_id', 'unknown')
                dimension_type = getattr(dim, 'path_type', 'creative_retrospection')
                
                strategy_id = f"retro_llm_{dimension_id}"
                
                # 注入MAB系统 - 利用动态创建能力
                success = self.mab_converger._create_strategy_arm_if_missing(
                    strategy_id, 
                    path_type=dimension_type
                )
                
                # 给予初始探索奖励
                initial_reward = self.config["assimilation"]["initial_exploration_reward"]
                update_result = self.mab_converger.update_path_performance(
                    strategy_id, 
                    success=True, 
                    reward=initial_reward,
                    source="retrospection"  # 🔍 标记来源为回溯分析
                )
                
                assimilated_strategies.append(strategy_id)
                mab_updates.append({
                    "strategy_id": strategy_id,
                    "source": "llm_dimension",
                    "initial_reward": initial_reward,
                    "dimension_data": dim
                })
                
                logger.debug(f"🧩 沉淀LLM维度: {strategy_id}")
            
            # 处理Aha-Moment路径
            for i, path in enumerate(aha_paths):
                try:
                    logger.debug(f"🔧 处理第{i+1}个Aha路径: {type(path)}")
                    
                    # 🔧 增强的防御性措施：多层检查确保安全访问
                    if isinstance(path, dict):
                        # 如果是字典，使用字典的 get 方法访问属性
                        strategy_id = path.get('path_id') or f"retro_aha_{int(time.time() * 1000)}"
                        path_type = path.get('path_type', 'creative_retrospection')
                        path_steps = path.get('steps', [])[:3] if path.get('steps') else []
                        confidence_score = path.get('confidence_score', 0.5)
                        logger.debug(f"   📋 字典模式访问成功: {strategy_id}")
                    elif hasattr(path, 'path_id'):
                        # 如果是 ReasoningPath 对象，使用安全的属性访问
                        strategy_id = getattr(path, 'path_id', None) or f"retro_aha_{int(time.time() * 1000)}"
                        path_type = getattr(path, 'path_type', 'creative_retrospection')
                        path_steps = getattr(path, 'steps', [])[:3] if hasattr(path, 'steps') else []
                        confidence_score = getattr(path, 'confidence_score', 0.5)
                        logger.debug(f"   🧠 对象模式访问成功: {strategy_id}")
                    else:
                        # 如果类型不明，使用默认值
                        logger.warning(f"⚠️ 未知路径类型，使用默认值: {type(path)}")
                        strategy_id = f"retro_aha_unknown_{int(time.time() * 1000)}_{i}"
                        path_type = 'creative_retrospection'
                        path_steps = []
                        confidence_score = 0.5
                    
                    # 注入MAB系统
                    success = self.mab_converger._create_strategy_arm_if_missing(
                        strategy_id,
                        path_type=path_type
                    )
                    
                    # 给予初始探索奖励
                    initial_reward = self.config["assimilation"]["initial_exploration_reward"]
                    update_result = self.mab_converger.update_path_performance(
                        strategy_id,
                        success=True,
                        reward=initial_reward * 1.2,  # Aha-Moment路径给予更高奖励
                        source="retrospection"  # 🔍 标记来源为回溯分析
                    )
                    
                    assimilated_strategies.append(strategy_id)
                    mab_updates.append({
                        "strategy_id": strategy_id,
                        "source": "aha_moment_path",
                        "initial_reward": initial_reward * 1.2,
                        "path_data": {
                            "path_type": path_type,
                            "steps": path_steps,
                            "confidence": confidence_score
                        }
                    })
                    
                    logger.debug(f"🧩 沉淀Aha-Moment路径: {strategy_id}")
                    
                except Exception as e:
                    logger.error(f"❌ 处理Aha-Moment路径时发生错误: {e}")
                    logger.error(f"   路径类型: {type(path)}")
                    logger.error(f"   路径内容: {path}")
                    continue
            
            logger.info(f"🧩 知识沉淀完成: {len(assimilated_strategies)} 个策略注入MAB系统")
            
        except Exception as e:
            logger.error(f"❌ 知识沉淀失败: {e}")
        
        return assimilated_strategies, mab_updates
    
    def _perform_tool_retrospection(self, task: RetrospectionTask) -> Dict[str, Any]:
        """
        🔧 工具复盘核心方法
        
        专门针对历史任务中的工具调用和结果进行精细化分析，
        提取工具使用模式、成功要素、失败根因，并生成工具选择优化建议。
        
        Args:
            task: 回溯任务，包含完整的工具调用历史
            
        Returns:
            包含工具复盘结果的字典，包括：
            - tool_usage_patterns: 工具使用模式分析
            - tool_success_factors: 工具成功要素
            - tool_failure_analysis: 工具失败分析  
            - tool_selection_insights: 工具选择洞察
            - tool_optimization_suggestions: 工具优化建议
        """
        logger.info(f"🔧 开始工具复盘分析: {task.task_id}")
        
        tool_calls = task.original_turn.tool_calls
        tool_results = getattr(task.original_turn, 'tool_results', [])
        
        if not tool_calls:
            logger.info("📝 该任务无工具调用，跳过工具复盘")
            return {
                "tool_usage_patterns": {},
                "tool_success_factors": [],
                "tool_failure_analysis": {},
                "tool_selection_insights": [],
                "tool_optimization_suggestions": [],
                "analysis_status": "no_tools_used"
            }
        
        logger.info(f"   分析 {len(tool_calls)} 个工具调用")
        
        # 1. 工具使用模式分析
        usage_patterns = self._analyze_tool_usage_patterns(tool_calls, tool_results)
        
        # 2. 工具成功要素提取
        success_factors = self._extract_tool_success_factors(tool_calls, tool_results)
        
        # 3. 工具失败根因分析
        failure_analysis = self._analyze_tool_failures(tool_calls, tool_results)
        
        # 4. 工具选择洞察挖掘
        selection_insights = self._extract_tool_selection_insights(
            tool_calls, tool_results, task
        )
        
        # 5. 工具优化建议生成
        optimization_suggestions = self._generate_tool_optimization_suggestions(
            usage_patterns, success_factors, failure_analysis, selection_insights
        )
        
        result = {
            "tool_usage_patterns": usage_patterns,
            "tool_success_factors": success_factors,
            "tool_failure_analysis": failure_analysis,
            "tool_selection_insights": selection_insights,
            "tool_optimization_suggestions": optimization_suggestions,
            "analysis_status": "completed",
            "tools_analyzed": len(tool_calls)
        }
        
        logger.info("🔧 工具复盘分析完成")
        logger.info(f"   识别模式: {len(usage_patterns)} 个")
        logger.info(f"   成功要素: {len(success_factors)} 个") 
        logger.info(f"   失败分析: {len(failure_analysis)} 项")
        logger.info(f"   优化建议: {len(optimization_suggestions)} 条")
        
        return result
    
    def _analyze_tool_usage_patterns(self, 
                                   tool_calls: List[Dict[str, Any]], 
                                   tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析工具使用模式"""
        patterns = {}
        
        # 工具调用序列分析
        tool_sequence = [call.get('tool_name', 'unknown') for call in tool_calls]
        patterns['call_sequence'] = tool_sequence
        patterns['sequence_length'] = len(tool_sequence)
        patterns['unique_tools'] = list(set(tool_sequence))
        patterns['tool_diversity'] = len(set(tool_sequence)) / len(tool_sequence) if tool_sequence else 0
        
        # 工具频次分析
        tool_frequency = {}
        for tool_name in tool_sequence:
            tool_frequency[tool_name] = tool_frequency.get(tool_name, 0) + 1
        patterns['tool_frequency'] = tool_frequency
        patterns['most_used_tool'] = max(tool_frequency.items(), key=lambda x: x[1]) if tool_frequency else None
        
        # 工具组合模式分析
        if len(tool_sequence) > 1:
            combinations = []
            for i in range(len(tool_sequence) - 1):
                combo = (tool_sequence[i], tool_sequence[i + 1])
                combinations.append(combo)
            patterns['tool_combinations'] = combinations
        else:
            patterns['tool_combinations'] = []
        
        # 参数使用模式分析
        param_patterns = {}
        for call in tool_calls:
            tool_name = call.get('tool_name', 'unknown')
            params = call.get('parameters', {})
            if tool_name not in param_patterns:
                param_patterns[tool_name] = {'param_types': set(), 'param_count': []}
            
            param_patterns[tool_name]['param_types'].update(params.keys())
            param_patterns[tool_name]['param_count'].append(len(params))
        
        # 转换集合为列表以便JSON序列化
        for tool_name in param_patterns:
            param_patterns[tool_name]['param_types'] = list(param_patterns[tool_name]['param_types'])
        
        patterns['parameter_patterns'] = param_patterns
        
        return patterns
    
    def _extract_tool_success_factors(self, 
                                    tool_calls: List[Dict[str, Any]], 
                                    tool_results: List[Dict[str, Any]]) -> List[str]:
        """提取工具成功要素"""
        success_factors = []
        
        successful_calls = []
        failed_calls = []
        
        for i, call in enumerate(tool_calls):
            is_successful = call.get('success', True)  # 默认成功
            if len(tool_results) > i:
                result = tool_results[i]
                is_successful = result.get('success', True)
            
            if is_successful:
                successful_calls.append(call)
            else:
                failed_calls.append(call)
        
        success_rate = len(successful_calls) / len(tool_calls) if tool_calls else 0
        
        if success_rate > 0.8:
            success_factors.append("整体工具调用成功率高")
        
        if successful_calls:
            # 分析成功工具的共同特征
            successful_tools = [call.get('tool_name') for call in successful_calls]
            tool_success_rate = {}
            for tool in set(successful_tools):
                total_calls = len([c for c in tool_calls if c.get('tool_name') == tool])
                success_calls = successful_tools.count(tool)
                tool_success_rate[tool] = success_calls / total_calls
            
            for tool, rate in tool_success_rate.items():
                if rate == 1.0:
                    success_factors.append(f"{tool}工具调用100%成功")
                elif rate > 0.8:
                    success_factors.append(f"{tool}工具调用成功率高({rate:.1%})")
        
        # 参数模式成功要素
        if successful_calls:
            common_params = set()
            for call in successful_calls[:3]:  # 分析前3个成功调用
                params = call.get('parameters', {})
                if not common_params:
                    common_params = set(params.keys())
                else:
                    common_params &= set(params.keys())
            
            if common_params:
                success_factors.append(f"成功调用共同包含参数: {', '.join(common_params)}")
        
        return success_factors
    
    def _analyze_tool_failures(self, 
                             tool_calls: List[Dict[str, Any]], 
                             tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析工具失败原因"""
        failure_analysis = {
            "failed_tools": [],
            "failure_patterns": [],
            "error_types": {},
            "failure_rate_by_tool": {},
            "critical_failures": []
        }
        
        failed_calls = []
        for i, call in enumerate(tool_calls):
            is_failed = not call.get('success', True)
            error_msg = ""
            
            if len(tool_results) > i:
                result = tool_results[i]
                is_failed = not result.get('success', True)
                error_msg = result.get('error_message', '') or result.get('error', '')
            
            if is_failed:
                failed_calls.append({
                    'call': call,
                    'error_message': error_msg,
                    'position': i
                })
        
        if not failed_calls:
            failure_analysis["status"] = "no_failures"
            return failure_analysis
        
        # 失败工具统计
        failure_analysis["failed_tools"] = [fc['call'].get('tool_name', 'unknown') for fc in failed_calls]
        
        # 失败率按工具计算
        all_tools = [call.get('tool_name', 'unknown') for call in tool_calls]
        for tool in set(all_tools):
            total = all_tools.count(tool)
            failed = failure_analysis["failed_tools"].count(tool)
            failure_analysis["failure_rate_by_tool"][tool] = failed / total if total > 0 else 0
        
        # 错误类型分析
        error_types = {}
        for fc in failed_calls:
            error_msg = fc['error_message'].lower()
            if 'timeout' in error_msg or '超时' in error_msg:
                error_types['timeout'] = error_types.get('timeout', 0) + 1
            elif 'permission' in error_msg or '权限' in error_msg:
                error_types['permission'] = error_types.get('permission', 0) + 1
            elif 'parameter' in error_msg or '参数' in error_msg:
                error_types['parameter'] = error_types.get('parameter', 0) + 1
            elif 'network' in error_msg or '网络' in error_msg:
                error_types['network'] = error_types.get('network', 0) + 1
            else:
                error_types['other'] = error_types.get('other', 0) + 1
        
        failure_analysis["error_types"] = error_types
        
        # 失败模式分析
        if len(failed_calls) > 1:
            # 连续失败检测
            positions = [fc['position'] for fc in failed_calls]
            consecutive_failures = any(positions[i] + 1 == positions[i + 1] for i in range(len(positions) - 1))
            if consecutive_failures:
                failure_analysis["failure_patterns"].append("存在连续工具调用失败")
        
        # 关键失败识别
        for fc in failed_calls:
            if fc['position'] == 0:
                failure_analysis["critical_failures"].append("首次工具调用失败，可能影响整体任务")
            if fc['position'] == len(tool_calls) - 1:
                failure_analysis["critical_failures"].append("最后工具调用失败，可能导致任务未完成")
        
        return failure_analysis
    
    def _extract_tool_selection_insights(self, 
                                       tool_calls: List[Dict[str, Any]], 
                                       tool_results: List[Dict[str, Any]],
                                       task: RetrospectionTask) -> List[str]:
        """提取工具选择洞察"""
        insights = []
        
        if not tool_calls:
            return ["任务未使用任何工具"]
        
        # 工具选择时机洞察
        task_complexity = task.complexity_score
        tool_count = len(tool_calls)
        
        if task_complexity > 0.7 and tool_count < 2:
            insights.append("高复杂度任务但工具使用较少，可能存在工具选择不足")
        elif task_complexity < 0.3 and tool_count > 5:
            insights.append("低复杂度任务但工具使用过多，可能存在工具选择冗余")
        
        # 工具多样性洞察
        unique_tools = len(set(call.get('tool_name') for call in tool_calls))
        diversity_ratio = unique_tools / tool_count if tool_count > 0 else 0
        
        if diversity_ratio < 0.3:
            insights.append("工具选择多样性不足，过度依赖特定工具")
        elif diversity_ratio > 0.8:
            insights.append("工具选择多样性高，策略探索充分")
        
        # 工具序列合理性洞察
        tool_sequence = [call.get('tool_name') for call in tool_calls]
        
        # 检查是否有明显的工具使用逻辑
        read_before_write = False
        if 'read_file' in tool_sequence and ('write' in str(tool_sequence) or 'edit' in str(tool_sequence)):
            read_pos = tool_sequence.index('read_file')
            write_pos = max([i for i, tool in enumerate(tool_sequence) 
                           if 'write' in tool or 'edit' in tool], default=-1)
            if read_pos < write_pos:
                read_before_write = True
                insights.append("遵循了先读取后写入的良好工具使用逻辑")
        
        # 搜索工具使用模式洞察
        search_tools = [tool for tool in tool_sequence if 'search' in tool or 'grep' in tool]
        if len(search_tools) > 3:
            insights.append("大量使用搜索工具，体现了信息收集的重要性")
        
        return insights
    
    def _generate_tool_optimization_suggestions(self, 
                                              usage_patterns: Dict[str, Any],
                                              success_factors: List[str],
                                              failure_analysis: Dict[str, Any],
                                              selection_insights: List[str]) -> List[str]:
        """生成工具优化建议"""
        suggestions = []
        
        # 基于使用模式的建议
        if usage_patterns.get('tool_diversity', 0) < 0.3:
            suggestions.append("建议增加工具选择的多样性，避免过度依赖单一工具")
        
        most_used = usage_patterns.get('most_used_tool')
        if most_used and most_used[1] > 5:
            suggestions.append(f"考虑减少对{most_used[0]}工具的过度使用，探索替代方案")
        
        # 基于失败分析的建议
        if failure_analysis.get("failed_tools"):
            high_failure_tools = [
                tool for tool, rate in failure_analysis.get("failure_rate_by_tool", {}).items()
                if rate > 0.5
            ]
            if high_failure_tools:
                suggestions.append(f"重点优化高失败率工具: {', '.join(high_failure_tools)}")
        
        error_types = failure_analysis.get("error_types", {})
        if error_types.get('parameter', 0) > 0:
            suggestions.append("加强工具调用参数验证，减少参数错误")
        if error_types.get('timeout', 0) > 0:
            suggestions.append("对超时敏感的工具增加重试机制")
        
        # 基于成功要素的建议
        if "100%成功" in str(success_factors):
            suggestions.append("保持和推广100%成功率工具的使用模式")
        
        # 基于选择洞察的建议
        for insight in selection_insights:
            if "工具选择不足" in insight:
                suggestions.append("增加工具调用数量，提供更丰富的信息支持")
            elif "工具选择冗余" in insight:
                suggestions.append("精简工具调用，提高执行效率")
            elif "多样性不足" in insight:
                suggestions.append("扩展工具选择范围，增强解决方案的鲁棒性")
        
        return suggestions
    
    # ==================== 辅助分析方法 ====================
    
    def _build_retrospective_prompt(self, task: RetrospectionTask) -> str:
        """构建回顾性Prompt"""
        original_question = task.original_turn.user_input
        original_answer = task.original_turn.llm_response[:500]  # 截断避免过长
        
        prompt = f"""
回顾性任务分析：

历史任务：'{original_question}'

当时的解决方案：'{original_answer}'

现在请你以全新的视角重新审视这个问题：
1. 不受当时决策的束缚，构想出2-3种完全不同的解决思路
2. 从不同的维度和角度切入这个问题
3. 探索当时可能没有考虑到的创新方案
4. 重点关注解决方案的多样性和创造性

请为这个历史任务构想全新的解决维度和方法。
        """
        
        return prompt.strip()
    
    def _filter_candidate_tasks(self, 
                              conversation_history: List[ConversationTurn]) -> List[ConversationTurn]:
        """过滤候选任务"""
        max_age_seconds = self.config["task_selection"]["max_task_age_hours"] * 3600
        current_time = time.time()
        
        candidates = []
        for turn in conversation_history:
            # 过滤条件
            age = current_time - turn.timestamp
            
            # 跳过太新或太老的任务
            if age < 60 or age > max_age_seconds:  # 至少1分钟前的任务
                continue
            
            # 跳过空白任务
            if not turn.user_input.strip() or len(turn.user_input) < 10:
                continue
            
            candidates.append(turn)
        
        return candidates
    
    def _calculate_task_complexity(self, turn: ConversationTurn) -> float:
        """计算任务复杂度"""
        complexity = 0.0
        
        # 基于输入长度
        complexity += min(len(turn.user_input) / 500, 0.3)
        
        # 基于工具调用数量
        complexity += min(len(turn.tool_calls) * 0.2, 0.4)
        
        # 基于MAB决策数量
        complexity += min(len(turn.mab_decisions) * 0.1, 0.2)
        
        # 基于执行时间（如果有记录）
        if hasattr(turn, 'execution_time'):
            complexity += min(getattr(turn, 'execution_time', 0) / 60, 0.1)
        
        return min(complexity, 1.0)
    
    def _calculate_priority_score(self, 
                                turn: ConversationTurn, 
                                strategy: RetrospectionStrategy) -> float:
        """计算优先级分数"""
        score = 0.5  # 基础分数
        
        # 策略加权
        if strategy == RetrospectionStrategy.FAILURE_FOCUSED and not turn.success:
            score += self.config["task_selection"]["failure_priority_boost"]
        
        if strategy == RetrospectionStrategy.COMPLEXITY_BASED:
            score += self._calculate_task_complexity(turn)
        
        if strategy == RetrospectionStrategy.RECENT_TASKS:
            age_hours = (time.time() - turn.timestamp) / 3600
            score += max(0, 1.0 - age_hours / 24)  # 24小时内的任务加分
        
        return min(score, 3.0)
    
    def _filter_creative_paths(self, 
                             paths: List[ReasoningPath], 
                             task: RetrospectionTask) -> List[ReasoningPath]:
        """过滤和优化创意路径"""
        if not paths:
            return []
        
        # 简单过滤：移除质量过低的路径
        filtered = []
        for path in paths:
            confidence = getattr(path, 'confidence_score', 0.5)
            if confidence >= 0.3:  # 最低置信度阈值
                filtered.append(path)
        
        # 限制数量
        max_paths = self.config["ideation"]["max_creative_paths"]
        return filtered[:max_paths]
    
    def _extract_insights(self, task: RetrospectionTask) -> Dict[str, Any]:
        """提取洞察"""
        return {
            "task_characteristics": {
                "complexity": task.complexity_score,
                "success": task.original_turn.success,
                "tool_usage": len(task.original_turn.tool_calls),
                "mab_decisions": len(task.original_turn.mab_decisions)
            },
            "execution_context": {
                "phase": task.original_turn.phase.value,
                "error_message": task.original_turn.error_message
            }
        }
    
    def _identify_success_patterns(self, task: RetrospectionTask) -> List[str]:
        """识别成功模式"""
        patterns = []
        
        if task.original_turn.success:
            if task.original_turn.tool_calls:
                patterns.append("成功的工具调用组合")
            
            if task.complexity_score > 0.7:
                patterns.append("高复杂度任务成功处理")
            
            if len(task.original_turn.mab_decisions) > 2:
                patterns.append("多步骤MAB决策成功")
        
        return patterns
    
    def _analyze_failure_causes(self, task: RetrospectionTask) -> List[str]:
        """分析失败原因"""
        causes = []
        
        if not task.original_turn.success:
            if task.original_turn.error_message:
                causes.append(f"系统错误: {task.original_turn.error_message}")
            
            if not task.original_turn.tool_calls:
                causes.append("缺少必要的工具调用")
            
            failed_tools = []
            for tool_call in task.original_turn.tool_calls:
                if not tool_call.get('success', True):
                    failed_tools.append(tool_call.get('tool_name', 'unknown'))
            
            if failed_tools:
                causes.append(f"工具调用失败: {', '.join(failed_tools)}")
        
        return causes
    
    def _generate_improvement_suggestions(self, 
                                        task: RetrospectionTask,
                                        llm_dimensions: List[Dict[str, Any]],
                                        aha_paths: List[ReasoningPath]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # 基于回溯结果的建议
        if llm_dimensions:
            suggestions.append(f"考虑采用{len(llm_dimensions)}种LLM生成的新思路维度")
        
        if aha_paths:
            suggestions.append(f"尝试{len(aha_paths)}条Aha-Moment创意突破路径")
        
        # 基于任务特征的建议
        if task.complexity_score > 0.8:
            suggestions.append("对高复杂度任务考虑分解处理策略")
        
        if not task.original_turn.success and not task.original_turn.tool_calls:
            suggestions.append("增加工具调用以提供更丰富的信息支持")
        
        return suggestions
    
    def _get_task_by_id(self, 
                       state_manager: StateManager, 
                       task_id: str) -> Optional[RetrospectionTask]:
        """根据ID获取任务"""
        for turn in state_manager.conversation_history:
            if turn.turn_id == task_id:
                return RetrospectionTask(
                    task_id=task_id,
                    original_turn=turn,
                    selection_reason="用户指定任务",
                    selection_strategy=RetrospectionStrategy.RANDOM_SAMPLING,
                    complexity_score=self._calculate_task_complexity(turn)
                )
        return None
    
    def _create_empty_result(self, 
                           retrospection_id: str, 
                           start_time: float) -> RetrospectionResult:
        """创建空回溯结果"""
        return RetrospectionResult(
            retrospection_id=retrospection_id,
            task=None,
            execution_time=time.time() - start_time,
            insights={"status": "no_suitable_tasks"}
        )
    
    def _create_error_result(self, 
                           retrospection_id: str, 
                           error_msg: str, 
                           start_time: float) -> RetrospectionResult:
        """创建错误回溯结果"""
        return RetrospectionResult(
            retrospection_id=retrospection_id,
            task=None,
            execution_time=time.time() - start_time,
            insights={"status": "error", "error_message": error_msg}
        )
    
    def _update_stats(self, result: RetrospectionResult):
        """更新统计信息"""
        self.stats["total_retrospections"] += 1
        
        if result.task:
            self.stats["total_tasks_analyzed"] += 1
        
        self.stats["total_insights_generated"] += len(result.insights)
        self.stats["total_strategies_assimilated"] += len(result.assimilated_strategies)
        
        # 更新平均执行时间
        total_time = (self.stats["average_execution_time"] * (self.stats["total_retrospections"] - 1) + 
                      result.execution_time)
        self.stats["average_execution_time"] = total_time / self.stats["total_retrospections"]
        
        # 更新成功率
        successful = 1 if result.task and len(result.insights) > 0 else 0
        total_successful = (self.stats["success_rate"] * (self.stats["total_retrospections"] - 1) + 
                           successful)
        self.stats["success_rate"] = total_successful / self.stats["total_retrospections"]
    
    def _merge_config(self, base_config: Dict, user_config: Dict):
        """递归合并配置"""
        for key, value in user_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def get_retrospection_stats(self) -> Dict[str, Any]:
        """获取回溯统计信息"""
        return {
            **self.stats,
            "recent_retrospections": len(self.retrospection_history[-10:]),
            "cached_tasks": len(self.selected_tasks_cache),
            "config": self.config
        }
    
    def clear_history(self):
        """清理回溯历史"""
        self.retrospection_history.clear()
        self.selected_tasks_cache.clear()
        logger.info("🧹 回溯历史已清理")
