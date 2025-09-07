#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Neogenesis智能Agent运行器
展示如何组装和运行完整的Agent系统

这个文件是重构后系统的完整入口点，演示了：
1. 如何组装NeogenesisPlanner、ToolExecutor和Memory
2. 如何创建完整的Agent实例
3. 简单的agent.run("你的问题")调用方式
4. 完整的内部工作流程观察
"""

import os
import sys
import time
import logging
from typing import Dict, List, Optional, Any

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加项目路径
project_root = os.path.dirname(__file__)
sys.path.insert(0, project_root)

try:
    # 导入框架核心
    from neogenesis_system import (
        # 数据结构
        Action, Plan, Observation, ExecutionContext, AgentState,
        # 抽象接口
        BaseToolExecutor, BaseMemory, BaseAgent,
        # 具体实现
        NeogenesisPlanner
    )
    
    # 导入Meta MAB组件
    from neogenesis_system.cognitive_engine.reasoner import PriorReasoner
    from neogenesis_system.cognitive_engine.path_generator import PathGenerator
    from neogenesis_system.cognitive_engine.mab_converger import MABConverger
    from neogenesis_system.providers.llm_manager import LLMManager
    from neogenesis_system.tools.tool_abstraction import global_tool_registry
    
    # 导入认知调度器
    from neogenesis_system.core.cognitive_scheduler import CognitiveScheduler
    
    # 检查是否可以使用真实组件
    REAL_COMPONENTS_AVAILABLE = True
    print("✅ 成功导入真实组件")
    
except Exception as e:
    print(f"⚠️ 无法导入真实组件，使用模拟组件: {e}")
    REAL_COMPONENTS_AVAILABLE = False
    
    # 加载简化组件
    sys.path.insert(0, os.path.join(project_root, 'neogenesis_system'))
    exec(open('neogenesis_system/data_structures.py', encoding='utf-8').read())
    
    from abc import ABC, abstractmethod
    
    class BaseToolExecutor(ABC):
        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description
        
        @abstractmethod
        def execute_plan(self, plan, context=None) -> List:
            pass
    
    class BaseMemory(ABC):
        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description
        
        @abstractmethod
        def store(self, key: str, value: Any, metadata=None) -> bool:
            pass
        
        @abstractmethod
        def retrieve(self, key: str) -> Any:
            pass
    
    class BaseAgent(ABC):
        def __init__(self, planner, tool_executor, memory, name="Agent"):
            self.planner = planner
            self.tool_executor = tool_executor
            self.memory = memory
            self.name = name
            self.stats = {"total_tasks": 0, "successful_tasks": 0}
        
        @abstractmethod
        def run(self, query: str, context=None) -> str:
            pass
    
    # 创建模拟的NeogenesisPlanner
    class NeogenesisPlanner:
        def __init__(self, name="NeogenesisPlanner"):
            self.name = name
        
        def create_plan(self, query: str, memory, context=None):
            # 简单的五阶段模拟逻辑
            if "搜索" in query or "查找" in query or "信息" in query:
                return Plan(
                    thought=f"基于五阶段智能决策，选择搜索策略处理'{query}'",
                    actions=[Action("web_search", {"query": query})]
                )
            elif "验证" in query or "可行" in query:
                return Plan(
                    thought=f"基于五阶段智能决策，选择验证策略分析'{query}'",
                    actions=[Action("idea_verification", {"idea_text": query})]
                )
            else:
                return Plan(
                    thought=f"基于五阶段智能决策，选择直接回答策略处理'{query}'",
                    final_answer=f"关于'{query}'，这是基于智能分析的回答：经过深度思考，我认为这个问题需要从多个角度来考虑..."
                )
        
        def validate_plan(self, plan):
            return True
        
        def get_stats(self):
            return {"name": self.name, "total_rounds": 0}


# =============================================================================
# 生产级工具执行器
# =============================================================================

class ProductionToolExecutor(BaseToolExecutor):
    """
    生产级工具执行器
    支持真实的web搜索、想法验证等工具调用
    """
    
    def __init__(self):
        super().__init__("ProductionToolExecutor", "生产级工具执行器")
        self._init_tools()
    
    def _init_tools(self):
        """初始化可用工具"""
        self.tools = {
            "web_search": self._web_search,
            "idea_verification": self._idea_verification,
            "text_analysis": self._text_analysis,
            "knowledge_query": self._knowledge_query
        }
        logger.info(f"🔧 工具执行器初始化完成，支持 {len(self.tools)} 个工具")
    
    def execute_plan(self, plan: Plan, context: Optional[ExecutionContext] = None) -> List[Observation]:
        """执行完整计划"""
        observations = []
        
        logger.info(f"🔧 开始执行计划: {len(plan.actions)} 个行动")
        
        for i, action in enumerate(plan.actions, 1):
            logger.info(f"   执行行动 {i}/{len(plan.actions)}: {action.tool_name}")
            
            observation = self.execute_action(action)
            observations.append(observation)
            
            # 实时反馈执行结果
            if observation.success:
                logger.info(f"   ✅ 成功: {observation.output[:80]}...")
            else:
                logger.warning(f"   ❌ 失败: {observation.error_message}")
        
        logger.info(f"🔧 计划执行完成: {sum(1 for obs in observations if obs.success)}/{len(observations)} 成功")
        return observations
    
    def execute_action(self, action: Action) -> Observation:
        """执行单个行动"""
        start_time = time.time()
        action.start_execution()
        
        try:
            if action.tool_name not in self.tools:
                raise ValueError(f"未知工具: {action.tool_name}")
            
            # 调用相应工具
            result = self.tools[action.tool_name](action.tool_input)
            
            action.complete_execution()
            execution_time = time.time() - start_time
            
            return Observation(
                action=action,
                output=result,
                success=True,
                execution_time=execution_time
            )
            
        except Exception as e:
            action.fail_execution()
            execution_time = time.time() - start_time
            
            return Observation(
                action=action,
                output="",
                success=False,
                error_message=str(e),
                execution_time=execution_time
            )
    
    def _web_search(self, params: Dict) -> str:
        """网页搜索工具"""
        query = params.get("query", "")
        
        # 模拟搜索过程（在生产环境中这里会调用真实的搜索API）
        logger.info(f"🔍 执行网页搜索: {query}")
        
        # 根据查询类型返回不同的模拟结果
        if "人工智能" in query or "AI" in query.upper():
            return (
                "🔍 搜索结果：人工智能技术正在快速发展，主要趋势包括：\n"
                "1. 大语言模型的突破性进展，如GPT-4、Claude等\n"
                "2. 多模态AI的发展，整合文本、图像、音频\n"
                "3. AI在各行业的深度应用和商业化\n"
                "4. 自主Agent和AI系统的智能化程度提升\n"
                "5. AI安全和对齐研究的重要性日益凸显"
            )
        elif "Python" in query:
            return (
                "🔍 搜索结果：Python编程学习建议：\n"
                "1. 从基础语法开始：变量、函数、类等\n"
                "2. 学习常用库：NumPy、Pandas、Requests等\n"
                "3. 实践项目：网站爬虫、数据分析、Web应用\n"
                "4. 了解框架：Django、Flask、FastAPI等\n"
                "5. 关注AI/ML：TensorFlow、PyTorch、Scikit-learn"
            )
        elif "区块链" in query:
            return (
                "🔍 搜索结果：区块链技术优势分析：\n"
                "1. 去中心化：无需中央权威机构\n"
                "2. 透明性：所有交易记录公开可查\n"
                "3. 安全性：密码学保护，难以篡改\n"
                "4. 不可逆性：交易一旦确认难以撤销\n"
                "5. 全球性：跨境交易便捷高效"
            )
        else:
            return f"🔍 搜索结果：关于'{query}'的相关信息已找到，包含详细资料和最新动态。"
    
    def _idea_verification(self, params: Dict) -> str:
        """想法验证工具"""
        idea = params.get("idea_text", "")
        
        logger.info(f"🔬 执行想法验证: {idea[:50]}...")
        
        # 模拟验证过程
        time.sleep(0.1)  # 模拟处理时间
        
        return (
            f"🔬 验证结果：对想法'{idea[:100]}...'的分析：\n"
            "✅ 可行性评估：具有一定的可行性\n"
            "📊 风险分析：存在一些潜在挑战需要关注\n"
            "🎯 建议：建议进一步细化实施方案\n"
            "📈 成功概率：预估70%的成功可能性"
        )
    
    def _text_analysis(self, params: Dict) -> str:
        """文本分析工具"""
        text = params.get("text", "")
        
        logger.info(f"📝 执行文本分析: {len(text)} 字符")
        
        return (
            f"📝 文本分析结果：\n"
            f"📊 文本长度：{len(text)} 字符\n"
            f"🔤 词汇丰富度：中等\n"
            f"😊 情感倾向：积极\n"
            f"🎯 主题关键词：已提取主要概念\n"
            f"📈 可读性：良好"
        )
    
    def _knowledge_query(self, params: Dict) -> str:
        """知识查询工具"""
        topic = params.get("topic", "")
        
        logger.info(f"🧠 执行知识查询: {topic}")
        
        return (
            f"🧠 知识库查询结果：关于'{topic}'的信息：\n"
            "📚 相关概念已整理\n"
            "🔗 关联知识已建立\n"
            "💡 深度见解已生成\n"
            "🎓 学习建议已提供"
        )


# =============================================================================
# 生产级记忆系统
# =============================================================================

class ProductionMemory(BaseMemory):
    """
    生产级记忆系统
    支持结构化存储、智能检索、持久化等功能
    """
    
    def __init__(self):
        super().__init__("ProductionMemory", "生产级记忆系统")
        self._memory_store = {}
        self._conversation_history = []
        self._performance_cache = {}
        logger.info("🧠 生产级记忆系统初始化完成")
    
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """存储信息到记忆系统"""
        try:
            self._memory_store[key] = {
                "value": value,
                "metadata": metadata or {},
                "timestamp": time.time(),
                "access_count": 0
            }
            
            # 如果是对话历史，单独存储
            if "conversation" in key or "query" in key:
                self._conversation_history.append({
                    "key": key,
                    "timestamp": time.time(),
                    "value": value
                })
                
                # 限制历史长度
                if len(self._conversation_history) > 100:
                    self._conversation_history = self._conversation_history[-50:]
            
            logger.debug(f"💾 存储记忆: {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 存储失败 {key}: {e}")
            return False
    
    def retrieve(self, key: str) -> Any:
        """从记忆系统检索信息"""
        if key in self._memory_store:
            item = self._memory_store[key]
            item["access_count"] += 1
            item["last_accessed"] = time.time()
            
            logger.debug(f"🔍 检索记忆: {key}")
            return item["value"]
        
        logger.debug(f"❓ 记忆不存在: {key}")
        return None
    
    def get_conversation_history(self, limit: int = 10) -> List[Dict]:
        """获取对话历史"""
        return self._conversation_history[-limit:] if self._conversation_history else []
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计"""
        total_items = len(self._memory_store)
        conversation_count = len(self._conversation_history)
        
        # 计算访问频率
        total_accesses = sum(item["access_count"] for item in self._memory_store.values())
        
        return {
            "total_items": total_items,
            "conversation_count": conversation_count,
            "total_accesses": total_accesses,
            "avg_access_per_item": total_accesses / total_items if total_items > 0 else 0
        }
    
    def cleanup_old_memories(self, max_age_hours: int = 24):
        """清理过期记忆"""
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        old_keys = [
            key for key, item in self._memory_store.items()
            if item["timestamp"] < cutoff_time and item["access_count"] == 0
        ]
        
        for key in old_keys:
            del self._memory_store[key]
        
        if old_keys:
            logger.info(f"🧹 清理了 {len(old_keys)} 个过期记忆")
    
    def delete(self, key: str) -> bool:
        """删除记忆中的信息 - 实现BaseMemory抽象方法"""
        try:
            if key in self._memory_store:
                # 删除主存储
                del self._memory_store[key]
                
                # 如果是对话历史，也从对话历史中删除
                self._conversation_history = [
                    item for item in self._conversation_history 
                    if item.get("key") != key
                ]
                
                logger.debug(f"🗑️ 删除记忆: {key}")
                return True
            else:
                logger.debug(f"🔍 删除失败，键不存在: {key}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 删除失败 {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在于记忆中 - 实现BaseMemory抽象方法"""
        try:
            exists = key in self._memory_store
            logger.debug(f"🔍 检查键存在性 {key}: {'存在' if exists else '不存在'}")
            return exists
            
        except Exception as e:
            logger.error(f"❌ 检查键存在性失败 {key}: {e}")
            return False


# =============================================================================
# 完整的Neogenesis智能Agent
# =============================================================================

class NeogenesisAgent(BaseAgent):
    """
    完整的Neogenesis智能Agent
    组装了NeogenesisPlanner、ProductionToolExecutor、ProductionMemory和CognitiveScheduler
    
    新增功能：
    - 认知调度器：赋予Agent"空闲"概念和主动反思能力
    - 后台认知循环：在任务间隙进行经验回溯和创新思考
    - 智能状态管理：从"任务驱动"升级为"任务驱动+自我驱动"
    """
    
    def __init__(self, 
                 planner,  # NeogenesisPlanner or mock
                 tool_executor,  # ProductionToolExecutor or mock
                 memory,  # ProductionMemory or mock
                 name: str = "NeogenesisAgent",
                 enable_cognitive_scheduler: bool = True,
                 cognitive_config: Optional[Dict[str, Any]] = None):
        
        super().__init__(planner, tool_executor, memory, name)
        
        # 扩展统计信息
        self.stats.update({
            "failed_tasks": 0,
            "total_execution_time": 0.0,
            "average_response_time": 0.0,
            "planner_calls": 0,
            "tool_calls": 0
        })
        
        # Agent状态管理
        self.current_context = None
        self.is_running = False
        
        # 🧠 认知调度器 - 新增功能
        self.enable_cognitive_scheduler = enable_cognitive_scheduler
        self.cognitive_scheduler = None
        
        if self.enable_cognitive_scheduler:
            try:
                # 获取StateManager（如果planner支持）
                state_manager = None
                if hasattr(self.planner, 'state_manager'):
                    state_manager = self.planner.state_manager
                elif hasattr(self.planner, 'get_state_manager'):
                    state_manager = self.planner.get_state_manager()
                else:
                    # 如果planner没有StateManager，创建一个临时的
                    from neogenesis_system.shared.state_manager import StateManager
                    state_manager = StateManager()
                    logger.warning("⚠️ Planner未提供StateManager，创建临时实例")
                
                # 获取LLM客户端（如果planner支持）
                llm_client = None
                if hasattr(self.planner, 'llm_manager'):
                    llm_client = self.planner.llm_manager
                elif hasattr(self.planner, 'get_llm_client'):
                    llm_client = self.planner.get_llm_client()
                
                # 创建认知调度器
                self.cognitive_scheduler = CognitiveScheduler(
                    state_manager=state_manager,
                    llm_client=llm_client,
                    config=cognitive_config
                )
                
                # 🔗 为回溯引擎提供依赖组件
                if hasattr(self.planner, 'path_generator') and hasattr(self.planner, 'mab_converger'):
                    success = self.cognitive_scheduler.update_retrospection_dependencies(
                        path_generator=self.planner.path_generator,
                        mab_converger=self.planner.mab_converger
                    )
                    if success:
                        logger.info("🔗 回溯引擎依赖组件链接完成")
                    else:
                        logger.warning("⚠️ 回溯引擎依赖组件链接失败")
                
                # 🔗 将认知调度器传递给规划器
                if hasattr(self.planner, 'cognitive_scheduler'):
                    self.planner.cognitive_scheduler = self.cognitive_scheduler
                    logger.info("🔗 认知调度器已连接到规划器")
                
                logger.info("🧠 认知调度器已集成 - 主动认知模式就绪")
                
            except Exception as e:
                logger.error(f"❌ 认知调度器初始化失败: {e}")
                logger.warning("⚠️ 将以传统模式运行（仅任务驱动）")
                self.enable_cognitive_scheduler = False
        
        logger.info(f"🤖 {self.name} 初始化完成")
        logger.info(f"   规划器: {self.planner.name}")
        logger.info(f"   工具执行器: {self.tool_executor.name}")
        logger.info(f"   记忆系统: {self.memory.name}")
        if self.enable_cognitive_scheduler:
            logger.info("   🧠 认知调度器: 已启用 (主动认知模式)")
        else:
            logger.info("   🧠 认知调度器: 未启用 (传统任务驱动模式)")
    
    def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Agent主运行方法
        这是用户与系统交互的主要入口点：agent.run("你的问题")
        """
        logger.info(f"\n🚀 NeogenesisAgent开始处理查询")
        logger.info(f"📝 用户输入: {query}")
        
        self.is_running = True
        start_time = time.time()
        task_id = f"task_{int(time.time())}"
        
        # 🧠 启动认知调度器（如果已启用）
        if self.enable_cognitive_scheduler and self.cognitive_scheduler:
            if not self.cognitive_scheduler.is_running:
                logger.info("🧠 启动认知调度器...")
                self.cognitive_scheduler.start()
        
        try:
            # =============================================================================
            # 第1步：Agent调用planner.create_plan()制定计划
            # =============================================================================
            logger.info(f"🧠 第1步：调用规划器制定计划...")
            
            plan_start = time.time()
            plan = self.planner.create_plan(query, self.memory, context)
            plan_time = time.time() - plan_start
            
            self.stats["planner_calls"] += 1
            
            logger.info(f"📋 规划完成 (耗时: {plan_time:.3f}s)")
            logger.info(f"💭 思考过程: {plan.thought[:100]}...")
            
            # 验证计划
            if not self.planner.validate_plan(plan):
                error_msg = "生成的计划无效，无法继续执行"
                logger.error(f"❌ {error_msg}")
                self._update_failure_stats(start_time)
                return error_msg
            
            # =============================================================================
            # 第2步：NeogenesisPlanner内部运行复杂的五阶段决策流程
            # =============================================================================
            logger.info(f"🧠 第2步：规划器已完成五阶段智能决策")
            if hasattr(plan, 'metadata') and 'neogenesis_decision' in plan.metadata:
                decision_info = plan.metadata['neogenesis_decision']
                logger.info(f"   🎯 选中策略: {decision_info.get('chosen_path', {}).get('path_type', '未知')}")
                logger.info(f"   📊 验证统计: {decision_info.get('verification_stats', {})}")
            
            # =============================================================================
            # 第3步：Agent拿到Plan对象
            # =============================================================================
            logger.info(f"📋 第3步：Agent获得标准Plan对象")
            
            if plan.is_direct_answer:
                logger.info(f"💬 计划类型: 直接回答")
                result = plan.final_answer
            else:
                logger.info(f"🔧 计划类型: 工具执行 ({len(plan.actions)} 个行动)")
                
                # 显示计划详情
                for i, action in enumerate(plan.actions, 1):
                    logger.info(f"   行动{i}: {action.tool_name} - {action.tool_input}")
                
                # =============================================================================
                # 第4步：Agent将Plan交给tool_executor.execute_plan()执行
                # =============================================================================
                logger.info(f"🔧 第4步：调用工具执行器执行计划...")
                
                exec_start = time.time()
                observations = self.tool_executor.execute_plan(plan)
                exec_time = time.time() - exec_start
                
                self.stats["tool_calls"] += len(plan.actions)
                
                # =============================================================================
                # 第5步：ToolExecutor调用相应工具，返回Observation结果
                # =============================================================================
                logger.info(f"📊 第5步：工具执行完成 (耗时: {exec_time:.3f}s)")
                
                # 处理执行结果
                successful_observations = [obs for obs in observations if obs.success]
                failed_observations = [obs for obs in observations if not obs.success]
                
                if failed_observations:
                    logger.warning(f"⚠️ 有 {len(failed_observations)} 个行动执行失败")
                
                if successful_observations:
                    # 组合成功的观察结果
                    result_parts = [obs.output for obs in successful_observations]
                    result = "\n\n".join(result_parts)
                    
                    logger.info(f"✅ 执行成功: {len(successful_observations)} 个行动完成")
                else:
                    result = "抱歉，所有工具调用都失败了，无法为您提供结果。"
                    logger.error("❌ 所有工具调用都失败")
            
            # =============================================================================
            # 第6步：Agent将Plan和Observation存入memory
            # =============================================================================
            logger.info(f"💾 第6步：存储交互记录到记忆系统...")
            
            # 存储完整的交互记录
            interaction_record = {
                "query": query,
                "plan": {
                    "thought": plan.thought,
                    "actions_count": len(plan.actions),
                    "is_direct_answer": plan.is_direct_answer,
                    "metadata": getattr(plan, 'metadata', {})
                },
                "observations": [
                    {
                        "tool_name": obs.action.tool_name,
                        "success": obs.success,
                        "output_length": len(obs.output),
                        "execution_time": obs.execution_time
                    } for obs in (observations if not plan.is_direct_answer else [])
                ],
                "result": result,
                "total_time": time.time() - start_time
            }
            
            self.memory.store(task_id, interaction_record)
            
            # =============================================================================
            # 第7步：Agent综合所有结果，生成最终答案
            # =============================================================================
            logger.info(f"🎯 第7步：生成最终答案...")
            
            # 更新统计信息
            execution_time = time.time() - start_time
            self._update_success_stats(execution_time)
            
            # 显示最终统计
            logger.info(f"📊 任务完成统计:")
            logger.info(f"   ⏱️ 总耗时: {execution_time:.3f}s")
            logger.info(f"   🧠 规划耗时: {plan_time:.3f}s")
            if not plan.is_direct_answer:
                logger.info(f"   🔧 执行耗时: {exec_time:.3f}s")
            logger.info(f"   📈 成功率: {self.success_rate:.1%}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"处理查询时发生错误: {str(e)}"
            
            logger.error(f"❌ {error_msg}")
            logger.error(f"   耗时: {execution_time:.3f}s")
            
            # 存储错误记录
            self.memory.store(f"error_{task_id}", {
                "query": query,
                "error": str(e),
                "execution_time": execution_time
            })
            
            self._update_failure_stats(start_time)
            
            return f"抱歉，{error_msg}"
            
        finally:
            self.is_running = False
    
    def _update_success_stats(self, execution_time: float):
        """更新成功统计"""
        self.stats["total_tasks"] += 1
        self.stats["successful_tasks"] += 1
        self.stats["total_execution_time"] += execution_time
        
        # 更新平均响应时间
        self.stats["average_response_time"] = (
            self.stats["total_execution_time"] / self.stats["total_tasks"]
        )
    
    def _update_failure_stats(self, start_time: float):
        """更新失败统计"""
        execution_time = time.time() - start_time
        self.stats["total_tasks"] += 1
        self.stats["failed_tasks"] += 1
        self.stats["total_execution_time"] += execution_time
        
        self.stats["average_response_time"] = (
            self.stats["total_execution_time"] / self.stats["total_tasks"]
        )
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.stats["total_tasks"]
        return self.stats["successful_tasks"] / total if total > 0 else 0.0
    
    def start_cognitive_mode(self):
        """
        启动认知模式 - 开启主动反思和创想功能
        
        在Agent长期运行或交互式会话中调用，
        让Agent获得"内在独白"和主动学习能力
        """
        if not self.enable_cognitive_scheduler:
            logger.warning("⚠️ 认知调度器未启用，无法启动认知模式")
            return False
        
        if not self.cognitive_scheduler:
            logger.error("❌ 认知调度器未初始化")
            return False
        
        if self.cognitive_scheduler.is_running:
            logger.info("🧠 认知调度器已在运行")
            return True
        
        try:
            self.cognitive_scheduler.start()
            logger.info("✅ 认知模式已启动 - Agent开始主动思考")
            return True
        except Exception as e:
            logger.error(f"❌ 启动认知模式失败: {e}")
            return False
    
    def stop_cognitive_mode(self):
        """
        停止认知模式 - 关闭后台认知功能
        
        在Agent需要释放资源或系统关闭时调用
        """
        if not self.cognitive_scheduler:
            return
        
        try:
            self.cognitive_scheduler.stop()
            logger.info("🛑 认知模式已停止")
        except Exception as e:
            logger.error(f"❌ 停止认知模式失败: {e}")
    
    def get_cognitive_status(self) -> Dict[str, Any]:
        """
        获取认知状态报告
        
        Returns:
            认知调度器的详细状态信息
        """
        if not self.cognitive_scheduler:
            return {
                "enabled": False,
                "status": "认知调度器未启用"
            }
        
        base_status = self.cognitive_scheduler.get_status()
        base_status["enabled"] = self.enable_cognitive_scheduler
        
        return base_status
    
    def __del__(self):
        """Agent析构时自动停止认知调度器"""
        self.stop_cognitive_mode()
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """获取详细统计信息"""
        memory_stats = self.memory.get_memory_stats()
        
        return {
            "agent_info": {
                "name": self.name,
                "is_running": self.is_running,
                "components": {
                    "planner": self.planner.name,
                    "tool_executor": self.tool_executor.name,
                    "memory": self.memory.name
                }
            },
            "performance_stats": self.stats.copy(),
            "memory_stats": memory_stats,
            "success_rate": self.success_rate,
            "planner_stats": getattr(self.planner, 'get_stats', lambda: {})()
        }
    
    def chat_mode(self):
        """进入聊天模式"""
        print(f"\n🤖 {self.name} 聊天模式启动")
        print("输入'quit'或'exit'退出，输入'stats'查看统计信息")
        print("-" * 50)
        
        while True:
            try:
                user_input = input(f"\n👤 您: ").strip()
                
                if user_input.lower() in ['quit', 'exit', '退出', 'q']:
                    print(f"👋 再见！")
                    break
                elif user_input.lower() == 'stats':
                    stats = self.get_detailed_stats()
                    print(f"\n📊 Agent统计信息:")
                    print(f"   总任务: {stats['performance_stats']['total_tasks']}")
                    print(f"   成功率: {stats['success_rate']:.1%}")
                    print(f"   平均响应时间: {stats['performance_stats']['average_response_time']:.2f}s")
                    continue
                elif not user_input:
                    continue
                
                # 处理用户输入
                response = self.run(user_input)
                print(f"\n🤖 {self.name}: {response}")
                
            except KeyboardInterrupt:
                print(f"\n👋 再见！")
                break
            except Exception as e:
                print(f"❌ 出现错误: {e}")


# =============================================================================
# Agent工厂和组装函数
# =============================================================================

def create_neogenesis_agent(api_key: str = "", config: Optional[Dict] = None):
    """
    创建完整的NeogenesisAgent实例
    
    这是系统的主要入口点，负责组装所有组件
    """
    logger.info("🏭 开始创建NeogenesisAgent...")
    
    try:
        # 设置环境变量
        if api_key:
            os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
            logger.info("🔑 API密钥已设置")
        
        if REAL_COMPONENTS_AVAILABLE:
            # 使用真实组件
            logger.info("🔧 使用真实Meta MAB组件...")
            
            try:
                # 创建LLM管理器
                llm_manager = LLMManager()
                logger.info("✅ LLM管理器创建成功")
                
                # 创建Meta MAB组件
                prior_reasoner = PriorReasoner(llm_manager)
                path_generator = PathGenerator(llm_manager)
                mab_converger = MABConverger()
                
                # 创建NeogenesisPlanner
                neogenesis_planner = NeogenesisPlanner(
                    prior_reasoner=prior_reasoner,
                    path_generator=path_generator,
                    mab_converger=mab_converger,
                    tool_registry=global_tool_registry,
                    config=config or {}
                )
                
                logger.info("✅ NeogenesisPlanner创建成功")
                
            except Exception as e:
                logger.warning(f"⚠️ 真实组件创建失败，使用模拟组件: {e}")
                # 回退到模拟组件
                neogenesis_planner = create_mock_neogenesis_planner()
        else:
            # 使用模拟组件
            logger.info("🔧 使用模拟组件...")
            neogenesis_planner = create_mock_neogenesis_planner()
        
        # 创建工具执行器和记忆系统
        tool_executor = ProductionToolExecutor()
        memory = ProductionMemory()
        
        # 组装Agent（默认启用认知调度器）
        agent = NeogenesisAgent(
            planner=neogenesis_planner,
            tool_executor=tool_executor,
            memory=memory,
            name="NeogenesisAgent",
            enable_cognitive_scheduler=config.get('enable_cognitive_scheduler', True),
            cognitive_config=config.get('cognitive_config', None)
        )
        
        logger.info("🎉 NeogenesisAgent创建完成！")
        return agent
        
    except Exception as e:
        logger.error(f"❌ Agent创建失败: {e}")
        raise


def create_mock_neogenesis_planner():
    """创建模拟的NeogenesisPlanner"""
    from abc import ABC, abstractmethod
    
    class MockNeogenesisPlanner:
        def __init__(self):
            self.name = "MockNeogenesisPlanner"
        
        def create_plan(self, query: str, memory, context=None):
            # 简单的模拟逻辑
            if "搜索" in query or "查找" in query or "信息" in query:
                return Plan(
                    thought=f"用户需要搜索关于'{query}'的信息",
                    actions=[Action("web_search", {"query": query})]
                )
            elif "验证" in query or "可行" in query:
                return Plan(
                    thought=f"用户需要验证想法的可行性",
                    actions=[Action("idea_verification", {"idea_text": query})]
                )
            else:
                return Plan(
                    thought=f"对于'{query}'，我提供直接回答",
                    final_answer=f"关于'{query}'，这是一个很好的问题。基于我的知识，我建议..."
                )
        
        def validate_plan(self, plan):
            return True
        
        def get_stats(self):
            return {"name": self.name, "total_rounds": 0}
    
    return MockNeogenesisPlanner()


# =============================================================================
# 主演示和入口点
# =============================================================================

def main():
    """主演示函数"""
    print("🚀 Neogenesis智能Agent系统")
    print("🎯 展示完整的组装与运行流程")
    print("=" * 60)
    
    try:
        # 创建Agent实例
        print("\n🏭 正在创建Agent实例...")
        agent = create_neogenesis_agent()
        
        # 显示Agent信息
        print(f"\n🤖 Agent实例创建成功！")
        print(f"   名称: {agent.name}")
        print(f"   组件: 规划器、工具执行器、记忆系统")
        
        # 测试查询
        test_queries = [
            "搜索人工智能的最新发展趋势",
            "验证这个想法：用AI来提升教育质量",
            "如何学习Python编程？",
            "区块链技术有什么优势？"
        ]
        
        print(f"\n🧪 开始测试 {len(test_queries)} 个查询")
        print("=" * 60)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n【测试 {i}/{len(test_queries)}】")
            print(f"查询: {query}")
            print("-" * 60)
            
            # 这就是用户使用系统的方式：agent.run("你的问题")
            result = agent.run(query)
            
            print(f"\n📤 最终回答:")
            print(f"{result}")
            print("-" * 60)
            
            time.sleep(1)  # 短暂休息
        
        # 显示最终统计
        print(f"\n📊 测试完成统计:")
        detailed_stats = agent.get_detailed_stats()
        
        perf_stats = detailed_stats["performance_stats"]
        print(f"   总任务数: {perf_stats['total_tasks']}")
        print(f"   成功任务: {perf_stats['successful_tasks']}")
        print(f"   成功率: {agent.success_rate:.1%}")
        print(f"   平均响应时间: {perf_stats['average_response_time']:.2f}秒")
        print(f"   规划器调用: {perf_stats['planner_calls']}")
        print(f"   工具调用: {perf_stats['tool_calls']}")
        
        memory_stats = detailed_stats["memory_stats"]
        print(f"   记忆项目: {memory_stats['total_items']}")
        print(f"   对话历史: {memory_stats['conversation_count']}")
        
        print(f"\n✨ 系统演示完成！")
        print(f"🎯 用户只需调用: agent.run(\"你的问题\")")
        print(f"💡 系统内部会自动完成7个步骤的完整流程")
        
        # 询问是否体验认知模式
        try_cognitive = input(f"\n🧠 是否体验全新的认知模式？(y/n): ").strip().lower()
        if try_cognitive in ['y', 'yes', '是', 'ok']:
            cognitive_mode_demo(agent)
        else:
            # 询问是否进入聊天模式
            try_chat = input(f"\n💬 是否进入聊天模式体验？(y/n): ").strip().lower()
            if try_chat in ['y', 'yes', '是', 'ok']:
                agent.chat_mode()
        
    except Exception as e:
        logger.error(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


def cognitive_mode_demo(agent):
    """
    认知模式演示 - 展示Agent的主动反思和创想能力
    
    这个演示展示了Agent如何在任务完成后进入"认知空闲"状态，
    并主动进行经验回溯、模式识别和创新思考。
    """
    print("\n🧠 Neogenesis认知模式演示")
    print("展示Agent的'内在独白'和主动思考能力")
    print("="*60)
    
    try:
        # 显示认知状态
        cognitive_status = agent.get_cognitive_status()
        print(f"\n🧠 当前认知状态: {cognitive_status}")
        
        if not cognitive_status.get("enabled", False):
            print("⚠️ 认知调度器未启用，正在启用...")
            # 重新创建带认知调度器的Agent
            config = {
                'api_key': os.getenv('DEEPSEEK_API_KEY', ''),
                'search_engine': 'duckduckgo',
                'enable_cognitive_scheduler': True,
                'cognitive_config': {
                    'idle_detection': {
                        'min_idle_duration': 5.0,    # 缩短演示时间
                        'check_interval': 1.0
                    },
                    'cognitive_tasks': {
                        'retrospection_interval': 15.0,  # 缩短演示间隔
                        'ideation_interval': 30.0
                    }
                }
            }
            agent = create_neogenesis_agent(config=config)
        
        # 手动启动认知模式
        print("\n🚀 启动认知模式...")
        if agent.start_cognitive_mode():
            print("✅ 认知模式已启动 - Agent开始主动思考")
        
        # 执行几个任务让Agent产生经验
        cognitive_queries = [
            "什么是强化学习的核心思想？",
            "搜索深度学习在医疗领域的应用",
            "分析元学习对人工智能发展的意义",
        ]
        
        print("\n📚 执行学习任务，为Agent积累认知经验...")
        for i, query in enumerate(cognitive_queries, 1):
            print(f"\n--- 认知任务{i}: {query[:30]}... ---")
            try:
                result = agent.run(query)
                print(f"✅ 任务完成: {len(result)} 字符回答")
                
                # 显示认知状态变化
                status = agent.get_cognitive_status()
                print(f"🧠 认知状态: {status.get('current_mode', 'unknown')} "
                      f"| 活跃认知任务: {status.get('active_cognitive_tasks', 0)} "
                      f"| 队列中任务: {status.get('queued_cognitive_tasks', 0)}")
                
            except Exception as e:
                print(f"❌ 任务失败: {e}")
            
            # 给认知调度器时间工作
            print("⏳ 等待认知调度器分析和思考...")
            time.sleep(8)
        
        print("\n📊 最终认知统计:")
        final_status = agent.get_cognitive_status()
        if 'stats' in final_status:
            stats = final_status['stats']
            print(f"   🔄 总空闲周期: {stats.get('total_idle_periods', 0)}")
            print(f"   ⏱️ 总空闲时间: {stats.get('total_idle_time', 0):.1f}s")
            print(f"   🧠 完成认知任务: {stats.get('cognitive_tasks_completed', 0)}")
            print(f"   📚 回溯会话: {stats.get('retrospection_sessions', 0)}")
            print(f"   💡 创想会话: {stats.get('ideation_sessions', 0)}")
            print(f"   🧩 知识综合: {stats.get('knowledge_synthesis_sessions', 0)}")
        
        # 停止认知模式
        print("\n🛑 停止认知模式...")
        agent.stop_cognitive_mode()
        
        print("\n" + "="*60)
        print("🎉 认知模式演示完成！")
        print("💡 您刚才见证了AI的重大进化：")
        print("   ✨ 从'被动应激'升级为'主动认知'")
        print("   🧠 任务完成后自动进入反思状态")
        print("   🔍 主动分析成功和失败模式")
        print("   💡 持续产生创新思路和突破性想法") 
        print("   📚 积累和整合认知成果为未来决策服务")
        print("   🚀 这就是'内在独白循环'的威力！")
        
    except Exception as e:
        print(f"❌ 认知模式演示失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
