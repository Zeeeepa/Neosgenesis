#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
认知引擎包 - Cognitive Engine Package

包含Neogenesis系统的核心认知组件：
- 语义分析器 (semantic_analyzer.py)
- 先验推理器 (reasoner.py) 
- 路径生成器 (path_generator.py)
- MAB收敛器 (mab_converger.py)
- 路径库 (path_library.py)
- 数据结构 (data_structures.py)
"""

__version__ = "1.0.0"
__author__ = "Neogenesis Team"

# 导入主要的类和函数
try:
    from .semantic_analyzer import SemanticAnalyzer, AnalysisTaskType, AnalysisTask
except ImportError:
    SemanticAnalyzer = None
    AnalysisTaskType = None
    AnalysisTask = None

try:
    from .reasoner import PriorReasoner, TaskComplexity, TaskDomain, TaskIntent
except ImportError:
    PriorReasoner = None
    TaskComplexity = None
    TaskDomain = None
    TaskIntent = None

try:
    from .path_generator import PathGenerator, LLMDrivenDimensionCreator
except ImportError:
    PathGenerator = None
    LLMDrivenDimensionCreator = None

try:
    from .mab_converger import MABConverger
except ImportError:
    MABConverger = None

try:
    from .data_structures import (
        ReasoningPath, TaskContext, DecisionResult, 
        PerformanceFeedback, SystemStatus, EnhancedDecisionArm
    )
except ImportError:
    ReasoningPath = None
    TaskContext = None
    DecisionResult = None
    PerformanceFeedback = None
    SystemStatus = None
    EnhancedDecisionArm = None

__all__ = [
    # 语义分析相关
    "SemanticAnalyzer",
    "AnalysisTaskType", 
    "AnalysisTask",
    
    # 推理相关
    "PriorReasoner",
    "TaskComplexity",
    "TaskDomain", 
    "TaskIntent",
    
    # 路径生成相关
    "PathGenerator",
    "LLMDrivenDimensionCreator",
    
    # MAB相关
    "MABConverger",
    
    # 数据结构
    "ReasoningPath",
    "TaskContext",
    "DecisionResult",
    "PerformanceFeedback", 
    "SystemStatus",
    "EnhancedDecisionArm",
]
