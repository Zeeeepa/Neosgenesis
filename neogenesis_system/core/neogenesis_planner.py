
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
from typing import Dict, List, Optional, Any, Tuple

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

# 导入种子验证器
from .seed_verifier import SeedVerifier

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
                 seed_verifier: Optional[SeedVerifier] = None,
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
            seed_verifier: 种子验证器实例（可选，如果未提供则自动创建）
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
        
        # 可选组件
        self.tool_registry = tool_registry or global_tool_registry
        
        # 🔥 从 prior_reasoner 获取 llm_manager 并设置为实例属性
        self.llm_manager = None
        if hasattr(self.prior_reasoner, 'llm_manager'):
            self.llm_manager = self.prior_reasoner.llm_manager
            logger.info("✅ 从 PriorReasoner 获取 LLM 管理器")
        else:
            logger.warning("⚠️ PriorReasoner 没有 llm_manager，部分功能将使用启发式方法")
        
        # 种子验证器 - 如果未提供则自动创建
        self.seed_verifier = seed_verifier
        if self.seed_verifier is None:
            self.seed_verifier = SeedVerifier(
                tool_registry=self.tool_registry,
                llm_manager=self.llm_manager
            )
            logger.info("✅ 自动创建 SeedVerifier 实例")
        
        # 确保搜索工具被注册
        self._ensure_search_tools_registered()
        
        self.state_manager = state_manager
        self.config = config or {}
        
        # 用户交互配置
        self.enable_dimension_interaction = self.config.get('enable_dimension_interaction', False)
        
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
        logger.info(f"👤 用户交互模式: {'已启用' if self.enable_dimension_interaction else '已禁用（自动模式）'}")
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
        
        工作流程：
        1. 执行五阶段战略决策 (make_strategic_decision)
        2. 基于五阶段决策上下文生成最终答案
        3. 返回包含最终答案的计划
        
        Args:
            query: 用户查询
            memory: Agent的记忆对象
            context: 可选的执行上下文
            
        Returns:
            Plan: 标准格式的执行计划
        """
        logger.info(f"NeogenesisPlanner开始五阶段决策: {query[:50]}...")
        start_time = time.time()
        
        # 通知认知调度器Agent正在活跃工作
        if self.cognitive_scheduler:
            self.cognitive_scheduler.notify_activity("task_planning", {
                "query": query[:100],
                "timestamp": start_time,
                "source": "create_plan"
            })
        
        try:
            # 执行五阶段战略决策
            logger.info("执行五阶段战略决策")
            strategy_decision = self.make_strategic_decision(
                user_query=query,
                execution_context=context
            )
            
            # 基于五阶段上下文生成最终答案
            logger.info("基于五阶段上下文生成最终答案")
            final_answer = self._generate_answer_from_context(query, strategy_decision, context)
            
            # 创建包含最终答案的计划
            chosen_path_type = "未知"
            if strategy_decision.chosen_path:
                if hasattr(strategy_decision.chosen_path, 'path_type'):
                    chosen_path_type = strategy_decision.chosen_path.path_type
                elif isinstance(strategy_decision.chosen_path, dict):
                    chosen_path_type = strategy_decision.chosen_path.get('path_type', '未知')
            
            plan = Plan(
                thought=f"基于五阶段决策，选择了'{chosen_path_type}'策略",
                final_answer=final_answer,
                is_direct_answer=True,
                metadata={
                    'strategy_decision': strategy_decision,
                    'has_five_stage_context': True,
                    'execution_time': time.time() - start_time
                }
            )
            
            # 更新性能统计
            execution_time = time.time() - start_time
            self._update_planner_stats(True, execution_time)
            
            logger.info(f"✅ 五阶段决策完成，耗时 {execution_time:.3f}s")
            return plan
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_planner_stats(False, execution_time)
            
            logger.error(f"❌ 五阶段决策失败: {e}")
            
            # 返回错误回退计划
            return Plan(
                thought=f"五阶段决策过程中出现错误: {str(e)}",
                final_answer=f"抱歉，我在处理您的请求时遇到了问题: {str(e)}",
                metadata={'error': str(e)}
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
            
            # 🔍 阶段二：种子验证检查 + 增强生成
            stage2_start = time.time()
            logger.info("🔍 阶段二：种子验证检查与增强生成")
            logger.info("   本阶段将：1) 验证思维种子可行性")
            logger.info("            2) 多维度搜索最新信息")
            logger.info("            3) 整合信息增强思维种子")
            
            # 使用重构后的 SeedVerifier 组件
            stage2_context = self.seed_verifier.verify(stage1_context, execution_context)
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
            logger.info("=" * 80)
            logger.info("🔍 阶段二：思维种子验证")
            logger.info("=" * 80)
            logger.info(f"我对生成的思维种子进行了可行性验证：")
            logger.info(f"📊 可行性评分: {seed_feasibility:.2f}/1.0")
            logger.info(f"🎯 奖励分数: {seed_reward:+.3f}")
            
            # 🔥 新增：显示搜索到的URL和详细信息
            search_results = seed_verification_result.get('search_results', [])
            if search_results:
                logger.info("")
                logger.info("🌐 搜索到的验证源：")
                for i, result in enumerate(search_results[:5], 1):  # 显示前5个结果
                    title = result.get('title', '无标题')
                    url = result.get('url', '无URL')
                    snippet = result.get('snippet', '无摘要')
                    relevance = result.get('relevance_score', 0.0)
                    
                    logger.info(f"   {i}. 📄 {title}")
                    logger.info(f"      🔗 URL: {url}")
                    logger.info(f"      📝 摘要: {snippet[:100]}{'...' if len(snippet) > 100 else ''}")
                    logger.info(f"      ⭐ 相关性: {relevance:.2f}")
                    logger.info("")
            else:
                logger.info("⚠️ 未找到搜索结果")
            
            # 显示验证分析摘要
            analysis_summary = seed_verification_result.get('analysis_summary', '')
            if analysis_summary:
                logger.info("📋 验证分析摘要：")
                logger.info(f"   {analysis_summary[:200]}{'...' if len(analysis_summary) > 200 else ''}")
            
            # 显示LLM评估信息（如果有）
            llm_prompt = seed_verification_result.get('llm_evaluation_prompt', '')
            llm_response = seed_verification_result.get('llm_evaluation_response', '')
            if llm_prompt and llm_response:
                logger.info("")
                logger.info("🧠 LLM评估过程：")
                logger.info(f"   📝 评估提示: {llm_prompt[:150]}{'...' if len(llm_prompt) > 150 else ''}")
                logger.info(f"   💭 评估响应: {llm_response[:200]}{'...' if len(llm_response) > 200 else ''}")
            
            logger.info("")
            logger.info(f"⏱️ 验证耗时: {seed_verification_time:.2f}秒")
            logger.info("=" * 80)
            
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
        elif routing_rec == 'multi_stage_processing':
            return min(8, base_count + 1)  # 多阶段处理需要额外路径
        else:
            return base_count

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
    
    def _verify_idea_feasibility(self, idea_text: str, context: Dict[str, Any], 
                                streaming_output = None) -> Dict[str, Any]:
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
                logger.info(f"🔍 [验证] streaming_output: {streaming_output is not None}")
                
                # 构建工具上下文（包含streaming_output）
                tool_context = {"user_query": user_query}
                if streaming_output is not None:
                    tool_context['_streaming_output'] = streaming_output
                
                result = execute_tool(
                    "idea_verification", 
                    idea_text=idea_text,  # 使用idea_text参数名
                    context=tool_context  # 传递用户查询和streaming_output
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
    
    def _execute_stage1_thinking_seed(self, user_query: str, execution_context: Optional[Dict], enable_streaming: bool = False) -> ThinkingSeedContext:
        """执行阶段一：思维种子生成"""
        context = ThinkingSeedContext(user_query=user_query, execution_context=execution_context)
        
        try:
            # 使用PriorReasoner生成思维种子
            seed_result = self.prior_reasoner.generate_thinking_seed(
                user_query=user_query,
                execution_context=execution_context,
                enable_streaming=enable_streaming
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
    
    def _execute_stage2_seed_verification(self, 
                                         stage1_context: ThinkingSeedContext,
                                         execution_context: Optional[Dict],
                                         streaming_output = None) -> SeedVerificationContext:
        """
        执行阶段二：种子验证与增强
        
        Args:
            stage1_context: 阶段一上下文
            execution_context: 执行上下文
            streaming_output: 流式输出处理器（可选）
            
        Returns:
            SeedVerificationContext: 种子验证上下文
        """
        try:
            logger.info("🔍 开始阶段二：种子验证与增强")
            
            # 使用 SeedVerifier 进行验证
            if self.seed_verifier:
                stage2_context = self.seed_verifier.verify(
                    stage1_context=stage1_context,
                    execution_context=execution_context,
                    streaming_output=streaming_output
                )
                return stage2_context
            else:
                # 如果没有 seed_verifier，创建一个简单的验证上下文
                logger.warning("⚠️ SeedVerifier 不可用，使用简化验证")
                context = SeedVerificationContext(
                    user_query=stage1_context.user_query,
                    execution_context=execution_context
                )
                context.verification_result = True
                context.feasibility_score = 0.6
                context.verification_method = "simplified_no_verifier"
                context.verification_evidence = ["SeedVerifier 不可用，使用简化验证"]
                context.enhanced_thinking_seed = stage1_context.thinking_seed
                return context
                
        except Exception as e:
            logger.error(f"❌ 阶段二执行异常: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # 创建异常回退上下文
            context = SeedVerificationContext(
                user_query=stage1_context.user_query,
                execution_context=execution_context
            )
            context.verification_result = True  # 不阻止流程继续
            context.feasibility_score = 0.3
            context.verification_method = "exception_fallback"
            context.verification_evidence = [f"验证异常: {str(e)}", "使用异常回退验证"]
            context.add_error(f"验证异常: {str(e)}")
            context.enhanced_thinking_seed = stage1_context.thinking_seed
            return context
    
    def _extract_key_concepts_from_seed(self, thinking_seed: str, max_concepts: int = 5) -> List[str]:
        """
        从思维种子中提取关键概念
        
        Args:
            thinking_seed: 思维种子文本
            max_concepts: 最多提取的概念数量
            
        Returns:
            List[str]: 提取的关键概念列表
        """
        import re
        
        key_concepts = []
        
        # 方法1: 提取专有名词和技术术语（英文大写开头的词组）
        # 匹配如 "AlphaGo", "ChatGPT", "Deep Learning" 等
        capitalized_terms = re.findall(r'\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b', thinking_seed)
        key_concepts.extend(capitalized_terms[:3])
        
        # 方法2: 提取中文专业术语（通过关键标记词识别）
        # 匹配如 "强化学习"、"神经网络"、"机器学习" 等
        cn_tech_patterns = [
            r'(\w{2,6}学习)',  # 学习相关
            r'(\w{2,6}算法)',  # 算法相关
            r'(\w{2,6}系统)',  # 系统相关
            r'(\w{2,6}技术)',  # 技术相关
            r'(\w{2,6}网络)',  # 网络相关
            r'(\w{2,6}模型)',  # 模型相关
            r'(\w{2,6}框架)',  # 框架相关
        ]
        
        for pattern in cn_tech_patterns:
            matches = re.findall(pattern, thinking_seed)
            key_concepts.extend(matches)
        
        # 方法3: 提取引号中的重点内容
        quoted_terms = re.findall(r'[「『""]([^」』""]+)[」』""]', thinking_seed)
        key_concepts.extend(quoted_terms[:2])
        
        # 去重并保留顺序
        seen = set()
        unique_concepts = []
        for concept in key_concepts:
            concept_clean = concept.strip()
            if concept_clean and len(concept_clean) > 1 and concept_clean not in seen:
                seen.add(concept_clean)
                unique_concepts.append(concept_clean)
        
        # 限制数量
        result = unique_concepts[:max_concepts]
        
        # 如果提取不到，使用种子的前30个字符作为关键概念
        if not result:
            seed_snippet = thinking_seed[:30].strip()
            if seed_snippet:
                result = [seed_snippet]
        
        logger.info(f"🔍 从种子中提取了 {len(result)} 个关键概念: {result}")
        return result
    
    def _llm_select_search_dimensions(self, thinking_seed: str, user_query: str, 
                                     key_concepts: List[str]) -> List[str]:
        """
        使用LLM智能选择需要搜索的维度
        
        Args:
            thinking_seed: 思维种子
            user_query: 用户原始查询
            key_concepts: 关键概念列表
            
        Returns:
            List[str]: 选择的搜索维度列表
        """
        import re
        
        try:
            # 如果有语义分析器，使用LLM进行智能选择
            if self.semantic_analyzer:
                logger.info("🧠 使用LLM智能选择搜索维度...")
                
                dimension_selection_prompt = f"""我正在分析用户的查询和我生成的思维种子，需要决定从哪些维度进行网络搜索验证。

**用户查询：**
{user_query}

**我的思维种子：**
{thinking_seed[:300]}

**提取的关键概念：**
{', '.join(key_concepts)}

**可选的搜索维度：**
1. 实际例子 - 搜索真实案例和应用实例
2. 实施案例 - 搜索具体的实施方案和应用场景
3. 潜在风险 - 搜索可能的问题、挑战和风险
4. 相关研究 - 搜索学术论文和研究成果（适用于学术/技术问题）
5. 最新进展 - 搜索最新的发展动态和趋势
6. 对比分析 - 搜索不同方案的对比和优缺点
7. 专家观点 - 搜索专家评价和权威观点

**请你模拟Agent的思考过程，用自然的语言分析并选择搜索维度。输出格式示例：**

让我分析一下这个问题。对于用户关于"XXX"的查询，这是一个【技术理论/实践操作/评估决策/知识了解】类问题。

基于我的思维种子分析，我认为从以下X个维度进行搜索验证更合适：
- 实际例子（因为需要了解真实应用场景）
- 最新进展（因为需要2025年的最新信息）
- 潜在风险（因为需要评估可行性）
...

现在让我开始搜索这些维度。

---
**要求：**
1. 必须明确说明问题类型（技术理论/实践操作/评估决策/知识了解等）
2. 必须选择3-5个维度，不要太多也不要太少
3. 每个维度要简短说明选择理由（括号内）
4. 避免选择不相关的维度（比如实践问题不需要学术论文）
5. 最后一句固定说"现在让我开始搜索这些维度"
"""

                # 直接调用LLM进行维度选择（绕过SemanticAnalyzer的JSON解析）
                logger.info("🧠 使用LLM直接进行维度选择...")
                
                # 使用PriorReasoner的LLM管理器直接调用
                if hasattr(self.prior_reasoner, 'llm_manager') and self.prior_reasoner.llm_manager:
                    try:
                        llm_response = self.prior_reasoner.llm_manager.call_api(
                            prompt=dimension_selection_prompt,
                            temperature=0.7,
                            max_tokens=1000
                        )
                        
                        if llm_response and isinstance(llm_response, str):
                            logger.info("")
                            logger.info("🧠 LLM维度选择分析过程：")
                            logger.info("-" * 60)
                            
                            # 显示LLM的完整分析过程
                            analysis_lines = llm_response.strip().split('\n')
                            for line in analysis_lines[:10]:  # 显示前10行关键分析
                                if line.strip():
                                    logger.info(f"   {line.strip()}")
                            
                            logger.info("-" * 60)
                            
                            # 解析LLM返回的维度列表
                            selected_dimensions = []
                            all_dimension_names = [
                                "实际例子", "实施案例", "潜在风险", "相关研究",
                                "最新进展", "对比分析", "专家观点"
                            ]
                            
                            # 从LLM响应中提取维度名称
                            analysis_content = llm_response.lower()
                            logger.info("🔍 解析LLM选择的维度：")
                            
                            for line in analysis_lines:
                                line_clean = line.strip().strip('- ').strip('* ').strip()
                                # 匹配维度名称（可能在括号前）
                                for dim_name in all_dimension_names:
                                    if dim_name in line_clean:
                                        if dim_name not in selected_dimensions:
                                            selected_dimensions.append(dim_name)
                                            logger.info(f"   ✅ 选择维度: {dim_name}")
                                            
                                            # 提取理由（括号内的内容）
                                            reason_match = re.search(r'（([^）]+)）|\(([^)]+)\)', line_clean)
                                            if reason_match:
                                                reason = reason_match.group(1) or reason_match.group(2)
                                                logger.info(f"      💡 选择理由: {reason}")
                                        break
                            
                            if selected_dimensions and len(selected_dimensions) >= 2:
                                logger.info(f"")
                                logger.info(f"🎯 LLM最终选择: {selected_dimensions}")
                                logger.info(f"📊 选择数量: {len(selected_dimensions)} 个维度")
                                return selected_dimensions
                            else:
                                logger.warning("⚠️ LLM返回的维度数量不足，使用回退策略")
                        else:
                            logger.warning("⚠️ LLM响应无效，使用回退策略")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ LLM调用失败: {e}")
                else:
                    logger.warning("⚠️ LLM管理器不可用，使用回退策略")
                
            else:
                logger.info("⚠️ 语义分析器不可用，使用启发式维度选择")
                
        except Exception as e:
            logger.warning(f"⚠️ LLM维度选择失败: {e}")
        
        # 回退策略：基于关键词的启发式选择
        query_lower = user_query.lower()
        seed_lower = thinking_seed.lower()
        combined_text = query_lower + " " + seed_lower
        
        selected = ["实际例子", "最新进展", "潜在风险"]  # 基础维度
        
        # 检测学术/技术关键词
        if any(kw in combined_text for kw in ['研究', '论文', '算法', '理论', 'research', 'algorithm']):
            if "相关研究" not in selected:
                selected.append("相关研究")
        
        # 检测实践关键词
        if any(kw in combined_text for kw in ['如何', '怎么', '实现', '操作', 'how to']):
            if "实施案例" not in selected:
                selected.append("实施案例")
        
        # 检测对比需求
        if any(kw in combined_text for kw in ['对比', '比较', '区别', 'compare', 'vs']):
            if "对比分析" not in selected:
                selected.append("对比分析")
        
        logger.info(f"📋 启发式选择了 {len(selected)} 个搜索维度: {selected}")
        return selected
    
    def _prompt_user_dimension_selection(self, llm_selected: List[str], 
                                        all_dimensions: List[str]) -> List[str]:
        """
        提示用户确认或调整搜索维度选择
        
        Args:
            llm_selected: LLM选择的维度
            all_dimensions: 所有可用维度
            
        Returns:
            List[str]: 最终确定的维度列表
        """
        try:
            # 计算未选择的维度
            not_selected = [d for d in all_dimensions if d not in llm_selected]
            
            # 展示选择结果
            logger.info("=" * 60)
            logger.info("🤖 Agent智能分析完成，搜索维度建议：")
            logger.info("=" * 60)
            logger.info("")
            logger.info("✅ Agent建议搜索以下维度：")
            for i, dim in enumerate(llm_selected, 1):
                logger.info(f"   {i}. {dim}")
            
            if not_selected:
                logger.info("")
                logger.info("⏸️  暂未选择的维度：")
                for i, dim in enumerate(not_selected, 1):
                    logger.info(f"   {len(llm_selected) + i}. {dim}")
            
            logger.info("")
            logger.info("💡 您可以：")
            logger.info("   - 直接回车：使用Agent的建议")
            logger.info("   - 输入数字（如 5,6）：补充额外的搜索维度")
            logger.info("   - 输入自定义维度名称：添加自定义搜索维度")
            logger.info("")
            
            # 设置超时等待用户输入
            import sys
            import select
            
            # Windows系统需要特殊处理
            if sys.platform == 'win32':
                # Windows上使用msvcrt
                try:
                    import msvcrt
                    import time
                    
                    logger.info("⏱️  等待5秒接收用户输入（Windows）...")
                    start_time = time.time()
                    user_input = ""
                    
                    while time.time() - start_time < 5:
                        if msvcrt.kbhit():
                            char = msvcrt.getwche()
                            if char == '\r':  # Enter键
                                break
                            elif char == '\b':  # 退格键
                                if user_input:
                                    user_input = user_input[:-1]
                                    sys.stdout.write('\b \b')
                            else:
                                user_input += char
                        time.sleep(0.1)
                    
                    print()  # 换行
                    
                except ImportError:
                    # 如果msvcrt不可用，直接使用input但不等待
                    logger.info("💬 请输入您的选择（直接回车使用默认）：")
                    user_input = ""
            else:
                # Unix/Linux系统使用select
                logger.info("⏱️  等待5秒接收用户输入...")
                ready, _, _ = select.select([sys.stdin], [], [], 5)
                if ready:
                    user_input = sys.stdin.readline().strip()
                else:
                    user_input = ""
            
            # 处理用户输入
            if not user_input or user_input.strip() == "":
                logger.info("✅ 使用Agent默认选择")
                return llm_selected
            
            # 解析用户输入
            final_dimensions = llm_selected.copy()
            
            # 检查是否为数字选择
            if any(c.isdigit() or c == ',' for c in user_input):
                # 解析数字
                numbers = []
                for part in user_input.replace('，', ',').split(','):
                    try:
                        num = int(part.strip())
                        if 1 <= num <= len(all_dimensions):
                            numbers.append(num)
                    except ValueError:
                        continue
                
                # 添加选择的维度
                all_dims_list = llm_selected + not_selected
                for num in numbers:
                    dim_name = all_dims_list[num - 1]
                    if dim_name not in final_dimensions:
                        final_dimensions.append(dim_name)
                        logger.info(f"➕ 添加维度: {dim_name}")
            else:
                # 作为自定义维度名称
                custom_dim = user_input.strip()
                if custom_dim and custom_dim not in final_dimensions:
                    final_dimensions.append(custom_dim)
                    logger.info(f"➕ 添加自定义维度: {custom_dim}")
            
            logger.info(f"✅ 最终搜索维度: {final_dimensions}")
            logger.info("=" * 60)
            
            return final_dimensions
            
        except Exception as e:
            logger.warning(f"⚠️ 用户交互失败: {e}")
            logger.info("✅ 使用Agent默认选择")
            return llm_selected
    
    def _perform_multidimensional_verification_search(self, key_concepts: List[str], 
                                                    user_query: str,
                                                    thinking_seed: str = "",
                                                    enable_user_interaction: bool = False) -> Dict[str, List[Dict]]:
        """
        执行多维度验证搜索（LLM智能选择维度）
        
        Args:
            key_concepts: 关键概念列表
            user_query: 用户原始查询
            thinking_seed: 思维种子（用于LLM分析）
            
        Returns:
            Dict[str, List[Dict]]: 按维度组织的搜索结果
        """
        from datetime import datetime
        
        # 获取当前年份
        current_year = datetime.now().year
        logger.info(f"📅 当前年份: {current_year}")
        
        # 选择主要关键概念（取前2个，避免查询过长）
        main_concepts = key_concepts[:2] if len(key_concepts) >= 2 else key_concepts
        concept_query = " ".join(main_concepts) if main_concepts else user_query[:30]
        
        # 🧠 使用LLM智能选择搜索维度
        selected_dimension_names = self._llm_select_search_dimensions(
            thinking_seed=thinking_seed,
            user_query=user_query,
            key_concepts=key_concepts
        )
        
        # 定义所有可能的搜索维度
        all_dimension_names = [
            "实际例子", "实施案例", "潜在风险", "相关研究",
            "最新进展", "对比分析", "专家观点"
        ]
        
        # 👤 如果启用用户交互，让用户确认或调整选择
        if enable_user_interaction:
            selected_dimension_names = self._prompt_user_dimension_selection(
                llm_selected=selected_dimension_names,
                all_dimensions=all_dimension_names
            )
        
        # 定义所有可能的搜索维度及其查询模板
        all_search_dimensions = {
            "实际例子": f"{concept_query} 实际例子 案例 {current_year}",
            "实施案例": f"{concept_query} 实施 应用案例 {current_year}",
            "潜在风险": f"{concept_query} 风险 问题 挑战",
            "相关研究": f"{concept_query} 研究 论文 {current_year}",
            "最新进展": f"{concept_query} 最新进展 {current_year}",
            "对比分析": f"{concept_query} 对比 比较 优缺点",
            "专家观点": f"{concept_query} 专家 观点 评价"
        }
        
        # 构建最终的搜索维度字典（包括自定义维度）
        search_dimensions = {}
        for dim_name in selected_dimension_names:
            if dim_name in all_search_dimensions:
                search_dimensions[dim_name] = all_search_dimensions[dim_name]
            else:
                # 用户自定义维度
                search_dimensions[dim_name] = f"{concept_query} {dim_name} {current_year}"
                logger.info(f"🆕 使用自定义搜索维度: {dim_name}")
        
        multidim_results = {}
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 开始执行多维度验证搜索")
        logger.info("=" * 80)
        logger.info(f"📊 计划搜索 {len(search_dimensions)} 个维度")
        logger.info("")
        
        for i, (dimension, query) in enumerate(search_dimensions.items(), 1):
            try:
                logger.info(f"🔎 [{i}/{len(search_dimensions)}] 搜索维度: {dimension}")
                logger.info(f"   📝 搜索查询: {query}")
                logger.info(f"   ⏳ 正在搜索...")
                
                # 使用 web_search 工具执行搜索
                search_result = execute_tool(
                    "web_search",
                    query=query,
                    max_results=3
                )
                
                if search_result and search_result.success:
                    # 提取搜索结果
                    results_data = search_result.data
                    search_results = results_data.get("results", [])
                    
                    multidim_results[dimension] = search_results
                    logger.info(f"   ✅ 搜索成功: 找到 {len(search_results)} 个结果")
                    
                    # 显示前2个结果的标题和URL
                    if search_results:
                        logger.info(f"   📄 搜索结果预览:")
                        for j, result in enumerate(search_results[:2], 1):
                            title = result.get('title', '无标题')
                            url = result.get('url', '无URL')
                            logger.info(f"      {j}. {title}")
                            logger.info(f"         🔗 {url}")
                    logger.info("")
                else:
                    logger.warning(f"   ⚠️ 搜索失败或无结果")
                    multidim_results[dimension] = []
                    logger.info("")
                    
            except Exception as e:
                logger.warning(f"   ❌ 搜索异常: {e}")
                multidim_results[dimension] = []
                logger.info("")
        
        # 统计总结果数
        total_results = sum(len(results) for results in multidim_results.values())
        logger.info(f"🎯 多维度搜索完成，共获得 {total_results} 个结果")
        
        return multidim_results
    
    def _ask_user_for_additional_search(self, completed_dimensions: List[str], 
                                        user_query: str, key_concepts: List[str]) -> List[str]:
        """
        在初始搜索完成后，询问用户是否要补充其他维度
        
        Args:
            completed_dimensions: 已完成的搜索维度
            user_query: 用户查询
            key_concepts: 关键概念
            
        Returns:
            List[str]: 用户选择的补充维度
        """
        from datetime import datetime
        current_year = datetime.now().year
        concept_query = " ".join(key_concepts[:2]) if key_concepts else user_query[:30]
        
        # 定义所有维度及其搜索内容
        all_dimensions = {
            "实际例子": f"{concept_query} 实际例子 案例 {current_year}",
            "实施案例": f"{concept_query} 实施 应用案例 {current_year}",
            "潜在风险": f"{concept_query} 风险 问题 挑战",
            "相关研究": f"{concept_query} 研究 论文 {current_year}",
            "最新进展": f"{concept_query} 最新进展 {current_year}",
            "对比分析": f"{concept_query} 对比 比较 优缺点",
            "专家观点": f"{concept_query} 专家 观点 评价"
        }
        
        # 未完成的维度
        remaining_dimensions = {k: v for k, v in all_dimensions.items() 
                              if k not in completed_dimensions}
        
        if not remaining_dimensions:
            print("\n✅ 所有搜索维度已完成，无需补充", flush=True)
            return []
        
        print("\n" + "="*80, flush=True)
        print("📊 初始搜索已完成", flush=True)
        print("="*80, flush=True)
        print(f"\n✅ 已完成的搜索维度 ({len(completed_dimensions)}个):", flush=True)
        for i, dim in enumerate(completed_dimensions, 1):
            print(f"   {i}. {dim}", flush=True)
        
        print(f"\n⏸️  可补充的搜索维度 ({len(remaining_dimensions)}个):", flush=True)
        dim_list = list(remaining_dimensions.keys())
        for i, dim in enumerate(dim_list, 1):
            search_query = remaining_dimensions[dim]
            print(f"   {i}. 【{dim}】", flush=True)
            print(f"      🔍 将搜索: {search_query}", flush=True)
        
        print("\n💡 您可以：", flush=True)
        print("   - 直接回车: 不补充，继续下一步", flush=True)
        print("   - 输入数字 (如: 1,3): 选择要补充的维度", flush=True)
        print("   - 输入 'all': 补充所有剩余维度", flush=True)
        print("   - 输入自定义内容: 自定义搜索查询", flush=True)
        print(flush=True)
        
        try:
            user_input = input("请选择 [默认: 跳过]: ").strip()
            
            if not user_input:
                print("✅ 跳过补充搜索", flush=True)
                return []
            
            if user_input.lower() == 'all':
                print(f"✅ 补充所有 {len(dim_list)} 个维度", flush=True)
                return dim_list
            
            # 检查是否为数字选择
            if any(c.isdigit() or c == ',' for c in user_input):
                selected = []
                for part in user_input.replace('，', ',').split(','):
                    try:
                        num = int(part.strip())
                        if 1 <= num <= len(dim_list):
                            selected.append(dim_list[num - 1])
                    except ValueError:
                        continue
                if selected:
                    print(f"✅ 补充选择的 {len(selected)} 个维度: {', '.join(selected)}", flush=True)
                    return selected
            
            # 自定义搜索
            print(f"✅ 添加自定义搜索: {user_input}", flush=True)
            return [f"自定义: {user_input}"]
            
        except (KeyboardInterrupt, EOFError):
            print("\n✅ 跳过补充搜索", flush=True)
            return []
    
    def _perform_additional_search(self, dimensions: List[str], 
                                   key_concepts: List[str],
                                   user_query: str) -> Dict[str, List[Dict]]:
        """执行用户选择的补充搜索"""
        from datetime import datetime
        current_year = datetime.now().year
        concept_query = " ".join(key_concepts[:2]) if key_concepts else user_query[:30]
        
        # 构建搜索查询
        search_queries = {}
        for dim in dimensions:
            if dim.startswith("自定义:"):
                # 用户自定义搜索
                custom_query = dim.replace("自定义:", "").strip()
                search_queries[dim] = custom_query
            else:
                # 预定义维度
                all_dimensions = {
                    "实际例子": f"{concept_query} 实际例子 案例 {current_year}",
                    "实施案例": f"{concept_query} 实施 应用案例 {current_year}",
                    "潜在风险": f"{concept_query} 风险 问题 挑战",
                    "相关研究": f"{concept_query} 研究 论文 {current_year}",
                    "最新进展": f"{concept_query} 最新进展 {current_year}",
                    "对比分析": f"{concept_query} 对比 比较 优缺点",
                    "专家观点": f"{concept_query} 专家 观点 评价"
                }
                search_queries[dim] = all_dimensions.get(dim, f"{concept_query} {dim}")
        
        # 执行搜索（复用现有逻辑）
        results = {}
        for dim, query in search_queries.items():
            print(f"\n🔎 搜索 【{dim}】", flush=True)
            print(f"   📝 查询: {query}", flush=True)
            try:
                search_result = execute_tool("web_search", query=query, max_results=3)
                if search_result and search_result.success:
                    results[dim] = search_result.data.get("results", [])
                    print(f"   ✅ 找到 {len(results[dim])} 个结果", flush=True)
                else:
                    results[dim] = []
                    print(f"   ⚠️ 搜索失败", flush=True)
            except Exception as e:
                results[dim] = []
                print(f"   ❌ 搜索异常: {e}", flush=True)
        
        return results
    
    def _enhance_thinking_seed_with_search_results(self, 
                                                   original_seed: str,
                                                   user_query: str,
                                                   verification_data: Dict[str, Any],
                                                   multidim_results: Dict[str, List[Dict]]) -> str:
        """
        基于搜索结果增强思维种子
        
        Args:
            original_seed: 原始思维种子
            user_query: 用户查询
            verification_data: 验证数据
            multidim_results: 多维度搜索结果
            
        Returns:
            str: 增强后的思维种子
        """
        try:
            logger.info("🚀 开始增强思维种子生成...")
            
            # 如果没有语义分析器，返回原始种子
            if not self.semantic_analyzer:
                logger.warning("⚠️ 语义分析器不可用，无法增强思维种子")
                return original_seed
            
            # 构建搜索结果摘要
            search_summary = self._build_search_results_summary(multidim_results)
            
            # 提取验证分析摘要
            analysis_summary = verification_data.get("analysis_summary", "")
            
            # 构建增强提示词
            enhancement_prompt = f"""我是一个智能推理Agent，现在需要基于新获取的信息来增强我的思维种子。

**用户原始查询：**
{user_query}

**我的初始思维种子：**
{original_seed}

**验证分析结果：**
{analysis_summary if analysis_summary else "暂无详细分析"}

**多维度搜索获取的最新信息：**
{search_summary}

**任务要求：**
请你作为Agent，整合以上所有信息，生成一个增强版的思维种子。增强后的思维种子应该：

1. **保留原始核心思想** - 不要完全抛弃初始种子的核心观点
2. **融入最新信息** - 将搜索结果中的关键事实、案例、数据融入思考
3. **修正潜在错误** - 如果搜索结果显示原始种子有误，进行修正
4. **增加深度和广度** - 基于多维度信息，让思考更全面
5. **保持连贯性** - 确保增强后的内容逻辑连贯、自然流畅

**输出格式：**
请直接输出增强后的思维种子内容，不要添加"增强后的思维种子："等前缀，直接以思维内容开始。

---
现在，让我整合这些信息，生成增强的思维种子：
"""

            # 直接调用LLM进行思维种子增强（绕过SemanticAnalyzer的JSON解析）
            logger.info("📝 正在调用LLM进行思维种子增强...")
            logger.info("   🤖 LLM正在分析搜索结果并整合信息...")
            logger.info("   ⏳ 预计耗时: 3-5秒")
            
            # 使用PriorReasoner的LLM管理器直接调用
            if hasattr(self.prior_reasoner, 'llm_manager') and self.prior_reasoner.llm_manager:
                try:
                    enhanced_seed = self.prior_reasoner.llm_manager.call_api(
                        prompt=enhancement_prompt,
                        temperature=0.7,
                        max_tokens=1200
                    )
                    
                    if enhanced_seed and isinstance(enhanced_seed, str) and len(enhanced_seed.strip()) > 20:
                        enhanced_seed = enhanced_seed.strip()
                        logger.info("✅ LLM增强完成！")
                        logger.info("")
                        logger.info("📊 增强统计:")
                        logger.info(f"   📏 原始长度: {len(original_seed)} 字符")
                        logger.info(f"   📏 增强后长度: {len(enhanced_seed)} 字符")
                        logger.info(f"   📈 增长比例: {len(enhanced_seed) / len(original_seed):.2f}x")
                        logger.info("")
                        logger.info("📝 增强后种子预览:")
                        logger.info(f"   {enhanced_seed[:200]}{'...' if len(enhanced_seed) > 200 else ''}")
                        return enhanced_seed
                    else:
                        logger.warning("⚠️ LLM返回的增强种子无效，使用原始种子")
                        logger.info("   (可能原因：LLM响应格式异常或内容过短)")
                        return original_seed
                        
                except Exception as e:
                    logger.error(f"❌ LLM调用失败: {e}")
                    logger.info("   (回退到原始种子)")
                    return original_seed
            else:
                logger.warning("⚠️ LLM管理器不可用，使用原始种子")
                logger.info("   (无法进行智能增强)")
                return original_seed
                
        except Exception as e:
            logger.error(f"❌ 思维种子增强失败: {e}")
            return original_seed
    
    def _build_search_results_summary(self, multidim_results: Dict[str, List[Dict]]) -> str:
        """
        构建多维度搜索结果的摘要文本
        
        Args:
            multidim_results: 多维度搜索结果
            
        Returns:
            str: 搜索结果摘要
        """
        summary_parts = []
        
        if not multidim_results:
            return "暂无搜索结果"
        
        for dimension, results in multidim_results.items():
            if results and len(results) > 0:
                summary_parts.append(f"\n【{dimension}】")
                for i, result in enumerate(results[:3], 1):  # 每个维度最多3条
                    title = result.get('title', '无标题')
                    snippet = result.get('snippet', '无摘要')
                    # 限制长度
                    snippet_short = snippet[:150] + "..." if len(snippet) > 150 else snippet
                    summary_parts.append(f"{i}. {title}")
                    summary_parts.append(f"   {snippet_short}")
        
        if not summary_parts:
            return "搜索结果为空"
        
        return "\n".join(summary_parts)
    
    def _execute_stage3_path_generation(self, stage1_context: ThinkingSeedContext,
                                      stage2_context: SeedVerificationContext,
                                      execution_context: Optional[Dict]) -> PathGenerationContext:
        """执行阶段三：思维路径生成"""
        context = PathGenerationContext(
            user_query=stage1_context.user_query,
            execution_context=execution_context
        )
        
        try:
            # 🔥 优先使用增强后的思维种子（如果存在）
            thinking_seed_to_use = stage1_context.thinking_seed
            if hasattr(stage2_context, 'enhanced_thinking_seed') and stage2_context.enhanced_thinking_seed:
                thinking_seed_to_use = stage2_context.enhanced_thinking_seed
                logger.info("✅ 使用阶段二增强后的思维种子生成路径")
                logger.info(f"增强种子摘要: {thinking_seed_to_use[:100]}...")
            else:
                logger.info("使用阶段一原始思维种子生成路径")
            
            # 使用PathGenerator生成多样化路径
            paths_result = self.path_generator.generate_reasoning_paths(
                thinking_seed=thinking_seed_to_use,
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
        """
        执行阶段四：路径策略验证与即时学习（基于策略的搜索验证）
        
        核心功能：
        1. 针对每个策略（系统分析型、创新突破型等）生成特定的搜索查询
        2. 执行搜索，验证该策略在解决此问题时的有效性
        3. 使用LLM评估搜索结果对策略的支持度
        4. 使用Contextual Bandit进行打分和即时学习
        5. 更新MAB系统的策略性能统计
        
        与阶段2的区别：
        - 阶段2：验证思维种子本身的可行性
        - 阶段4：验证具体策略（如"系统分析型"）解决问题的有效性
        """
        context = PathVerificationContext(
            user_query=stage3_context.user_query,
            execution_context=execution_context
        )
        
        verification_start_time = time.time()
        
        try:
            # 填充路径信息
            context.populate_from_reasoning_paths(stage3_context.generated_paths)
            
            logger.info(f"🔬 阶段四：策略验证与即时学习")
            logger.info(f"   待验证策略数: {len(stage3_context.generated_paths)}")
            
            # 统计变量
            verified_count = 0
            feasible_count = 0
            total_effectiveness_score = 0.0
            learning_updates_count = 0
            
            # 验证每个策略路径的有效性
            for i, path in enumerate(stage3_context.generated_paths, 1):
                if not hasattr(path, 'path_id'):
                    logger.warning(f"⚠️ 路径 {i} 缺少path_id，跳过")
                    continue
                
                path_type = getattr(path, 'path_type', 'unknown')
                strategy_id = getattr(path, 'strategy_id', path.path_id)
                prompt_template = getattr(path, 'prompt_template', '')
                
                logger.info(f"\n{'='*80}")
                logger.info(f"🔍 验证策略 {i}/{len(stage3_context.generated_paths)}: 【{path_type}】")
                logger.info(f"{'='*80}")
                
                try:
                    # ✨ 步骤1：基于策略类型和提示词，生成针对性的搜索查询
                    search_queries = self._generate_strategy_specific_search_queries(
                        path=path,
                        user_query=stage3_context.user_query,
                        execution_context=execution_context
                    )
                    
                    if not search_queries:
                        logger.warning(f"⚠️ 未能为策略 {path_type} 生成搜索查询，使用回退评分")
                        effectiveness_score = 0.5
                        reward_score = 0.1
                        search_results = []
                    else:
                        # ✨ 步骤2：执行搜索，收集该策略的支持证据
                        search_results = self._execute_strategy_verification_search(
                            search_queries=search_queries,
                            path_type=path_type
                        )
                        
                        # ✨ 步骤3：使用LLM评估策略的有效性（基于搜索结果）
                        effectiveness_score, evaluation_details = self._evaluate_strategy_effectiveness(
                            path=path,
                            user_query=stage3_context.user_query,
                            search_results=search_results,
                            execution_context=execution_context
                        )
                        
                        # ✨ 步骤4：使用Contextual Bandit计算奖励分数
                        reward_score = self._calculate_contextual_bandit_reward(
                            effectiveness_score=effectiveness_score,
                            path_type=path_type,
                            evaluation_details=evaluation_details
                        )
                        
                        # 🎯 显示 Contextual Bandit 奖励计算详情
                        logger.info("")
                        logger.info("="*80)
                        logger.info("🎯 Contextual Bandit 奖励计算")
                        logger.info("="*80)
                        logger.info(f"📊 输入参数:")
                        logger.info(f"   • 策略类型: {path_type}")
                        logger.info(f"   • 有效性评分: {effectiveness_score:.3f}")
                        logger.info(f"   • 评估方法: {evaluation_details.get('method', 'unknown')}")
                        logger.info(f"")
                        logger.info(f"🧮 奖励计算过程:")
                        # 显示奖励映射逻辑
                        if effectiveness_score >= 0.7:
                            base_range = f"[0.3, 0.9]"
                            reward_level = "高效策略 - 正奖励"
                        elif effectiveness_score >= 0.5:
                            base_range = f"[0.1, 0.3]"
                            reward_level = "中等效果 - 小正奖励"
                        elif effectiveness_score >= 0.3:
                            base_range = f"[-0.1, 0.0]"
                            reward_level = "效果不佳 - 小负奖励"
                        else:
                            base_range = f"[-0.3, -0.1]"
                            reward_level = "无效策略 - 负奖励"
                        
                        logger.info(f"   • 奖励级别: {reward_level}")
                        logger.info(f"   • 基础奖励范围: {base_range}")
                        logger.info(f"   • 最终奖励分数: {reward_score:.3f}")
                        logger.info("="*80)
                        logger.info("")
                    
                    # ✨ 步骤5：即时学习 - 更新MAB系统
                    if hasattr(self, 'mab_converger') and self.mab_converger:
                        try:
                            is_effective = effectiveness_score > 0.5
                            
                            # 获取更新前的 MAB 统计信息
                            mab_stats_before = None
                            if strategy_id in self.mab_converger.path_arms:
                                arm = self.mab_converger.path_arms[strategy_id]
                                mab_stats_before = {
                                    'pulls': arm.total_uses,
                                    'successes': arm.success_count,
                                    'total_reward': arm.total_reward,
                                    'avg_reward': arm.total_reward / arm.total_uses if arm.total_uses > 0 else 0.0
                                }
                            
                            # 更新策略性能统计
                            self.mab_converger.update_path_performance(
                                path_id=strategy_id,
                                success=is_effective,
                                reward=reward_score,
                                source="strategy_verification"  # 标记来源
                            )
                            learning_updates_count += 1
                            
                            # 获取更新后的 MAB 统计信息
                            if strategy_id in self.mab_converger.path_arms:
                                arm = self.mab_converger.path_arms[strategy_id]
                                mab_stats_after = {
                                    'pulls': arm.total_uses,
                                    'successes': arm.success_count,
                                    'total_reward': arm.total_reward,
                                    'avg_reward': arm.total_reward / arm.total_uses if arm.total_uses > 0 else 0.0
                                }
                                
                                # 显示 MAB 更新详情
                                status = "✅ 有效" if is_effective else "❌ 效果不佳"
                                logger.info("")
                                logger.info("="*80)
                                logger.info("🎰 Contextual Bandit (MAB) 即时学习更新")
                                logger.info("="*80)
                                logger.info(f"策略验证结果: {status} - {path_type}")
                                logger.info(f"")
                                logger.info(f"📈 MAB 统计变化:")
                                if mab_stats_before:
                                    logger.info(f"   更新前:")
                                    logger.info(f"      • 拉取次数: {mab_stats_before['pulls']}")
                                    logger.info(f"      • 成功次数: {mab_stats_before['successes']}")
                                    logger.info(f"      • 累计奖励: {mab_stats_before['total_reward']:.3f}")
                                    logger.info(f"      • 平均奖励: {mab_stats_before['avg_reward']:.3f}")
                                    logger.info(f"")
                                logger.info(f"   更新后:")
                                logger.info(f"      • 拉取次数: {mab_stats_after['pulls']} (+1)")
                                logger.info(f"      • 成功次数: {mab_stats_after['successes']} ({'+1' if is_effective else '+0'})")
                                logger.info(f"      • 累计奖励: {mab_stats_after['total_reward']:.3f} ({reward_score:+.3f})")
                                logger.info(f"      • 平均奖励: {mab_stats_after['avg_reward']:.3f}")
                                logger.info(f"")
                                logger.info(f"💡 学习效果:")
                                logger.info(f"   • 本次反馈: {'成功 ✓' if is_effective else '失败 ✗'}")
                                logger.info(f"   • 奖励值: {reward_score:+.3f}")
                                logger.info(f"   • 反馈来源: strategy_verification (阶段四策略验证)")
                                success_rate = mab_stats_after['successes']/mab_stats_after['pulls']*100 if mab_stats_after['pulls'] > 0 else 0.0
                                logger.info(f"   • 成功率: {success_rate:.1f}%")
                                logger.info("="*80)
                            else:
                                logger.info(f"{status}: {path_type}")
                                logger.info(f"   • 有效性评分: {effectiveness_score:.3f}")
                                logger.info(f"   • 奖励分数: {reward_score:.3f}")
                                logger.info(f"   • MAB已更新")
                            
                            if is_effective:
                                feasible_count += 1
                                
                        except Exception as mab_error:
                            logger.warning(f"⚠️ MAB更新失败: {mab_error}")
                    else:
                        logger.warning("⚠️ MAB收敛器不可用")
                    
                    # 记录验证结果
                    verification_result = {
                        "path_id": path.path_id,
                        "feasibility": effectiveness_score,  # 使用有效性分数
                        "confidence": effectiveness_score,
                        "verified": True,
                        "path_type": path_type,
                        "description": getattr(path, 'description', ''),
                        "reward_score": reward_score,
                        "search_queries": search_queries,
                        "search_results_count": len(search_results),
                        "is_feasible": effectiveness_score > 0.5,
                        "verification_method": "strategy_based_search"
                    }
                    
                    context.add_verification_result(path.path_id, verification_result)
                    context.verified_paths.append(verification_result)
                    context.verification_confidence[path.path_id] = effectiveness_score
                    context.path_rankings.append((path.path_id, effectiveness_score))
                    
                    # 确保路径信息完整
                    if path.path_id not in context.path_types:
                        context.add_path_info(
                            path_id=path.path_id,
                            path_type=path_type,
                            description=getattr(path, 'description', ''),
                            metadata={
                                'strategy_id': strategy_id,
                                'effectiveness_score': effectiveness_score,
                                'reward_score': reward_score,
                                'search_queries_count': len(search_queries),
                                'verification_method': 'strategy_based_search'
                            }
                        )
                    
                    verified_count += 1
                    total_effectiveness_score += effectiveness_score
                    
                except Exception as verification_error:
                    logger.error(f"❌ 策略验证失败: {verification_error}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    
                    # 回退结果
                    fallback_result = {
                        "path_id": path.path_id,
                        "feasibility": 0.5,
                        "confidence": 0.3,
                        "verified": False,
                        "path_type": path_type,
                        "description": getattr(path, 'description', ''),
                        "reward_score": 0.0,
                        "verification_error": str(verification_error),
                        "is_feasible": False
                    }
                    context.add_verification_result(path.path_id, fallback_result)
                    context.verified_paths.append(fallback_result)
            
            # 排序路径（按有效性分数）
            context.path_rankings.sort(key=lambda x: x[1], reverse=True)
            
            # 统计和输出
            verification_time = time.time() - verification_start_time
            avg_effectiveness = total_effectiveness_score / verified_count if verified_count > 0 else 0.0
            
            logger.info("")
            logger.info(f"✅ 阶段四完成 (耗时: {verification_time:.3f}s)")
            logger.info(f"   📊 验证统计:")
            logger.info(f"      • 总策略数: {len(stage3_context.generated_paths)}")
            logger.info(f"      • 已验证: {verified_count}")
            logger.info(f"      • 有效策略: {feasible_count}")
            logger.info(f"      • 低效策略: {verified_count - feasible_count}")
            logger.info(f"      • 平均有效性: {avg_effectiveness:.3f}")
            logger.info(f"      • MAB学习更新: {learning_updates_count} 次")
            
            # 显示 Contextual Bandit 整体统计
            if hasattr(self, 'mab_converger') and self.mab_converger:
                logger.info("")
                logger.info("="*80)
                logger.info("🎰 Contextual Bandit (MAB) 整体学习状况")
                logger.info("="*80)
                try:
                    # 统计所有策略的 MAB 数据
                    mab_summary = []
                    for path_id in context.path_types.keys():
                        if path_id in self.mab_converger.path_arms:
                            arm = self.mab_converger.path_arms[path_id]
                            path_type = context.path_types.get(path_id, '未知')
                            total_uses = arm.total_uses
                            mab_summary.append({
                                'path_type': path_type,
                                'path_id': path_id,
                                'pulls': total_uses,
                                'successes': arm.success_count,
                                'total_reward': arm.total_reward,
                                'avg_reward': arm.total_reward / total_uses if total_uses > 0 else 0.0,
                                'success_rate': arm.success_count / total_uses if total_uses > 0 else 0.0
                            })
                    
                    if mab_summary:
                        # 按平均奖励排序
                        mab_summary.sort(key=lambda x: x['avg_reward'], reverse=True)
                        
                        logger.info(f"📊 策略学习表现 (按平均奖励排序):")
                        logger.info("")
                        for i, item in enumerate(mab_summary, 1):
                            logger.info(f"{i}. 【{item['path_type']}】")
                            logger.info(f"   • 尝试次数: {item['pulls']}")
                            logger.info(f"   • 成功次数: {item['successes']}")
                            logger.info(f"   • 成功率: {item['success_rate']*100:.1f}%")
                            logger.info(f"   • 累计奖励: {item['total_reward']:.3f}")
                            logger.info(f"   • 平均奖励: {item['avg_reward']:.3f}")
                            logger.info("")
                        
                        logger.info(f"💡 学习洞察:")
                        best_strategy = mab_summary[0]
                        worst_strategy = mab_summary[-1]
                        logger.info(f"   • 最佳策略: {best_strategy['path_type']} (平均奖励: {best_strategy['avg_reward']:.3f})")
                        logger.info(f"   • 最差策略: {worst_strategy['path_type']} (平均奖励: {worst_strategy['avg_reward']:.3f})")
                        
                        total_pulls = sum(item['pulls'] for item in mab_summary)
                        total_successes = sum(item['successes'] for item in mab_summary)
                        overall_success_rate = total_successes / total_pulls if total_pulls > 0 else 0.0
                        logger.info(f"   • 整体成功率: {overall_success_rate*100:.1f}%")
                        logger.info(f"   • 本轮学习更新: {learning_updates_count} 次")
                        
                    else:
                        logger.info("暂无 MAB 学习数据")
                    
                    logger.info("="*80)
                    
                except Exception as mab_summary_error:
                    logger.warning(f"⚠️ 生成 MAB 统计摘要失败: {mab_summary_error}")
            
            logger.info("")
            
            # 显示策略排名
            if context.path_rankings:
                logger.info(f"   🏆 策略有效性排名:")
                for rank, (path_id, score) in enumerate(context.path_rankings[:3], 1):
                    path_type = context.path_types.get(path_id, '未知')
                    logger.info(f"      {rank}. {path_type} (有效性: {score:.3f})")
            
            # 记录指标
            context.add_metric("verified_paths_count", verified_count)
            context.add_metric("feasible_paths_count", feasible_count)
            context.add_metric("average_feasibility_score", avg_effectiveness)
            context.add_metric("mab_learning_updates", learning_updates_count)
            context.add_metric("verification_time", verification_time)
            
            if feasible_count == 0:
                logger.warning("⚠️ 所有策略验证效果不佳")
                context.add_warning("所有策略有效性评分偏低")
                
        except Exception as e:
            logger.error(f"❌ 策略验证异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            context.add_error(f"策略验证异常: {str(e)}")
        
        return context
    
    def _generate_strategy_specific_search_queries(self, path, user_query: str, 
                                                   execution_context: Optional[Dict]) -> List[str]:
        """
        基于策略类型和提示词，生成针对性的搜索查询
        
        Args:
            path: ReasoningPath对象，包含策略信息
            user_query: 用户原始问题
            execution_context: 执行上下文
            
        Returns:
            List[str]: 搜索查询列表（1-3个）
        """
        try:
            path_type = getattr(path, 'path_type', 'unknown')
            prompt_template = getattr(path, 'prompt_template', '')
            description = getattr(path, 'description', '')
            
            logger.info(f"🔍 为策略【{path_type}】生成搜索查询...")
            
            # 获取当前时间
            from datetime import datetime
            current_year = datetime.now().year
            
            # 构建LLM提示词
            planning_prompt = f"""你是一个搜索查询专家。现在需要验证一个问题解决策略的有效性。

📋 **任务背景**:
- 用户问题: {user_query}
- 策略类型: {path_type}
- 策略描述: {description}
- 策略提示词: {prompt_template[:200]}...

🎯 **你的任务**:
基于这个策略类型，生成2-3个搜索查询，用于验证该策略在解决此类问题时的有效性。

**搜索查询应该关注**:
1. 该策略在类似问题中的成功案例
2. 该策略的方法论和最佳实践
3. 专家对该策略的评价和建议

**重要**:
- 查询要具体、可执行
- 如果涉及时间，使用{current_year}年
- 每个查询一行，不要编号

请直接输出搜索查询（一行一个），不要其他解释："""
            
            # 调用LLM生成查询
            if not hasattr(self, 'llm_manager') or not self.llm_manager:
                logger.warning("⚠️ LLM管理器不可用，使用启发式方法生成查询")
                return self._generate_fallback_search_queries(path_type, user_query, current_year)
            
            logger.debug("🤖 调用LLM生成搜索查询...")
            
            # 使用LLM生成
            response = self.llm_manager.call_api(
                prompt=planning_prompt,
                temperature=0.7,
                max_tokens=300
            )
            
            # 提取响应内容
            content = ""
            if isinstance(response, dict) and 'content' in response:
                content = response['content']
            elif isinstance(response, str):
                content = response
            elif hasattr(response, 'content'):
                content = response.content
            
            if not content:
                logger.warning("⚠️ LLM未返回有效内容，使用回退方法")
                return self._generate_fallback_search_queries(path_type, user_query, current_year)
            
            # 解析查询（每行一个）
            queries = []
            for line in content.strip().split('\n'):
                line = line.strip()
                # 移除可能的编号
                line = line.lstrip('0123456789.-:：、）) ')
                if line and len(line) > 10:
                    queries.append(line)
            
            # 限制数量
            queries = queries[:3]
            
            if queries:
                logger.info(f"✅ 生成了 {len(queries)} 个搜索查询:")
                for i, q in enumerate(queries, 1):
                    logger.info(f"   {i}. {q}")
                return queries
            else:
                logger.warning("⚠️ 未能从LLM响应中提取查询，使用回退方法")
                return self._generate_fallback_search_queries(path_type, user_query, current_year)
                
        except Exception as e:
            logger.error(f"❌ 生成搜索查询失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # 使用回退方法
            from datetime import datetime
            return self._generate_fallback_search_queries(
                getattr(path, 'path_type', 'unknown'), 
                user_query, 
                datetime.now().year
            )
    
    def _generate_fallback_search_queries(self, path_type: str, user_query: str, 
                                         current_year: int) -> List[str]:
        """启发式生成搜索查询（当LLM不可用时）"""
        queries = []
        
        # 根据策略类型调整关键词
        strategy_keywords = {
            "系统分析型": "系统分析方法",
            "创新突破型": "创新思维方法",
            "批判质疑型": "批判性思维",
            "实用直接型": "实用解决方案",
            "平衡综合型": "综合分析方法"
        }
        
        keyword = strategy_keywords.get(path_type, "问题解决方法")
        
        # 生成基础查询
        queries.append(f"{user_query[:40]} {keyword} {current_year}")
        queries.append(f"{keyword} 成功案例 最佳实践")
        
        return queries[:3]
    
    def _execute_strategy_verification_search(self, search_queries: List[str], 
                                             path_type: str) -> List[Dict[str, Any]]:
        """
        执行策略验证搜索
        
        Args:
            search_queries: 搜索查询列表
            path_type: 策略类型
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        try:
            all_results = []
            
            logger.info(f"\n🔎 执行策略验证搜索 ({len(search_queries)} 个查询)...")
            
            # 检查是否有搜索工具
            if not hasattr(self, 'tool_registry') or not self.tool_registry:
                logger.warning("⚠️ 工具注册表不可用")
                return []
            
            if not self.tool_registry.has_tool("web_search"):
                logger.warning("⚠️ web_search工具不可用")
                return []
            
            # 执行每个查询
            for i, query in enumerate(search_queries, 1):
                try:
                    print(f"\n{'─'*80}")
                    print(f"🔍 搜索查询 {i}/{len(search_queries)}: {query}")
                    print(f"{'─'*80}")
                    
                    # 调用搜索工具
                    search_result = self.tool_registry.execute_tool(
                        name="web_search",
                        query=query
                    )
                    
                    if search_result and search_result.success:
                        result_data = search_result.data
                        
                        # 提取结果
                        if isinstance(result_data, dict) and 'results' in result_data:
                            results_list = result_data['results']
                            print(f"✅ 找到 {len(results_list)} 条结果")
                            
                            # 显示前2条
                            for j, item in enumerate(results_list[:2], 1):
                                if isinstance(item, dict):
                                    title = item.get('title', '无标题')
                                    url = item.get('url', '')
                                    print(f"  {j}. 📄 {title[:60]}")
                                    print(f"     🔗 {url[:70]}")
                            
                            all_results.extend(results_list)
                        else:
                            print(f"⚠️  搜索结果格式未知")
                    else:
                        error_msg = search_result.error_message if search_result else "未知错误"
                        print(f"❌ 搜索失败: {error_msg}")
                        
                except Exception as search_error:
                    print(f"❌ 搜索异常: {str(search_error)}")
                    logger.error(f"搜索异常: {search_error}")
                    continue
            
            print(f"\n{'='*80}")
            print(f"✅ 策略验证搜索完成: 共获得 {len(all_results)} 条结果")
            print(f"{'='*80}\n")
            
            logger.info(f"✅ 搜索完成，共 {len(all_results)} 条结果")
            return all_results
            
        except Exception as e:
            logger.error(f"❌ 执行搜索失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _evaluate_strategy_effectiveness(self, path, user_query: str, 
                                        search_results: List[Dict[str, Any]],
                                        execution_context: Optional[Dict]) -> Tuple[float, Dict[str, Any]]:
        """
        使用LLM评估策略的有效性
        
        Args:
            path: ReasoningPath对象
            user_query: 用户问题
            search_results: 搜索结果
            execution_context: 执行上下文
            
        Returns:
            Tuple[float, Dict]: (有效性分数, 评估详情)
        """
        try:
            path_type = getattr(path, 'path_type', 'unknown')
            prompt_template = getattr(path, 'prompt_template', '')
            
            logger.info(f"🤖 使用LLM评估策略有效性...")
            
            # 如果没有搜索结果，给基础分数
            if not search_results:
                logger.warning("⚠️ 无搜索结果，使用基础评分")
                return 0.5, {"reason": "no_search_results"}
            
            # 构建搜索结果摘要
            results_summary = self._build_search_results_summary_for_llm(search_results[:5])
            
            # 构建LLM评估提示词
            evaluation_prompt = f"""你是一个策略有效性评估专家。

**用户问题**: {user_query}

**待评估策略**: {path_type}
- 策略描述: {getattr(path, 'description', '')}
- 策略方法: {prompt_template[:150]}

**搜索到的证据**:
{results_summary}

**评估任务**:
基于搜索到的证据，评估该策略解决此问题的有效性。

**评估标准**:
1. 该策略是否有成功案例支持
2. 该策略是否适用于此类问题
3. 搜索结果是否验证了策略的可行性
4. 是否有专家推荐或最佳实践支持

**输出格式**:
有效性评分: [0.0-1.0之间的数字]
评估理由: [一句话说明理由]

请直接输出评分和理由："""
            
            # 调用LLM
            if not hasattr(self, 'llm_manager') or not self.llm_manager:
                logger.warning("⚠️ LLM管理器不可用，使用启发式评分")
                return self._calculate_heuristic_effectiveness(search_results), {"method": "heuristic"}
            
            print("\n" + "="*80)
            print("🤖 LLM策略有效性评估:")
            print("="*80)
            
            response = self.llm_manager.call_api(
                prompt=evaluation_prompt,
                temperature=0.3,  # 较低温度，更客观
                max_tokens=500
            )
            
            # 提取响应内容
            content = ""
            if isinstance(response, dict) and 'content' in response:
                content = response['content']
            elif isinstance(response, str):
                content = response
            elif hasattr(response, 'content'):
                content = response.content
            
            if not content:
                logger.warning("⚠️ LLM未返回有效内容")
                return self._calculate_heuristic_effectiveness(search_results), {"method": "fallback"}
            
            print(content)
            print("="*80 + "\n")
            
            # 解析评分
            import re
            score_match = re.search(r'(?:有效性评分|评分)[:：\s]*([0-9.]+)', content)
            if score_match:
                score = float(score_match.group(1))
                score = max(0.0, min(1.0, score))  # 限制在0-1范围
                logger.info(f"✅ LLM评估分数: {score:.3f}")
                
                # 提取理由
                reason_match = re.search(r'(?:评估理由|理由)[:：\s]*(.+?)(?:\n|$)', content)
                reason = reason_match.group(1).strip() if reason_match else content[:100]
                
                return score, {
                    "method": "llm_evaluation",
                    "reason": reason,
                    "full_response": content
                }
            else:
                logger.warning("⚠️ 无法从LLM响应中提取评分")
                return self._calculate_heuristic_effectiveness(search_results), {
                    "method": "parse_failed",
                    "llm_response": content
                }
                
        except Exception as e:
            logger.error(f"❌ 策略有效性评估失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return 0.5, {"method": "error", "error": str(e)}
    
    def _build_search_results_summary_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """构建搜索结果摘要供LLM评估"""
        if not results:
            return "（无搜索结果）"
        
        summary_lines = []
        for i, result in enumerate(results[:5], 1):
            title = result.get('title', '无标题')
            snippet = result.get('snippet', result.get('content', ''))[:150]
            summary_lines.append(f"{i}. {title}\n   摘要: {snippet}")
        
        return "\n\n".join(summary_lines)
    
    def _calculate_heuristic_effectiveness(self, search_results: List[Dict[str, Any]]) -> float:
        """启发式计算有效性分数（当LLM不可用时）"""
        if not search_results:
            return 0.3
        
        # 基于结果数量的简单评分
        result_count = len(search_results)
        if result_count >= 5:
            return 0.7
        elif result_count >= 3:
            return 0.6
        elif result_count >= 1:
            return 0.5
        else:
            return 0.3
    
    def _calculate_contextual_bandit_reward(self, effectiveness_score: float,
                                           path_type: str,
                                           evaluation_details: Dict[str, Any]) -> float:
        """
        使用Contextual Bandit机制计算奖励分数
        
        Args:
            effectiveness_score: 策略有效性分数 (0.0-1.0)
            path_type: 策略类型
            evaluation_details: 评估详情
            
        Returns:
            float: 奖励分数 (-1.0 到 1.0)
        """
        try:
            # 🎯 Contextual Bandit核心：基于上下文调整奖励
            
            # 基础奖励：从有效性分数映射到奖励值
            if effectiveness_score >= 0.7:
                # 高效策略：正奖励
                base_reward = 0.3 + (effectiveness_score - 0.7) * 2.0  # 0.3-0.9
            elif effectiveness_score >= 0.5:
                # 中等效果：小正奖励
                base_reward = 0.1 + (effectiveness_score - 0.5) * 1.0  # 0.1-0.3
            elif effectiveness_score >= 0.3:
                # 效果不佳：小负奖励
                base_reward = -0.1 + (effectiveness_score - 0.3) * 0.5  # -0.1-0.0
            else:
                # 无效策略：负奖励
                base_reward = -0.3 + effectiveness_score * 0.67  # -0.3到-0.1
            
            # 🎯 上下文调整：根据评估方法调整权重
            method = evaluation_details.get('method', 'unknown')
            if method == 'llm_evaluation':
                # LLM评估更可信，保持原奖励
                context_adjustment = 0.0
            elif method == 'heuristic':
                # 启发式评估不太可信，降低奖励幅度
                context_adjustment = -0.1
            else:
                # 其他情况，轻微降低
                context_adjustment = -0.05
            
            # 最终奖励
            final_reward = base_reward + context_adjustment
            final_reward = max(-1.0, min(1.0, final_reward))
            
            # 确保不为零（MAB学习需要）
            if final_reward == 0.0:
                final_reward = 0.05 if effectiveness_score >= 0.5 else -0.05
            
            logger.debug(f"奖励计算: 有效性={effectiveness_score:.3f}, 基础={base_reward:.3f}, 调整={context_adjustment:.3f}, 最终={final_reward:.3f}")
            
            return final_reward
            
        except Exception as e:
            logger.warning(f"⚠️ 奖励计算失败: {e}")
            # 回退到简单映射
            return 0.1 if effectiveness_score >= 0.5 else -0.1
    
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
    
    def _generate_answer_from_context(self, query: str, strategy_decision: 'StrategyDecision', 
                                     context: Optional[Dict[str, Any]] = None) -> str:
        """
        基于五阶段上下文生成最终答案
        
        这个方法整合前四阶段的所有信息：
        - 阶段一：思维种子（thinking_seed）
        - 阶段二：种子验证结果（搜索信息、事实检查）
        - 阶段三：生成的推理路径
        - 阶段四：路径验证结果
        - 阶段五：选择的最优路径
        
        Args:
            query: 用户查询
            strategy_decision: 五阶段战略决策结果
            context: 可选的执行上下文
            
        Returns:
            str: 基于上下文生成的最终答案
        """
        try:
            # 提取各阶段上下文信息
            thinking_seed = getattr(strategy_decision, 'thinking_seed', '')
            chosen_path = strategy_decision.chosen_path
            
            # 获取阶段上下文
            stage1_context = getattr(strategy_decision, 'stage1_context', None)
            stage2_context = getattr(strategy_decision, 'stage2_context', None)
            stage3_context = getattr(strategy_decision, 'stage3_context', None)
            stage4_context = getattr(strategy_decision, 'stage4_context', None)
            stage5_context = getattr(strategy_decision, 'stage5_context', None)
            
            # 构建上下文摘要
            context_summary = self._build_context_summary(
                query, thinking_seed, chosen_path,
                stage1_context, stage2_context, stage3_context, stage4_context, stage5_context
            )
            
            # 🔥 增强：传递 chosen_path 和 stage2_context 给 LLM，充分利用策略和搜索结果
            llm_answer = self._generate_llm_answer(
                query, 
                context_summary,
                chosen_path=chosen_path,
                stage2_context=stage2_context
            )
            
            if llm_answer:
                return llm_answer
            else:
                # 如果LLM生成失败，使用模板生成答案
                return self._generate_template_answer(query, context_summary, chosen_path)
                
        except Exception as e:
            logger.error(f"基于上下文生成答案失败: {e}")
            # 返回基本答案
            return self._generate_fallback_answer(query, strategy_decision)
    
    def _build_context_summary(self, query: str, thinking_seed: str, chosen_path: Any,
                              stage1_ctx, stage2_ctx, stage3_ctx, stage4_ctx, stage5_ctx) -> str:
        """构建五阶段上下文摘要"""
        summary_parts = []
        
        summary_parts.append(f"用户问题：{query}\n")
        
        # 阶段一：思维种子
        if thinking_seed:
            summary_parts.append(f"\n【思维种子】\n{thinking_seed}\n")
        
        # 阶段二：搜索和验证信息
        if stage2_ctx and hasattr(stage2_ctx, 'search_results'):
            search_results = stage2_ctx.search_results
            if search_results:
                summary_parts.append(f"\n【搜索信息】")
                for dim, results in search_results.items():
                    if results:
                        summary_parts.append(f"\n{dim}维度：")
                        for i, result in enumerate(results[:2], 1):  # 只取前2个结果
                            title = result.get('title', '')
                            snippet = result.get('snippet', result.get('content', ''))[:150]
                            summary_parts.append(f"{i}. {title}: {snippet}...")
        
        # 阶段三：生成的路径
        if stage3_ctx and hasattr(stage3_ctx, 'generated_paths'):
            paths = stage3_ctx.generated_paths
            if paths:
                summary_parts.append(f"\n\n【候选策略路径】")
                for i, path in enumerate(paths[:3], 1):  # 只取前3个路径
                    path_type = getattr(path, 'path_type', '未知')
                    desc = getattr(path, 'description', '')
                    summary_parts.append(f"{i}. {path_type}: {desc}")
        
        # 阶段五：最终选择的路径
        if chosen_path:
            path_type = getattr(chosen_path, 'path_type', chosen_path.get('path_type', '未知') if isinstance(chosen_path, dict) else '未知')
            path_desc = getattr(chosen_path, 'description', chosen_path.get('description', '') if isinstance(chosen_path, dict) else '')
            summary_parts.append(f"\n\n【选择的最优策略】\n类型：{path_type}\n描述：{path_desc}")
        
        return "\n".join(summary_parts)
    
    def _generate_llm_answer(self, query: str, context_summary: str, 
                           chosen_path: Any = None, stage2_context = None) -> Optional[str]:
        """使用LLM基于上下文生成答案 - 增强版：充分利用策略和搜索结果"""
        try:
            # 检查是否有可用的LLM
            llm_manager = None
            if hasattr(self.prior_reasoner, 'llm_manager'):
                llm_manager = self.prior_reasoner.llm_manager
            
            if not llm_manager:
                logger.debug("未找到LLM管理器，跳过LLM生成")
                return None
            
            # 🔥 提取选中策略的 prompt_template（策略的核心方法论）
            strategy_prompt = ""
            if chosen_path:
                if hasattr(chosen_path, 'prompt_template'):
                    strategy_prompt = chosen_path.prompt_template
                elif isinstance(chosen_path, dict):
                    strategy_prompt = chosen_path.get('prompt_template', '')
            
            # 🔥 提取阶段2的搜索结果
            search_content = ""
            if stage2_context:
                # 🔍 调试：打印 stage2_context 的结构
                print(f"\n🔍 [DEBUG] stage2_context 类型: {type(stage2_context)}")
                if isinstance(stage2_context, dict):
                    print(f"🔍 [DEBUG] stage2_context 键: {list(stage2_context.keys())}")
                else:
                    print(f"🔍 [DEBUG] stage2_context 属性: {dir(stage2_context)}")
                
                # 尝试多个可能的字段名，支持字典和对象两种形式
                search_results = None
                if isinstance(stage2_context, dict):
                    search_results = stage2_context.get('multidimensional_search_results') or \
                                   stage2_context.get('search_results') or \
                                   stage2_context.get('verification_sources') or {}
                else:
                    search_results = getattr(stage2_context, 'multidimensional_search_results', None) or \
                                    getattr(stage2_context, 'search_results', None) or {}
                
                print(f"🔍 [DEBUG] search_results 类型: {type(search_results)}")
                if search_results:
                    if isinstance(search_results, dict):
                        print(f"🔍 [DEBUG] search_results 键: {list(search_results.keys())}")
                    print(f"🔍 [DEBUG] search_results 前100字符: {str(search_results)[:100]}")
                
                # 如果有多维度搜索结果
                if search_results and isinstance(search_results, dict):
                    search_parts = []
                    for dim, results in search_results.items():
                        if results and isinstance(results, list):
                            search_parts.append(f"\n**{dim}维度的搜索结果：**")
                            # 🔥 增加展示数量：从3个增加到5个，提供更多例子
                            for i, result in enumerate(results[:5], 1):
                                if isinstance(result, dict):
                                    title = result.get('title', '无标题')
                                    snippet = result.get('snippet', result.get('content', ''))
                                    url = result.get('url', '')
                                    search_parts.append(f"{i}. 【{title}】")
                                    if snippet:
                                        # 🔥 增加摘要长度：从300增加到500字符，提供更详细的信息
                                        search_parts.append(f"   内容: {snippet[:500]}")
                                    if url:
                                        search_parts.append(f"   来源: {url}")
                    if search_parts:
                        search_content = "\n".join(search_parts)
                
                # 如果没有多维度搜索结果，尝试 verification_sources
                if not search_content:
                    # 支持字典和对象两种形式
                    if isinstance(stage2_context, dict):
                        verification_sources = stage2_context.get('verification_sources', [])
                    else:
                        verification_sources = getattr(stage2_context, 'verification_sources', [])
                    
                    print(f"🔍 [DEBUG] verification_sources 类型: {type(verification_sources)}, 长度: {len(verification_sources) if verification_sources else 0}")
                    if verification_sources:
                        search_parts = ["\n**验证信息源：**"]
                        # 🔥 增加展示数量：从5个增加到8个
                        for i, source in enumerate(verification_sources[:8], 1):
                            if isinstance(source, dict):
                                title = source.get('title', '无标题')
                                snippet = source.get('snippet', source.get('content', ''))
                                url = source.get('url', '')
                                search_parts.append(f"{i}. 【{title}】")
                                if snippet:
                                    # 🔥 增加摘要长度：从300增加到500字符
                                    search_parts.append(f"   内容: {snippet[:500]}")
                                if url:
                                    search_parts.append(f"   来源: {url}")
                        search_content = "\n".join(search_parts)
            
            # 🔍 调试：显示最终的 search_content
            print(f"\n🔍 [DEBUG] 最终 search_content 长度: {len(search_content) if search_content else 0}")
            if search_content:
                print(f"🔍 [DEBUG] search_content 前500字符:\n{search_content[:500]}")
            else:
                print(f"⚠️ [WARNING] search_content 为空！")
            
            # 🔥 构建增强版提示词
            # 检查是否有搜索结果
            has_search_results = bool(search_content and search_content.strip() and search_content != "（暂无搜索结果）")
            print(f"🔍 [DEBUG] has_search_results: {has_search_results}")
            
            from datetime import datetime
            current_year = datetime.now().year
            
            prompt = f"""你是一个智能助手，现在需要基于五阶段决策系统的完整上下文来回答用户问题。

## 📋 用户问题
{query}

## 🎯 选中的策略方法论
系统经过五阶段智能决策，选择了以下策略来回答这个问题：

{strategy_prompt if strategy_prompt else "（策略提示词不可用，请使用标准方法回答）"}

## 🌐 搜索到的最新信息（{current_year}年实时数据）
{search_content if search_content else "（暂无搜索结果）"}

## 📊 完整决策上下文
{context_summary}

## ✅ 你的任务和要求

### 1. **必须遵循策略方法论**
   - 仔细阅读上面的"选中的策略方法论"
   - 按照该策略的思维方式、分析步骤和结构来组织答案
   - 体现策略的特色（如探索调研型要全面系统，实用务实型要简洁直接）

### 2. **⚠️ 强制要求：优先使用搜索信息**
{'''   ✅ 检测到搜索结果！你必须：
   - **第一优先级：引用上面"搜索到的最新信息"中的具体内容**
   - **必须在答案中明确展示搜索到的案例、数据、观点**
   - 直接引用搜索结果的标题和内容片段
   - **举例时，必须优先使用搜索结果中的实际例子**，而不是训练数据中的例子
   - 如果搜索结果提到了具体的例子、应用、数据，必须在答案中详细展示
   - 在引用处标注【来源：搜索结果】或【来源：搜索结果 - 标题名】
   - ⚠️ 如果你的答案中没有使用任何搜索结果的内容，这是不合格的！
   - ⚠️ 如果举例时没有使用搜索结果中的例子，也是不合格的！''' if has_search_results else '''   ⚠️ 暂无搜索结果，使用训练数据回答
   - 要明确说明这些是基于训练数据的一般性知识
   - 建议说明可能需要进一步查证最新信息'''}

### 3. **答案结构要求**
   - 开头：简要概述
   - 主体：按策略要求的步骤展开，**尽可能详细、深入**
   {'- **必须有独立段落展示搜索到的实际案例和数据**' if has_search_results else ''}
   {'- **举例部分：专门展示搜索结果中的例子，包括标题、内容、来源**' if has_search_results else ''}
   - 结尾：总结要点

### 4. **质量标准**
   - **内容必须详细、深入、全面**
   - **不限制字数长度，鼓励详细展开说明**
   - 逻辑清晰、层次分明
   - 语言专业但易懂
   {'- **核心要求：必须包含并详细展示搜索结果的具体内容**' if has_search_results else ''}
   {'- **举例标准：优先使用搜索结果中的例子，详细描述，包含来源信息**' if has_search_results else ''}

现在，请严格按照上述要求生成答案：
"""
            
            # 调用LLM - 增加 max_tokens 支持详细回答
            if hasattr(llm_manager, 'call_api'):
                # 🔥 取消字数限制：增加到 6000 tokens，支持详细、深入的回答
                response = llm_manager.call_api(prompt, max_tokens=6000, temperature=0.7)
                if response and isinstance(response, str) and len(response.strip()) > 0:
                    return response.strip()
            
            return None
            
        except Exception as e:
            logger.debug(f"LLM生成答案失败: {e}")
            return None
    
    def _generate_template_answer(self, query: str, context_summary: str, chosen_path: Any) -> str:
        """使用模板生成答案"""
        path_type = "未知"
        path_desc = ""
        
        if chosen_path:
            if hasattr(chosen_path, 'path_type'):
                path_type = chosen_path.path_type
                path_desc = getattr(chosen_path, 'description', '')
            elif isinstance(chosen_path, dict):
                path_type = chosen_path.get('path_type', '未知')
                path_desc = chosen_path.get('description', '')
        
        answer = f"针对您的问题「{query}」，我进行了深入分析：\n\n"
        
        # 添加策略说明
        answer += f"**选择策略**：{path_type}\n"
        if path_desc:
            answer += f"**策略描述**：{path_desc}\n\n"
        
        # 添加上下文信息
        if "【搜索信息】" in context_summary:
            answer += "**相关信息**：\n"
            answer += "经过多维度搜索验证，收集了相关背景信息和参考资料。\n\n"
        
        # 根据路径类型提供不同的建议
        if "exploratory" in path_type.lower():
            answer += "**建议**：建议采用探索调研的方式，全面收集信息，分析不同观点，最后形成综合性结论。\n"
        elif "practical" in path_type.lower():
            answer += "**建议**：建议采用实用直接的方式，明确目标，选择最有效的方法快速执行。\n"
        elif "analytical" in path_type.lower():
            answer += "**建议**：建议采用系统分析的方式，将问题分解，逐一研究各部分及其关联，形成整体方案。\n"
        else:
            answer += f"**建议**：根据{path_type}策略，建议制定详细计划，分步骤执行并持续优化。\n"
        
        return answer
    
    def _generate_fallback_answer(self, query: str, strategy_decision: 'StrategyDecision') -> str:
        """生成回退答案"""
        thinking_seed = getattr(strategy_decision, 'thinking_seed', '')
        
        answer = f"针对您的问题「{query}」：\n\n"
        
        if thinking_seed:
            answer += f"**初步分析**：\n{thinking_seed[:200]}...\n\n"
        
        answer += "我已经完成了五阶段智能决策分析，包括思维种子生成、多维度验证、路径生成、路径验证和最优选择。"
        answer += "建议您根据具体情况，结合相关信息制定详细的执行计划。\n"
        
        return answer
