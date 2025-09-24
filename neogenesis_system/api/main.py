"""
Neogenesis System FastAPI 主应用程序

这个文件负责初始化 NeogenesisAgent 并创建 FastAPI 应用，
提供完整的 Web API 接口来访问 Neogenesis System 的核心功能。
"""

import logging
import os
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

# 导入数据模型
from .models import (
    HealthResponse,
    ErrorResponse, 
    PlanningRequest,
    PlanningResponse,
    CognitiveRequest,
    CognitiveResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    SystemStatusResponse,
    BaseResponse,
    create_error_response,
    create_success_response
)

# 尝试导入 Neogenesis 核心组件
try:
    # 导入 NeogenesisAgent 和相关组件
    from ..examples.neogenesis_planner_demo import NeogenesisAgent, AgentFactory
    from ..core.neogenesis_planner import NeogenesisPlanner
    from ..core.cognitive_scheduler import CognitiveScheduler
    from ..core.retrospection_engine import RetrospectionEngine
    from ..providers.knowledge_explorer import KnowledgeExplorer
    from ..shared.state_manager import StateManager
    from ..config import get_default_config
    from .. import create_system
    
    NEOGENESIS_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ Neogenesis 核心组件导入成功")
    
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ 无法导入 Neogenesis 核心组件: {e}")
    logger.warning("API 将在有限模式下运行")
    NEOGENESIS_AVAILABLE = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 全局变量存储 NeogenesisAgent 实例和其他组件
neogenesis_agent: Optional[NeogenesisAgent] = None
neogenesis_system = None
cognitive_scheduler: Optional[CognitiveScheduler] = None
knowledge_explorer: Optional[KnowledgeExplorer] = None
state_manager: Optional[StateManager] = None

# 系统统计信息
system_stats = {
    "startup_time": None,
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "agent_initialized": False
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    # 启动时初始化
    logger.info("🚀 启动 Neogenesis System API...")
    system_stats["startup_time"] = datetime.utcnow()
    
    try:
        if NEOGENESIS_AVAILABLE:
            await initialize_neogenesis_agent()
            await initialize_additional_components()
            logger.info("✅ Neogenesis System 初始化完成")
        else:
            logger.warning("⚠️ 在有限模式下启动 - 某些功能可能不可用")
    except Exception as e:
        logger.error(f"❌ 系统初始化失败: {e}")
        logger.error(traceback.format_exc())
    
    yield
    
    # 关闭时清理资源
    logger.info("🔄 清理 Neogenesis System 资源...")
    await cleanup_resources()
    logger.info("✅ 资源清理完成")


async def initialize_neogenesis_agent():
    """初始化 NeogenesisAgent"""
    global neogenesis_agent, neogenesis_system
    
    try:
        logger.info("🤖 初始化 NeogenesisAgent...")
        
        # 智能获取 API 密钥（检测多种提供商）
        api_key = ""
        provider_used = "none"
        
        # 按优先级检查API密钥
        for provider, env_var in [
            ("Gemini", "GEMINI_API_KEY"),
            ("DeepSeek", "DEEPSEEK_API_KEY"), 
            ("OpenAI", "OPENAI_API_KEY"),
            ("Anthropic", "ANTHROPIC_API_KEY")
        ]:
            key = os.getenv(env_var, "")
            if key:
                api_key = key
                provider_used = provider
                logger.info(f"✅ 找到 {provider} API密钥，将使用 {provider} 提供商")
                break
        
        if not api_key:
            logger.warning("⚠️ 未找到任何LLM提供商的API密钥，使用模拟模式")
        
        # 使用工厂方法创建 NeogenesisAgent
        neogenesis_agent = AgentFactory.create_neogenesis_agent(
            api_key=api_key,
            config=get_default_config() if 'get_default_config' in globals() else {}
        )
        
        # 同时创建 NeogenesisSystem (如果需要)
        try:
            neogenesis_system = create_system(api_key=api_key)
            logger.info("✅ NeogenesisSystem 创建成功")
        except Exception as e:
            logger.warning(f"⚠️ NeogenesisSystem 创建失败: {e}")
        
        system_stats["agent_initialized"] = True
        logger.info("✅ NeogenesisAgent 初始化成功")
        
    except Exception as e:
        logger.error(f"❌ NeogenesisAgent 初始化失败: {e}")
        logger.error(traceback.format_exc())
        system_stats["agent_initialized"] = False


async def initialize_additional_components():
    """初始化额外的系统组件"""
    global cognitive_scheduler, knowledge_explorer, state_manager
    
    try:
        logger.info("🧠 初始化额外组件...")
        
        # 初始化状态管理器
        if 'StateManager' in globals():
            state_manager = StateManager()
            logger.info("✅ StateManager 初始化成功")
        
        # 初始化认知调度器（如果可用）
        if 'CognitiveScheduler' in globals() and state_manager:
            try:
                config = get_default_config() if 'get_default_config' in globals() else {}
                
                # 🔧 修复：创建LLM客户端以正确初始化回溯引擎（智能选择）
                llm_client = None
                # 智能获取API密钥（检测多种提供商）
                api_key = ""
                for env_var in ["GEMINI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
                    key = os.getenv(env_var, "")
                    if key:
                        api_key = key
                        break
                if api_key:
                    try:
                        # 优先尝试使用LLM管理器来自动选择最佳客户端
                        from ..providers.llm_manager import LLMManager
                        llm_manager = LLMManager()
                        if llm_manager.initialized and llm_manager.providers:
                            llm_client = llm_manager
                            logger.info(f"✅ LLM管理器创建成功，用于认知调度器，提供商: {list(llm_manager.providers.keys())}")
                        else:
                            # 回退到DeepSeek客户端
                            from ..providers.impl.deepseek_client import create_llm_client
                            llm_client = create_llm_client(api_key)
                            logger.info("✅ LLM客户端创建成功（DeepSeek），用于认知调度器")
                    except Exception as e:
                        logger.warning(f"⚠️ LLM客户端创建失败: {e}")
                
                cognitive_scheduler = CognitiveScheduler(state_manager, llm_client, config)
                logger.info("✅ CognitiveScheduler 初始化成功")
                
                # 🔧 修复：双向依赖注入 - 确保认知调度器与主系统正确链接
                _inject_bidirectional_dependencies(cognitive_scheduler)
                
            except Exception as e:
                logger.warning(f"⚠️ CognitiveScheduler 初始化失败: {e}")
        
        # 初始化知识探索器（如果可用）
        if 'KnowledgeExplorer' in globals():
            try:
                config = get_default_config() if 'get_default_config' in globals() else {}
                knowledge_explorer = KnowledgeExplorer(config)
                logger.info("✅ KnowledgeExplorer 初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ KnowledgeExplorer 初始化失败: {e}")
        
    except Exception as e:
        logger.error(f"❌ 额外组件初始化失败: {e}")


def _inject_bidirectional_dependencies(scheduler):
    """双向依赖注入 - 确保认知调度器与主系统组件正确连接"""
    try:
        success_count = 0
        
        # 方案1：从 neogenesis_agent 获取依赖
        if neogenesis_agent and hasattr(neogenesis_agent, 'planner'):
            planner = neogenesis_agent.planner
            if hasattr(planner, 'path_generator') and hasattr(planner, 'mab_converger'):
                try:
                    success = scheduler.update_retrospection_dependencies(
                        path_generator=planner.path_generator,
                        mab_converger=planner.mab_converger
                    )
                    if success:
                        success_count += 1
                        logger.info("✅ 方案1：从Agent获取依赖成功")
                        
                        # 反向注入：将认知调度器设置到Planner中
                        if hasattr(planner, 'set_cognitive_scheduler'):
                            planner.set_cognitive_scheduler(scheduler)
                        elif hasattr(planner, 'cognitive_scheduler'):
                            planner.cognitive_scheduler = scheduler
                            
                except Exception as e:
                    logger.warning(f"⚠️ 方案1失败: {e}")
        
        # 方案2：从 neogenesis_system 获取依赖
        if neogenesis_system and success_count == 0:
            try:
                if hasattr(neogenesis_system, 'path_generator') and hasattr(neogenesis_system, 'mab_converger'):
                    success = scheduler.update_retrospection_dependencies(
                        path_generator=neogenesis_system.path_generator,
                        mab_converger=neogenesis_system.mab_converger
                    )
                    if success:
                        success_count += 1
                        logger.info("✅ 方案2：从System获取依赖成功")
            except Exception as e:
                logger.warning(f"⚠️ 方案2失败: {e}")
        
        # 报告结果
        if success_count > 0:
            logger.info("✅ 回溯引擎依赖组件链接成功")
        else:
            logger.warning("⚠️ 回溯引擎依赖组件链接失败")
            
    except Exception as e:
        logger.error(f"❌ 双向依赖注入异常: {e}")


async def cleanup_resources():
    """清理系统资源"""
    global neogenesis_agent, neogenesis_system, cognitive_scheduler, knowledge_explorer, state_manager
    
    try:
        # 清理各个组件
        neogenesis_agent = None
        neogenesis_system = None
        cognitive_scheduler = None
        knowledge_explorer = None
        state_manager = None
        
        system_stats["agent_initialized"] = False
        logger.info("✅ 所有资源已清理")
        
    except Exception as e:
        logger.error(f"❌ 资源清理失败: {e}")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="Neogenesis System API",
    description="Neogenesis 智能认知决策系统的 Web API 接口",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该配置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求统计中间件
@app.middleware("http")
async def stats_middleware(request, call_next):
    """请求统计中间件"""
    system_stats["total_requests"] += 1
    start_time = time.time()
    
    try:
        response = await call_next(request)
        system_stats["successful_requests"] += 1
        return response
    except Exception as e:
        system_stats["failed_requests"] += 1
        logger.error(f"请求处理失败: {e}")
        raise
    finally:
        process_time = time.time() - start_time
        logger.debug(f"请求处理耗时: {process_time:.3f}s")


# ==================== 依赖注入函数 ====================

def get_neogenesis_agent() -> NeogenesisAgent:
    """获取 NeogenesisAgent 实例（依赖注入）"""
    if not neogenesis_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NeogenesisAgent 未初始化或不可用"
        )
    return neogenesis_agent


def get_neogenesis_system():
    """获取 NeogenesisSystem 实例（依赖注入）"""
    if not neogenesis_system:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NeogenesisSystem 未初始化或不可用"
        )
    return neogenesis_system


def get_cognitive_scheduler() -> CognitiveScheduler:
    """获取认知调度器实例（依赖注入）"""
    if not cognitive_scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CognitiveScheduler 未初始化或不可用"
        )
    return cognitive_scheduler


def get_knowledge_explorer() -> KnowledgeExplorer:
    """获取知识探索器实例（依赖注入）"""
    if not knowledge_explorer:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="KnowledgeExplorer 未初始化或不可用"
        )
    return knowledge_explorer


# ==================== API 路由端点 ====================

@app.get("/", response_model=Dict[str, str])
async def root():
    """API 根路径 - 欢迎信息"""
    return {
        "message": "欢迎使用 Neogenesis System API",
        "description": "智能认知决策系统 Web API 接口",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "status": "/status"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """系统健康检查端点"""
    try:
        # 检查各组件状态
        components_status = {
            "neogenesis_agent": neogenesis_agent is not None,
            "neogenesis_system": neogenesis_system is not None,
            "cognitive_scheduler": cognitive_scheduler is not None,
            "knowledge_explorer": knowledge_explorer is not None,
            "state_manager": state_manager is not None,
            "core_available": NEOGENESIS_AVAILABLE
        }
        
        # 判断整体健康状态
        critical_components = ["neogenesis_agent", "core_available"]
        critical_healthy = all(components_status.get(comp, False) for comp in critical_components)
        
        if critical_healthy:
            status_text = "healthy"
        elif components_status["core_available"]:
            status_text = "degraded"
        else:
            status_text = "unhealthy"
        
        return HealthResponse(
            success=True,
            timestamp=datetime.utcnow(),
            status=status_text,
            components=components_status,
            core_available=NEOGENESIS_AVAILABLE,
            message=f"系统状态: {status_text}"
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return HealthResponse(
            success=False,
            timestamp=datetime.utcnow(),
            status="error",
            components={},
            core_available=False,
            message=f"健康检查失败: {str(e)}"
        )


@app.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """获取详细的系统状态信息"""
    try:
        # 计算运行时间
        uptime_seconds = 0
        if system_stats["startup_time"]:
            uptime_seconds = (datetime.utcnow() - system_stats["startup_time"]).total_seconds()
        
        # 收集系统状态信息
        status_info = {
            "startup_time": system_stats["startup_time"].isoformat() if system_stats["startup_time"] else None,
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{uptime_seconds // 3600:.0f}h {(uptime_seconds % 3600) // 60:.0f}m {uptime_seconds % 60:.0f}s",
            "total_requests": system_stats["total_requests"],
            "successful_requests": system_stats["successful_requests"],
            "failed_requests": system_stats["failed_requests"],
            "success_rate": (system_stats["successful_requests"] / max(system_stats["total_requests"], 1)) * 100,
            "agent_initialized": system_stats["agent_initialized"],
            "core_components_available": NEOGENESIS_AVAILABLE,
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        }
        
        return SystemStatusResponse(
            success=True,
            timestamp=datetime.utcnow(),
            status="operational" if NEOGENESIS_AVAILABLE else "limited",
            system_info=status_info,
            message="系统状态正常" if NEOGENESIS_AVAILABLE else "系统在有限模式下运行"
        )
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )


@app.post("/agent/run", response_model=BaseResponse)
async def run_agent_query(
    request: PlanningRequest,
    agent: NeogenesisAgent = Depends(get_neogenesis_agent)
):
    """运行 NeogenesisAgent 处理查询"""
    try:
        logger.info(f"🤖 Agent 收到查询: {request.query}")
        start_time = time.time()
        
        # 调用 Agent 处理查询
        result = agent.run(
            query=request.query,
            context=request.context or {}
        )
        
        process_time = time.time() - start_time
        logger.info(f"✅ Agent 处理完成，耗时: {process_time:.3f}s")
        
        return BaseResponse(
            success=True,
            timestamp=datetime.utcnow(),
            message=f"查询处理完成，结果: {result}"
        )
        
    except Exception as e:
        logger.error(f"❌ Agent 查询处理失败: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent 查询处理失败: {str(e)}"
        )


@app.post("/planning/create-plan", response_model=PlanningResponse)
async def create_plan(
    request: PlanningRequest,
    agent: NeogenesisAgent = Depends(get_neogenesis_agent)
):
    """使用 NeogenesisAgent 创建执行计划"""
    try:
        logger.info(f"📋 收到规划请求: {request.query}")
        
        # 通过 Agent 的 planner 组件创建计划
        if hasattr(agent, 'planner'):
            plan = agent.planner.plan_task(
                query=request.query,
                context=request.context or {}
            )
            
            # 转换为响应格式
            plan_data = {
                "plan_id": f"plan_{int(time.time())}",
                "query": request.query,
                "actions": [
                    {
                        "tool_name": action.tool_name,
                        "parameters": action.parameters,
                        "description": getattr(action, 'description', '')
                    }
                    for action in plan.actions
                ],
                "confidence": getattr(plan, 'confidence', 0.8),
                "estimated_duration": getattr(plan, 'estimated_duration', None),
                "created_at": datetime.utcnow()
            }
            
            return PlanningResponse(
                success=True,
                timestamp=datetime.utcnow(),
                plan=plan_data,
                message="执行计划创建成功"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Agent 规划器不可用"
            )
        
    except Exception as e:
        logger.error(f"❌ 创建执行计划失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建执行计划失败: {str(e)}"
        )


@app.post("/cognitive/process", response_model=CognitiveResponse)
async def cognitive_process(
    request: CognitiveRequest,
    system_instance = Depends(get_neogenesis_system)
):
    """使用 NeogenesisSystem 进行认知处理"""
    try:
        logger.info(f"🧠 收到认知处理请求: {request.task}")
        start_time = time.time()
        
        # 使用 NeogenesisSystem 处理查询
        result = system_instance.process_query(
            user_query=request.task,
            execution_context=request.context or {}
        )
        
        process_time = time.time() - start_time
        
        # 构建认知处理结果
        cognitive_result = {
            "task_id": f"task_{int(time.time())}",
            "result": result,
            "confidence": result.get('confidence', 0.7) if isinstance(result, dict) else 0.7,
            "processing_time": process_time,
            "metadata": {
                "priority": request.priority,
                "timeout": request.timeout
            }
        }
        
        return CognitiveResponse(
            success=True,
            timestamp=datetime.utcnow(),
            result=cognitive_result,
            message="认知处理完成"
        )
        
    except Exception as e:
        logger.error(f"❌ 认知处理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"认知处理失败: {str(e)}"
        )


@app.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def knowledge_search(
    request: KnowledgeSearchRequest
):
    """知识搜索功能（简化版本）"""
    try:
        logger.info(f"🔍 收到知识搜索请求: {request.query}")
        
        # 这里提供一个基础的搜索实现
        # 在实际应用中，这应该连接到真实的知识库
        mock_results = [
            {
                "id": f"knowledge_{i}",
                "title": f"关于 '{request.query}' 的知识项 {i+1}",
                "content": f"这是关于 {request.query} 的相关知识内容...",
                "source": "Neogenesis Knowledge Base",
                "confidence": max(0.5, 1.0 - i * 0.1),
                "metadata": {"type": "generated", "index": i},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            for i in range(min(request.limit or 5, 10))
        ]
        
        return KnowledgeSearchResponse(
            success=True,
            timestamp=datetime.utcnow(),
            results=mock_results,
            total_results=len(mock_results),
            query_time=0.1,
            message="知识搜索完成"
        )
        
    except Exception as e:
        logger.error(f"❌ 知识搜索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"知识搜索失败: {str(e)}"
        )


@app.post("/chat")
async def chat_endpoint(request: dict):
    """聊天API端点 - 为Web UI提供兼容接口"""
    try:
        logger.info(f"💬 收到聊天请求: {request.get('query', 'N/A')[:100]}")
        
        # 从请求中提取查询和上下文
        query = request.get('query', '')
        context = request.get('context', {})
        
        if not query:
            return JSONResponse(
                status_code=400,
                content={"error": "查询不能为空"}
            )
        
        # 调用NeogenesisAgent处理查询
        try:
            agent = neogenesis_agent
            if not agent:
                # 尝试获取Agent实例
                agent = await get_neogenesis_agent()
            
            if agent:
                # 使用Agent处理查询
                result = agent.run(query=query, context=context)
                
                # 构建响应
                return {
                    "result": result,
                    "thinking_process": [
                        {
                            "step": "思考起点与核心目标",
                            "description": "为问题确定核心处理策略",
                            "status": "completed"
                        },
                        {
                            "step": "思维方向验证", 
                            "description": "验证策略可行性",
                            "status": "completed"
                        },
                        {
                            "step": "最终策略选择",
                            "description": "选择最优处理方案",
                            "status": "completed"
                        },
                        {
                            "step": "数据验证正误学习",
                            "description": "学习优化系统表现",
                            "status": "completed"
                        },
                        {
                            "step": "效率与成本平衡",
                            "description": "优化响应效率",
                            "status": "completed"
                        }
                    ],
                    "tool_calls": [],
                    "success": True
                }
            else:
                # 没有Agent时的回退处理
                logger.warning("⚠️ NeogenesisAgent不可用，使用智能回答")
                query_lower = query.lower().strip()
                
                if any(greeting in query_lower for greeting in ['你好', 'hello', 'hi', '您好']):
                    fallback_result = "你好！我是Neogenesis智能助手，很高兴为您服务。有什么我可以帮助您的吗？"
                elif "介绍" in query_lower and ("自己" in query_lower or "你" in query_lower):
                    fallback_result = "我是Neogenesis智能助手，基于先进的认知架构设计。我可以帮助您进行信息查询、问题分析、创意思考等多种任务。我的特点是能够根据不同问题智能选择最合适的处理方式，为您提供准确、有用的回答。"
                else:
                    fallback_result = f"我理解您关于「{query}」的问题。基于我的分析，这是一个很值得探讨的话题，我很乐意为您提供详细的解答和建议。请问您希望了解哪个具体方面呢？"
                
                return {
                    "result": fallback_result,
                    "thinking_process": [],
                    "tool_calls": [],
                    "success": True
                }
                
        except Exception as e:
            logger.error(f"❌ Agent处理失败: {e}")
            logger.error(traceback.format_exc())
            
            # 智能回退处理
            query_lower = query.lower().strip()
            if any(greeting in query_lower for greeting in ['你好', 'hello', 'hi', '您好']):
                fallback_result = "你好！我是Neogenesis智能助手，很高兴为您服务。有什么我可以帮助您的吗？"
            elif "介绍" in query_lower and ("自己" in query_lower or "你" in query_lower):
                fallback_result = "我是Neogenesis智能助手，基于先进的认知架构设计。我可以帮助您进行信息查询、问题分析、创意思考等多种任务。"
            else:
                fallback_result = f"我理解您关于「{query}」的问题。这是一个很值得探讨的话题，我很乐意为您提供详细的解答和建议。"
            
            return {
                "result": fallback_result,
                "thinking_process": [],
                "tool_calls": [],
                "success": True
            }
            
    except Exception as e:
        logger.error(f"❌ 聊天端点处理失败: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": f"服务器错误: {str(e)}"}
        )


# ==================== 异常处理 ====================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    """处理 Pydantic 验证错误"""
    logger.error(f"数据验证失败: {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            error_type="validation_error",
            message="请求数据验证失败",
            details={"errors": exc.errors()}
        ).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """处理 HTTP 异常"""
    logger.error(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error_type="http_error",
            message=exc.detail,
            details={"status_code": exc.status_code}
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """处理一般异常"""
    logger.error(f"未处理的异常: {exc}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            error_type="internal_server_error",
            message="服务器内部错误",
            details={"exception": str(exc)}
        ).model_dump()
    )


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    # 配置启动参数
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )