#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据结构定义 - 存放所有数据类和类型定义
Data Structures - contains all data classes and type definitions

扩展功能:
- 知识溯源 (Knowledge Provenance) 支持
- 学习路径的完整生命周期追踪
- 知识网络和关联管理
"""

import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

# 导入知识溯源系统
try:
    from ..shared.data_structures import KnowledgeProvenance, SourceReference, KnowledgeSource, CredibilityLevel
except ImportError:
    # 如果无法导入知识溯源系统，设置为空类型以保持兼容性
    KnowledgeProvenance = type(None)
    SourceReference = type(None)
    KnowledgeSource = None 
    CredibilityLevel = None


@dataclass
class ReasoningPath:
    """
    代表一个完整且独特的思考范式
    
    扩展功能：
    - 支持知识溯源 (Knowledge Provenance)
    - 增强的元数据系统
    - 学习路径的完整生命周期追踪
    """
    # 基础路径信息（保持向后兼容）
    path_id: str  # 路径的唯一标识，例如 'systematic_methodical_v1'
    path_type: str  # 路径类型，如 '系统方法型', '创新直觉型', '批判质疑型'
    description: str  # 对这条思维路径的详细描述
    prompt_template: str  # 执行该路径时，用于生成最终提示的核心模板
    
    # 🎯 MAB学习修复：新增策略级别固定ID用于MAB学习
    strategy_id: str = ""  # 策略级别的固定ID，用于MAB学习（如'systematic_analytical'）
    instance_id: str = ""  # 实例级别的唯一ID，用于会话追踪（如'systematic_analytical_v1_1703123456789_1234'）
    
    # 🌟 知识溯源系统 (Knowledge Provenance)
    provenance: Optional[KnowledgeProvenance] = None  # 完整的知识溯源信息
    
    # 🔍 增强的元数据系统
    name: str = ""  # 路径友好名称
    steps: List[str] = field(default_factory=list)  # 思维步骤详细列表
    keywords: List[str] = field(default_factory=list)  # 关键词标签
    complexity_level: int = 3  # 复杂度级别 (1-5)
    estimated_steps: int = 5  # 预估步骤数
    success_indicators: List[str] = field(default_factory=list)  # 成功指标
    failure_patterns: List[str] = field(default_factory=list)  # 失败模式
    
    # 📊 性能和使用统计
    usage_count: int = 0  # 使用次数
    success_rate: float = 0.0  # 成功率
    avg_execution_time: float = 0.0  # 平均执行时间
    last_used: Optional[float] = None  # 最后使用时间
    
    # 🔗 关联和上下文
    context_tags: Set[str] = field(default_factory=set)  # 上下文标签
    applicable_domains: List[str] = field(default_factory=list)  # 适用领域
    prerequisites: List[str] = field(default_factory=list)  # 前置条件
    related_paths: List[str] = field(default_factory=list)  # 相关路径ID
    
    # 🎯 学习和进化相关
    learning_source: str = "static"  # 学习来源: static, learned_exploration, manual_addition
    confidence_score: float = 1.0  # 置信度分数 (0.0-1.0)
    validation_status: str = "unverified"  # 验证状态: unverified, pending, verified, conflicting
    evolution_generation: int = 0  # 进化代数 (0=原始, 1+=演化版本)
    parent_path_id: Optional[str] = None  # 父路径ID (如果是演化版本)
    
    # 📝 扩展元数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据字典
    
    def __post_init__(self):
        """初始化后处理：增强版本，支持知识溯源初始化"""
        # 🎯 基本兼容性检查（保持原有逻辑）
        if not self.strategy_id:
            self.strategy_id = self.path_id
            
        if not self.instance_id:
            self.instance_id = self.path_id
        
        # 📝 从现有字段推导友好名称
        if not self.name:
            self.name = self.path_type or self.path_id
        
        # 🔍 从元数据中提取知识溯源信息（如果存在）
        if not self.provenance and self.metadata.get("source"):
            self._initialize_provenance_from_metadata()
        
        # ⏰ 设置初始时间戳
        if not self.last_used and self.usage_count > 0:
            self.last_used = time.time()
    
    def _initialize_provenance_from_metadata(self):
        """从现有metadata初始化知识溯源信息"""
        if KnowledgeProvenance is None:
            return  # 知识溯源系统不可用
        
        try:
            # 创建基础溯源记录
            self.provenance = KnowledgeProvenance(
                knowledge_id=self.path_id,
                confidence_score=self.confidence_score,
                context_tags=self.context_tags.copy() if self.context_tags else set()
            )
            
            # 从元数据创建源引用
            source_info = self.metadata.get("source")
            if isinstance(source_info, str):
                source_ref = SourceReference(
                    title=f"路径来源: {source_info}",
                    source_type=self._infer_knowledge_source(source_info),
                    metadata={"original_source": source_info}
                )
                self.provenance.add_source(source_ref, is_primary=True)
            
            # 添加学习相关信息
            if "learned_from" in self.metadata:
                self.provenance.add_context_tag("learned_path")
                self.provenance.add_context_tag(self.metadata["learned_from"])
            
            # 设置置信度
            if "confidence" in self.metadata:
                confidence = float(self.metadata["confidence"])
                self.provenance.confidence_score = confidence
                self.confidence_score = confidence
                
        except Exception as e:
            # 如果初始化失败，记录但不中断
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"知识溯源初始化失败 for {self.path_id}: {e}")
    
    def _infer_knowledge_source(self, source_info: str) -> Optional[Any]:
        """根据源信息推断知识来源类型"""
        if KnowledgeSource is None:
            return None
            
        source_lower = source_info.lower()
        if "web" in source_lower or "网络" in source_lower:
            return KnowledgeSource.WEB_SCRAPING
        elif "api" in source_lower:
            return KnowledgeSource.API_QUERY
        elif "exploration" in source_lower or "探索" in source_lower:
            return KnowledgeSource.KNOWLEDGE_BASE
        elif "user" in source_lower or "用户" in source_lower:
            return KnowledgeSource.USER_INPUT
        else:
            return KnowledgeSource.UNKNOWN
    
    # 🚀 知识溯源相关方法
    
    def add_provenance_source(self, url: Optional[str] = None, title: Optional[str] = None, 
                            author: Optional[str] = None, source_type: Optional[Any] = None,
                            content: Optional[str] = None) -> bool:
        """
        添加知识来源信息
        
        Args:
            url: 源URL
            title: 源标题  
            author: 作者
            source_type: 来源类型
            content: 内容（用于生成哈希）
            
        Returns:
            是否成功添加
        """
        if self.provenance is None:
            if KnowledgeProvenance is None:
                return False  # 知识溯源系统不可用
            self.provenance = KnowledgeProvenance(knowledge_id=self.path_id)
        
        try:
            source_ref = SourceReference(
                url=url,
                title=title or f"路径来源: {self.name}",
                author=author,
                source_type=source_type or KnowledgeSource.UNKNOWN if KnowledgeSource else None
            )
            
            if content:
                source_ref.generate_content_hash(content)
            
            self.provenance.add_source(source_ref)
            return True
        except Exception:
            return False
    
    def record_usage(self, success: bool = True, execution_time: Optional[float] = None):
        """
        记录路径使用情况
        
        Args:
            success: 是否成功
            execution_time: 执行时间
        """
        self.usage_count += 1
        self.last_used = time.time()
        
        # 更新成功率
        if self.usage_count == 1:
            self.success_rate = 1.0 if success else 0.0
        else:
            # 指数移动平均
            alpha = 0.1  # 学习率
            new_success_rate = 1.0 if success else 0.0
            self.success_rate = (1 - alpha) * self.success_rate + alpha * new_success_rate
        
        # 更新执行时间
        if execution_time is not None:
            if self.avg_execution_time == 0.0:
                self.avg_execution_time = execution_time
            else:
                alpha = 0.1
                self.avg_execution_time = (1 - alpha) * self.avg_execution_time + alpha * execution_time
        
        # 更新知识溯源记录
        if self.provenance:
            self.provenance.record_usage(success)
    
    def add_context_tag(self, tag: str):
        """添加上下文标签"""
        self.context_tags.add(tag)
        if self.provenance:
            self.provenance.add_context_tag(tag)
    
    def remove_context_tag(self, tag: str):
        """移除上下文标签"""
        self.context_tags.discard(tag)
        if self.provenance:
            self.provenance.remove_context_tag(tag)
    
    def update_confidence(self, new_confidence: float, reason: str = ""):
        """
        更新置信度
        
        Args:
            new_confidence: 新的置信度值 (0.0-1.0)
            reason: 更新原因
        """
        old_confidence = self.confidence_score
        self.confidence_score = max(0.0, min(1.0, new_confidence))
        
        # 更新知识溯源记录
        if self.provenance:
            from ..shared.data_structures import KnowledgeUpdate
            if KnowledgeUpdate:
                update = KnowledgeUpdate(
                    update_type="confidence_update",
                    reason=reason or "置信度更新",
                    confidence_change=self.confidence_score - old_confidence
                )
                update.add_change(f"置信度从 {old_confidence:.3f} 更新到 {self.confidence_score:.3f}")
                self.provenance.add_update(update)
    
    def mark_as_verified(self, verification_method: str = "manual", 
                        confidence: float = 0.9, notes: str = ""):
        """
        标记路径为已验证
        
        Args:
            verification_method: 验证方法
            confidence: 验证置信度
            notes: 验证备注
        """
        self.validation_status = "verified"
        
        if self.provenance:
            from ..shared.data_structures import KnowledgeValidation, VerificationStatus
            if KnowledgeValidation and VerificationStatus:
                validation = KnowledgeValidation(
                    validation_method=verification_method,
                    status=VerificationStatus.VERIFIED,
                    confidence_score=confidence,
                    notes=notes
                )
                self.provenance.add_validation(validation)
    
    def create_evolved_version(self, changes: List[str], reason: str = "") -> 'ReasoningPath':
        """
        创建当前路径的进化版本
        
        Args:
            changes: 变更描述列表
            reason: 进化原因
            
        Returns:
            新的进化版本路径
        """
        # 生成新的路径ID
        new_generation = self.evolution_generation + 1
        new_path_id = f"{self.path_id}_v{new_generation}"
        
        # 创建进化版本
        evolved_path = ReasoningPath(
            path_id=new_path_id,
            path_type=self.path_type,
            description=self.description,
            prompt_template=self.prompt_template,
            name=f"{self.name} v{new_generation}",
            steps=self.steps.copy(),
            keywords=self.keywords.copy(),
            complexity_level=self.complexity_level,
            estimated_steps=self.estimated_steps,
            success_indicators=self.success_indicators.copy(),
            failure_patterns=self.failure_patterns.copy(),
            context_tags=self.context_tags.copy(),
            applicable_domains=self.applicable_domains.copy(),
            learning_source="evolved",
            confidence_score=self.confidence_score * 0.9,  # 新版本初始置信度略低
            evolution_generation=new_generation,
            parent_path_id=self.path_id,
            metadata=self.metadata.copy()
        )
        
        # 如果父路径有溯源信息，继承并标记为衍生
        if self.provenance:
            evolved_path.provenance = KnowledgeProvenance(
                knowledge_id=new_path_id,
                confidence_score=evolved_path.confidence_score,
                context_tags=self.context_tags.copy()
            )
            
            # 继承主要来源
            if self.provenance.primary_source:
                evolved_path.provenance.add_source(self.provenance.primary_source)
            
            # 记录进化更新
            from ..shared.data_structures import KnowledgeUpdate
            if KnowledgeUpdate:
                update = KnowledgeUpdate(
                    update_type="evolution_update",
                    reason=reason or "路径进化",
                    changes=changes.copy(),
                    source="evolution_system"
                )
                evolved_path.provenance.add_update(update)
            
            # 建立知识网络关联
            evolved_path.provenance.knowledge_network.add_relationship(
                self.path_id, "derived", similarity_score=0.8,
                metadata={"relationship": "evolved_version", "generation": new_generation}
            )
        
        return evolved_path
    
    # 🔍 查询和分析方法
    
    @property
    def is_learned_path(self) -> bool:
        """判断是否为学习路径"""
        return self.learning_source in ["learned_exploration", "manual_addition", "evolved"]
    
    @property
    def is_verified(self) -> bool:
        """判断是否已验证"""
        if self.validation_status == "verified":
            return True
        if self.provenance:
            return self.provenance.is_verified
        return False
    
    @property
    def has_conflicts(self) -> bool:
        """判断是否存在冲突"""
        if self.validation_status == "conflicting":
            return True
        if self.provenance:
            return self.provenance.has_conflicts
        return False
    
    @property
    def age_in_days(self) -> float:
        """获取路径年龄（天）"""
        if self.provenance:
            return self.provenance.age_in_days
        return 0.0
    
    @property
    def freshness_score(self) -> float:
        """计算新鲜度分数"""
        if self.provenance:
            return self.provenance.freshness_score
        return 1.0  # 静态路径默认新鲜度
    
    def get_provenance_summary(self) -> Dict[str, Any]:
        """获取知识溯源摘要"""
        base_summary = {
            "path_id": self.path_id,
            "name": self.name,
            "learning_source": self.learning_source,
            "confidence_score": self.confidence_score,
            "validation_status": self.validation_status,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "is_learned_path": self.is_learned_path,
            "is_verified": self.is_verified,
            "has_conflicts": self.has_conflicts,
            "evolution_generation": self.evolution_generation,
            "parent_path_id": self.parent_path_id,
            "context_tags": list(self.context_tags),
            "applicable_domains": self.applicable_domains
        }
        
        # 如果有详细的知识溯源信息，添加到摘要中
        if self.provenance:
            provenance_summary = self.provenance.get_provenance_summary()
            base_summary.update({
                "detailed_provenance": provenance_summary,
                "age_days": self.age_in_days,
                "freshness_score": self.freshness_score,
                "network_connections": provenance_summary.get("network_connections", 0),
                "source_count": provenance_summary.get("source_count", 0)
            })
        
        return base_summary
    
    def get(self, key: str, default=None):
        """
        🔧 向后兼容性方法：提供类似字典的 get 方法
        
        这个方法允许代码以字典方式访问 ReasoningPath 对象的属性，
        避免 'ReasoningPath' object has no attribute 'get' 错误
        
        Args:
            key: 属性名
            default: 默认值
            
        Returns:
            属性值或默认值
        """
        return getattr(self, key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        🔧 转换为字典格式，便于序列化和兼容性处理
        
        Returns:
            包含所有属性的字典
        """
        return {
            "path_id": self.path_id,
            "path_type": self.path_type,
            "description": self.description,
            "prompt_template": self.prompt_template,
            "strategy_id": self.strategy_id,
            "instance_id": self.instance_id,
            "name": self.name,
            "steps": self.steps,
            "keywords": self.keywords,
            "complexity_level": self.complexity_level,
            "estimated_steps": self.estimated_steps,
            "success_indicators": self.success_indicators,
            "failure_patterns": self.failure_patterns,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "last_used": self.last_used,
            "context_tags": list(self.context_tags),
            "applicable_domains": self.applicable_domains,
            "prerequisites": self.prerequisites,
            "related_paths": self.related_paths,
            "learning_source": self.learning_source,
            "confidence_score": self.confidence_score,
            "validation_status": self.validation_status,
            "evolution_generation": self.evolution_generation,
            "parent_path_id": self.parent_path_id,
            "metadata": self.metadata
        }


@dataclass 
class TaskComplexity:
    """任务复杂度"""
    overall_score: float = 0.5
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class EnhancedDecisionArm:
    """决策臂 - 追踪思维路径的性能"""
    path_id: str  # 关联的思维路径ID
    option: str = ""  # 路径类型/选项 (兼容性字段)
    
    # 基础性能追踪
    success_count: int = 0
    failure_count: int = 0
    total_reward: float = 0.0
    
    # 历史记录（限制长度避免内存膨胀）
    recent_rewards: List[float] = field(default_factory=list)  # 最近的奖励记录
    rl_reward_history: List[float] = field(default_factory=list)  # RL奖励历史
    recent_results: List[bool] = field(default_factory=list)  # 最近的执行结果
    
    # 使用统计
    activation_count: int = 0
    last_used: float = 0.0
    
    def update_performance(self, success: bool, reward: float):
        """更新性能数据"""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            
        self.total_reward += reward
        self.recent_rewards.append(reward)
        self.rl_reward_history.append(reward)  # 添加到RL奖励历史
        self.recent_results.append(success)  # 添加到结果历史
        
        # 限制历史长度
        if len(self.recent_rewards) > 20:
            self.recent_rewards = self.recent_rewards[-10:]
        if len(self.rl_reward_history) > 50:
            self.rl_reward_history = self.rl_reward_history[-25:]
        if len(self.recent_results) > 50:
            self.recent_results = self.recent_results[-25:]
            
        self.activation_count += 1
        self.last_used = time.time()
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / max(total, 1)
    
    @property
    def average_reward(self) -> float:
        """平均奖励"""
        if not self.recent_rewards:
            return 0.0
        return sum(self.recent_rewards) / len(self.recent_rewards)
    
    @property
    def total_uses(self) -> int:
        """总使用次数"""
        return self.success_count + self.failure_count


@dataclass
class TaskContext:
    """任务上下文"""
    user_query: str
    task_type: str = "general"
    complexity_score: float = 0.5
    deepseek_confidence: float = 0.5
    real_time_requirements: bool = False
    domain_tags: List[str] = field(default_factory=list)
    execution_context: Optional[Dict] = None
    dynamic_classification: Optional[Dict] = None


@dataclass
class DecisionResult:
    """决策结果数据结构"""
    timestamp: float
    round_number: int
    user_query: str
    selected_dimensions: Dict[str, str]
    confidence_scores: Dict[str, float]
    task_confidence: float
    complexity_analysis: Dict[str, Any]
    mab_decisions: Dict[str, Dict[str, Any]]
    reasoning: str
    fallback_used: bool
    component_architecture: bool = True
    
    # 可选字段
    overall_confidence: Optional[float] = None
    algorithm_used: Optional[str] = None
    dimension_count: Optional[int] = None
    bypass_reason: Optional[str] = None
    direct_response: Optional[str] = None


@dataclass
class PerformanceFeedback:
    """性能反馈数据结构"""
    timestamp: float
    execution_success: bool
    execution_time: float
    user_satisfaction: float
    rl_reward: float
    task_completion_score: float = 0.0
    error_details: Optional[str] = None
    output_quality_score: Optional[float] = None


@dataclass
class LimitationAnalysis:
    """局限性分析结果"""
    type: str
    severity: float
    description: str
    specific_context: str
    impact: str
    confidence: float
    compensation_strategy: List[str]
    source: str
    timestamp: float


@dataclass
class AlternativeThinkingSignal:
    """替代思考信号"""
    timestamp: float
    user_query: str
    reason: str
    suggested_reassessment: bool
    creative_approaches_needed: bool
    environmental_exploration: bool


@dataclass
class FailureAnalysis:
    """失败分析结果"""
    timestamp: float
    user_query: str
    failed_dimensions: Dict[str, str]
    rl_reward: float
    failure_severity: float
    consecutive_failures: int
    context_change_needed: bool
    alternative_strategies: List[str]


@dataclass
class SuccessPattern:
    """成功模式数据结构"""
    pattern_id: str
    dimension_combination: Dict[str, str]
    success_contexts: List[str]
    quality_score: float
    replication_count: int
    confidence: float
    last_used: float
    
    
@dataclass
class SystemStatus:
    """系统状态数据结构"""
    total_rounds: int
    component_architecture: bool
    prior_reasoner_assessments: int
    path_generator_cache_size: int
    mab_converger_arms: int
    convergence_status: Dict[str, bool]
    recent_decisions: int
    
    # 性能指标
    avg_decision_time: Optional[float] = None
    success_rate: Optional[float] = None
    exploration_rate: Optional[float] = None
