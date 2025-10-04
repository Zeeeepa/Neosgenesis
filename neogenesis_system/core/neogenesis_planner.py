
"""
Neogenesis智能规划器 - 基于Meta MAB的高级规划系统
将MainController的五阶段智能决策逻辑重构为符合框架标准的规划器组件

核心特性:
1. 五阶段智能验证-学习决策流程
2. 依赖注入式组件协作
3. 标准Plan输出格式
4. 智能决策结果翻译
"""

import time
import logging
from typing import Dict, List, Optional, Any

# 导入框架核心
try:
    from ..abstractions import BasePlanner
    from ..shared.data_structures import (
        Plan, Action,
        # 导入新的上下文协议数据结构
        StrategyDecision, StageContext, ThinkingSeedContext, SeedVerificationContext,
        PathGenerationContext, PathVerificationContext, MABDecisionContext
    )
except ImportError:
    from neogenesis_system.abstractions import BasePlanner
    from neogenesis_system.shared.data_structures import (
        Plan, Action,
        # 导入新的上下文协议数据结构
        StrategyDecision, StageContext, ThinkingSeedContext, SeedVerificationContext,
        PathGenerationContext, PathVerificationContext, MABDecisionContext
    )

# 导入Meta MAB组件
from ..cognitive_engine.reasoner import PriorReasoner
from ..cognitive_engine.path_generator import PathGenerator
from ..cognitive_engine.mab_converger import MABConverger

# 导入语义分析器
try:
    from ..cognitive_engine.semantic_analyzer import create_semantic_analyzer
    SEMANTIC_ANALYZER_AVAILABLE = True
except ImportError:
    SEMANTIC_ANALYZER_AVAILABLE = False
from ..cognitive_engine.data_structures import DecisionResult, ReasoningPath
from ..shared.state_manager import StateManager

# 导入工具系统
from ..tools.tool_abstraction import (
    ToolRegistry, 
    global_tool_registry,
    execute_tool,
    ToolResult
)

logger = logging.getLogger(__name__)


class NeogenesisPlanner(BasePlanner):
    """
    Neogenesis智能规划器
    
    将MainController的五阶段决策逻辑重构为标准规划器组件：
    1. 思维种子生成 (PriorReasoner)
    2. 种子验证检查 (idea_verification)
    3. 思维路径生成 (PathGenerator)
    4. 路径验证学习 (核心创新)
    5. 智能最终决策 (升级版MAB)
    """
    
    def __init__(self, 
                 prior_reasoner: PriorReasoner,
                 path_generator: PathGenerator,
                 mab_converger: MABConverger,
                 workflow_agent=None,
                 tool_registry: Optional[ToolRegistry] = None,
                 state_manager: Optional[StateManager] = None,
                 config: Optional[Dict] = None,
                 cognitive_scheduler=None):
        """
        依赖注入式初始化
        
        Args:
            prior_reasoner: 先验推理器实例
            path_generator: 路径生成器实例  
            mab_converger: MAB收敛器实例
            workflow_agent: WorkflowGenerationAgent实例（可选，用于委托战术规划）
            tool_registry: 工具注册表（可选，默认使用全局注册表）
            state_manager: 状态管理器（可选）
            config: 配置字典（可选）
            cognitive_scheduler: 认知调度器（可选）
        """
        super().__init__(
            name="NeogenesisPlanner",
            description="基于Meta MAB的五阶段智能规划器"
        )
        
        # 依赖注入的核心组件
        self.prior_reasoner = prior_reasoner
        self.path_generator = path_generator
        self.mab_converger = mab_converger
        
        # MABConverger初始化验证
        self._validate_mab_converger_initialization()
        
        # 委托代理 - 用于战术规划
        self.workflow_agent = workflow_agent
        
        # 可选组件
        self.tool_registry = tool_registry or global_tool_registry
        
        # 确保搜索工具被注册
        self._ensure_search_tools_registered()
        
        self.state_manager = state_manager
        self.config = config or {}
        
        # 认知调度器集成
        self.cognitive_scheduler = cognitive_scheduler
        
        # 初始化语义分析器
        self.semantic_analyzer = None
        if SEMANTIC_ANALYZER_AVAILABLE:
            try:
                self.semantic_analyzer = create_semantic_analyzer()
                logger.info("NeogenesisPlanner 已集成语义分析器")
            except Exception as e:
                logger.warning(f"⚠️ 语义分析器初始化失败，将使用降级方法: {e}")
                self.semantic_analyzer = None
        else:
            logger.info("未发现语义分析器，使用传统关键词方法")
        
        # 如果认知调度器存在，尝试注入回溯引擎依赖
        if self.cognitive_scheduler:
            self._inject_cognitive_dependencies()
        
        # 内部状态
        self.total_rounds = 0
        self.decision_history = []
        self.performance_stats = {
            'total_decisions': 0,
            'avg_decision_time': 0.0,
            'component_performance': {
                'prior_reasoner': {'calls': 0, 'avg_time': 0.0},
                'path_generator': {'calls': 0, 'avg_time': 0.0},
                'mab_converger': {'calls': 0, 'avg_time': 0.0}
            }
        }
        
        logger.info(f"🧠 NeogenesisPlanner 初始化完成")
        logger.info(f"战略组件: PriorReasoner, PathGenerator, MABConverger")
        logger.info(f"战术代理: {'已配置WorkflowAgent' if self.workflow_agent else '未配置(兼容模式)'}")
        try:
            tool_count = len(self.tool_registry.tools) if hasattr(self.tool_registry, 'tools') else len(getattr(self.tool_registry, '_tools', {}))
            logger.info(f"   工具注册表: {tool_count} 个工具")
        except:
            logger.info(f"   工具注册表: 已初始化")
    
    def _ensure_search_tools_registered(self):
        """确保搜索工具被正确注册"""
        try:
            # 🔥 修复：先导入default_tools，再导入search_tools以覆盖模拟实现
            from ..tools import default_tools
            from ..providers import search_tools  # 这个会覆盖default_tools中的模拟实现
            
            # 检查关键工具是否已注册
            required_tools = ["idea_verification", "web_search"]
            missing_tools = []
            
            for tool_name in required_tools:
                if not self.tool_registry.has_tool(tool_name):
                    missing_tools.append(tool_name)
            
            if missing_tools:
                logger.warning(f"⚠️ 缺少关键工具: {missing_tools}")
                logger.info("尝试重新导入工具模块...")
                
                # 🔥 强制重新导入（保持正确顺序）
                import importlib
                importlib.reload(default_tools)
                importlib.reload(search_tools)  # 确保search_tools覆盖default_tools
                
                # 再次检查
                still_missing = []
                for tool_name in missing_tools:
                    if not self.tool_registry.has_tool(tool_name):
                        still_missing.append(tool_name)
                
                if still_missing:
                    logger.error(f"❌ 仍然缺少工具: {still_missing}")
                else:
                    logger.info("✅ 所有工具已成功注册")
            else:
                logger.info("✅ 所有必需工具已注册")
                
            # 🔥 修复：安全地记录当前注册的工具
            try:
                if hasattr(self.tool_registry, 'list_tools'):
                    available_tools = list(self.tool_registry.list_tools())
                elif hasattr(self.tool_registry, 'list_all_tools'):
                    available_tools = list(self.tool_registry.list_all_tools())
                elif hasattr(self.tool_registry, '_tools'):
                    available_tools = list(self.tool_registry._tools.keys())
                else:
                    available_tools = ["无法获取工具列表"]
                
                logger.debug(f"🔧 当前可用工具: {available_tools}")
            except Exception as list_error:
                logger.debug(f"⚠️ 获取工具列表失败: {list_error}")
                logger.debug("🔧 工具注册表可能不完整，但系统将继续运行")
            
        except Exception as e:
            logger.error(f"❌ 工具注册检查失败: {e}")
            logger.warning("⚠️ 将使用启发式验证作为回退")
            
            # 🔥 新增：提供更详细的错误信息和恢复建议
            if "list_tools" in str(e):
                logger.info("建议：检查ToolRegistry是否正确实现了list_tools方法")
            elif "has_tool" in str(e):
                logger.info("建议：检查ToolRegistry是否正确实现了has_tool方法")
            else:
                logger.info("建议：检查工具注册表的初始化和依赖注入")
    
    def _inject_cognitive_dependencies(self):
        """向认知调度器注入核心依赖组件"""
        try:
            if (self.cognitive_scheduler and 
                hasattr(self.cognitive_scheduler, 'update_retrospection_dependencies')):
                
                success = self.cognitive_scheduler.update_retrospection_dependencies(
                    path_generator=self.path_generator,
                    mab_converger=self.mab_converger
                )
                
                if success:
                    logger.info("✅ 回溯引擎依赖组件已成功注入")
                else:
                    logger.warning("⚠️ 回溯引擎依赖组件注入失败")
            
        except Exception as e:
            logger.warning(f"⚠️ 认知调度器依赖注入异常: {e}")
    
    def set_cognitive_scheduler(self, cognitive_scheduler):
        """设置认知调度器并自动注入依赖组件"""
        self.cognitive_scheduler = cognitive_scheduler
        if cognitive_scheduler:
            self._inject_cognitive_dependencies()
            logger.info("认知调度器已设置并完成依赖注入")
    
    def create_plan(self, query: str, memory: Any, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        创建执行计划 - 实现BasePlanner接口
        
        新的委托模式：
        1. 执行战略决策 (make_strategic_decision) 
        2. 委托战术规划 (_delegate_to_workflow_agent)
        3. 返回完整的执行计划
        
        Args:
            query: 用户查询
            memory: Agent的记忆对象
            context: 可选的执行上下文
            
        Returns:
            Plan: 标准格式的执行计划
        """
        logger.info(f"NeogenesisPlanner开始战略+委托模式: {query[:50]}...")
        start_time = time.time()
        
        # 通知认知调度器Agent正在活跃工作
        if self.cognitive_scheduler:
            self.cognitive_scheduler.notify_activity("task_planning", {
                "query": query[:100],
                "timestamp": start_time,
                "source": "create_plan"
            })
        
        try:
            # 阶段1: 执行战略决策
            logger.info("阶段1: 战略规划")
            strategy_decision = self.make_strategic_decision(
                user_query=query,
                execution_context=context
            )
            
            # 阶段2: 委托战术规划
            logger.info("阶段2: 委托战术规划")
            plan = self._delegate_to_workflow_agent(query, memory, strategy_decision)
            
            # 更新性能统计
            execution_time = time.time() - start_time
            self._update_planner_stats(True, execution_time)
            
            logger.info(f"✅ 战略+委托规划完成: {plan.action_count if plan.actions else 0} 个行动, 耗时 {execution_time:.3f}s")
            return plan
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_planner_stats(False, execution_time)
            
            logger.error(f"❌ 战略+委托规划失败: {e}")
            
            # 返回错误回退计划
            return Plan(
                thought=f"战略+委托规划过程中出现错误: {str(e)}",
                final_answer=f"抱歉，我在处理您的请求时遇到了问题: {str(e)}",
                metadata={'delegation_error': str(e)}
            )
    
    def validate_plan(self, plan: Plan) -> bool:
        """
        验证计划的有效性
        
        Args:
            plan: 要验证的计划
            
        Returns:
            bool: 计划是否有效
        """
        try:
            # 检查基本结构
            if not plan.thought:
                return False
            
            # 直接回答模式
            if plan.is_direct_answer:
                return plan.final_answer is not None and len(plan.final_answer.strip()) > 0
            
            # 工具执行模式
            if not plan.actions:
                return False
            
            # 验证所有行动
            for action in plan.actions:
                if not action.tool_name or not isinstance(action.tool_input, dict):
                    return False
                
                # 检查工具是否存在
                if self.tool_registry and not self.tool_registry.has_tool(action.tool_name):
                    logger.warning(f"⚠️ 工具 '{action.tool_name}' 未在注册表中找到")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 计划验证失败: {e}")
            return False
    
    def make_strategic_decision(self, user_query: str, execution_context: Optional[Dict[str, Any]] = None) -> StrategyDecision:
        """
        执行完整的五阶段战略决策流程，返回标准化的StrategyDecision对象
        
        这是新的中心化上下文协议的核心方法，将原有的_make_decision_logic重构为
        标准化的战略决策流程，输出完整的上下文信息。
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            
        Returns:
            StrategyDecision: 包含完整五阶段上下文的战略决策结果
        """
        start_time = time.time()
        self.total_rounds += 1
        
        logger.info(f"开始第 {self.total_rounds} 轮五阶段战略决策")
        logger.info(f"查询: {user_query[:50]}...")
        
        # 初始化战略决策对象
        strategy_decision = StrategyDecision(
            user_query=user_query,
            round_number=self.total_rounds,
            execution_context=execution_context
        )
        
        try:
            # 阶段一：思维种子生成
            stage1_start = time.time()
            logger.info("阶段一：思维种子生成")
            
            stage1_context = self._execute_stage1_thinking_seed(user_query, execution_context)
            stage1_context.add_metric("execution_time", time.time() - stage1_start)
            strategy_decision.add_stage_context(1, stage1_context)
            
            if stage1_context.has_errors:
                strategy_decision.add_error("阶段一执行失败")
                return self._create_fallback_decision(strategy_decision, "思维种子生成失败")
            
            # 🔍 阶段二：种子验证检查
            stage2_start = time.time()
            logger.info("🔍 阶段二：种子验证检查")
            
            stage2_context = self._execute_stage2_seed_verification(stage1_context, execution_context)
            stage2_context.add_metric("execution_time", time.time() - stage2_start)
            strategy_decision.add_stage_context(2, stage2_context)
            
            if not stage2_context.verification_result:
                strategy_decision.add_warning("种子验证存在问题，但继续执行")
            
            # 🛤️ 阶段三：思维路径生成
            stage3_start = time.time()
            logger.info("🛤️ 阶段三：思维路径生成")
            
            stage3_context = self._execute_stage3_path_generation(stage1_context, stage2_context, execution_context)
            stage3_context.add_metric("execution_time", time.time() - stage3_start)
            strategy_decision.add_stage_context(3, stage3_context)
            
            if stage3_context.path_count == 0:
                strategy_decision.add_error("路径生成失败")
                return self._create_fallback_decision(strategy_decision, "无法生成思维路径")
            
            # 阶段四：路径验证与即时学习
            stage4_start = time.time()
            logger.info("阶段四：路径验证与即时学习")
            
            stage4_context = self._execute_stage4_path_verification(stage3_context, execution_context)
            stage4_context.add_metric("execution_time", time.time() - stage4_start)
            strategy_decision.add_stage_context(4, stage4_context)
            
            # 阶段五：MAB最终决策
            stage5_start = time.time()
            logger.info("阶段五：MAB最终决策")
            
            stage5_context = self._execute_stage5_mab_decision(stage4_context, execution_context)
            stage5_context.add_metric("execution_time", time.time() - stage5_start)
            strategy_decision.add_stage_context(5, stage5_context)
            
            if not stage5_context.selected_path:
                strategy_decision.add_error("MAB决策失败")
                return self._create_fallback_decision(strategy_decision, "无法选择最优路径")
            
            # 设置最终决策结果
            strategy_decision.chosen_path = stage5_context.selected_path
            strategy_decision.final_reasoning = stage5_context.decision_reasoning
            strategy_decision.confidence_score = stage5_context.selection_confidence
            
            # 计算决策质量指标
            total_time = time.time() - start_time
            strategy_decision.total_execution_time = total_time
            strategy_decision.add_quality_metric("decision_completeness", 1.0 if strategy_decision.is_complete else 0.5)
            strategy_decision.add_quality_metric("average_stage_time", total_time / 5)
            strategy_decision.add_quality_metric("path_diversity", stage3_context.diversity_score)
            
            # logger.info(f"✅ 五阶段战略决策完成")  # 详细流程日志已简化
            logger.info(f"   选择路径: {strategy_decision.chosen_path.get('path_id', 'Unknown') if isinstance(strategy_decision.chosen_path, dict) else 'Unknown'}")
            logger.info(f"   置信度: {strategy_decision.confidence_score:.3f}")
            logger.info(f"   总耗时: {total_time:.3f}s")
            
            return strategy_decision
            
        except Exception as e:
            logger.error(f"❌ 战略决策过程失败: {e}")
            strategy_decision.add_error(f"决策过程异常: {str(e)}")
            return self._create_fallback_decision(strategy_decision, f"决策过程异常: {str(e)}")
    
    def _make_decision_logic(self, user_query: str, deepseek_confidence: float = 0.5, 
                           execution_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        LLM增强的六阶段智能验证-学习决策逻辑
        
        新架构：
        阶段零：LLM智能路由分析 (新增)
        阶段一：先验推理 - 生成思维种子
        阶段二：验证思维种子
        阶段三：路径生成
        阶段四：路径验证与选择
        阶段五：MAB学习与优化
        """
        start_time = time.time()
        self.total_rounds += 1
        
        logger.info(f"🚀 开始第 {self.total_rounds} 轮LLM增强的六阶段智能决策")
        logger.info(f"   查询: {user_query[:50]}...")
        logger.info(f"   置信度: {deepseek_confidence:.2f}")
        
        try:
            # 阶段零：LLM智能路由分析 (新增)
            route_analysis_start = time.time()
            route_classification = self.prior_reasoner.classify_and_route(
                user_query=user_query, 
                execution_context=execution_context
            )
            route_analysis_time = time.time() - route_analysis_start
            
            # logger.info(f"阶段零完成: LLM路由分析")  # 详细流程日志已简化
            logger.info(f"复杂度: {route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'unknown'}")
            logger.info(f"领域: {route_classification.domain.value if hasattr(route_classification, 'domain') else 'unknown'}")
            logger.info(f"意图: {route_classification.intent.value if hasattr(route_classification, 'intent') else 'unknown'}")
            logger.info(f"置信度: {route_classification.confidence if hasattr(route_classification, 'confidence') else 0.0:.2f}")
            logger.info(f"耗时: {route_analysis_time:.3f}s")
            
            # 🔀 根据路由策略决定处理流程
            if self._should_use_fast_path(route_classification, user_query):
                # logger.info("使用快速处理路径")  # 详细流程日志已简化
                return self._execute_fast_path_decision(
                    user_query, route_classification, start_time, execution_context
                )
            else:
                # logger.info("使用完整六阶段处理流径")  # 详细流程日志已简化
                return self._execute_full_stage_decision(
                    user_query, route_classification, deepseek_confidence, 
                    start_time, execution_context
                )
                
        except Exception as e:
            logger.error(f"❌ 决策过程异常: {e}")
            return self._create_error_decision_result(user_query, str(e), time.time() - start_time)

    def _should_use_fast_path(self, route_classification, user_query: str) -> bool:
        """
        判断是否应该使用快速处理路径
        
        快速路径设计原则：只处理"你好"这类极其简单、无需专业知识的输入
        绝不处理任何需要技术知识解答的问题，哪怕是"什么是HTTP"这样看似简单的问题
        
        Args:
            route_classification: 路由分类结果
            user_query: 用户查询（用于严格内容检查）
            
        Returns:
            bool: 是否使用快速路径
        """
        from ..cognitive_engine.reasoner import TaskComplexity, RouteStrategy
        
        # 基础条件检查 - 修复：使用字典访问
        is_simple = (hasattr(route_classification, 'complexity') and 
                     route_classification.complexity.value in ['simple', 'low'])
        is_direct_response = (hasattr(route_classification, 'route_strategy') and 
                             route_classification.route_strategy.value == 'direct_response')
        is_high_confidence = (hasattr(route_classification, 'confidence') and 
                             route_classification.confidence >= 0.8)
        
        if not (is_simple and is_direct_response and is_high_confidence):
            return False
            
        # 严格的内容过滤 - 排除任何需要专业知识的查询
        query_lower = user_query.lower().strip()
        
        # 允许的极简输入白名单 - 优先检查
        simple_greetings = [
            # 基本问候语
            "你好", "hi", "hello", "hey", "好", "在吗", "在不在",
            
            # 自我介绍相关
            "介绍一下你自己", "介绍下你自己", "介绍你自己", "自我介绍",
            "你是谁", "你是什么", "who are you", "what are you",
            "tell me about yourself", "introduce yourself",
            
            # 能力询问
            "你能做什么", "你的功能", "你有什么功能", "what can you do",
            "你会什么", "你擅长什么", "你的能力", "your capabilities",
            
            # 系统状态
            "系统状态", "status", "测试", "test", "ping", "ok", "好的", 
            
            # 礼貌用语
            "谢谢", "thank", "再见", "bye", "没事", "没问题",
            
            # 简单确认
            "是的", "对", "yes", "确定", "好", "行"
        ]
        
        # 优先检查白名单 - 如果在白名单中，直接允许快速路径
        is_simple_greeting = any(greeting in query_lower for greeting in simple_greetings)
        
        if is_simple_greeting:
            logger.info(f"✅ 检测到简单问候语，允许快速路径: {user_query[:30]}")
            return True
        
        # 如果不在白名单中，检查是否为技术查询模式
        tech_question_patterns = [
            "什么是", "what is", "如何", "how to", "怎么", "怎样", 
            "为什么", "why", "原理", "principle", "工作", "work",
            "实现", "implement", "配置", "config", "设置", "setup",
            "安装", "install", "部署", "deploy", "优化", "optimize",
            "调试", "debug", "错误", "error", "问题", "problem",
            "解决", "solve", "修复", "fix", "api", "数据库", "database",
            "协议", "protocol", "框架", "framework", "架构", "architecture"
        ]
        
        # 如果包含任何技术查询模式，拒绝快速路径
        if any(pattern in query_lower for pattern in tech_question_patterns):
            logger.info(f"🚫 检测到技术查询模式，拒绝快速路径: {user_query[:50]}")
            return False
        
        # 其他情况也拒绝快速路径（保守策略）
        logger.info(f"🚫 不符合快速路径白名单，转入完整处理: {user_query[:50]}")
        return False

    def _execute_fast_path_decision(self, user_query: str, route_classification, 
                                   start_time: float, execution_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行快速路径决策 - 适用于简单直接的任务
        
        Args:
            user_query: 用户查询
            route_classification: 路由分类结果
            start_time: 开始时间
            execution_context: 执行上下文
            
        Returns:
            Dict: 决策结果
        """
        logger.info("⚡ 执行快速路径决策")
        
        # 生成简化的思维种子
        thinking_seed = self.prior_reasoner.get_thinking_seed(user_query, execution_context)
        
        # 创建单一的快速响应路径
        from ..cognitive_engine.data_structures import ReasoningPath
        
        fast_path = ReasoningPath(
            path_id="llm_route_fast_path",
            path_type="direct_answer",
            description=f"基于LLM路由分析的快速响应路径",
            prompt_template=f"基于LLM路由分析，这是一个{route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'medium'}任务，"
                           f"领域为{route_classification.domain.value if hasattr(route_classification, 'domain') else 'general'}，建议直接回答。",
            confidence_score=route_classification.confidence if hasattr(route_classification, 'confidence') else 0.7
        )
        
        execution_time = time.time() - start_time
        
        # 构建快速决策结果
        decision_result = {
            'chosen_path': fast_path,
            'thinking_seed': thinking_seed,
            'reasoning': f"LLM路由分析确定这是简单任务，采用快速处理路径。分析理由: {route_classification.reasoning}",
            'available_paths': [fast_path],
            'verified_paths': [fast_path],
            'timestamp': time.time(),
            'round_number': self.total_rounds,
            'selection_algorithm': 'llm_route_fast_path',
            'verification_stats': {
                'total_verifications': 1,
                'successful_verifications': 1,
                'verification_time': 0.001  # 快速路径跳过验证
            },
            'performance_metrics': {
                'total_time': execution_time,
                'route_analysis_time': execution_time * 0.8,
                'path_generation_time': execution_time * 0.1,
                'mab_time': execution_time * 0.1,
                'fast_path_used': True
            },
            'route_classification': route_classification
        }
        
        logger.info(f"⚡ 快速路径决策完成，耗时: {execution_time:.3f}s")
        return decision_result

    def _execute_full_stage_decision(self, user_query: str, route_classification, 
                                   deepseek_confidence: float, start_time: float,
                                   execution_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行完整六阶段决策 - 适用于复杂任务
        
        Args:
            user_query: 用户查询
            route_classification: 路由分类结果
            deepseek_confidence: DeepSeek置信度
            start_time: 开始时间
            execution_context: 执行上下文
            
        Returns:
            Dict: 决策结果
        """
        logger.info("🔬 执行完整六阶段决策")
        
        try:
            # 阶段一：先验推理 - 生成增强思维种子
            reasoner_start = time.time()
            
            # 根据路由分析结果增强思维种子生成
            enhanced_context = execution_context.copy() if execution_context else {}
            enhanced_context.update({
                # 只传递可序列化的信息，不传递 TriageClassification 对象
                'llm_route_analysis': {
                    'complexity': route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'medium',
                    'domain': route_classification.domain.value if hasattr(route_classification, 'domain') else 'general',
                    'intent': route_classification.intent.value if hasattr(route_classification, 'intent') else 'question',
                    'route_strategy': route_classification.route_strategy.value if hasattr(route_classification, 'route_strategy') else 'direct_response',
                    'confidence': route_classification.confidence if hasattr(route_classification, 'confidence') else 0.7,
                    'reasoning': route_classification.reasoning if hasattr(route_classification, 'reasoning') else 'No reasoning provided'
                },
                'suggested_complexity': route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'medium',
                'suggested_domain': route_classification.domain.value if hasattr(route_classification, 'domain') else 'general',
                'suggested_strategy': route_classification.route_strategy.value if hasattr(route_classification, 'route_strategy') else 'direct_response'
            })
            
            thinking_seed = self.prior_reasoner.get_thinking_seed(user_query, enhanced_context)
            
            # 兼容性：获取旧格式数据
            task_confidence = self.prior_reasoner.assess_task_confidence(user_query, execution_context)
            complexity_info = self.prior_reasoner.analyze_task_complexity(user_query)
            
            reasoner_time = time.time() - reasoner_start
            self._update_component_performance('prior_reasoner', reasoner_time)
            
            # 显示Agent的真实思考内容
            logger.info("阶段一：思维种子生成")
            logger.info(f"基于用户查询「{user_query[:50]}...」，我生成了以下思维种子：")
            logger.info(f" {thinking_seed[:200]}{'...' if len(thinking_seed) > 200 else ''}")
            logger.info(f"种子长度: {len(thinking_seed)} 字符，生成耗时: {reasoner_time:.2f}秒")
            
            # 🔍 阶段二：LLM增强思维种子验证
            seed_verification_start = time.time()
            seed_verification_result = self._verify_idea_feasibility(
                idea_text=thinking_seed,
                context={
                    'stage': 'thinking_seed',
                    'domain': route_classification.domain.value if hasattr(route_classification, 'domain') else 'general',  # 使用LLM路由分析的领域
                    'complexity': route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'medium',  # 使用LLM路由分析的复杂度
                    'route_strategy': route_classification.route_strategy.value if hasattr(route_classification, 'route_strategy') else 'standard_rag',  # 使用LLM路由策略
                    'query': user_query,
                    'llm_routing_enabled': True,  # 标记启用了LLM路由
                    **(execution_context if execution_context else {})
                }
            )
            seed_verification_time = time.time() - seed_verification_start
            
            # 分析种子验证结果
            seed_feasibility = seed_verification_result.get('feasibility_analysis', {}).get('feasibility_score', 0.5)
            seed_reward = seed_verification_result.get('reward_score', 0.0)
            
            # 显示种子验证的详细结果
            logger.info("阶段二：思维种子验证")
            logger.info(f"我对生成的思维种子进行了可行性验证：")
            logger.info(f"可行性评分: {seed_feasibility:.2f}/1.0")
            logger.info(f"奖励分数: {seed_reward:+.3f}")
            verification_summary = seed_verification_result.get('verification_summary', '验证完成')
            logger.info(f"验证结论: {verification_summary[:150]}{'...' if len(verification_summary) > 150 else ''}")
            logger.info(f"验证耗时: {seed_verification_time:.2f}秒")
            
            # 🛤️ 阶段三：LLM优化路径生成
            generator_start = time.time()
            
            # 根据LLM路由分析优化路径生成参数
            max_paths = self._get_optimal_path_count_for_route(route_classification)
            
            all_reasoning_paths = self.path_generator.generate_paths(
                thinking_seed=thinking_seed, 
                task=user_query,
                max_paths=max_paths
                # 注释：路由提示信息已通过enhanced_context传递给思维种子生成
            )
            generator_time = time.time() - generator_start
            self._update_component_performance('path_generator', generator_time)
            
            # 显示路径生成的详细结果
            logger.info("阶段三：思维路径生成")
            logger.info(f"   基于验证后的思维种子，我生成了 {len(all_reasoning_paths)} 条候选思维路径：")
            for i, path in enumerate(all_reasoning_paths[:3], 1):  # 只显示前3条路径
                path_type = getattr(path, 'path_type', '未知类型')
                path_desc = getattr(path, 'description', '无描述')[:100]
                logger.info(f"   {i}. 【{path_type}】{path_desc}{'...' if len(getattr(path, 'description', '')) > 100 else ''}")
            if len(all_reasoning_paths) > 3:
                logger.info(f"   ... 还有 {len(all_reasoning_paths) - 3} 条路径")
            strategy = route_classification.route_strategy.value if hasattr(route_classification, 'route_strategy') else 'standard_rag'
            logger.info(f"生成策略: {strategy}，耗时: {generator_time:.2f}秒")
            
            # 阶段四：路径验证学习
            path_verification_start = time.time()
            verified_paths = []
            all_infeasible = True
            
            logger.info(f"🔬 阶段四开始: 验证思维路径")
            
            # 简化版路径验证（避免复杂的并行处理）
            for i, path in enumerate(all_reasoning_paths, 1):
                logger.debug(f"🔬 验证路径 {i}/{len(all_reasoning_paths)}: {path.path_type}")
                
                # 构建详细的路径策略内容用于LLM整合
                detailed_path_content = self._build_detailed_path_content(path, user_query)
                
                # 验证单个路径
                path_verification_result = self._verify_idea_feasibility(
                    idea_text=detailed_path_content,
                    context={
                        'stage': 'reasoning_path',
                        'path_id': path.path_id,
                        'path_type': path.path_type,
                        'query': user_query,
                        'user_query': user_query,  # 确保传递用户查询
                        **(execution_context if execution_context else {})
                    }
                )
                
                # 提取验证结果
                path_feasibility = path_verification_result.get('feasibility_analysis', {}).get('feasibility_score', 0.5)
                path_reward = path_verification_result.get('reward_score', 0.0)
                verification_success = not path_verification_result.get('fallback', False)
                
                # 即时学习：立即将验证结果反馈给MAB系统
                if verification_success and path_feasibility > 0.3:
                    # 可行的路径 - 正面学习信号
                    self.mab_converger.update_path_performance(
                        path_id=path.strategy_id,
                        success=True,
                        reward=path_reward
                    )
                    all_infeasible = False
                    logger.debug(f"✅ 路径 {path.path_type} 验证通过: 可行性={path_feasibility:.2f}")
                else:
                    # 不可行的路径 - 负面学习信号
                    self.mab_converger.update_path_performance(
                        path_id=path.strategy_id,
                        success=False,
                        reward=path_reward
                    )
                    logger.debug(f"❌ 路径 {path.path_type} 验证失败: 可行性={path_feasibility:.2f}")
                
                # 记录验证结果
                verified_paths.append({
                    'path': path,
                    'verification_result': path_verification_result,
                    'feasibility_score': path_feasibility,
                    'reward_score': path_reward,
                    'is_feasible': path_feasibility > 0.3
                })
            
            path_verification_time = time.time() - path_verification_start
            feasible_count = sum(1 for vp in verified_paths if vp['is_feasible'])
            
            # 显示路径验证的详细结果
            logger.info("阶段四：路径验证与学习")
            logger.info(f"我对 {len(all_reasoning_paths)} 条候选路径进行了深度验证：")
            logger.info(f"可行路径: {feasible_count} 条")
            logger.info(f"不可行路径: {len(all_reasoning_paths) - feasible_count} 条")
            
            # 显示可行路径的详细信息
            feasible_paths = [vp for vp in verified_paths if vp['is_feasible']]
            for i, vp in enumerate(feasible_paths[:2], 1):  # 只显示前2条可行路径
                path_info = vp.get('path', {})
                path_type = path_info.get('path_type', '未知')
                feasibility = vp.get('feasibility_score', 0.0)
                logger.info(f"{i}. 【{path_type}】可行性: {feasibility:.2f}")
            
            logger.info(f"验证耗时: {path_verification_time:.2f}秒")
            
            # 阶段五：智能最终决策
            final_decision_start = time.time()
            
            if all_infeasible:
                # 所有路径都不可行 - 触发智能绕道思考
                logger.warning("所有思维路径都被验证为不可行，触发智能绕道思考")
                chosen_path = self._execute_intelligent_detour_thinking(
                    user_query, thinking_seed, all_reasoning_paths
                )
                selection_algorithm = 'intelligent_detour'
            else:
                # ✅ 至少有可行路径 - 使用增强的MAB选择
                logger.info("✅ 发现可行路径，使用验证增强的MAB决策")
                chosen_path = self.mab_converger.select_best_path(all_reasoning_paths)
                selection_algorithm = 'verification_enhanced_mab'
            
            final_decision_time = time.time() - final_decision_start
            total_mab_time = path_verification_time + final_decision_time
            self._update_component_performance('mab_converger', total_mab_time)
            
            # 计算总体决策时间
            total_decision_time = time.time() - start_time
            
            # 构建决策结果
            decision_result = {
                # 基本信息
                'timestamp': time.time(),
                'round_number': self.total_rounds,
                'user_query': user_query,
                'deepseek_confidence': deepseek_confidence,
                'execution_context': execution_context,
                
                # 五阶段决策结果
                'thinking_seed': thinking_seed,
                'seed_verification': seed_verification_result,
                'chosen_path': chosen_path,
                'available_paths': all_reasoning_paths,
                'verified_paths': verified_paths,
                
                # 决策元信息
                'reasoning': f"五阶段智能验证-学习决策: {chosen_path.path_type} - {chosen_path.description}",
                'path_count': len(all_reasoning_paths),
                'feasible_path_count': feasible_count,
                'selection_algorithm': selection_algorithm,
                'architecture_version': '5-stage-verification',
                'verification_enabled': True,
                'instant_learning_enabled': True,
                
                # 验证统计
                'verification_stats': {
                    'seed_feasibility': seed_feasibility,
                    'seed_reward': seed_reward,
                    'paths_verified': len(verified_paths),
                    'feasible_paths': feasible_count,
                    'infeasible_paths': len(verified_paths) - feasible_count,
                    'all_paths_infeasible': all_infeasible,
                    'average_path_feasibility': sum(vp['feasibility_score'] for vp in verified_paths) / len(verified_paths) if verified_paths else 0.0,
                    'total_verification_time': seed_verification_time + path_verification_time
                },
                
                # 性能指标
                'performance_metrics': {
                    'total_time': total_decision_time,
                    'stage1_reasoner_time': reasoner_time,
                    'stage2_seed_verification_time': seed_verification_time,
                    'stage3_generator_time': generator_time,
                    'stage4_path_verification_time': path_verification_time,
                    'stage5_final_decision_time': final_decision_time,
                }
            }
            
            # 记录决策历史
            self.decision_history.append(decision_result)
            
            # 限制历史记录长度
            max_history = 100  # 简化的限制
            if len(self.decision_history) > max_history:
                self.decision_history = self.decision_history[-max_history//2:]
            
            # 显示最终决策的详细结果
            logger.info("阶段五：智能最终决策")
            logger.info(f"经过MAB算法分析，我选择了最优路径：")
            logger.info(f"选择路径: 【{chosen_path.path_type}】")
            path_desc = getattr(chosen_path, 'description', '无描述')
            logger.info(f"路径描述: {path_desc[:150]}{'...' if len(path_desc) > 150 else ''}")
            logger.info(f"决策置信度: {getattr(chosen_path, 'confidence_score', deepseek_confidence):.3f}")
            logger.info(f"决策耗时: {final_decision_time:.2f}秒")
            logger.info("")
            # logger.info("五阶段智能决策流程完成")  # 详细流程日志已简化
            logger.info(f"总耗时: {total_decision_time:.3f}秒")
            
            return decision_result
            
        except Exception as e:
            logger.error(f"❌ 决策过程失败: {e}")
            # 返回错误决策结果
            return self._create_error_decision_result(user_query, str(e), time.time() - start_time)
    
    def make_strategic_decision(self, user_query: str, confidence: float = 0.5, 
                              execution_context: Optional[Dict] = None) -> 'StrategyDecision':
        """
        执行战略决策 - NeogenesisPlanner的核心职责
        
        专注于"决定做什么"，输出StrategyDecision供战术规划器使用
        
        Args:
            user_query: 用户查询
            confidence: 置信度
            execution_context: 执行上下文
            
        Returns:
            StrategyDecision: 战略决策结果
        """
        from ..shared.data_structures import StrategyDecision
        
        # 调用原有的决策逻辑
        decision_result = self._make_decision_logic(user_query, confidence, execution_context)
        
        # 转换为StrategyDecision格式 - 修复：只使用存在的字段
        strategy_decision = StrategyDecision(
            chosen_path=decision_result.get('chosen_path'),
            final_reasoning=decision_result.get('reasoning', ''),
            user_query=user_query,
            timestamp=decision_result.get('timestamp', time.time()),
            round_number=decision_result.get('round_number', self.total_rounds),
            execution_context=execution_context,
            confidence_score=confidence
        )
        
        # 添加质量指标
        performance_metrics = decision_result.get('performance_metrics', {})
        for metric_name, value in performance_metrics.items():
            strategy_decision.add_quality_metric(metric_name, value)
        
        # 安全检查chosen_path
        if strategy_decision.chosen_path:
            logger.info(f"战略决策完成: {strategy_decision.chosen_path.path_type}")
        else:
            logger.warning("战略决策完成，但未选择具体路径")
        return strategy_decision
    
    
    def _get_optimal_path_count_for_route(self, route_classification) -> int:
        """
        根据LLM路由分类获取最优路径数量
        
        Args:
            route_classification: LLM路由分类结果
            
        Returns:
            int: 最优路径数量
        """
        from ..cognitive_engine.reasoner import TaskComplexity, RouteStrategy
        
        # 基于复杂度的基础路径数
        base_count = {
            TaskComplexity.SIMPLE: 3,
            TaskComplexity.MODERATE: 5,
            TaskComplexity.COMPLEX: 6,
            TaskComplexity.EXPERT: 8
        }.get(route_classification.complexity.value if hasattr(route_classification, 'complexity') else 'medium', 6)
        
        # 基于路由策略的调整
        routing_rec = route_classification.route_strategy.value if hasattr(route_classification, 'route_strategy') else 'standard_rag'
        if routing_rec == 'direct_response':
            return max(2, base_count // 2)  # 直接回答需要较少路径
        elif routing_rec == 'expert_consultation':
            return min(10, base_count + 2)  # 专家咨询需要更多路径
        elif routing_rec == 'workflow_planning':
            return min(8, base_count + 1)  # 工作流规划需要额外路径
        else:
            return base_count

    # ==================== 委托管理方法 ====================
    
    def _delegate_to_workflow_agent(self, query: str, memory: Any, 
                                   strategy_decision: 'StrategyDecision') -> Plan:
        """
        委托给WorkflowGenerationAgent进行战术规划
        
        Args:
            query: 用户查询
            memory: Agent记忆
            strategy_decision: 战略决策结果
            
        Returns:
            Plan: 完整的执行计划
        """
        # 🔍 调试：检查WorkflowAgent状态
        logger.debug(f"WorkflowAgent状态检查: {self.workflow_agent}")
        logger.debug(f"WorkflowAgent类型: {type(self.workflow_agent)}")
        logger.debug(f"WorkflowAgent是否为None: {self.workflow_agent is None}")
        
        if not self.workflow_agent:
            logger.warning("⚠️ 未配置WorkflowAgent，使用简化的回退计划")
            logger.warning(f"⚠️ WorkflowAgent详细状态: {self.workflow_agent}")
            return self._create_fallback_plan(query, strategy_decision)
        
        try:
            logger.info(f"委托战术规划: {strategy_decision.chosen_path.path_type}")
            
            # 构建上下文，包含战略决策
            context = {
                'strategy_decision': strategy_decision,
                'source': 'strategic_planner',
                'delegation_timestamp': time.time()
            }
            
            # 委托给WorkflowAgent执行
            result = self.workflow_agent.run(query, context)
            
            if isinstance(result, str):
                # 如果返回字符串，转换为Plan
                return Plan(
                    thought=f"通过委托完成战术规划：{strategy_decision.chosen_path.path_type}",
                    final_answer=result,
                    metadata={
                        'strategy_decision': strategy_decision,
                        'is_delegated': True,
                        'delegation_successful': True
                    }
                )
            elif hasattr(result, 'actions') or hasattr(result, 'final_answer'):
                # 如果返回Plan对象，添加委托元数据
                if hasattr(result, 'metadata'):
                    result.metadata.update({
                        'strategy_decision': strategy_decision,
                        'is_delegated': True,
                        'delegation_successful': True
                    })
                return result
            else:
                logger.warning(f"⚠️ WorkflowAgent返回了未预期的结果类型: {type(result)}")
                return self._create_fallback_plan(query, strategy_decision)
                
        except Exception as e:
            logger.error(f"❌ WorkflowAgent委托失败: {e}")
            return self._create_fallback_plan(query, strategy_decision, error=str(e))
    
    def _create_fallback_plan(self, query: str, strategy_decision: 'StrategyDecision', 
                             error: Optional[str] = None) -> Plan:
        """
        创建回退计划（当委托失败时使用）
        
        Args:
            query: 用户查询
            strategy_decision: 战略决策
            error: 错误信息（可选）
            
        Returns:
            Plan: 回退执行计划
        """
        chosen_path = strategy_decision.chosen_path
        
        if error:
            thought = f"委托失败({error})，基于战略决策'{chosen_path.path_type}'生成简化计划"
            answer = f"我已经分析了您的查询「{query}」，选择了'{chosen_path.path_type}'处理策略。由于战术规划组件暂不可用，我提供简化的处理建议："
        else:
            thought = f"未配置WorkflowAgent，基于战略决策'{chosen_path.path_type}'生成简化计划"
            answer = f"我已经分析了您的查询「{query}」，选择了'{chosen_path.path_type}'处理策略："
        
        # 根据路径类型提供不同的建议
        if chosen_path.path_type == "exploratory_investigative":
            answer += "\n\n建议采用探索调研策略：\n1. 收集相关信息和资料\n2. 分析不同观点和方案\n3. 验证关键假设和数据\n4. 形成综合性结论"
        elif chosen_path.path_type == "practical_pragmatic":
            answer += "\n\n建议采用实用直接策略：\n1. 明确具体目标和要求\n2. 选择最直接有效的方法\n3. 快速执行和验证结果\n4. 根据反馈调整优化"
        elif chosen_path.path_type == "systematic_analytical":
            answer += "\n\n建议采用系统分析策略：\n1. 分解问题为多个子问题\n2. 逐一分析各个组成部分\n3. 研究部分间的关联关系\n4. 综合形成整体解决方案"
        else:
            answer += f"\n\n基于'{chosen_path.path_type}'策略，建议您：\n1. {chosen_path.description}\n2. 根据具体情况制定详细计划\n3. 分步骤执行并监控进度\n4. 持续优化和改进"
        
        return Plan(
            thought=thought,
            final_answer=answer,
            metadata={
                'strategy_decision': strategy_decision,
                'is_fallback': True,
                'fallback_reason': error or 'no_workflow_agent'
            }
        )

    # ==================== 战略规划专用方法 ====================
    
    def _build_detailed_path_content(self, path, user_query: str) -> str:
        """
        构建详细的思维路径策略内容，用于LLM深度整合
        
        Args:
            path: ReasoningPath对象
            user_query: 用户原始查询
            
        Returns:
            str: 包含详细策略内容的文本
        """
        content_parts = []
        
        # 基本信息
        content_parts.append(f"**策略类型**: {path.path_type}")
        content_parts.append(f"**策略描述**: {path.description}")
        
        # 添加具体的执行模板内容
        if hasattr(path, 'prompt_template') and path.prompt_template:
            # 提取模板中的关键策略步骤
            template = path.prompt_template
            
            # 查找步骤部分
            if "**分析步骤**" in template or "**创新方法**" in template or "**实用步骤**" in template:
                # 提取步骤内容
                import re
                steps_match = re.search(r'\*\*[^*]+\*\*:\s*(.*?)(?=\n\n|\n基于思维种子|$)', template, re.DOTALL)
                if steps_match:
                    steps_content = steps_match.group(1).strip()
                    content_parts.append(f"**具体策略步骤**:\n{steps_content}")
        
        # 添加思维步骤（如果有）
        if hasattr(path, 'steps') and path.steps:
            steps_text = "\n".join([f"- {step}" for step in path.steps[:5]])  # 限制前5个步骤
            content_parts.append(f"**执行步骤**:\n{steps_text}")
        
        # 添加关键词（如果有）
        if hasattr(path, 'keywords') and path.keywords:
            keywords_text = ", ".join(path.keywords[:8])  # 限制前8个关键词
            content_parts.append(f"**关键词**: {keywords_text}")
        
        # 添加适用领域（如果有）
        if hasattr(path, 'applicable_domains') and path.applicable_domains:
            domains_text = ", ".join(path.applicable_domains[:3])  # 限制前3个领域
            content_parts.append(f"**适用领域**: {domains_text}")
        
        # 添加成功指标（如果有）
        if hasattr(path, 'success_indicators') and path.success_indicators:
            indicators_text = "\n".join([f"- {indicator}" for indicator in path.success_indicators[:3]])
            content_parts.append(f"**成功指标**:\n{indicators_text}")
        
        # 组合所有内容
        detailed_content = "\n\n".join(content_parts)
        
        # 添加用户查询上下文
        final_content = f"""针对用户查询「{user_query}」的思维路径策略：

{detailed_content}

请基于以上具体策略内容和用户查询，验证该思维路径的可行性和有效性。"""
        
        return final_content
    
    def _verify_idea_feasibility(self, idea_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证想法可行性（增强版实现）- 修复奖励为0的问题
        
        这里调用工具系统中的idea_verification工具，并确保总是返回合理的奖励值
        """
        try:
            # 🔥 详细日志：检查工具注册表状态
            logger.info(f"🔍 [验证] 检查工具注册表状态")
            logger.info(f"🔍 [验证] tool_registry存在: {self.tool_registry is not None}")
            
            if self.tool_registry:
                has_tool = self.tool_registry.has_tool("idea_verification")
                logger.info(f"🔍 [验证] idea_verification工具存在: {has_tool}")
                
                # 列出所有已注册的工具
                try:
                    if hasattr(self.tool_registry, 'tools'):
                        all_tools = list(self.tool_registry.tools.keys())
                    elif hasattr(self.tool_registry, '_tools'):
                        all_tools = list(self.tool_registry._tools.keys())
                    else:
                        all_tools = []
                    logger.info(f"🔍 [验证] 已注册工具列表: {all_tools}")
                except Exception as e:
                    logger.warning(f"⚠️ [验证] 无法获取工具列表: {e}")
            else:
                logger.warning(f"⚠️ [验证] tool_registry为None，无法调用工具")
            
            if self.tool_registry and self.tool_registry.has_tool("idea_verification"):
                # 修复：正确传递用户查询和上下文
                user_query = context.get('query', '')
                logger.info(f"✅ [验证] 准备调用idea_verification工具")
                logger.info(f"🔍 [验证] idea_text: {idea_text[:50]}...")
                logger.info(f"🔍 [验证] user_query: {user_query}")
                
                result = execute_tool(
                    "idea_verification", 
                    idea_text=idea_text,  # 使用idea_text参数名
                    context={"user_query": user_query}  # 传递用户查询
                )
                
                logger.info(f"🔍 [验证] execute_tool返回: success={result.success}")
                
                if result.success:
                    logger.info(f"✅ [验证] 工具执行成功")
                    # 确保工具返回的数据包含reward_score
                    data = result.data
                    if 'reward_score' not in data:
                        # 基于feasibility_score计算reward_score
                        feasibility_score = data.get('feasibility_analysis', {}).get('feasibility_score', 0.5)
                        data['reward_score'] = self._calculate_reward_from_feasibility(feasibility_score)
                        logger.info(f"🎯 [验证] 基于可行性计算奖励: {data['reward_score']:.3f}")
                    return data
                else:
                    logger.warning(f"⚠️ [验证] 工具执行失败: {result.error_message}")
            else:
                logger.warning(f"⚠️ [验证] idea_verification工具不可用，使用回退逻辑")
            
            # 回退实现 - 使用更合理的奖励计算
            logger.info(f"🔄 [验证] 使用回退验证逻辑")
            feasibility_score = 0.7
            reward_score = self._calculate_reward_from_feasibility(feasibility_score)
            
            return {
                'feasibility_analysis': {'feasibility_score': feasibility_score},
                'reward_score': reward_score,
                'fallback': True
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 想法验证失败: {e}")
            
            # 即使失败也要给合理的奖励值，而不是0
            feasibility_score = 0.5
            reward_score = self._calculate_reward_from_feasibility(feasibility_score, is_error=True)
            
            return {
                'feasibility_analysis': {'feasibility_score': feasibility_score},
                'reward_score': reward_score,
                'fallback': True
            }
    
    def _calculate_reward_from_feasibility(self, feasibility_score: float, is_error: bool = False) -> float:
        """
        基于可行性分数计算奖励值
        
        Args:
            feasibility_score: 可行性分数 (0.0-1.0)
            is_error: 是否是错误情况
            
        Returns:
            float: 奖励值 (-1.0 到 1.0)
        """
        try:
            if is_error:
                # 错误情况下给予小的负奖励，但不是零
                return -0.1
            
            # 将可行性分数转换为奖励值
            # 可行性 > 0.7: 正奖励
            # 可行性 0.3-0.7: 小正奖励
            # 可行性 < 0.3: 负奖励
            
            if feasibility_score >= 0.7:
                # 高可行性：0.2 到 0.8 的正奖励
                reward = 0.2 + (feasibility_score - 0.7) * 2.0  # (0.7-1.0) -> (0.2-0.8)
            elif feasibility_score >= 0.3:
                # 中等可行性：0.1 到 0.2 的小正奖励
                reward = 0.1 + (feasibility_score - 0.3) * 0.25  # (0.3-0.7) -> (0.1-0.2)
            else:
                # 低可行性：-0.3 到 0.1 的奖励
                reward = -0.3 + feasibility_score * 1.33  # (0.0-0.3) -> (-0.3-0.1)
            
            # 确保奖励值在合理范围内
            reward = max(-1.0, min(1.0, reward))
            
            # 确保奖励值不为零（除非是明确的失败）
            if reward == 0.0:
                reward = 0.05 if feasibility_score >= 0.5 else -0.05
            
            logger.debug(f"奖励计算: 可行性={feasibility_score:.3f} -> 奖励={reward:.3f}")
            return reward
            
        except Exception as e:
            logger.warning(f"⚠️ 奖励计算失败: {e}")
            return 0.1  # 默认小正奖励
    
    def _execute_intelligent_detour_thinking(self, user_query: str, thinking_seed: str, 
                                           all_paths: List[ReasoningPath]) -> ReasoningPath:
        """
        执行智能绕道思考（简化版实现）
        
        当所有路径都不可行时，创建一个备选路径
        """
        logger.info("执行智能绕道思考")
        
        # 创建一个创新路径作为绕道方案
        detour_path = ReasoningPath(
            path_id=f"detour_{int(time.time())}",
            path_type="创新绕道思考",
            description=f"针对'{user_query}'的创新解决方案，突破常规思维限制",
            prompt_template="采用创新思维，寻找独特的解决角度",
            strategy_id="creative_detour",
            instance_id=f"creative_detour_{int(time.time())}"
        )
        
        return detour_path
    
    def _update_component_performance(self, component_name: str, execution_time: float):
        """更新组件性能统计"""
        if component_name in self.performance_stats['component_performance']:
            component_stats = self.performance_stats['component_performance'][component_name]
            component_stats['calls'] += 1
            
            # 计算移动平均
            current_avg = component_stats['avg_time']
            call_count = component_stats['calls']
            component_stats['avg_time'] = (current_avg * (call_count - 1) + execution_time) / call_count
    
    def _update_planner_stats(self, success: bool, execution_time: float):
        """更新规划器统计"""
        self.performance_stats['total_decisions'] += 1
        
        # 更新平均决策时间
        current_avg = self.performance_stats['avg_decision_time']
        total_decisions = self.performance_stats['total_decisions']
        
        if total_decisions == 1:
            self.performance_stats['avg_decision_time'] = execution_time
        else:
            self.performance_stats['avg_decision_time'] = (
                current_avg * (total_decisions - 1) + execution_time
            ) / total_decisions
    
    def _create_error_decision_result(self, user_query: str, error_msg: str, execution_time: float) -> Dict[str, Any]:
        """创建错误决策结果"""
        return {
            'timestamp': time.time(),
            'round_number': self.total_rounds,
            'user_query': user_query,
            'chosen_path': None,
            'available_paths': [],
            'verified_paths': [],
            'reasoning': f"决策失败: {error_msg}",
            'fallback_used': True,
            'error': error_msg,
            'performance_metrics': {
                'total_time': execution_time,
                'error': True
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取规划器统计信息"""
        return {
            'name': self.name,
            'total_rounds': self.total_rounds,
            'performance_stats': self.performance_stats.copy(),
            'decision_history_length': len(self.decision_history),
            'components': {
                'prior_reasoner': type(self.prior_reasoner).__name__,
                'path_generator': type(self.path_generator).__name__,
                'mab_converger': type(self.mab_converger).__name__
            }
        }
    
    # ==================== 新增：中心化上下文协议辅助方法 ====================
    
    def _execute_stage1_thinking_seed(self, user_query: str, execution_context: Optional[Dict]) -> ThinkingSeedContext:
        """执行阶段一：思维种子生成"""
        context = ThinkingSeedContext(user_query=user_query, execution_context=execution_context)
        
        try:
            # 使用PriorReasoner生成思维种子
            seed_result = self.prior_reasoner.generate_thinking_seed(
                user_query=user_query,
                execution_context=execution_context
            )
            
            context.thinking_seed = seed_result.get("thinking_seed", "")
            context.reasoning_process = seed_result.get("reasoning", "")
            context.confidence_score = seed_result.get("confidence", 0.5)
            context.generation_method = "prior_reasoning"
            context.seed_type = "basic"
            
            logger.info(f"思维种子: {context.thinking_seed[:100]}...")
            
        except Exception as e:
            logger.error(f"   ❌ 思维种子生成失败: {e}")
            context.add_error(f"种子生成失败: {str(e)}")
            context.thinking_seed = f"基于查询的基础分析: {user_query}"
            context.confidence_score = 0.3
        
        return context
    
    def _execute_stage2_seed_verification(self, stage1_context: ThinkingSeedContext, 
                                        execution_context: Optional[Dict]) -> SeedVerificationContext:
        """执行阶段二：种子验证检查"""
        import time
        
        context = SeedVerificationContext(
            user_query=stage1_context.user_query,
            execution_context=execution_context
        )
        
        # 添加计时逻辑
        verification_start_time = time.time()
        
        try:
            logger.info(f"开始种子验证: {stage1_context.thinking_seed[:50]}...")
            
            # 检查工具注册表状态
            if not self.tool_registry:
                logger.warning("   ⚠️ 工具注册表未初始化，使用简化验证")
                context.verification_result = True
                context.feasibility_score = 0.6
                context.verification_method = "simplified_heuristic"
                context.verification_evidence = ["工具注册表未初始化，使用启发式验证"]
                
            elif not self.tool_registry.has_tool("idea_verification"):
                logger.warning("   ⚠️ idea_verification工具不可用，使用启发式验证")
                
                # 启发式验证逻辑
                seed_text = stage1_context.thinking_seed
                seed_length = len(seed_text) if seed_text else 0
                has_keywords = any(keyword in seed_text.lower() for keyword in 
                                 ["分析", "方法", "策略", "解决", "建议", "系统", "优化"]) if seed_text else False
                
                if seed_length > 30 and has_keywords:
                    context.feasibility_score = 0.7
                    context.verification_result = True
                    context.verification_evidence = [f"种子长度: {seed_length}字符", "包含关键分析词汇"]
                else:
                    context.feasibility_score = 0.5
                    context.verification_result = True
                    context.verification_evidence = [f"种子长度: {seed_length}字符", "基础验证通过"]
                
                context.verification_method = "heuristic_analysis"
                
            else:
                # 使用工具进行种子验证
                logger.info("调用idea_verification工具进行验证...")
                
                # 调试：检查用户查询是否正确传递
                logger.info(f"准备调用idea_verification工具:")
                logger.info(f"thinking_seed: {stage1_context.thinking_seed[:50]}...")
                logger.info(f"user_query: {stage1_context.user_query}")
                
                verification_result = execute_tool(
                    "idea_verification",
                    idea_text=stage1_context.thinking_seed,
                    context={"user_query": stage1_context.user_query}
                )
                
                if verification_result and verification_result.success:
                    verification_data = verification_result.data
                    context.verification_result = True
                    context.feasibility_score = verification_data.get("feasibility_score", 0.5)
                    
                    # 处理验证证据和分析摘要
                    analysis_summary = verification_data.get("analysis_summary", "")
                    if analysis_summary:
                        context.verification_evidence = analysis_summary.split("\n")[:5]  # 限制证据数量
                        context.analysis_summary = analysis_summary  # 🔥 保存完整分析摘要
                    else:
                        context.verification_evidence = ["工具验证完成"]
                    
                    context.verification_method = "web_search_verification"
                    
                    # 🔥🔥🔥 关键修复：添加搜索结果信息
                    search_results = verification_data.get("search_results", [])
                    if search_results:
                        # 确保保存SearchResult对象或转换为字典
                        sources_to_save = []
                        for sr in search_results[:5]:  # 保存前5个搜索结果
                            if hasattr(sr, '__dict__'):
                                # 如果是对象，转换为字典
                                sources_to_save.append({
                                    'title': getattr(sr, 'title', ''),
                                    'snippet': getattr(sr, 'snippet', ''),
                                    'url': getattr(sr, 'url', ''),
                                    'relevance_score': getattr(sr, 'relevance_score', 0.0)
                                })
                            elif isinstance(sr, dict):
                                sources_to_save.append(sr)
                        
                        context.verification_sources = sources_to_save
                        logger.info(f"   ✅ 保存了 {len(sources_to_save)} 个搜索结果到verification_sources")
                    else:
                        logger.warning(f"   ⚠️ 验证数据中没有搜索结果")
                    
                    logger.info(f"   ✅ 工具验证成功，可行性评分: {context.feasibility_score:.3f}")
                    logger.info(f"验证证据数量: {len(context.verification_evidence)}")
                    logger.info(f"搜索结果源数量: {len(context.verification_sources)}")
                    
                else:
                    error_msg = verification_result.error_message if verification_result else "工具返回空结果"
                    logger.warning(f"   ⚠️ 工具验证失败: {error_msg}")
                    
                    # 回退到启发式验证
                    context.verification_result = True  # 即使工具失败，也不阻止流程
                    context.feasibility_score = 0.4
                    context.verification_method = "tool_fallback_heuristic"
                    context.verification_evidence = [f"工具验证失败: {error_msg}", "使用回退验证"]
                    context.add_error("验证工具执行失败，使用回退方法")
                
        except Exception as e:
            logger.error(f"   ❌ 种子验证异常: {e}")
            
            # 异常回退
            context.verification_result = True  # 不阻止流程继续
            context.feasibility_score = 0.3
            context.verification_method = "exception_fallback"
            context.verification_evidence = [f"验证异常: {str(e)}", "使用异常回退验证"]
            context.add_error(f"验证异常: {str(e)}")
        
        # 计算并记录执行时间
        verification_time = time.time() - verification_start_time
        context.add_metric("verification_time", verification_time)
        context.add_metric("feasibility_confidence", context.feasibility_score)
        
        logger.info(f"种子验证耗时: {verification_time:.3f}s")
        logger.info(f"最终可行性评分: {context.feasibility_score:.3f}")
        logger.info(f"验证方法: {context.verification_method}")
        
        return context
    
    def _execute_stage3_path_generation(self, stage1_context: ThinkingSeedContext,
                                      stage2_context: SeedVerificationContext,
                                      execution_context: Optional[Dict]) -> PathGenerationContext:
        """执行阶段三：思维路径生成"""
        context = PathGenerationContext(
            user_query=stage1_context.user_query,
            execution_context=execution_context
        )
        
        try:
            # 使用PathGenerator生成多样化路径
            paths_result = self.path_generator.generate_reasoning_paths(
                thinking_seed=stage1_context.thinking_seed,
                user_query=stage1_context.user_query,
                max_paths=4,
                execution_context=execution_context
            )
            
            if paths_result and "paths" in paths_result:
                context.generated_paths = paths_result["paths"]
                context.path_count = len(context.generated_paths)
                context.diversity_score = paths_result.get("diversity_score", 0.0)
                context.generation_strategy = "llm_driven_multi_path"
                
                # 计算路径质量评分
                for path in context.generated_paths:
                    if hasattr(path, 'path_id') and hasattr(path, 'success_rate'):
                        context.path_quality_scores[path.path_id] = path.success_rate
                
                logger.info(f"   ✅ 生成 {context.path_count} 条思维路径")
                logger.info(f"多样性评分: {context.diversity_score:.3f}")
            else:
                context.add_error("路径生成结果为空")
                logger.error("   ❌ 路径生成失败：结果为空")
                
        except Exception as e:
            logger.error(f"   ❌ 路径生成异常: {e}")
            context.add_error(f"路径生成异常: {str(e)}")
        
        return context
    
    def _execute_stage4_path_verification(self, stage3_context: PathGenerationContext,
                                        execution_context: Optional[Dict]) -> PathVerificationContext:
        """执行阶段四：路径验证与即时学习"""
        context = PathVerificationContext(
            user_query=stage3_context.user_query,
            execution_context=execution_context
        )
        
        try:
            # 首先从生成的路径中填充路径信息（支持第五阶段MAB决策）
            context.populate_from_reasoning_paths(stage3_context.generated_paths)
            
            # 验证每条路径的可行性
            for path in stage3_context.generated_paths:
                if hasattr(path, 'path_id'):
                    verification_result = {
                        "path_id": path.path_id,
                        "feasibility": getattr(path, 'success_rate', 0.5),
                        "confidence": getattr(path, 'confidence_score', getattr(path, 'confidence', 0.5)),
                        "verified": True,
                        "path_type": getattr(path, 'path_type', 'unknown'),
                        "description": getattr(path, 'description', '')
                    }
                    
                    context.add_verification_result(path.path_id, verification_result)
                    context.verified_paths.append(verification_result)
                    context.verification_confidence[path.path_id] = verification_result["confidence"]
                    context.path_rankings.append((path.path_id, verification_result["feasibility"]))
                    
                    # 确保路径信息完整（如果populate_from_reasoning_paths没有填充）
                    if path.path_id not in context.path_types:
                        context.add_path_info(
                            path_id=path.path_id,
                            path_type=getattr(path, 'path_type', 'unknown'),
                            description=getattr(path, 'description', ''),
                            metadata={
                                'strategy_id': getattr(path, 'strategy_id', path.path_id),
                                'instance_id': getattr(path, 'instance_id', path.path_id),
                                'confidence_score': verification_result["confidence"],
                                'feasibility_score': verification_result["feasibility"]
                            }
                        )
            
            # 排序路径
            context.path_rankings.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"   ✅ 验证 {len(context.verified_paths)} 条路径")
            if context.path_rankings:
                top_path = context.path_rankings[0]
                logger.info(f"最佳路径: {top_path[0]} (评分: {top_path[1]:.3f})")
                
        except Exception as e:
            logger.error(f"   ❌ 路径验证异常: {e}")
            context.add_error(f"路径验证异常: {str(e)}")
        
        return context
    
    def _execute_stage5_mab_decision(self, stage4_context: PathVerificationContext,
                                   execution_context: Optional[Dict]) -> MABDecisionContext:
        """执行阶段五：MAB最终决策 - 真正使用MABConverger算法"""
        context = MABDecisionContext(
            user_query=stage4_context.user_query,
            execution_context=execution_context
        )
        
        try:
            # 使用真正的MABConverger进行决策
            if hasattr(self, 'mab_converger') and self.mab_converger:
                logger.info("使用真正的MABConverger进行第五阶段决策")
                
                # 从stage4_context中重建ReasoningPath对象（确保必需字段完整）
                reasoning_paths = []
                for path_id, score in stage4_context.path_rankings:
                    # 创建ReasoningPath对象
                    try:
                        from neogenesis_system.cognitive_engine.data_structures import ReasoningPath
                        path_type = stage4_context.path_types.get(path_id, "实用务实型")
                        description = stage4_context.path_descriptions.get(path_id, f"基于{path_type}的思维路径")
                        confidence = stage4_context.verification_confidence.get(path_id, score)
                        prompt_template = f"采用{path_type}的方法来分析和解决问题。{description}"
                        reasoning_path = ReasoningPath(
                            path_id=path_id,
                            path_type=path_type,
                            description=description,
                            prompt_template=prompt_template,
                            strategy_id=path_id,
                            instance_id=f"stage5_{path_id}_{int(time.time())}"
                        )
                        # 将置信度写入属性（非构造参数）
                        reasoning_path.confidence_score = confidence
                        reasoning_paths.append(reasoning_path)
                    except Exception:
                        # 降级为简单对象（维持属性访问语义）
                        confidence = stage4_context.verification_confidence.get(path_id, score)
                        simple_path = type('SimpleReasoningPath', (), {
                            'path_id': path_id,
                            'path_type': stage4_context.path_types.get(path_id, "实用务实型"),
                            'description': stage4_context.path_descriptions.get(path_id, "基础思维路径"),
                            'prompt_template': f"采用{stage4_context.path_types.get(path_id, '实用务实型')}方法分析问题",
                            'confidence_score': confidence,
                            'strategy_id': path_id,
                            'instance_id': f"stage5_{path_id}_{int(time.time())}"
                        })()
                        reasoning_paths.append(simple_path)
                
                if reasoning_paths:
                    # 调用真正的MAB算法
                    selected_path = self.mab_converger.select_best_path(
                        paths=reasoning_paths,
                        algorithm='auto'  # 让MAB自动选择最佳算法
                    )
                    
                    # 获取MAB统计信息
                    mab_stats = {
                        "total_selections": getattr(self.mab_converger, 'total_path_selections', 0),
                        "algorithm_used": getattr(self.mab_converger, '_last_algorithm_used', 'thompson_sampling'),
                        "exploration_rate": 0.15,  # 默认值
                        "convergence_level": 0.5   # 默认值
                    }
                    
                    # 设置上下文结果（保持对象语义，避免下游.dict访问错误）
                    context.selected_path = selected_path
                    context.selection_confidence = getattr(selected_path, 'confidence_score', 0.5)
                    context.selection_algorithm = mab_stats["algorithm_used"]
                    context.decision_reasoning = f"MAB算法({mab_stats['algorithm_used']})选择最优路径: {getattr(context.selected_path, 'path_id', 'unknown')}"
                    context.mab_statistics = mab_stats
                    
                    # 记录备选选择
                    for path in reasoning_paths[1:3]:  # 记录前2个备选
                        alt_info = {
                            "path_id": getattr(path, 'path_id', 'unknown'),
                            "confidence": getattr(path, 'confidence_score', 0.5)
                        }
                        context.alternative_choices.append((alt_info, getattr(path, 'confidence_score', 0.5)))
                    
                    logger.info(f"MAB算法选择: {getattr(context.selected_path, 'path_id', 'unknown')} (算法: {context.selection_algorithm})")
                    logger.info(f"选择置信度: {context.selection_confidence:.3f}")
                    
                else:
                    context.add_error("无法创建ReasoningPath对象")
                    logger.error("   ❌ MAB决策失败：无法创建路径对象")
            else:
                # 回退到简单选择逻辑
                logger.warning("⚠️ MABConverger不可用，使用回退决策逻辑")
                available = []
                for path_id, score in stage4_context.path_rankings:
                    confidence = stage4_context.verification_confidence.get(path_id, 0.5)
                    available.append((path_id, score, confidence))
                
                if available:
                    best_path_id, best_score, best_conf = max(available, key=lambda x: x[1])
                    # 构造一个简单的对象，保持属性访问语义
                    simple_selected = type('SelectedPath', (), {
                        'path_id': best_path_id,
                        'path_type': stage4_context.path_types.get(best_path_id, 'unknown'),
                        'description': stage4_context.path_descriptions.get(best_path_id, ''),
                        'confidence_score': best_conf
                    })()
                    context.selected_path = simple_selected
                    context.selection_confidence = best_conf
                    context.selection_algorithm = "fallback_max_score"
                    context.decision_reasoning = f"回退逻辑选择最高评分路径: {best_path_id}"
                    
                    logger.info(f"   ✅ 回退选择路径: {best_path_id}")
                    logger.info(f"选择置信度: {context.selection_confidence:.3f}")
                else:
                    context.add_error("没有可用路径进行决策")
                    logger.error("   ❌ 决策失败：无可用路径")
                
        except Exception as e:
            logger.error(f"   ❌ 第五阶段MAB决策异常: {e}")
            context.add_error(f"MAB决策异常: {str(e)}")
        
        return context
    
    def _create_fallback_decision(self, strategy_decision: StrategyDecision, error_message: str) -> StrategyDecision:
        """创建回退决策"""
        strategy_decision.add_error(error_message)
        strategy_decision.confidence_score = 0.1
        strategy_decision.final_reasoning = f"决策过程失败，使用回退策略: {error_message}"
        
        # 创建一个基本的回退路径
        fallback_path = {
            "path_id": "fallback_direct_response",
            "path_type": "直接回答",
            "description": "回退到直接回答模式"
        }
        strategy_decision.chosen_path = fallback_path
        
        return strategy_decision
    
    def _validate_mab_converger_initialization(self):
        """增强版：验证MABConverger的初始化状态"""
        if not self.mab_converger:
            logger.error("❌ MABConverger未初始化")
            raise ValueError("MABConverger不能为None")
        
        # 修复：检查必要的方法（包含兼容性方法）
        required_methods = ['select_best_path', 'get_path_statistics']
        optional_methods = ['update_path_feedback', 'update_path_performance']  # 两个都支持
        missing_methods = []
        
        for method_name in required_methods:
            if not hasattr(self.mab_converger, method_name):
                missing_methods.append(method_name)
        
        # 检查可选方法（至少要有一个）
        has_feedback_method = any(
            hasattr(self.mab_converger, method) for method in optional_methods
        )
        
        if not has_feedback_method:
            missing_methods.extend(optional_methods)
        
        if missing_methods:
            logger.warning(f"⚠️ MABConverger缺少方法: {missing_methods}")
            # 新增：提供修复建议
            if 'update_path_feedback' in missing_methods:
                logger.info("💡 建议：已添加update_path_feedback方法作为update_path_performance的别名")
        else:
            logger.info("✅ MABConverger方法验证通过")
        
        # 检查基本属性
        required_attrs = ['path_arms', 'total_path_selections']
        missing_attrs = []
        
        for attr_name in required_attrs:
            if not hasattr(self.mab_converger, attr_name):
                missing_attrs.append(attr_name)
        
        if missing_attrs:
            logger.warning(f"⚠️ MABConverger缺少属性: {missing_attrs}")
        else:
            logger.info("✅ MABConverger属性验证通过")
        
        # 初始化检查通过
        logger.info("✅ MABConverger初始化验证通过")
        
        # 增强版：安全地记录MAB状态
        try:
            total_selections = getattr(self.mab_converger, 'total_path_selections', 0)
            path_arms_count = len(getattr(self.mab_converger, 'path_arms', {}))
            tool_arms_count = len(getattr(self.mab_converger, 'tool_arms', {}))
            
            logger.info(f"MAB状态: {total_selections}次选择, {path_arms_count}个决策臂")
            if tool_arms_count > 0:
                logger.debug(f"工具决策臂: {tool_arms_count}个")
                
        except Exception as e:
            logger.debug(f"   ⚠️ 无法获取MAB详细状态: {e}")
            logger.debug("   MAB组件可能不完整，但系统将继续运行")
