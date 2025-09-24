#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用数据结构定义 - Universal Data Structures
定义框架级别的核心数据结构，为所有模块提供统一的数据格式

这些数据结构是框架的基础"词汇"，确保所有组件都能以相同的方式理解和交换信息。

扩展功能:
- 知识溯源 (Knowledge Provenance) 系统
- 学习路径的完整生命周期追踪
- 知识网络和关联管理
"""

import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from enum import Enum
from urllib.parse import urlparse


class ActionStatus(Enum):
    """行动状态枚举"""
    PENDING = "pending"       # 等待执行
    EXECUTING = "executing"   # 正在执行
    COMPLETED = "completed"   # 执行完成
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 跳过执行


class PlanStatus(Enum):
    """计划状态枚举"""
    CREATED = "created"       # 已创建
    EXECUTING = "executing"   # 正在执行
    COMPLETED = "completed"   # 执行完成
    FAILED = "failed"         # 执行失败
    CANCELLED = "cancelled"   # 已取消


@dataclass
class Action:
    """
    行动 - 最基本的指令单元
    
    这是框架中最基本的执行单位。每个Action代表一次具体的工具调用，
    清楚地说明了要使用哪个工具以及需要什么输入参数。
    
    Attributes:
        tool_name: 工具名称，必须是已注册的工具
        tool_input: 工具输入参数，字典格式
        action_id: 行动的唯一标识符
        status: 行动状态
        created_at: 创建时间戳
        started_at: 开始执行时间戳
        completed_at: 完成时间戳
        metadata: 附加元数据
    """
    tool_name: str
    tool_input: Dict[str, Any]
    action_id: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成action_id"""
        if not self.action_id:
            timestamp = int(time.time() * 1000)
            self.action_id = f"action_{self.tool_name}_{timestamp}"
    
    def start_execution(self):
        """标记行动开始执行"""
        self.status = ActionStatus.EXECUTING
        self.started_at = time.time()
    
    def complete_execution(self):
        """标记行动执行完成"""
        self.status = ActionStatus.COMPLETED
        self.completed_at = time.time()
    
    def fail_execution(self):
        """标记行动执行失败"""
        self.status = ActionStatus.FAILED
        self.completed_at = time.time()
    
    @property
    def execution_time(self) -> Optional[float]:
        """计算执行时间"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class Plan:
    """
    计划 - 规划器的最终输出
    
    Plan是Planner生成的完整执行方案，包含Agent的思考过程和具体的行动序列。
    如果任务不需要工具就能直接回答，Plan会包含final_answer。
    
    Attributes:
        thought: Agent的思考过程，解释为什么选择这些行动
        actions: 行动列表，按执行顺序排列
        final_answer: 如果不需要工具就能回答，直接提供答案
        plan_id: 计划的唯一标识符
        status: 计划状态
        created_at: 创建时间戳
        metadata: 附加元数据
        confidence: 计划的置信度分数
        estimated_time: 预估执行时间
    """
    thought: str
    actions: List[Action] = field(default_factory=list)
    final_answer: Optional[str] = None
    plan_id: str = ""
    status: PlanStatus = PlanStatus.CREATED
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    estimated_time: Optional[float] = None
    
    def __post_init__(self):
        """初始化后处理：生成plan_id"""
        if not self.plan_id:
            timestamp = int(time.time() * 1000)
            self.plan_id = f"plan_{timestamp}"
    
    def add_action(self, action: Action):
        """添加行动到计划中"""
        self.actions.append(action)
    
    def start_execution(self):
        """标记计划开始执行"""
        self.status = PlanStatus.EXECUTING
    
    def complete_execution(self):
        """标记计划执行完成"""
        self.status = PlanStatus.COMPLETED
    
    def fail_execution(self):
        """标记计划执行失败"""
        self.status = PlanStatus.FAILED
    
    def cancel_execution(self):
        """标记计划已取消"""
        self.status = PlanStatus.CANCELLED
    
    @property
    def is_direct_answer(self) -> bool:
        """判断是否为直接回答（不需要执行工具）"""
        return self.final_answer is not None and len(self.actions) == 0
    
    @property
    def action_count(self) -> int:
        """获取行动数量"""
        return len(self.actions)
    
    @property
    def pending_actions(self) -> List[Action]:
        """获取待执行的行动"""
        return [action for action in self.actions if action.status == ActionStatus.PENDING]
    
    @property
    def completed_actions(self) -> List[Action]:
        """获取已完成的行动"""
        return [action for action in self.actions if action.status == ActionStatus.COMPLETED]


@dataclass
class Observation:
    """
    观察 - 执行行动后的结果
    
    Observation记录了执行某个Action后得到的具体结果，包括成功输出或错误信息。
    这是Agent学习和调整策略的重要数据来源。
    
    Attributes:
        action: 执行的行动对象
        output: 工具返回的输出结果
        success: 执行是否成功
        error_message: 如果失败，错误信息
        execution_time: 执行耗时
        timestamp: 观察记录的时间戳
        metadata: 附加元数据
    """
    action: Action
    output: str
    success: bool = True
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def action_id(self) -> str:
        """获取关联的行动ID"""
        return self.action.action_id
    
    @property
    def tool_name(self) -> str:
        """获取使用的工具名称"""
        return self.action.tool_name
    
    def is_successful(self) -> bool:
        """判断执行是否成功"""
        return self.success and self.error_message is None


@dataclass
class ExecutionContext:
    """
    执行上下文 - 记录完整的执行过程
    
    ExecutionContext跟踪一个完整的任务执行过程，包括计划、所有观察结果和最终状态。
    这为系统提供了完整的执行历史和学习数据。
    
    Attributes:
        plan: 执行的计划
        observations: 所有观察结果
        final_result: 最终执行结果
        total_time: 总执行时间
        context_id: 上下文的唯一标识符
        created_at: 创建时间戳
        metadata: 附加元数据
    """
    plan: Plan
    observations: List[Observation] = field(default_factory=list)
    final_result: Optional[str] = None
    total_time: Optional[float] = None
    context_id: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成context_id"""
        if not self.context_id:
            timestamp = int(time.time() * 1000)
            self.context_id = f"ctx_{timestamp}"
    
    def add_observation(self, observation: Observation):
        """添加观察结果"""
        self.observations.append(observation)
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if not self.observations:
            return 0.0
        successful = sum(1 for obs in self.observations if obs.is_successful())
        return successful / len(self.observations)
    
    @property
    def failed_observations(self) -> List[Observation]:
        """获取失败的观察结果"""
        return [obs for obs in self.observations if not obs.is_successful()]
    
    @property
    def successful_observations(self) -> List[Observation]:
        """获取成功的观察结果"""
        return [obs for obs in self.observations if obs.is_successful()]


@dataclass
class AgentState:
    """
    Agent状态 - 记录Agent的当前状态和历史
    
    AgentState维护Agent的完整状态信息，包括当前执行的任务、历史记录和性能统计。
    
    Attributes:
        current_context: 当前执行上下文
        execution_history: 历史执行记录
        memory_state: 内存状态快照
        performance_metrics: 性能指标
        state_id: 状态的唯一标识符
        last_updated: 最后更新时间
        metadata: 附加元数据
    """
    current_context: Optional[ExecutionContext] = None
    execution_history: List[ExecutionContext] = field(default_factory=list)
    memory_state: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    state_id: str = ""
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成state_id"""
        if not self.state_id:
            timestamp = int(time.time() * 1000)
            self.state_id = f"state_{timestamp}"
    
    def update_context(self, context: ExecutionContext):
        """更新当前执行上下文"""
        if self.current_context:
            self.execution_history.append(self.current_context)
        self.current_context = context
        self.last_updated = time.time()
    
    def complete_current_task(self):
        """完成当前任务"""
        if self.current_context:
            self.execution_history.append(self.current_context)
            self.current_context = None
            self.last_updated = time.time()
    
    @property
    def total_executions(self) -> int:
        """获取总执行次数"""
        return len(self.execution_history)
    
    @property
    def average_success_rate(self) -> float:
        """计算平均成功率"""
        if not self.execution_history:
            return 0.0
        total_rate = sum(ctx.success_rate for ctx in self.execution_history)
        return total_rate / len(self.execution_history)


# ========================================
# 知识溯源 (Knowledge Provenance) 系统
# ========================================

class KnowledgeSource(Enum):
    """知识来源类型枚举"""
    WEB_SCRAPING = "web_scraping"           # 网络爬取
    API_QUERY = "api_query"                 # API查询
    DOCUMENT_ANALYSIS = "document_analysis" # 文档分析
    ACADEMIC_PAPER = "academic_paper"       # 学术论文
    EXPERT_SYSTEM = "expert_system"         # 专家系统
    USER_INPUT = "user_input"              # 用户输入
    INTERNAL_REASONING = "internal_reasoning" # 内部推理
    KNOWLEDGE_BASE = "knowledge_base"       # 知识库
    REAL_TIME_DATA = "real_time_data"      # 实时数据
    SOCIAL_MEDIA = "social_media"          # 社交媒体
    NEWS_FEED = "news_feed"                # 新闻订阅
    SCIENTIFIC_DATABASE = "scientific_database" # 科学数据库
    GOVERNMENT_DATA = "government_data"     # 政府数据
    COMMERCIAL_API = "commercial_api"       # 商业API
    PEER_AGENT = "peer_agent"              # 其他Agent
    UNKNOWN = "unknown"                    # 未知来源


class CredibilityLevel(Enum):
    """可信度级别枚举"""
    VERY_HIGH = "very_high"     # 极高 (0.9-1.0)
    HIGH = "high"               # 高 (0.7-0.9)
    MEDIUM = "medium"           # 中等 (0.5-0.7)
    LOW = "low"                 # 低 (0.3-0.5)
    VERY_LOW = "very_low"       # 极低 (0.1-0.3)
    UNVERIFIED = "unverified"   # 未验证 (0.0-0.1)


class VerificationStatus(Enum):
    """验证状态枚举"""
    NOT_VERIFIED = "not_verified"           # 未验证
    PENDING_VERIFICATION = "pending_verification" # 等待验证
    PARTIALLY_VERIFIED = "partially_verified"     # 部分验证
    VERIFIED = "verified"                   # 已验证
    CONFLICTING = "conflicting"             # 存在冲突
    OUTDATED = "outdated"                  # 已过时
    INVALID = "invalid"                    # 无效


@dataclass
class SourceReference:
    """
    源引用信息 - 记录知识的具体来源
    
    用于详细记录知识的原始来源，支持引用追踪和验证。
    
    Attributes:
        url: 源URL（如果适用）
        title: 源标题或名称
        author: 作者或创建者
        published_date: 发布日期
        access_date: 访问日期
        source_type: 源类型
        content_hash: 内容哈希值（用于检测变更）
        metadata: 额外的源信息
    """
    url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[float] = None
    access_date: float = field(default_factory=time.time)
    source_type: KnowledgeSource = KnowledgeSource.UNKNOWN
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        # 从URL推断源类型
        if self.url and self.source_type == KnowledgeSource.UNKNOWN:
            self.source_type = self._infer_source_type_from_url(self.url)
    
    def _infer_source_type_from_url(self, url: str) -> KnowledgeSource:
        """根据URL推断源类型"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            if any(academic in domain for academic in ['arxiv', 'scholar.google', 'pubmed', 'ieee', 'acm']):
                return KnowledgeSource.ACADEMIC_PAPER
            elif any(news in domain for news in ['news', 'cnn', 'bbc', 'reuters', 'nytimes']):
                return KnowledgeSource.NEWS_FEED
            elif any(social in domain for social in ['twitter', 'facebook', 'linkedin', 'reddit']):
                return KnowledgeSource.SOCIAL_MEDIA
            elif any(gov in domain for gov in ['.gov', 'government']):
                return KnowledgeSource.GOVERNMENT_DATA
            elif 'api' in parsed.path.lower():
                return KnowledgeSource.API_QUERY
            else:
                return KnowledgeSource.WEB_SCRAPING
        except:
            return KnowledgeSource.UNKNOWN
    
    def generate_content_hash(self, content: str) -> str:
        """生成内容哈希值"""
        self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        return self.content_hash
    
    @property
    def is_web_source(self) -> bool:
        """判断是否为网络源"""
        return self.url is not None and self.url.startswith(('http://', 'https://'))
    
    @property
    def domain(self) -> Optional[str]:
        """获取域名"""
        if self.url:
            try:
                return urlparse(self.url).netloc
            except:
                pass
        return None


@dataclass
class KnowledgeValidation:
    """
    知识验证记录 - 记录知识的验证过程和结果
    
    用于追踪知识的验证历史，包括验证方法、结果和置信度。
    
    Attributes:
        validation_id: 验证记录ID
        validation_method: 验证方法
        validator: 验证者（系统或人员）
        validation_date: 验证日期
        status: 验证状态
        confidence_score: 置信度分数 (0.0-1.0)
        evidence: 验证证据
        conflicts: 发现的冲突
        notes: 验证备注
        metadata: 额外验证信息
    """
    validation_id: str = ""
    validation_method: str = "automatic"
    validator: str = "system"
    validation_date: float = field(default_factory=time.time)
    status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    confidence_score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成validation_id"""
        if not self.validation_id:
            timestamp = int(time.time() * 1000)
            self.validation_id = f"validation_{timestamp}"
    
    def add_evidence(self, evidence: str):
        """添加验证证据"""
        self.evidence.append(evidence)
    
    def add_conflict(self, conflict: str):
        """添加发现的冲突"""
        self.conflicts.append(conflict)
    
    @property
    def is_verified(self) -> bool:
        """判断是否已验证"""
        return self.status in [VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED]
    
    @property
    def has_conflicts(self) -> bool:
        """判断是否存在冲突"""
        return len(self.conflicts) > 0 or self.status == VerificationStatus.CONFLICTING


@dataclass
class KnowledgeUpdate:
    """
    知识更新记录 - 追踪知识的更新历史
    
    用于维护知识的版本历史，支持知识进化追踪。
    
    Attributes:
        update_id: 更新记录ID
        update_date: 更新日期
        update_type: 更新类型
        previous_version_hash: 之前版本的哈希值
        new_version_hash: 新版本的哈希值
        changes: 变更描述
        reason: 更新原因
        source: 更新来源
        confidence_change: 置信度变化
        metadata: 更新元信息
    """
    update_id: str = ""
    update_date: float = field(default_factory=time.time)
    update_type: str = "content_update"  # content_update, confidence_update, verification_update
    previous_version_hash: Optional[str] = None
    new_version_hash: Optional[str] = None
    changes: List[str] = field(default_factory=list)
    reason: str = ""
    source: str = "system"
    confidence_change: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成update_id"""
        if not self.update_id:
            timestamp = int(time.time() * 1000)
            self.update_id = f"update_{timestamp}"
    
    def add_change(self, change: str):
        """添加变更描述"""
        self.changes.append(change)


@dataclass
class KnowledgeNetwork:
    """
    知识关联网络 - 管理知识之间的关系
    
    用于建立和维护知识点之间的关联，支持知识图谱构建。
    
    Attributes:
        related_knowledge: 相关知识ID列表
        contradictory_knowledge: 矛盾知识ID列表
        supporting_knowledge: 支持性知识ID列表
        derived_from: 派生来源知识ID列表
        influences: 影响的知识ID列表
        similarity_scores: 与相关知识的相似度分数
        relationship_metadata: 关系元信息
    """
    related_knowledge: List[str] = field(default_factory=list)
    contradictory_knowledge: List[str] = field(default_factory=list)
    supporting_knowledge: List[str] = field(default_factory=list)
    derived_from: List[str] = field(default_factory=list)
    influences: List[str] = field(default_factory=list)
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    relationship_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def add_relationship(self, knowledge_id: str, relationship_type: str, 
                        similarity_score: Optional[float] = None, 
                        metadata: Optional[Dict[str, Any]] = None):
        """
        添加知识关系
        
        Args:
            knowledge_id: 关联的知识ID
            relationship_type: 关系类型 (related, contradictory, supporting, derived, influences)
            similarity_score: 相似度分数
            metadata: 关系元数据
        """
        if relationship_type == "related":
            if knowledge_id not in self.related_knowledge:
                self.related_knowledge.append(knowledge_id)
        elif relationship_type == "contradictory":
            if knowledge_id not in self.contradictory_knowledge:
                self.contradictory_knowledge.append(knowledge_id)
        elif relationship_type == "supporting":
            if knowledge_id not in self.supporting_knowledge:
                self.supporting_knowledge.append(knowledge_id)
        elif relationship_type == "derived":
            if knowledge_id not in self.derived_from:
                self.derived_from.append(knowledge_id)
        elif relationship_type == "influences":
            if knowledge_id not in self.influences:
                self.influences.append(knowledge_id)
        
        if similarity_score is not None:
            self.similarity_scores[knowledge_id] = similarity_score
        
        if metadata:
            self.relationship_metadata[knowledge_id] = metadata
    
    def remove_relationship(self, knowledge_id: str):
        """移除知识关系"""
        for knowledge_list in [self.related_knowledge, self.contradictory_knowledge,
                             self.supporting_knowledge, self.derived_from, self.influences]:
            if knowledge_id in knowledge_list:
                knowledge_list.remove(knowledge_id)
        
        self.similarity_scores.pop(knowledge_id, None)
        self.relationship_metadata.pop(knowledge_id, None)
    
    @property
    def total_connections(self) -> int:
        """获取总连接数"""
        return (len(self.related_knowledge) + len(self.contradictory_knowledge) + 
                len(self.supporting_knowledge) + len(self.derived_from) + len(self.influences))
    
    @property
    def connection_strength(self) -> float:
        """计算连接强度（基于相似度分数）"""
        if not self.similarity_scores:
            return 0.0
        return sum(self.similarity_scores.values()) / len(self.similarity_scores)


@dataclass
class KnowledgeProvenance:
    """
    知识溯源 - 完整的知识溯源信息
    
    这是知识溯源系统的核心数据结构，记录了知识的完整生命周期，
    包括来源、验证、更新历史和关联网络。
    
    Attributes:
        provenance_id: 溯源记录唯一ID
        knowledge_id: 关联的知识ID
        creation_date: 知识创建日期
        last_updated: 最后更新时间
        primary_source: 主要来源信息
        additional_sources: 额外来源信息
        credibility_level: 整体可信度级别
        confidence_score: 置信度分数 (0.0-1.0)
        validation_history: 验证历史记录
        update_history: 更新历史记录
        knowledge_network: 知识关联网络
        usage_stats: 使用统计
        quality_metrics: 质量指标
        context_tags: 上下文标签
        expiration_date: 过期日期（如果适用）
        metadata: 额外元信息
    """
    provenance_id: str = ""
    knowledge_id: str = ""
    creation_date: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    primary_source: Optional[SourceReference] = None
    additional_sources: List[SourceReference] = field(default_factory=list)
    credibility_level: CredibilityLevel = CredibilityLevel.UNVERIFIED
    confidence_score: float = 0.0
    validation_history: List[KnowledgeValidation] = field(default_factory=list)
    update_history: List[KnowledgeUpdate] = field(default_factory=list)
    knowledge_network: KnowledgeNetwork = field(default_factory=KnowledgeNetwork)
    usage_stats: Dict[str, int] = field(default_factory=dict)
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    context_tags: Set[str] = field(default_factory=set)
    expiration_date: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理：生成唯一ID"""
        if not self.provenance_id:
            timestamp = int(time.time() * 1000)
            self.provenance_id = f"provenance_{timestamp}"
        
        if not self.knowledge_id:
            self.knowledge_id = f"knowledge_{timestamp}"
        
        # 初始化使用统计
        if not self.usage_stats:
            self.usage_stats = {
                "access_count": 0,
                "successful_applications": 0,
                "failed_applications": 0,
                "last_accessed": 0
            }
    
    def add_source(self, source: SourceReference, is_primary: bool = False):
        """添加知识来源"""
        if is_primary or self.primary_source is None:
            self.primary_source = source
        else:
            self.additional_sources.append(source)
        self.last_updated = time.time()
    
    def add_validation(self, validation: KnowledgeValidation):
        """添加验证记录"""
        self.validation_history.append(validation)
        # 更新整体置信度和可信度
        self._update_credibility_from_validations()
        self.last_updated = time.time()
    
    def add_update(self, update: KnowledgeUpdate):
        """添加更新记录"""
        self.update_history.append(update)
        self.last_updated = time.time()
    
    def record_usage(self, success: bool = True):
        """记录使用情况"""
        self.usage_stats["access_count"] += 1
        self.usage_stats["last_accessed"] = time.time()
        
        if success:
            self.usage_stats["successful_applications"] += 1
        else:
            self.usage_stats["failed_applications"] += 1
        
        # 基于使用情况调整置信度
        self._adjust_confidence_from_usage()
    
    def add_context_tag(self, tag: str):
        """添加上下文标签"""
        self.context_tags.add(tag)
    
    def remove_context_tag(self, tag: str):
        """移除上下文标签"""
        self.context_tags.discard(tag)
    
    def set_expiration(self, expiration_date: float):
        """设置过期日期"""
        self.expiration_date = expiration_date
    
    def _update_credibility_from_validations(self):
        """根据验证历史更新可信度"""
        if not self.validation_history:
            return
        
        recent_validations = [v for v in self.validation_history if v.validation_date > (time.time() - 86400)]  # 最近24小时
        
        if not recent_validations:
            recent_validations = self.validation_history[-3:]  # 取最近3次验证
        
        avg_confidence = sum(v.confidence_score for v in recent_validations) / len(recent_validations)
        self.confidence_score = avg_confidence
        
        # 更新可信度级别
        if avg_confidence >= 0.9:
            self.credibility_level = CredibilityLevel.VERY_HIGH
        elif avg_confidence >= 0.7:
            self.credibility_level = CredibilityLevel.HIGH
        elif avg_confidence >= 0.5:
            self.credibility_level = CredibilityLevel.MEDIUM
        elif avg_confidence >= 0.3:
            self.credibility_level = CredibilityLevel.LOW
        elif avg_confidence >= 0.1:
            self.credibility_level = CredibilityLevel.VERY_LOW
        else:
            self.credibility_level = CredibilityLevel.UNVERIFIED
    
    def _adjust_confidence_from_usage(self):
        """根据使用情况调整置信度"""
        total_applications = self.usage_stats["successful_applications"] + self.usage_stats["failed_applications"]
        
        if total_applications > 0:
            success_rate = self.usage_stats["successful_applications"] / total_applications
            
            # 基于成功率调整置信度（缓慢调整）
            confidence_adjustment = (success_rate - 0.5) * 0.1  # 最大调整 ±0.05
            self.confidence_score = max(0.0, min(1.0, self.confidence_score + confidence_adjustment))
    
    @property
    def is_expired(self) -> bool:
        """判断知识是否已过期"""
        if self.expiration_date:
            return time.time() > self.expiration_date
        return False
    
    @property
    def is_verified(self) -> bool:
        """判断知识是否已验证"""
        return any(v.is_verified for v in self.validation_history)
    
    @property
    def has_conflicts(self) -> bool:
        """判断是否存在冲突"""
        return any(v.has_conflicts for v in self.validation_history)
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.usage_stats["successful_applications"] + self.usage_stats["failed_applications"]
        if total == 0:
            return 0.0
        return self.usage_stats["successful_applications"] / total
    
    @property
    def age_in_days(self) -> float:
        """获取知识年龄（天）"""
        return (time.time() - self.creation_date) / 86400
    
    @property
    def freshness_score(self) -> float:
        """计算新鲜度分数（越新越高）"""
        age_days = self.age_in_days
        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.6
        elif age_days <= 90:
            return 0.4
        elif age_days <= 365:
            return 0.2
        else:
            return 0.1
    
    def get_provenance_summary(self) -> Dict[str, Any]:
        """获取溯源摘要信息"""
        return {
            "provenance_id": self.provenance_id,
            "knowledge_id": self.knowledge_id,
            "creation_date": self.creation_date,
            "age_days": round(self.age_in_days, 2),
            "credibility_level": self.credibility_level.value,
            "confidence_score": round(self.confidence_score, 3),
            "is_verified": self.is_verified,
            "has_conflicts": self.has_conflicts,
            "success_rate": round(self.success_rate, 3),
            "freshness_score": round(self.freshness_score, 3),
            "source_count": len(self.additional_sources) + (1 if self.primary_source else 0),
            "validation_count": len(self.validation_history),
            "update_count": len(self.update_history),
            "network_connections": self.knowledge_network.total_connections,
            "usage_count": self.usage_stats["access_count"],
            "context_tags": list(self.context_tags),
            "is_expired": self.is_expired
        }


# ========================================
# 中心化上下文协议 (Centralized Context Protocol)
# ========================================

@dataclass
class StageContext:
    """
    阶段上下文基类 - 所有阶段间传递的基础信息
    
    定义了各个决策阶段之间传递的通用上下文信息，
    确保信息的完整性和一致性。
    
    Attributes:
        stage_id: 阶段唯一标识符
        stage_name: 阶段名称
        timestamp: 阶段执行时间戳
        user_query: 用户原始查询
        execution_context: 执行上下文信息
        metadata: 阶段特定的元数据
        performance_metrics: 性能指标
        errors: 错误信息列表
    """
    stage_id: str = ""
    stage_name: str = ""
    timestamp: float = field(default_factory=time.time)
    user_query: str = ""
    execution_context: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理：生成stage_id"""
        if not self.stage_id:
            timestamp = int(time.time() * 1000)
            self.stage_id = f"{self.stage_name}_{timestamp}"
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
    
    def add_metric(self, metric_name: str, value: float):
        """添加性能指标"""
        self.performance_metrics[metric_name] = value
    
    @property
    def has_errors(self) -> bool:
        """判断是否有错误"""
        return len(self.errors) > 0
    
    @property
    def execution_time(self) -> Optional[float]:
        """获取执行时间"""
        return self.performance_metrics.get("execution_time")


@dataclass
class ThinkingSeedContext(StageContext):
    """
    思维种子阶段上下文 - 阶段一输出
    
    包含思维种子生成阶段的完整结果，为后续阶段提供基础思维起点。
    
    Attributes:
        thinking_seed: 生成的思维种子
        seed_type: 种子类型 (basic, rag_enhanced, creative)
        generation_method: 生成方法
        confidence_score: 种子置信度
        source_information: 源信息（RAG增强时）
        search_results: 搜索结果（如果使用了搜索）
        reasoning_process: 推理过程
        alternative_seeds: 备选种子
    """
    thinking_seed: str = ""
    seed_type: str = "basic"  # basic, rag_enhanced, creative
    generation_method: str = "prior_reasoning"
    confidence_score: float = 0.5
    source_information: List[Dict[str, Any]] = field(default_factory=list)
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_process: str = ""
    alternative_seeds: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.stage_name:
            self.stage_name = "thinking_seed_generation"


@dataclass
class SeedVerificationContext(StageContext):
    """
    种子验证阶段上下文 - 阶段二输出
    
    包含思维种子验证的完整结果，评估种子的可行性和质量。
    
    Attributes:
        verification_result: 验证结果
        feasibility_score: 可行性评分
        verification_method: 验证方法
        verification_evidence: 验证证据
        identified_risks: 识别的风险
        improvement_suggestions: 改进建议
        verification_sources: 验证信息源
        cross_validation_results: 交叉验证结果
    """
    verification_result: bool = False
    feasibility_score: float = 0.0
    verification_method: str = "web_search"
    verification_evidence: List[str] = field(default_factory=list)
    identified_risks: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    verification_sources: List[Dict[str, Any]] = field(default_factory=list)
    cross_validation_results: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.stage_name:
            self.stage_name = "seed_verification"


@dataclass
class PathGenerationContext(StageContext):
    """
    路径生成阶段上下文 - 阶段三输出
    
    包含多路径思维生成的完整结果，提供多样化的解决方案路径。
    
    Attributes:
        generated_paths: 生成的推理路径列表
        path_count: 路径数量
        generation_strategy: 生成策略
        diversity_score: 多样性评分
        path_quality_scores: 路径质量评分
        generation_time: 生成耗时
        failed_generations: 失败的生成尝试
        path_categories: 路径分类信息
    """
    generated_paths: List[Any] = field(default_factory=list)  # List[ReasoningPath]
    path_count: int = 0
    generation_strategy: str = "llm_driven"
    diversity_score: float = 0.0
    path_quality_scores: Dict[str, float] = field(default_factory=dict)
    generation_time: float = 0.0
    failed_generations: List[str] = field(default_factory=list)
    path_categories: Dict[str, List[str]] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.stage_name:
            self.stage_name = "path_generation"
        self.path_count = len(self.generated_paths)
    
    def add_path(self, path: Any):
        """添加生成的路径"""
        self.generated_paths.append(path)
        self.path_count = len(self.generated_paths)
    
    def get_paths_by_category(self, category: str) -> List[Any]:
        """根据类别获取路径"""
        if category not in self.path_categories:
            return []
        path_ids = self.path_categories[category]
        return [path for path in self.generated_paths if path.path_id in path_ids]


@dataclass
class PathVerificationContext(StageContext):
    """
    路径验证阶段上下文 - 阶段四输出
    
    包含路径验证和即时学习的完整结果，评估各路径的可行性。
    
    Attributes:
        verified_paths: 验证过的路径信息
        verification_results: 验证结果详情
        learning_updates: 学习更新信息
        path_rankings: 路径排名
        verification_confidence: 验证置信度
        rejected_paths: 被拒绝的路径
        verification_time: 验证耗时
        learning_feedback: 学习反馈
    """
    verified_paths: List[Dict[str, Any]] = field(default_factory=list)
    verification_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    learning_updates: List[Dict[str, Any]] = field(default_factory=list)
    path_rankings: List[Tuple[str, float]] = field(default_factory=list)
    verification_confidence: Dict[str, float] = field(default_factory=dict)
    rejected_paths: List[Dict[str, Any]] = field(default_factory=list)
    verification_time: float = 0.0
    learning_feedback: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.stage_name:
            self.stage_name = "path_verification"
    
    def add_verification_result(self, path_id: str, result: Dict[str, Any]):
        """添加验证结果"""
        self.verification_results[path_id] = result
    
    def get_top_paths(self, n: int = 3) -> List[Tuple[str, float]]:
        """获取排名前N的路径"""
        return sorted(self.path_rankings, key=lambda x: x[1], reverse=True)[:n]


@dataclass
class MABDecisionContext(StageContext):
    """
    MAB决策阶段上下文 - 阶段五输出
    
    包含多臂老虎机最终决策的完整结果，选择最优路径。
    
    Attributes:
        selected_path: 最终选择的路径
        selection_algorithm: 使用的MAB算法
        selection_confidence: 选择置信度
        algorithm_comparison: 算法比较结果
        exploration_exploitation_balance: 探索利用平衡
        golden_template_used: 是否使用了黄金模板
        aha_moment_triggered: 是否触发了Aha时刻
        decision_reasoning: 决策推理过程
        alternative_choices: 备选选择
        mab_statistics: MAB统计信息
    """
    selected_path: Optional[Any] = None  # ReasoningPath
    selection_algorithm: str = ""
    selection_confidence: float = 0.0
    algorithm_comparison: Dict[str, float] = field(default_factory=dict)
    exploration_exploitation_balance: Dict[str, float] = field(default_factory=dict)
    golden_template_used: bool = False
    aha_moment_triggered: bool = False
    decision_reasoning: str = ""
    alternative_choices: List[Tuple[Any, float]] = field(default_factory=list)
    mab_statistics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.stage_name:
            self.stage_name = "mab_decision"


@dataclass
class StrategyDecision:
    """
    战略决策结果 - 连接战略规划器和战术规划器的桥梁
    
    这是完整的五阶段决策流程的最终输出，包含了所有阶段的上下文信息，
    为战术规划器提供完整的决策上下文。这个数据结构实现了真正的"上下文协议"。
    
    Attributes:
        decision_id: 决策唯一标识符
        user_query: 用户原始查询
        timestamp: 决策时间戳
        round_number: 决策轮次
        
        # 五阶段上下文信息
        stage1_context: 思维种子生成上下文
        stage2_context: 种子验证上下文  
        stage3_context: 路径生成上下文
        stage4_context: 路径验证上下文
        stage5_context: MAB决策上下文
        
        # 最终决策结果
        chosen_path: 选中的推理路径
        final_reasoning: 最终推理结果
        confidence_score: 整体置信度
        
        # 决策质量指标
        decision_quality_metrics: 决策质量指标
        total_execution_time: 总执行时间
        stage_execution_times: 各阶段执行时间
        
        # 扩展信息
        execution_context: 执行上下文
        metadata: 额外元数据
        errors: 决策过程中的错误
        warnings: 警告信息
    """
    decision_id: str = ""
    user_query: str = ""
    timestamp: float = field(default_factory=time.time)
    round_number: int = 1
    
    # 五阶段上下文信息
    stage1_context: Optional[ThinkingSeedContext] = None
    stage2_context: Optional[SeedVerificationContext] = None
    stage3_context: Optional[PathGenerationContext] = None
    stage4_context: Optional[PathVerificationContext] = None
    stage5_context: Optional[MABDecisionContext] = None
    
    # 最终决策结果
    chosen_path: Optional[Any] = None  # ReasoningPath
    final_reasoning: str = ""
    confidence_score: float = 0.5
    
    # 决策质量指标
    decision_quality_metrics: Dict[str, float] = field(default_factory=dict)
    total_execution_time: float = 0.0
    stage_execution_times: Dict[str, float] = field(default_factory=dict)
    
    # 扩展信息
    execution_context: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """初始化后处理：生成decision_id"""
        if not self.decision_id:
            timestamp = int(time.time() * 1000)
            self.decision_id = f"strategy_decision_{timestamp}_{self.round_number}"
    
    def add_stage_context(self, stage_num: int, context: StageContext):
        """添加阶段上下文"""
        if stage_num == 1 and isinstance(context, ThinkingSeedContext):
            self.stage1_context = context
        elif stage_num == 2 and isinstance(context, SeedVerificationContext):
            self.stage2_context = context
        elif stage_num == 3 and isinstance(context, PathGenerationContext):
            self.stage3_context = context
        elif stage_num == 4 and isinstance(context, PathVerificationContext):
            self.stage4_context = context
        elif stage_num == 5 and isinstance(context, MABDecisionContext):
            self.stage5_context = context
        
        # 更新阶段执行时间
        if context.execution_time:
            self.stage_execution_times[context.stage_name] = context.execution_time
            self.total_execution_time = sum(self.stage_execution_times.values())
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """添加警告信息"""
        self.warnings.append(warning)
    
    def add_quality_metric(self, metric_name: str, value: float):
        """添加决策质量指标"""
        self.decision_quality_metrics[metric_name] = value
    
    @property
    def has_errors(self) -> bool:
        """判断是否有错误"""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """判断是否有警告"""
        return len(self.warnings) > 0
    
    @property
    def is_complete(self) -> bool:
        """判断决策是否完整（所有五个阶段都有上下文）"""
        return all([
            self.stage1_context is not None,
            self.stage2_context is not None,
            self.stage3_context is not None,
            self.stage4_context is not None,
            self.stage5_context is not None,
            self.chosen_path is not None
        ])
    
    @property
    def thinking_seed(self) -> str:
        """获取思维种子"""
        if self.stage1_context:
            return self.stage1_context.thinking_seed
        return ""
    
    @property
    def available_paths(self) -> List[Any]:
        """获取所有可用路径"""
        if self.stage3_context:
            return self.stage3_context.generated_paths
        return []
    
    @property
    def verified_paths(self) -> List[Dict[str, Any]]:
        """获取验证过的路径"""
        if self.stage4_context:
            return self.stage4_context.verified_paths
        return []
    
    @property
    def selection_algorithm(self) -> str:
        """获取选择算法"""
        if self.stage5_context:
            return self.stage5_context.selection_algorithm
        return ""
    
    @property
    def verification_stats(self) -> Dict[str, Any]:
        """获取验证统计信息"""
        if self.stage4_context:
            return {
                "verified_count": len(self.stage4_context.verified_paths),
                "rejected_count": len(self.stage4_context.rejected_paths),
                "verification_time": self.stage4_context.verification_time,
                "average_confidence": sum(self.stage4_context.verification_confidence.values()) / 
                                   len(self.stage4_context.verification_confidence) if self.stage4_context.verification_confidence else 0.0
            }
        return {}
    
    @property
    def performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            "total_execution_time": self.total_execution_time,
            "stage_times": self.stage_execution_times.copy(),
            "confidence_score": self.confidence_score,
            "decision_quality": self.decision_quality_metrics.copy(),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "completeness": self.is_complete
        }
    
    def _get_chosen_path_id(self) -> Optional[str]:
        """安全地获取选择路径的ID"""
        if not self.chosen_path:
            return None
        
        # 处理字典格式的路径
        if isinstance(self.chosen_path, dict):
            return self.chosen_path.get("path_id")
        
        # 处理对象格式的路径
        if hasattr(self.chosen_path, 'path_id'):
            return self.chosen_path.path_id
        
        # 回退：尝试获取字符串表示
        return str(self.chosen_path) if self.chosen_path else None
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """获取决策摘要"""
        return {
            "decision_id": self.decision_id,
            "user_query": self.user_query[:100] + "..." if len(self.user_query) > 100 else self.user_query,
            "timestamp": self.timestamp,
            "round_number": self.round_number,
            "chosen_path_id": self._get_chosen_path_id(),
            "confidence_score": self.confidence_score,
            "total_execution_time": self.total_execution_time,
            "is_complete": self.is_complete,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "stage_count": sum(1 for ctx in [self.stage1_context, self.stage2_context, 
                                           self.stage3_context, self.stage4_context, self.stage5_context] if ctx is not None)
        }
