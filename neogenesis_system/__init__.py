#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Neogenesis System - 智能决策系统
A modular intelligent decision-making system powered by LLMs and MAB algorithms

主要组件:
- MainController: 主控制器，协调所有组件
- PriorReasoner: 先验推理器，任务理解和置信度评估
- PathGenerator: 路径生成器，维度生成和路径规划
- MABConverger: MAB收敛器，多臂老虎机算法决策
"""

__version__ = "1.0.0"
__author__ = "Neogenesis Team"
__email__ = "team@neogenesis.ai"

# 导入核心组件
# from .meta_mab.controller import MainController  # 已废弃，使用 NeogenesisPlanner
from .cognitive_engine.reasoner import PriorReasoner
from .cognitive_engine.path_generator import PathGenerator, LLMDrivenDimensionCreator
from .cognitive_engine.mab_converger import MABConverger

# 导入框架级通用数据结构
from .shared.data_structures import (
    Action,
    Plan,
    Observation,
    ExecutionContext,
    AgentState,
    ActionStatus,
    PlanStatus,
    # 中心化上下文协议数据结构
    StageContext,
    ThinkingSeedContext,
    SeedVerificationContext,
    PathGenerationContext,
    PathVerificationContext,
    MABDecisionContext,
    StrategyDecision
)

# 导入框架接口抽象
from .abstractions import (
    BasePlanner,
    BaseToolExecutor,
    BaseAsyncToolExecutor,
    BaseMemory,
    BaseAgent,
    BaseAsyncAgent,
    create_agent
)

# 导入具体实现
from .core.neogenesis_planner import NeogenesisPlanner

# 导入领域特定数据结构
from .cognitive_engine.data_structures import (
    ReasoningPath,
    TaskComplexity,
    EnhancedDecisionArm,
    TaskContext,
    DecisionResult,
    PerformanceFeedback,
    SystemStatus
)

# 导入工具（已迁移到适配器模式）
# from .meta_mab.utils.api_caller import DeepSeekAPICaller  # 已弃用，使用 DeepSeekClientAdapter

# 导入配置
from .config import (
    DEEPSEEK_API_BASE,
    DEEPSEEK_MODEL,
    API_CONFIG,
    MAB_CONFIG,
    SYSTEM_LIMITS,
    EVALUATION_CONFIG,
    PROMPT_TEMPLATES,
    FEATURE_FLAGS,
    PERFORMANCE_CONFIG
)

__all__ = [
    # 核心组件
    # "MainController",  # 已废弃，使用 NeogenesisPlanner
    "PriorReasoner", 
    "PathGenerator",
    "LLMDrivenDimensionCreator",
    "MABConverger",
    
    # 框架级通用数据结构
    "Action",
    "Plan", 
    "Observation",
    "ExecutionContext",
    "AgentState",
    "ActionStatus",
    "PlanStatus",
    
    # 中心化上下文协议数据结构
    "StageContext",
    "ThinkingSeedContext",
    "SeedVerificationContext",
    "PathGenerationContext",
    "PathVerificationContext",
    "MABDecisionContext",
    "StrategyDecision",
    
    # 框架接口抽象
    "BasePlanner",
    "BaseToolExecutor",
    "BaseAsyncToolExecutor", 
    "BaseMemory",
    "BaseAgent",
    "BaseAsyncAgent",
    "create_agent",
    
    # 具体实现
    "NeogenesisPlanner",
    
    # 领域特定数据结构
    "ReasoningPath",
    "TaskComplexity",
    "EnhancedDecisionArm",
    "TaskContext",
    "DecisionResult",
    "PerformanceFeedback",
    "SystemStatus",
    
    # 工具（已迁移到适配器模式）
    # "DeepSeekAPICaller",  # 已弃用，使用 DeepSeekClientAdapter
    
    # 配置
    "DEEPSEEK_API_BASE",
    "DEEPSEEK_MODEL",
    "API_CONFIG",
    "MAB_CONFIG", 
    "SYSTEM_LIMITS",
    "EVALUATION_CONFIG",
    "PROMPT_TEMPLATES",
    "FEATURE_FLAGS",
    "PERFORMANCE_CONFIG"
]


def create_system(api_key: str = None, config: dict = None):
    """
    创建Neogenesis智能决策系统实例
    
    Args:
        api_key: DeepSeek API密钥（可选，用于完整功能）
        config: 系统配置字典
        
    Returns:
        NeogenesisPlanner实例
        
    Example:
        >>> from neogenesis_system.planners import NeogenesisPlanner
        >>> planner = create_system()
        >>> plan = planner.create_plan("查询最近上映的电影")
        >>> print(plan.actions)
    """
    from .core.neogenesis_planner import NeogenesisPlanner
    from .cognitive_engine.reasoner import PriorReasoner
    from .cognitive_engine.path_generator import PathGenerator
    from .cognitive_engine.mab_converger import MABConverger
    
    # 创建组件
    prior_reasoner = PriorReasoner(api_key or "")
    
    # 创建LLM客户端（智能选择最佳可用客户端）
    llm_client = None
    if api_key:
        try:
            # 优先尝试使用LLM管理器来自动选择最佳客户端
            from .providers.llm_manager import LLMManager
            llm_manager = LLMManager()
            if llm_manager.initialized and llm_manager.providers:
                llm_client = llm_manager
            else:
                # 回退到DeepSeek客户端
                from .providers.impl.deepseek_client import create_llm_client
                llm_client = create_llm_client(api_key)
        except Exception as e:
            # 静默失败，不在create_system函数中打印错误
            pass
    
    path_generator = PathGenerator(api_key or "", llm_client=llm_client)
    mab_converger = MABConverger()
    
    return NeogenesisPlanner(
        prior_reasoner=prior_reasoner,
        path_generator=path_generator,
        mab_converger=mab_converger
    )


def get_version() -> str:
    """获取系统版本号"""
    return __version__


def get_system_info() -> dict:
    """获取系统信息"""
    return {
        "name": "Neogenesis System",
        "version": __version__,
        "description": "智能决策系统 - LLM驱动的多臂老虎机决策框架",
        "author": __author__,
        "components": [
            "NeogenesisPlanner",
            "PriorReasoner", 
            "PathGenerator",
            "MABConverger"
        ],
        "features": [
            "AI驱动的动态维度创建",
            "多臂老虎机算法优化",
            "强化学习反馈机制",
            "组件化架构设计",
            "多LLM智能推理集成"
        ]
    }
