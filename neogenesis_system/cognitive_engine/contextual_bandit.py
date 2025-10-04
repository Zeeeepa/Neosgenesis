#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
上下文多臂老虎机 (Contextual Multi-Armed Bandit)
Contextual Multi-Armed Bandit for intelligent strategy selection

核心创新：
1. 基于任务上下文特征的智能策略选择
2. LinUCB 和 Contextual Thompson Sampling 实现
3. 持久化学习参数存储 (SQLite/DuckDB)
4. 工具健康状态和环境感知
5. 可验证的成功信号定义
"""

import time
import json
import sqlite3
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib
from enum import Enum

logger = logging.getLogger(__name__)

class SuccessMetric(Enum):
    """成功指标定义"""
    CONTRACT_SUCCESS = "contract_success"      # 合同成功判定通过
    EXECUTION_SUCCESS = "execution_success"    # 执行成功
    USER_SATISFACTION = "user_satisfaction"    # 用户满意度
    COST_EFFICIENCY = "cost_efficiency"        # 成本效率
    TIME_EFFICIENCY = "time_efficiency"        # 时间效率

@dataclass
class ContextFeatures:
    """上下文特征向量"""
    # 任务签名特征
    task_intent: str = "question"              # 任务意图
    task_domain: str = "general"               # 任务领域
    task_complexity: float = 0.5               # 复杂度 [0,1]
    input_length: int = 0                      # 输入长度
    input_structure_score: float = 0.5         # 输入结构化程度
    
    # 工具可达性特征
    tool_health_scores: Dict[str, float] = field(default_factory=dict)  # 工具健康分数
    tool_latencies: Dict[str, float] = field(default_factory=dict)      # 工具延迟
    tool_rate_limits: Dict[str, bool] = field(default_factory=dict)     # 速率限制状态
    
    # 环境特征
    current_hour: int = 12                     # 当前小时
    network_quality: float = 1.0              # 网络质量 [0,1]
    system_load: float = 0.5                  # 系统负载 [0,1]
    
    # 历史绩效特征
    historical_success_rates: Dict[str, float] = field(default_factory=dict)  # 历史成功率
    recent_failures: Dict[str, int] = field(default_factory=dict)             # 最近失败次数
    
    # 预算和约束
    time_budget: float = 30.0                  # 时间预算(秒)
    cost_budget: float = 1.0                   # 成本预算
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return asdict(self)
    
    def to_vector(self, feature_names: List[str]) -> np.ndarray:
        """转换为特征向量"""
        vector = []
        feature_dict = asdict(self)
        
        for name in feature_names:
            if name in feature_dict:
                value = feature_dict[name]
                if isinstance(value, (int, float)):
                    vector.append(float(value))
                elif isinstance(value, str):
                    # 字符串特征编码
                    vector.append(hash(value) % 100 / 100.0)
                elif isinstance(value, dict):
                    # 字典特征聚合
                    if value:
                        vector.append(np.mean(list(value.values())))
                    else:
                        vector.append(0.0)
                else:
                    vector.append(0.0)
            else:
                vector.append(0.0)
        
        return np.array(vector)

@dataclass
class ActionOutcome:
    """动作结果"""
    action_id: str
    context_features: ContextFeatures
    success_metrics: Dict[SuccessMetric, float]
    execution_time: float
    cost: float
    timestamp: float
    additional_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def overall_reward(self) -> float:
        """计算综合奖励"""
        # 加权组合不同成功指标
        weights = {
            SuccessMetric.CONTRACT_SUCCESS: 0.4,
            SuccessMetric.EXECUTION_SUCCESS: 0.3,
            SuccessMetric.USER_SATISFACTION: 0.2,
            SuccessMetric.COST_EFFICIENCY: 0.05,
            SuccessMetric.TIME_EFFICIENCY: 0.05
        }
        
        reward = 0.0
        for metric, weight in weights.items():
            if metric in self.success_metrics:
                reward += weight * self.success_metrics[metric]
        
        return reward

class ContextualBanditStorage:
    """持久化存储管理器"""
    
    def __init__(self, db_path: str = "contextual_bandit.db"):
        self.db_path = Path(db_path)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bandit_parameters (
                    algorithm TEXT,
                    action_id TEXT,
                    parameter_name TEXT,
                    parameter_value BLOB,
                    updated_at REAL,
                    PRIMARY KEY (algorithm, action_id, parameter_name)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT,
                    context_hash TEXT,
                    context_features TEXT,
                    reward REAL,
                    execution_time REAL,
                    cost REAL,
                    timestamp REAL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_metadata (
                    feature_name TEXT PRIMARY KEY,
                    feature_type TEXT,
                    normalization_params TEXT,
                    updated_at REAL
                )
            """)
    
    def save_parameters(self, algorithm: str, action_id: str, parameters: Dict[str, np.ndarray]):
        """保存模型参数"""
        with sqlite3.connect(self.db_path) as conn:
            for param_name, param_value in parameters.items():
                conn.execute("""
                    INSERT OR REPLACE INTO bandit_parameters 
                    (algorithm, action_id, parameter_name, parameter_value, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (algorithm, action_id, param_name, param_value.tobytes(), time.time()))
    
    def load_parameters(self, algorithm: str, action_id: str) -> Dict[str, np.ndarray]:
        """加载模型参数"""
        parameters = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT parameter_name, parameter_value 
                FROM bandit_parameters 
                WHERE algorithm = ? AND action_id = ?
            """, (algorithm, action_id))
            
            for param_name, param_blob in cursor.fetchall():
                parameters[param_name] = np.frombuffer(param_blob)
        
        return parameters
    
    def save_action_outcome(self, outcome: ActionOutcome):
        """保存动作结果"""
        context_hash = hashlib.md5(
            json.dumps(asdict(outcome.context_features), sort_keys=True).encode()
        ).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO action_history 
                (action_id, context_hash, context_features, reward, execution_time, cost, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                outcome.action_id,
                context_hash,
                json.dumps(asdict(outcome.context_features)),
                outcome.overall_reward,
                outcome.execution_time,
                outcome.cost,
                outcome.timestamp
            ))

class LinUCBBandit:
    """Linear Upper Confidence Bound Bandit"""
    
    def __init__(self, feature_dim: int, alpha: float = 1.0, storage: Optional[ContextualBanditStorage] = None):
        self.feature_dim = feature_dim
        self.alpha = alpha
        self.storage = storage
        
        # 每个动作的参数
        self.A = {}  # 协方差矩阵 A_a
        self.b = {}  # 奖励向量 b_a
        self.theta = {}  # 参数估计 theta_a
        
        logger.info(f"🎯 LinUCB Bandit 初始化完成，特征维度: {feature_dim}")
    
    def _init_action(self, action_id: str):
        """初始化动作参数"""
        if action_id not in self.A:
            # 尝试从存储加载
            if self.storage:
                params = self.storage.load_parameters("linucb", action_id)
                if params:
                    self.A[action_id] = params.get("A", np.eye(self.feature_dim))
                    self.b[action_id] = params.get("b", np.zeros(self.feature_dim))
                    self.theta[action_id] = params.get("theta", np.zeros(self.feature_dim))
                    logger.debug(f"📂 从存储加载 LinUCB 参数: {action_id}")
                    return
            
            # 新初始化
            self.A[action_id] = np.eye(self.feature_dim)
            self.b[action_id] = np.zeros(self.feature_dim)
            self.theta[action_id] = np.zeros(self.feature_dim)
            logger.debug(f"🆕 新建 LinUCB 动作: {action_id}")
    
    def predict(self, context: ContextFeatures, available_actions: List[str]) -> Tuple[str, float, Dict[str, float]]:
        """预测最佳动作"""
        feature_names = [
            "task_complexity", "input_length", "input_structure_score",
            "current_hour", "network_quality", "system_load", "time_budget", "cost_budget"
        ]
        x = context.to_vector(feature_names)
        
        if len(x) != self.feature_dim:
            # 调整特征向量维度
            if len(x) < self.feature_dim:
                x = np.pad(x, (0, self.feature_dim - len(x)))
            else:
                x = x[:self.feature_dim]
        
        ucb_values = {}
        
        for action_id in available_actions:
            self._init_action(action_id)
            
            # 计算 UCB 值
            A_inv = np.linalg.inv(self.A[action_id])
            theta = A_inv @ self.b[action_id]
            
            confidence_bonus = self.alpha * np.sqrt(x.T @ A_inv @ x)
            ucb_value = theta.T @ x + confidence_bonus
            
            ucb_values[action_id] = float(ucb_value)
        
        # 选择最高 UCB 值的动作
        best_action = max(ucb_values, key=ucb_values.get)
        best_value = ucb_values[best_action]
        
        logger.debug(f"🎯 LinUCB 预测: {best_action} (UCB: {best_value:.3f})")
        return best_action, best_value, ucb_values
    
    def fit(self, context: ContextFeatures, action_id: str, reward: float):
        """更新模型参数"""
        feature_names = [
            "task_complexity", "input_length", "input_structure_score", 
            "current_hour", "network_quality", "system_load", "time_budget", "cost_budget"
        ]
        x = context.to_vector(feature_names)
        
        if len(x) != self.feature_dim:
            if len(x) < self.feature_dim:
                x = np.pad(x, (0, self.feature_dim - len(x)))
            else:
                x = x[:self.feature_dim]
        
        self._init_action(action_id)
        
        # 更新参数
        self.A[action_id] += np.outer(x, x)
        self.b[action_id] += reward * x
        
        # 保存到存储
        if self.storage:
            params = {
                "A": self.A[action_id],
                "b": self.b[action_id],
                "theta": np.linalg.inv(self.A[action_id]) @ self.b[action_id]
            }
            self.storage.save_parameters("linucb", action_id, params)
        
        logger.debug(f"📈 LinUCB 参数更新: {action_id}, 奖励: {reward:.3f}")

class ContextualThompsonSampling:
    """上下文 Thompson Sampling"""
    
    def __init__(self, feature_dim: int, alpha: float = 1.0, beta: float = 1.0, 
                 storage: Optional[ContextualBanditStorage] = None):
        self.feature_dim = feature_dim
        self.alpha = alpha  # 先验精度
        self.beta = beta    # 噪声精度
        self.storage = storage
        
        # 每个动作的贝叶斯线性回归参数
        self.S = {}  # 协方差矩阵的逆
        self.mu = {}  # 均值向量
        
        logger.info(f"🎲 Contextual Thompson Sampling 初始化完成，特征维度: {feature_dim}")
    
    def _init_action(self, action_id: str):
        """初始化动作参数"""
        if action_id not in self.S:
            # 尝试从存储加载
            if self.storage:
                params = self.storage.load_parameters("thompson", action_id)
                if params:
                    self.S[action_id] = params.get("S", self.alpha * np.eye(self.feature_dim))
                    self.mu[action_id] = params.get("mu", np.zeros(self.feature_dim))
                    logger.debug(f"📂 从存储加载 Thompson 参数: {action_id}")
                    return
            
            # 新初始化
            self.S[action_id] = self.alpha * np.eye(self.feature_dim)
            self.mu[action_id] = np.zeros(self.feature_dim)
            logger.debug(f"🆕 新建 Thompson 动作: {action_id}")
    
    def predict(self, context: ContextFeatures, available_actions: List[str]) -> Tuple[str, float, Dict[str, float]]:
        """预测最佳动作"""
        feature_names = [
            "task_complexity", "input_length", "input_structure_score",
            "current_hour", "network_quality", "system_load", "time_budget", "cost_budget"
        ]
        x = context.to_vector(feature_names)
        
        if len(x) != self.feature_dim:
            if len(x) < self.feature_dim:
                x = np.pad(x, (0, self.feature_dim - len(x)))
            else:
                x = x[:self.feature_dim]
        
        sampled_values = {}
        
        for action_id in available_actions:
            self._init_action(action_id)
            
            # 从后验分布采样 theta
            try:
                S_inv = np.linalg.inv(self.S[action_id])
                theta_sample = np.random.multivariate_normal(self.mu[action_id], S_inv)
                sampled_value = float(theta_sample.T @ x)
                sampled_values[action_id] = sampled_value
            except np.linalg.LinAlgError:
                # 处理奇异矩阵
                sampled_values[action_id] = np.random.normal(0, 1)
        
        # 选择最高采样值的动作
        best_action = max(sampled_values, key=sampled_values.get)
        best_value = sampled_values[best_action]
        
        logger.debug(f"🎲 Thompson 预测: {best_action} (采样值: {best_value:.3f})")
        return best_action, best_value, sampled_values
    
    def fit(self, context: ContextFeatures, action_id: str, reward: float):
        """更新模型参数"""
        feature_names = [
            "task_complexity", "input_length", "input_structure_score",
            "current_hour", "network_quality", "system_load", "time_budget", "cost_budget"
        ]
        x = context.to_vector(feature_names)
        
        if len(x) != self.feature_dim:
            if len(x) < self.feature_dim:
                x = np.pad(x, (0, self.feature_dim - len(x)))
            else:
                x = x[:self.feature_dim]
        
        self._init_action(action_id)
        
        # 贝叶斯更新
        self.S[action_id] += self.beta * np.outer(x, x)
        
        try:
            S_inv = np.linalg.inv(self.S[action_id])
            self.mu[action_id] = S_inv @ (self.S[action_id] @ self.mu[action_id] + self.beta * reward * x)
        except np.linalg.LinAlgError:
            logger.warning(f"⚠️ Thompson Sampling 矩阵奇异，跳过更新: {action_id}")
            return
        
        # 保存到存储
        if self.storage:
            params = {
                "S": self.S[action_id],
                "mu": self.mu[action_id]
            }
            self.storage.save_parameters("thompson", action_id, params)
        
        logger.debug(f"📈 Thompson 参数更新: {action_id}, 奖励: {reward:.3f}")

class ContextualBanditManager:
    """上下文Bandit管理器"""
    
    def __init__(self, feature_dim: int = 8, algorithm: str = "linucb", 
                 storage_path: str = "contextual_bandit.db"):
        self.feature_dim = feature_dim
        self.algorithm = algorithm
        self.storage = ContextualBanditStorage(storage_path)
        
        # 初始化算法
        if algorithm == "linucb":
            self.bandit = LinUCBBandit(feature_dim, storage=self.storage)
        elif algorithm == "thompson":
            self.bandit = ContextualThompsonSampling(feature_dim, storage=self.storage)
        else:
            raise ValueError(f"不支持的算法: {algorithm}")
        
        # 统计信息
        self.total_selections = 0
        self.action_counts = {}
        self.recent_rewards = []
        
        logger.info(f"🎯 ContextualBandit 管理器初始化: {algorithm}, 特征维度: {feature_dim}")
    
    def select_action(self, context: ContextFeatures, available_actions: List[str]) -> Tuple[str, float, Dict[str, Any]]:
        """选择最佳动作"""
        if not available_actions:
            raise ValueError("可用动作列表不能为空")
        
        self.total_selections += 1
        
        # 预测最佳动作
        best_action, confidence, all_values = self.bandit.predict(context, available_actions)
        
        # 更新统计
        self.action_counts[best_action] = self.action_counts.get(best_action, 0) + 1
        
        selection_info = {
            "algorithm": self.algorithm,
            "confidence": confidence,
            "all_action_values": all_values,
            "selection_count": self.total_selections,
            "action_usage_count": self.action_counts[best_action],
            "context_summary": {
                "task_complexity": context.task_complexity,
                "task_domain": context.task_domain,
                "task_intent": context.task_intent
            }
        }
        
        logger.info(f"🎯 选择动作: {best_action} (置信度: {confidence:.3f})")
        return best_action, confidence, selection_info
    
    def update_reward(self, context: ContextFeatures, action_id: str, outcome: ActionOutcome):
        """更新奖励信号"""
        reward = outcome.overall_reward
        
        # 更新模型
        self.bandit.fit(context, action_id, reward)
        
        # 保存结果
        self.storage.save_action_outcome(outcome)
        
        # 更新统计
        self.recent_rewards.append(reward)
        if len(self.recent_rewards) > 100:
            self.recent_rewards = self.recent_rewards[-50:]
        
        logger.info(f"📈 更新奖励: {action_id}, 奖励: {reward:.3f}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = {
            "total_selections": self.total_selections,
            "action_counts": self.action_counts.copy(),
            "recent_avg_reward": np.mean(self.recent_rewards) if self.recent_rewards else 0.0,
            "algorithm": self.algorithm,
            "feature_dim": self.feature_dim
        }
        
        if self.action_counts:
            most_used = max(self.action_counts, key=self.action_counts.get)
            stats["most_used_action"] = most_used
            stats["usage_distribution"] = {
                action: count / self.total_selections 
                for action, count in self.action_counts.items()
            }
        
        return stats
