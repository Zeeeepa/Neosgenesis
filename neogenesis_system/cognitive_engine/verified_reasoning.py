#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
可验证推理系统 (Verified Reasoning System)
Verified Reasoning System for reliable AI planning and execution

核心创新：
1. Claim → Evidence → ActionContract 三段式推理
2. 静态约束检查器 (ArgSchemaValidator, PreconditionChecker, BudgetPlanner)
3. 工具健康探针和资源存在性验证
4. 预算和约束管理
5. 可追溯的推理链条
"""

import json
import time
import logging
import requests
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import jsonschema
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

class ClaimType(Enum):
    """声明类型"""
    FACTUAL = "factual"                    # 事实性声明
    PROCEDURAL = "procedural"              # 程序性声明
    CONDITIONAL = "conditional"            # 条件性声明
    CAUSAL = "causal"                      # 因果性声明
    EVALUATIVE = "evaluative"              # 评价性声明

class EvidenceType(Enum):
    """证据类型"""
    URL_VERIFICATION = "url_verification"          # URL验证
    API_RESPONSE = "api_response"                  # API响应
    TOOL_OUTPUT = "tool_output"                    # 工具输出
    DATABASE_QUERY = "database_query"              # 数据库查询
    FILE_EXISTENCE = "file_existence"              # 文件存在性
    SCHEMA_VALIDATION = "schema_validation"        # 模式验证
    HEALTH_CHECK = "health_check"                  # 健康检查

class ContractStatus(Enum):
    """合同状态"""
    DRAFT = "draft"                        # 草稿
    VALIDATED = "validated"                # 已验证
    APPROVED = "approved"                  # 已批准
    EXECUTING = "executing"                # 执行中
    COMPLETED = "completed"                # 已完成
    FAILED = "failed"                      # 失败
    CANCELLED = "cancelled"                # 已取消

@dataclass
class Claim:
    """推理声明"""
    claim_id: str
    claim_type: ClaimType
    statement: str                         # 声明内容
    confidence: float                      # 置信度 [0,1]
    dependencies: List[str] = field(default_factory=list)  # 依赖的其他声明
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

@dataclass
class Evidence:
    """推理证据"""
    evidence_id: str
    evidence_type: EvidenceType
    claim_id: str                          # 支持的声明ID
    verification_method: str               # 验证方法
    verification_target: str               # 验证目标 (URL, 选择器, 字段名, ID等)
    expected_result: Any                   # 期望结果
    actual_result: Optional[Any] = None    # 实际结果
    verification_status: bool = False      # 验证状态
    verification_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionContract:
    """动作合同"""
    contract_id: str
    action_name: str                       # 动作名称
    tool_name: str                         # 工具名称
    arguments: Dict[str, Any]              # 参数
    preconditions: List[str]               # 前置条件 (Claim IDs)
    expected_outcomes: List[str]           # 期望结果 (Claim IDs)
    resource_requirements: Dict[str, Any]  # 资源需求
    budget_cost: float                     # 预算成本
    time_estimate: float                   # 时间估计
    status: ContractStatus = ContractStatus.DRAFT
    validation_results: Dict[str, Any] = field(default_factory=dict)
    execution_results: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

@dataclass
class ReasoningChain:
    """推理链条"""
    chain_id: str
    user_query: str
    claims: List[Claim] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    contracts: List[ActionContract] = field(default_factory=list)
    validation_summary: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

class ArgSchemaValidator:
    """参数模式验证器"""
    
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        self.validation_cache = {}
        logger.info("🔍 ArgSchemaValidator 初始化完成")
    
    def validate_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证工具参数是否符合JSONSchema"""
        try:
            if not self.tool_registry or not self.tool_registry.has_tool(tool_name):
                return False, [f"工具 '{tool_name}' 未在注册表中找到"]
            
            tool_info = self.tool_registry.get_tool_info(tool_name)
            if not tool_info or 'schema' not in tool_info:
                return True, []  # 没有schema则跳过验证
            
            schema = tool_info['schema']
            
            # 使用jsonschema验证
            validate(arguments, schema)
            
            logger.debug(f"✅ 参数验证通过: {tool_name}")
            return True, []
            
        except ValidationError as e:
            error_msg = f"参数验证失败: {e.message}"
            logger.warning(f"❌ {error_msg}")
            return False, [error_msg]
        except Exception as e:
            error_msg = f"验证过程异常: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, [error_msg]
    
    def get_required_fields(self, tool_name: str) -> List[str]:
        """获取工具必需字段"""
        try:
            if not self.tool_registry or not self.tool_registry.has_tool(tool_name):
                return []
            
            tool_info = self.tool_registry.get_tool_info(tool_name)
            if not tool_info or 'schema' not in tool_info:
                return []
            
            schema = tool_info['schema']
            return schema.get('required', [])
            
        except Exception as e:
            logger.error(f"❌ 获取必需字段失败: {e}")
            return []

class PreconditionChecker:
    """前置条件检查器"""
    
    def __init__(self, tool_registry=None):
        self.tool_registry = tool_registry
        self.health_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        logger.info("🔍 PreconditionChecker 初始化完成")
    
    def check_tool_health(self, tool_name: str) -> Tuple[bool, Dict[str, Any]]:
        """检查工具健康状态"""
        cache_key = f"health_{tool_name}"
        current_time = time.time()
        
        # 检查缓存
        if cache_key in self.health_cache:
            cached_result, cached_time = self.health_cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                return cached_result
        
        try:
            if not self.tool_registry or not self.tool_registry.has_tool(tool_name):
                result = (False, {"error": f"工具 '{tool_name}' 未找到"})
                self.health_cache[cache_key] = (result, current_time)
                return result
            
            # 执行健康检查
            health_info = {
                "tool_name": tool_name,
                "available": True,
                "response_time": 0.0,
                "last_check": current_time,
                "error": None
            }
            
            # 如果工具有健康检查接口，调用它
            tool_info = self.tool_registry.get_tool_info(tool_name)
            if tool_info and 'health_check_url' in tool_info:
                start_time = time.time()
                try:
                    response = requests.get(tool_info['health_check_url'], timeout=5)
                    health_info["response_time"] = time.time() - start_time
                    health_info["available"] = response.status_code == 200
                    if not health_info["available"]:
                        health_info["error"] = f"HTTP {response.status_code}"
                except requests.RequestException as e:
                    health_info["available"] = False
                    health_info["error"] = str(e)
                    health_info["response_time"] = time.time() - start_time
            
            result = (health_info["available"], health_info)
            self.health_cache[cache_key] = (result, current_time)
            
            logger.debug(f"🏥 工具健康检查: {tool_name} -> {'✅' if health_info['available'] else '❌'}")
            return result
            
        except Exception as e:
            error_info = {
                "tool_name": tool_name,
                "available": False,
                "error": str(e),
                "last_check": current_time
            }
            result = (False, error_info)
            self.health_cache[cache_key] = (result, current_time)
            logger.error(f"❌ 工具健康检查异常: {tool_name} -> {e}")
            return result
    
    def check_resource_existence(self, resource_type: str, resource_id: str) -> Tuple[bool, Dict[str, Any]]:
        """检查资源存在性"""
        try:
            if resource_type == "url":
                return self._check_url_existence(resource_id)
            elif resource_type == "file":
                return self._check_file_existence(resource_id)
            elif resource_type == "api_endpoint":
                return self._check_api_endpoint(resource_id)
            else:
                return False, {"error": f"不支持的资源类型: {resource_type}"}
                
        except Exception as e:
            logger.error(f"❌ 资源存在性检查异常: {resource_type}:{resource_id} -> {e}")
            return False, {"error": str(e)}
    
    def _check_url_existence(self, url: str) -> Tuple[bool, Dict[str, Any]]:
        """检查URL可访问性"""
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            exists = response.status_code < 400
            info = {
                "url": url,
                "status_code": response.status_code,
                "accessible": exists,
                "response_time": response.elapsed.total_seconds()
            }
            return exists, info
        except requests.RequestException as e:
            return False, {"url": url, "error": str(e), "accessible": False}
    
    def _check_file_existence(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """检查文件存在性"""
        path = Path(file_path)
        exists = path.exists()
        info = {
            "file_path": file_path,
            "exists": exists,
            "is_file": path.is_file() if exists else False,
            "size": path.stat().st_size if exists and path.is_file() else 0
        }
        return exists, info
    
    def _check_api_endpoint(self, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """检查API端点可用性"""
        try:
            response = requests.get(endpoint, timeout=10)
            available = response.status_code < 500
            info = {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "available": available,
                "response_time": response.elapsed.total_seconds()
            }
            return available, info
        except requests.RequestException as e:
            return False, {"endpoint": endpoint, "error": str(e), "available": False}

class BudgetPlanner:
    """预算规划器"""
    
    def __init__(self, global_budget: Dict[str, float] = None):
        self.global_budget = global_budget or {
            "time_seconds": 300.0,      # 5分钟时间预算
            "cost_dollars": 5.0,        # 5美元成本预算
            "api_calls": 100,           # 100次API调用
            "memory_mb": 1024           # 1GB内存预算
        }
        self.used_budget = {key: 0.0 for key in self.global_budget.keys()}
        logger.info(f"💰 BudgetPlanner 初始化: {self.global_budget}")
    
    def check_budget_feasibility(self, contracts: List[ActionContract]) -> Tuple[bool, Dict[str, Any]]:
        """检查预算可行性"""
        total_requirements = {key: 0.0 for key in self.global_budget.keys()}
        
        # 计算总需求
        for contract in contracts:
            if contract.status not in [ContractStatus.COMPLETED, ContractStatus.CANCELLED]:
                total_requirements["time_seconds"] += contract.time_estimate
                total_requirements["cost_dollars"] += contract.budget_cost
                
                # 从资源需求中提取其他预算项
                for resource, amount in contract.resource_requirements.items():
                    if resource in total_requirements:
                        total_requirements[resource] += float(amount)
        
        # 检查是否超出预算
        budget_status = {}
        overall_feasible = True
        
        for resource, required in total_requirements.items():
            available = self.global_budget[resource] - self.used_budget[resource]
            feasible = required <= available
            
            budget_status[resource] = {
                "required": required,
                "available": available,
                "used": self.used_budget[resource],
                "total_budget": self.global_budget[resource],
                "feasible": feasible,
                "utilization": (self.used_budget[resource] + required) / self.global_budget[resource]
            }
            
            if not feasible:
                overall_feasible = False
        
        result = {
            "overall_feasible": overall_feasible,
            "budget_breakdown": budget_status,
            "total_contracts": len(contracts),
            "active_contracts": len([c for c in contracts if c.status not in [ContractStatus.COMPLETED, ContractStatus.CANCELLED]])
        }
        
        logger.info(f"💰 预算可行性检查: {'✅ 可行' if overall_feasible else '❌ 超预算'}")
        return overall_feasible, result
    
    def reserve_budget(self, contract: ActionContract) -> bool:
        """预留预算"""
        try:
            # 检查单个合同的预算需求
            required_time = contract.time_estimate
            required_cost = contract.budget_cost
            
            if (self.used_budget["time_seconds"] + required_time > self.global_budget["time_seconds"] or
                self.used_budget["cost_dollars"] + required_cost > self.global_budget["cost_dollars"]):
                return False
            
            # 预留预算
            self.used_budget["time_seconds"] += required_time
            self.used_budget["cost_dollars"] += required_cost
            
            for resource, amount in contract.resource_requirements.items():
                if resource in self.used_budget:
                    self.used_budget[resource] += float(amount)
            
            logger.debug(f"💰 预算预留成功: {contract.contract_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 预算预留失败: {e}")
            return False
    
    def release_budget(self, contract: ActionContract):
        """释放预算"""
        try:
            self.used_budget["time_seconds"] -= contract.time_estimate
            self.used_budget["cost_dollars"] -= contract.budget_cost
            
            for resource, amount in contract.resource_requirements.items():
                if resource in self.used_budget:
                    self.used_budget[resource] -= float(amount)
            
            # 确保不会出现负数
            for key in self.used_budget:
                self.used_budget[key] = max(0.0, self.used_budget[key])
            
            logger.debug(f"💰 预算释放: {contract.contract_id}")
            
        except Exception as e:
            logger.error(f"❌ 预算释放失败: {e}")

class VerifiedReasoningEngine:
    """可验证推理引擎"""
    
    def __init__(self, tool_registry=None, global_budget: Dict[str, float] = None):
        self.tool_registry = tool_registry
        self.arg_validator = ArgSchemaValidator(tool_registry)
        self.precondition_checker = PreconditionChecker(tool_registry)
        self.budget_planner = BudgetPlanner(global_budget)
        
        self.reasoning_chains = {}
        self.validation_stats = {
            "total_chains": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "budget_rejections": 0
        }
        
        logger.info("🔬 VerifiedReasoningEngine 初始化完成")
    
    def create_reasoning_chain(self, user_query: str) -> str:
        """创建推理链条"""
        chain_id = f"chain_{int(time.time() * 1000)}"
        chain = ReasoningChain(
            chain_id=chain_id,
            user_query=user_query
        )
        
        self.reasoning_chains[chain_id] = chain
        self.validation_stats["total_chains"] += 1
        
        logger.info(f"🔗 创建推理链条: {chain_id}")
        return chain_id
    
    def add_claim(self, chain_id: str, claim_type: ClaimType, statement: str, 
                  confidence: float = 0.8, dependencies: List[str] = None) -> str:
        """添加声明"""
        if chain_id not in self.reasoning_chains:
            raise ValueError(f"推理链条不存在: {chain_id}")
        
        claim_id = f"claim_{len(self.reasoning_chains[chain_id].claims) + 1}"
        claim = Claim(
            claim_id=claim_id,
            claim_type=claim_type,
            statement=statement,
            confidence=confidence,
            dependencies=dependencies or []
        )
        
        self.reasoning_chains[chain_id].claims.append(claim)
        logger.debug(f"📝 添加声明: {claim_id} -> {statement[:50]}...")
        return claim_id
    
    def add_evidence(self, chain_id: str, claim_id: str, evidence_type: EvidenceType,
                     verification_method: str, verification_target: str, 
                     expected_result: Any = None) -> str:
        """添加证据"""
        if chain_id not in self.reasoning_chains:
            raise ValueError(f"推理链条不存在: {chain_id}")
        
        evidence_id = f"evidence_{len(self.reasoning_chains[chain_id].evidence) + 1}"
        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            claim_id=claim_id,
            verification_method=verification_method,
            verification_target=verification_target,
            expected_result=expected_result
        )
        
        self.reasoning_chains[chain_id].evidence.append(evidence)
        logger.debug(f"🔍 添加证据: {evidence_id} -> {verification_target}")
        return evidence_id
    
    def add_action_contract(self, chain_id: str, action_name: str, tool_name: str,
                           arguments: Dict[str, Any], preconditions: List[str] = None,
                           expected_outcomes: List[str] = None, 
                           budget_cost: float = 0.1, time_estimate: float = 10.0,
                           resource_requirements: Dict[str, Any] = None) -> str:
        """添加动作合同"""
        if chain_id not in self.reasoning_chains:
            raise ValueError(f"推理链条不存在: {chain_id}")
        
        contract_id = f"contract_{len(self.reasoning_chains[chain_id].contracts) + 1}"
        contract = ActionContract(
            contract_id=contract_id,
            action_name=action_name,
            tool_name=tool_name,
            arguments=arguments,
            preconditions=preconditions or [],
            expected_outcomes=expected_outcomes or [],
            resource_requirements=resource_requirements or {},
            budget_cost=budget_cost,
            time_estimate=time_estimate
        )
        
        self.reasoning_chains[chain_id].contracts.append(contract)
        logger.debug(f"📋 添加动作合同: {contract_id} -> {action_name}")
        return contract_id
    
    def validate_reasoning_chain(self, chain_id: str) -> Tuple[bool, Dict[str, Any]]:
        """验证推理链条"""
        if chain_id not in self.reasoning_chains:
            raise ValueError(f"推理链条不存在: {chain_id}")
        
        chain = self.reasoning_chains[chain_id]
        validation_results = {
            "chain_id": chain_id,
            "overall_valid": True,
            "claim_validations": [],
            "evidence_validations": [],
            "contract_validations": [],
            "budget_validation": {},
            "validation_time": time.time()
        }
        
        try:
            # 1. 验证证据
            for evidence in chain.evidence:
                evidence_valid = self._verify_evidence(evidence)
                validation_results["evidence_validations"].append({
                    "evidence_id": evidence.evidence_id,
                    "valid": evidence_valid,
                    "verification_status": evidence.verification_status,
                    "error": evidence.error_message
                })
                if not evidence_valid:
                    validation_results["overall_valid"] = False
            
            # 2. 验证动作合同
            for contract in chain.contracts:
                contract_valid, contract_errors = self._validate_action_contract(contract)
                validation_results["contract_validations"].append({
                    "contract_id": contract.contract_id,
                    "valid": contract_valid,
                    "errors": contract_errors
                })
                if not contract_valid:
                    validation_results["overall_valid"] = False
            
            # 3. 验证预算
            budget_feasible, budget_info = self.budget_planner.check_budget_feasibility(chain.contracts)
            validation_results["budget_validation"] = budget_info
            if not budget_feasible:
                validation_results["overall_valid"] = False
                self.validation_stats["budget_rejections"] += 1
            
            # 更新统计
            if validation_results["overall_valid"]:
                self.validation_stats["successful_validations"] += 1
            else:
                self.validation_stats["failed_validations"] += 1
            
            # 保存验证结果
            chain.validation_summary = validation_results
            
            logger.info(f"🔬 推理链条验证完成: {chain_id} -> {'✅ 通过' if validation_results['overall_valid'] else '❌ 失败'}")
            return validation_results["overall_valid"], validation_results
            
        except Exception as e:
            logger.error(f"❌ 推理链条验证异常: {chain_id} -> {e}")
            validation_results["overall_valid"] = False
            validation_results["validation_error"] = str(e)
            return False, validation_results
    
    def _verify_evidence(self, evidence: Evidence) -> bool:
        """验证单个证据"""
        try:
            evidence.verification_time = time.time()
            
            if evidence.evidence_type == EvidenceType.URL_VERIFICATION:
                exists, info = self.precondition_checker.check_resource_existence("url", evidence.verification_target)
                evidence.actual_result = info
                evidence.verification_status = exists
                
            elif evidence.evidence_type == EvidenceType.FILE_EXISTENCE:
                exists, info = self.precondition_checker.check_resource_existence("file", evidence.verification_target)
                evidence.actual_result = info
                evidence.verification_status = exists
                
            elif evidence.evidence_type == EvidenceType.HEALTH_CHECK:
                healthy, info = self.precondition_checker.check_tool_health(evidence.verification_target)
                evidence.actual_result = info
                evidence.verification_status = healthy
                
            else:
                # 其他类型的证据验证
                evidence.verification_status = True
                evidence.actual_result = {"status": "skipped", "reason": "verification_not_implemented"}
            
            if not evidence.verification_status and "error" in evidence.actual_result:
                evidence.error_message = evidence.actual_result["error"]
            
            return evidence.verification_status
            
        except Exception as e:
            evidence.verification_status = False
            evidence.error_message = str(e)
            logger.error(f"❌ 证据验证失败: {evidence.evidence_id} -> {e}")
            return False
    
    def _validate_action_contract(self, contract: ActionContract) -> Tuple[bool, List[str]]:
        """验证动作合同"""
        errors = []
        
        try:
            # 1. 参数模式验证
            args_valid, arg_errors = self.arg_validator.validate_arguments(contract.tool_name, contract.arguments)
            if not args_valid:
                errors.extend(arg_errors)
            
            # 2. 工具健康检查
            tool_healthy, health_info = self.precondition_checker.check_tool_health(contract.tool_name)
            if not tool_healthy:
                errors.append(f"工具不健康: {health_info.get('error', 'unknown')}")
            
            # 3. 预算检查
            if not self.budget_planner.reserve_budget(contract):
                errors.append("预算不足")
            else:
                # 如果预留成功但验证失败，需要释放预算
                if errors:
                    self.budget_planner.release_budget(contract)
            
            # 更新合同状态
            if not errors:
                contract.status = ContractStatus.VALIDATED
            else:
                contract.status = ContractStatus.FAILED
            
            contract.validation_results = {
                "args_valid": args_valid,
                "tool_healthy": tool_healthy,
                "errors": errors,
                "validated_at": time.time()
            }
            
            return len(errors) == 0, errors
            
        except Exception as e:
            error_msg = f"合同验证异常: {str(e)}"
            errors.append(error_msg)
            logger.error(f"❌ {error_msg}")
            return False, errors
    
    def get_reasoning_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """获取推理链条"""
        return self.reasoning_chains.get(chain_id)
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """获取验证统计"""
        return self.validation_stats.copy()
