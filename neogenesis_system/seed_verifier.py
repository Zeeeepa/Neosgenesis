"""
种子验证器模块 - 专门负责思维种子的验证和增强逻辑

本模块从 NeogenesisPlanner 中提取出来，实现职责单一化：
- 负责阶段二的种子验证和增强逻辑
- 智能规划验证搜索维度
- 执行信息搜索和种子增强
- 提供启发式回退机制
"""

import time
import logging
import json
from typing import Optional, Dict, List, Any

# 导入数据结构
try:
    from ..shared.data_structures import (
        ThinkingSeedContext,
        SeedVerificationContext
    )
except ImportError:
    from neogenesis_system.shared.data_structures import (
        ThinkingSeedContext,
        SeedVerificationContext
    )

# 导入工具系统
try:
    from ..tools.tool_abstraction import ToolRegistry
except ImportError:
    from neogenesis_system.tools.tool_abstraction import ToolRegistry

# 导入 LLM 管理器
try:
    from ..providers.llm_manager import LLMManager
except ImportError:
    try:
        from neogenesis_system.providers.llm_manager import LLMManager
    except ImportError:
        LLMManager = None

logger = logging.getLogger(__name__)


class SeedVerifier:
    """
    种子验证器类
    
    专门负责思维种子的验证检查和增强生成逻辑。
    将原本在 NeogenesisPlanner 中的阶段二逻辑独立出来，
    提高代码的可维护性和可测试性。
    
    核心功能：
    1. 验证思维种子的可行性
    2. 智能规划搜索维度
    3. 执行多维度信息搜索
    4. 整合信息生成增强版种子
    """
    
    def __init__(self, 
                 tool_registry: Optional[ToolRegistry] = None,
                 llm_manager: Optional[Any] = None):
        """
        初始化种子验证器
        
        Args:
            tool_registry: 工具注册表实例，用于调用验证和搜索工具
            llm_manager: LLM管理器实例，用于生成搜索规划和种子增强
        """
        self.tool_registry = tool_registry
        self.llm_manager = llm_manager
        logger.info("✅ SeedVerifier 初始化完成")
    
    def verify(self, 
               stage1_context: ThinkingSeedContext,
               execution_context: Optional[Dict] = None,
               streaming_output = None) -> SeedVerificationContext:
        """
        执行种子验证检查与增强生成
        
        这是阶段二的核心方法，负责：
        1. 验证思维种子的可行性
        2. 智能规划搜索维度
        3. 执行多维度信息搜索
        4. 整合信息生成增强版种子
        
        Args:
            stage1_context: 阶段一的思维种子上下文
            execution_context: 执行上下文字典（可选）
            streaming_output: 流式输出处理器（可选）
            
        Returns:
            SeedVerificationContext: 包含验证结果和增强种子的上下文对象
        """
        # 创建验证上下文
        context = SeedVerificationContext(
            user_query=stage1_context.user_query,
            execution_context=execution_context
        )
        
        # 添加计时逻辑
        verification_start_time = time.time()
        
        try:
            logger.info(f"开始种子验证与增强: {stage1_context.thinking_seed[:50]}...")
            
            # 流式输出：阶段二开始
            self._send_streaming_output(
                streaming_output,
                stage="stage2_start",
                content="🔍 【阶段二：种子验证与增强】开始...",
                metadata={"thinking_seed_preview": stage1_context.thinking_seed[:100]}
            )
            
            # 基础验证
            self._send_streaming_output(
                streaming_output,
                stage="stage2_basic_verification",
                content="📋 正在执行基础验证...",
                metadata={}
            )
            
            basic_verification_success = self._perform_basic_verification(
                stage1_context, context, streaming_output
            )
            
            if not basic_verification_success:
                logger.warning("⚠️ 基础验证未通过，使用原始种子")
                context.enhanced_thinking_seed = stage1_context.thinking_seed
                
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_verification_result",
                    content="⚠️ 基础验证未通过，将使用原始思维种子继续",
                    metadata={"verification_passed": False}
                )
            else:
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_verification_result",
                    content=f"✅ 基础验证通过（可行性评分：{context.feasibility_score:.2f}）",
                    metadata={
                        "verification_passed": True,
                        "feasibility_score": context.feasibility_score,
                        "verification_method": context.verification_method
                    }
                )
                
                # 如果有 LLM 管理器，执行完整的增强流程
                if self.llm_manager and self.tool_registry:
                    logger.info("🔍 执行完整的种子验证和增强流程")
                    
                    # 🔥 明确分隔基础验证和增强流程
                    print("\n\n" + "🔷"*40, flush=True)
                    print("🔷  基础验证完成，开始智能增强流程", flush=True)
                    print("🔷"*40 + "\n", flush=True)
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_enhancement_start",
                        content="🔍 开始智能增强流程...",
                        metadata={}
                    )
                    
                    # 步骤1: 规划验证搜索维度
                    print("\n" + "🔸"*80, flush=True)
                    print("🔸 【第一步：智能规划搜索维度】", flush=True)
                    print("🔸 说明：基于思维种子，智能分析需要从哪些维度搜索信息进行验证和增强", flush=True)
                    print("🔸"*80, flush=True)
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_planning",
                        content="📋 正在规划信息搜索维度...",
                        metadata={}
                    )
                    
                    search_dimensions = self._plan_verification_search(
                        stage1_context, context, streaming_output
                    )
                    
                    print(f"\n✅ 维度规划完成：共规划 {len(search_dimensions) if search_dimensions else 0} 个搜索维度", flush=True)
                    print("🔸"*80 + "\n", flush=True)
                    
                    if search_dimensions:
                        logger.info(f"✅ 规划了 {len(search_dimensions)} 个搜索维度")
                        context.add_metric("search_dimensions_count", len(search_dimensions))
                        
                        # 打印规划的维度详情 - 使用更醒目的格式
                        print("┏" + "━"*78 + "┓", flush=True)
                        print("┃  📌 规划的搜索维度详情                                                   ┃", flush=True)
                        print("┗" + "━"*78 + "┛\n", flush=True)
                        
                        for i, dim in enumerate(search_dimensions, 1):
                            print(f"╔══ 维度 {i} ══════════════════════════════════════════════════════════════╗", flush=True)
                            print(f"║ 名称：{dim.get('dimension', '未命名')}", flush=True)
                            print(f"║ 查询：{dim.get('query', '')}", flush=True)
                            print(f"║ 优先级：{dim.get('priority', 'medium').upper()}", flush=True)
                            if dim.get('reason'):
                                print(f"║ 理由：{dim.get('reason', '')}", flush=True)
                            print(f"╚{'═'*74}╝\n", flush=True)
                        
                        # 步骤2: 执行多维度搜索
                        print("\n" + "🔸"*80, flush=True)
                        print("🔸 【第二步：执行多维度信息搜索】", flush=True)
                        print("🔸 说明：根据规划的维度，调用搜索工具获取最新信息", flush=True)
                        print("🔸"*80, flush=True)
                        
                        search_results = self._execute_multi_dimension_search(
                            search_dimensions, context, streaming_output
                        )
                        
                        if search_results:
                            logger.info(f"✅ 收集了 {len(search_results)} 条搜索结果")
                            context.add_metric("search_results_count", len(search_results))
                            
                            # 🔥 修复：保存搜索结果到 context
                            # 1. 构建多维度搜索结果字典
                            multidim_dict = {}
                            all_verification_sources = []
                            
                            for result in search_results:
                                dimension = result.get('dimension', '未知维度')
                                content = result.get('content', {})
                                
                                # 提取 results 列表
                                if isinstance(content, dict) and 'results' in content:
                                    results_list = content['results']
                                    multidim_dict[dimension] = results_list
                                    
                                    # 转换为 verification_sources 格式
                                    for item in results_list[:5]:  # 每个维度最多取5条
                                        if isinstance(item, dict):
                                            source_dict = {
                                                'title': item.get('title', ''),
                                                'snippet': item.get('snippet', item.get('content', '')),
                                                'url': item.get('url', ''),
                                                'dimension': dimension  # 添加维度信息
                                            }
                                            all_verification_sources.append(source_dict)
                            
                            # 保存到 context
                            context.multidimensional_search_results = multidim_dict
                            context.verification_sources = all_verification_sources
                            
                            logger.info(f"   📊 保存了 {len(multidim_dict)} 个维度的搜索结果")
                            logger.info(f"   📄 保存了 {len(all_verification_sources)} 条验证源")
                            
                            # 展示多维度搜索结果 - 使用醒目的格式
                            print("\n" + "┏" + "━"*78 + "┓", flush=True)
                            print("┃  📚 多维度搜索结果汇总                                                   ┃", flush=True)
                            print("┗" + "━"*78 + "┛\n", flush=True)
                            
                            for i, result in enumerate(search_results, 1):
                                dimension = result.get('dimension', f'维度{i}')
                                query = result.get('query', '')
                                
                                print(f"┌── 维度 {i}：【{dimension}】" + "─"*(60-len(dimension)-len(str(i))) + "┐", flush=True)
                                print(f"│ 🔍 查询：{query}", flush=True)
                                print(f"├{'─'*76}┤", flush=True)
                                
                                # 显示搜索内容预览
                                content = result.get('content', {})
                                if isinstance(content, dict) and 'results' in content:
                                    results_list = content['results']
                                    print(f"│ ✅ 找到 {len(results_list)} 条相关结果", flush=True)
                                    # 显示前2条
                                    for j, item in enumerate(results_list[:2], 1):
                                        if isinstance(item, dict):
                                            title = item.get('title', '无标题')
                                            url = item.get('url', '')
                                            snippet = item.get('snippet', '')
                                            print(f"│   {j}) 📄 {title[:60]}{'...' if len(title) > 60 else ''}", flush=True)
                                            print(f"│      🔗 {url[:65]}{'...' if len(url) > 65 else ''}", flush=True)
                                            if snippet:
                                                print(f"│      📝 {snippet[:60]}{'...' if len(snippet) > 60 else ''}", flush=True)
                                elif isinstance(content, str):
                                    print(f"│ 📝 内容预览：{content[:60]}...", flush=True)
                                else:
                                    print(f"│ ⚠️  搜索结果格式未知", flush=True)
                                
                                print(f"└{'─'*76}┘\n", flush=True)
                            
                            print("🔸"*80 + "\n", flush=True)
                            
                            # 步骤3: 增强种子
                            print("\n" + "🔸"*80, flush=True)
                            print("🔸 【第三步：生成增强版思维种子】", flush=True)
                            print("🔸 说明：整合搜索信息，生成增强版思维种子", flush=True)
                            print("🔸"*80, flush=True)
                            print(f"📊 将整合 {len(search_results)} 条搜索结果...\n", flush=True)
                            
                            self._send_streaming_output(
                                streaming_output,
                                stage="stage2_enhancing",
                                content=f"🔄 正在整合 {len(search_results)} 条搜索结果，生成增强版思维种子...",
                                metadata={"search_results_count": len(search_results)}
                            )
                            
                            enhanced_seed = self._enhance_seed(
                                stage1_context, search_results, context, streaming_output
                            )
                            
                            if enhanced_seed:
                                context.enhanced_thinking_seed = enhanced_seed
                                logger.info("✅ 成功生成增强版思维种子")
                                
                                self._send_streaming_output(
                                    streaming_output,
                                    stage="stage2_enhanced_seed",
                                    content=f"✅ 成功生成增强版思维种子\n\n{enhanced_seed}",
                                    metadata={
                                        "enhanced": True,
                                        "seed_length": len(enhanced_seed),
                                        "feasibility_score": context.feasibility_score
                                    }
                                )
                            else:
                                context.enhanced_thinking_seed = stage1_context.thinking_seed
                                logger.warning("⚠️ 增强失败，使用原始种子")
                                
                                self._send_streaming_output(
                                    streaming_output,
                                    stage="stage2_enhanced_seed",
                                    content="⚠️ 种子增强失败，将使用原始种子",
                                    metadata={"enhanced": False}
                                )
                        else:
                            context.enhanced_thinking_seed = stage1_context.thinking_seed
                            logger.info("ℹ️  未找到搜索结果，使用原始种子")
                            
                            print("\n" + "⚠️ "*40, flush=True)
                            print("⚠️  多维度搜索未返回有效结果", flush=True)
                            print("⚠️  将跳过增强步骤，使用原始思维种子", flush=True)
                            print("⚠️ "*40 + "\n", flush=True)
                            
                            self._send_streaming_output(
                                streaming_output,
                                stage="stage2_enhanced_seed",
                                content="ℹ️ 未找到有效搜索结果，将使用原始思维种子",
                                metadata={"enhanced": False, "reason": "no_search_results"}
                            )
                    else:
                        context.enhanced_thinking_seed = stage1_context.thinking_seed
                        logger.warning("⚠️ 未规划搜索维度，使用原始种子")
                        logger.warning("🔍 诊断信息：")
                        logger.warning(f"   - LLM Manager可用: {self.llm_manager is not None}")
                        logger.warning(f"   - Tool Registry可用: {self.tool_registry is not None}")
                        
                        print("\n" + "┏" + "━"*78 + "┓", flush=True)
                        print("┃ ⚠️  维度搜索规划未执行                                                  ┃", flush=True)
                        print("┗" + "━"*78 + "┛", flush=True)
                        print("📌 原因分析：", flush=True)
                        print("  • LLM未能成功规划出有效的搜索维度", flush=True)
                        print("  • 可能的原因：", flush=True)
                        print("    - LLM响应格式不符合预期", flush=True)
                        print("    - LLM服务暂时不可用", flush=True)
                        print("    - 网络连接问题", flush=True)
                        print("\n📌 处理方式：", flush=True)
                        print("  • 跳过多维度搜索增强步骤", flush=True)
                        print("  • 使用原始思维种子（已通过基础验证）", flush=True)
                        print("  • 流程将继续进行到下一阶段", flush=True)
                        print("\n🔍 诊断信息：", flush=True)
                        print(f"  • LLM Manager 可用性: {'✅ 是' if self.llm_manager else '❌ 否'}", flush=True)
                        print(f"  • Tool Registry 可用性: {'✅ 是' if self.tool_registry else '❌ 否'}", flush=True)
                        print("┄"*80 + "\n", flush=True)
                        
                        self._send_streaming_output(
                            streaming_output,
                            stage="stage2_enhanced_seed",
                            content="ℹ️ 未规划搜索维度，将使用原始思维种子",
                            metadata={"enhanced": False, "reason": "no_dimensions"}
                        )
                else:
                    # 降级：直接使用原始种子
                    context.enhanced_thinking_seed = stage1_context.thinking_seed
                    logger.info("ℹ️  LLM管理器未配置，使用原始种子")
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_enhanced_seed",
                        content="ℹ️ LLM管理器未配置，将使用原始思维种子",
                        metadata={"enhanced": False, "reason": "no_llm_manager"}
                    )
                
        except Exception as e:
            logger.error(f"   ❌ 种子验证异常: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # 异常回退
            context.verification_result = True  # 不阻止流程继续
            context.feasibility_score = 0.3
            context.verification_method = "exception_fallback"
            context.verification_evidence = [f"验证异常: {str(e)}", "使用异常回退验证"]
            context.add_error(f"验证异常: {str(e)}")
            context.enhanced_thinking_seed = stage1_context.thinking_seed
            
            self._send_streaming_output(
                streaming_output,
                stage="stage2_error",
                content=f"❌ 种子验证过程出现异常：{str(e)}\n将使用原始种子继续",
                metadata={"error": str(e), "fallback": True}
            )
        
        # 计算并记录执行时间
        verification_time = time.time() - verification_start_time
        context.add_metric("verification_time", verification_time)
        context.add_metric("feasibility_confidence", context.feasibility_score)
        
        logger.info(f"种子验证耗时: {verification_time:.3f}s")
        logger.info(f"最终可行性评分: {context.feasibility_score:.3f}")
        logger.info(f"验证方法: {context.verification_method}")
        
        # 流式输出：阶段二完成
        self._send_streaming_output(
            streaming_output,
            stage="stage2_complete",
            content=f"✅ 【阶段二完成】验证耗时 {verification_time:.2f}秒，可行性评分：{context.feasibility_score:.2f}",
            metadata={
                "verification_time": verification_time,
                "feasibility_score": context.feasibility_score,
                "verification_method": context.verification_method,
                "enhanced_seed": context.enhanced_thinking_seed
            }
        )
        
        return context
    
    def _perform_basic_verification(self, 
                                    stage1_context: ThinkingSeedContext,
                                    context: SeedVerificationContext,
                                    streaming_output = None) -> bool:
        """
        执行基础验证
        
        Args:
            stage1_context: 阶段一上下文
            context: 验证上下文
            
        Returns:
            bool: 验证是否成功
        """
        # 检查工具注册表状态
        if not self.tool_registry:
            logger.warning("   ⚠️ 工具注册表未初始化，使用简化验证")
            context.verification_result = True
            context.feasibility_score = 0.6
            context.verification_method = "simplified_heuristic"
            context.verification_evidence = ["工具注册表未初始化，使用启发式验证"]
            return True
            
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
            return True
            
        else:
            # 🔥 修复：真正调用 idea_verification 工具获取事实验证
            logger.info("✅ 使用 idea_verification 工具进行事实验证...")
            
            self._send_streaming_output(
                streaming_output,
                stage="stage2_fact_verification",
                content="🔍 正在调用事实验证工具...",
                metadata={}
            )
            
            try:
                # 准备验证输入
                verification_input = {
                    'idea_text': stage1_context.thinking_seed,
                    'context': {
                        'user_query': stage1_context.user_query,
                        '_streaming_output': streaming_output  # 传递streaming_output
                    }
                }
                
                # 🎯 真正调用 idea_verification 工具
                logger.info(f"📞 调用 idea_verification: {stage1_context.thinking_seed[:100]}...")
                verification_result = self.tool_registry.execute_tool(
                    name="idea_verification",
                    **verification_input
                )
                
                if verification_result and verification_result.success:
                    logger.info("✅ 事实验证成功")
                    
                    # 提取验证结果
                    result_data = verification_result.data  # 🔥 修复：使用 data 而不是 result
                    if isinstance(result_data, dict):
                        context.feasibility_score = result_data.get('feasibility_score', 0.7)
                        context.verification_result = result_data.get('verification_passed', True)
                        context.verification_evidence = result_data.get('key_findings', [])
                        context.verification_method = "idea_verification_tool"
                        
                        # 🔥 保存事实验证的详细结果
                        context.verification_results = result_data
                        
                        # 🔥 修复：提取并保存搜索结果到 verification_sources
                        search_results = result_data.get('search_results', [])
                        if search_results:
                            verification_sources = []
                            for sr in search_results[:5]:  # 保存前5个搜索结果
                                if isinstance(sr, dict):
                                    source_dict = {
                                        'title': sr.get('title', ''),
                                        'snippet': sr.get('snippet', ''),
                                        'url': sr.get('url', ''),
                                        'relevance_score': sr.get('relevance_score', 0.0)
                                    }
                                    verification_sources.append(source_dict)
                            
                            context.verification_sources = verification_sources
                            logger.info(f"   📄 保存了 {len(verification_sources)} 条基础验证的搜索结果")
                        
                        # 流式输出验证结果摘要
                        findings_preview = "\n".join([f"• {finding}" for finding in context.verification_evidence[:3]])
                        self._send_streaming_output(
                            streaming_output,
                            stage="stage2_fact_verification_result",
                            content=f"✅ 事实验证完成\n\n可行性评分：{context.feasibility_score:.2f}\n\n关键发现：\n{findings_preview}",
                            metadata={
                                "feasibility_score": context.feasibility_score,
                                "verification_passed": context.verification_result,
                                "evidence_count": len(context.verification_evidence)
                            }
                        )
                        
                        return True
                    else:
                        logger.warning("⚠️ 验证结果格式异常，使用简化验证")
                        context.verification_result = True
                        context.feasibility_score = 0.7
                        context.verification_method = "simplified_verification"
                        context.verification_evidence = ["验证结果格式异常"]
                        return True
                else:
                    logger.warning(f"⚠️ idea_verification 调用失败: {verification_result.error_message if verification_result else 'Unknown error'}")
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_fact_verification_failed",
                        content="⚠️ 事实验证失败，使用简化验证",
                        metadata={}
                    )
                    
                    # 回退到简化验证
                    context.verification_result = True
                    context.feasibility_score = 0.6
                    context.verification_method = "simplified_fallback"
                    context.verification_evidence = ["idea_verification调用失败，使用简化验证"]
                    return True
                    
            except Exception as e:
                logger.error(f"❌ 事实验证异常: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_fact_verification_error",
                    content=f"❌ 事实验证异常：{str(e)}\n使用简化验证",
                    metadata={"error": str(e)}
                )
                
                # 回退到简化验证
                context.verification_result = True
                context.feasibility_score = 0.6
                context.verification_method = "exception_fallback"
                context.verification_evidence = [f"验证异常: {str(e)}"]
                return True
    
    def _plan_verification_search(self,
                                  stage1_context: ThinkingSeedContext,
                                  context: SeedVerificationContext,
                                  streaming_output = None) -> List[Dict[str, str]]:
        """
        智能规划验证搜索维度
        
        基于用户查询和思维种子，利用 LLM 智能分析应该从哪些维度搜索信息，
        以验证和增强思维种子。
        
        Args:
            stage1_context: 阶段一上下文
            context: 验证上下文
            
        Returns:
            List[Dict]: 搜索维度列表，每个维度包含 dimension、query、priority
        """
        try:
            logger.info("📋 开始规划验证搜索维度...")
            print("⏳ 正在调用 LLM 分析搜索维度...", flush=True)
            
            # 🔥 获取当前时间信息
            from datetime import datetime
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            current_date = now.strftime('%Y年%m月')
            
            # 构建搜索规划提示语
            planning_prompt = f"""你是一个智能信息搜索规划专家。

📅 **当前时间信息**（规划搜索时必须使用）:
- 当前年份: {current_year}年
- 当前月份: {current_date}
- ⚠️ 重要：在搜索查询中，如果需要最新信息，请使用 "{current_year}" 而不是其他年份

用户问题：{stage1_context.user_query}

初始思维种子：
{stage1_context.thinking_seed}

请分析这个思维种子，并规划应该从哪些维度搜索最新信息来验证和增强它。
每个搜索维度应该包含：
1. dimension: 维度名称（如"技术趋势"、"行业现状"、"最佳实践"等）
2. query: 具体的搜索查询语句
3. priority: 优先级（high/medium/low）

请以JSON格式返回搜索维度列表，格式如下：
{{
    "dimensions": [
        {{
            "dimension": "维度名称",
            "query": "搜索查询",
            "priority": "high",
            "reason": "搜索理由"
        }}
    ]
}}

要求：
- 最多规划3-5个搜索维度
- 每个维度的查询应该具体、可执行
- 优先选择对验证和增强种子最有价值的维度
- **时间准确性**: 如果用户问题或种子涉及"最新"、"当前"、"现在"等时间概念，搜索查询中必须使用"{current_year}"年份
- **避免过时信息**: 不要在查询中使用{current_year-1}年或更早的年份
"""

            # 🔥 修复：使用流式生成器实时输出
            response_content = ""
            
            if hasattr(self.llm_manager, 'call_api_streaming_generator'):
                logger.info("🌊 使用流式生成器进行搜索规划...")
                
                # 流式输出提示
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_llm_planning",
                    content="🤖 正在调用 LLM 规划搜索维度（流式输出）...\n",
                    metadata={}
                )
                
                try:
                    # 使用流式生成器 - 实时显示每个token
                    for chunk in self.llm_manager.call_api_streaming_generator(
                        prompt=planning_prompt,
                        temperature=0.7,
                        max_tokens=1000
                    ):
                        if chunk:
                            # 实时流式输出每个chunk
                            self._send_streaming_output(
                                streaming_output,
                                stage="stage2_llm_planning_chunk",
                                content=chunk,
                                metadata={"is_chunk": True}
                            )
                            response_content += chunk
                    
                    # 流式输出完成提示
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_llm_planning_complete",
                        content="\n✅ 搜索规划生成完成",
                        metadata={"total_length": len(response_content)}
                    )
                    
                except Exception as stream_error:
                    logger.warning(f"⚠️ 流式生成失败，回退到普通模式: {stream_error}")
                    # 回退到普通API
                    if hasattr(self.llm_manager, 'call_api'):
                        response_content = self.llm_manager.call_api(
                            prompt=planning_prompt,
                            temperature=0.7,
                            max_tokens=1000
                        )
                        # 提取content
                        if isinstance(response_content, dict) and 'content' in response_content:
                            response_content = response_content['content']
                        elif hasattr(response_content, 'content'):
                            response_content = response_content.content
                    else:
                        logger.warning("⚠️ LLM管理器不支持 call_api 方法")
                        return self._get_fallback_dimensions(stage1_context)
                        
            elif hasattr(self.llm_manager, 'call_api'):
                logger.info("⚠️ 流式生成器不可用，使用普通API")
                response = self.llm_manager.call_api(
                    prompt=planning_prompt,
                    temperature=0.7,
                    max_tokens=1000
                )
                # 提取content
                if isinstance(response, dict) and 'content' in response:
                    response_content = response['content']
                elif isinstance(response, str):
                    response_content = response
                elif hasattr(response, 'content'):
                    response_content = response.content
            else:
                logger.warning("⚠️ LLM管理器不支持任何API方法")
                return self._get_fallback_dimensions(stage1_context)
            
            # 解析响应 - 现在 response_content 已经是字符串了
            content = response_content if response_content else None
            
            if content:
                print(f"✅ LLM 响应已接收（长度: {len(content)} 字符）", flush=True)
                logger.debug(f"LLM响应内容（前200字符）: {content[:200]}...")
                
                # 尝试提取JSON
                import re
                print("🔍 正在解析 LLM 响应中的搜索维度...", flush=True)
                
                # 改进的JSON提取正则：支持多行，处理嵌套
                json_match = re.search(r'\{[^{}]*"dimensions"[^{}]*\[[^\]]*\][^{}]*\}', content, re.DOTALL)
                if not json_match:
                    # 备用方案：查找第一个完整的JSON对象
                    json_match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', content, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(0)
                    print(f"✅ 找到 JSON 格式数据（长度: {len(json_str)} 字符）", flush=True)
                    
                    try:
                        planning_result = json.loads(json_str)
                        print("✅ JSON 解析成功", flush=True)
                        
                        if 'dimensions' in planning_result and planning_result['dimensions']:
                            dimensions = planning_result['dimensions']
                            print(f"✅ 成功提取 {len(dimensions)} 个搜索维度", flush=True)
                            logger.info(f"✅ 成功规划 {len(dimensions)} 个搜索维度")
                            
                            # 构建维度展示信息
                            dimensions_display = []
                            for i, dim in enumerate(dimensions, 1):
                                dimension_name = dim.get('dimension', '')
                                query = dim.get('query', '')
                                priority = dim.get('priority', 'medium')
                                reason = dim.get('reason', '')
                                
                                logger.info(f"  📌 {dimension_name}: {query}")
                                dimensions_display.append(
                                    f"{i}. 【{dimension_name}】({priority})\n"
                                    f"   查询：{query}\n"
                                    f"   理由：{reason}"
                                )
                            
                            # 流式输出：展示搜索维度
                            self._send_streaming_output(
                                streaming_output,
                                stage="stage2_dimensions_planned",
                                content=f"✅ 成功规划 {len(dimensions)} 个搜索维度：\n\n" + "\n\n".join(dimensions_display),
                                metadata={
                                    "dimensions_count": len(dimensions),
                                    "dimensions": dimensions
                                }
                            )
                            
                            return dimensions
                        else:
                            print("⚠️ JSON 中未找到有效的 dimensions 字段", flush=True)
                            logger.warning("⚠️ JSON中未找到有效的dimensions字段")
                            print(f"   JSON 内容预览: {json_str[:200]}...", flush=True)
                    except json.JSONDecodeError as je:
                        print(f"❌ JSON 解析失败: {je}", flush=True)
                        logger.warning(f"⚠️ JSON解析失败: {je}")
                        logger.debug(f"尝试解析的JSON: {json_str[:200]}...")
                        print(f"   尝试解析的内容: {json_str[:150]}...", flush=True)
                else:
                    print("⚠️ 响应中未找到 JSON 格式数据", flush=True)
                    logger.warning("⚠️ 响应中未找到JSON格式数据")
                    logger.debug(f"响应内容: {content[:300]}...")
                    print(f"   响应内容预览: {content[:200]}...", flush=True)
            else:
                print("⚠️ LLM 未返回有效内容", flush=True)
                logger.warning("⚠️ LLM未返回有效内容")
            
            # 回退到默认搜索维度
            print("\n⚠️ 使用回退策略：基于启发式规则生成默认搜索维度", flush=True)
            logger.info("📋 使用回退搜索维度策略...")
            fallback_dimensions = self._get_fallback_dimensions(stage1_context)
            
            self._send_streaming_output(
                streaming_output,
                stage="stage2_dimensions_planned",
                content=f"ℹ️ 使用默认搜索维度（共 {len(fallback_dimensions)} 个）",
                metadata={
                    "dimensions_count": len(fallback_dimensions),
                    "dimensions": fallback_dimensions,
                    "fallback": True
                }
            )
            
            return fallback_dimensions
            
        except Exception as e:
            logger.error(f"❌ 搜索规划失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return self._get_fallback_dimensions(stage1_context)
    
    def _get_fallback_dimensions(self, stage1_context: ThinkingSeedContext) -> List[Dict[str, str]]:
        """
        获取回退的默认搜索维度
        
        当LLM规划失败时，使用基于启发式规则的默认搜索维度
        
        Args:
            stage1_context: 阶段一上下文
            
        Returns:
            List[Dict]: 默认搜索维度列表
        """
        user_query = stage1_context.user_query
        thinking_seed = stage1_context.thinking_seed
        
        # 🔥 获取当前时间
        from datetime import datetime
        current_year = datetime.now().year
        
        # 基于查询内容判断类型
        query_lower = user_query.lower()
        
        # 默认维度
        dimensions = []
        
        # 技术/学术类问题
        if any(keyword in query_lower for keyword in ['是什么', '原理', '如何', '怎么', '技术', '算法', 'how', 'what']):
            dimensions.extend([
                {
                    "dimension": "基础概念",
                    "query": f"{user_query[:50]} 基础概念 定义",
                    "priority": "high",
                    "reason": "理解基础概念"
                },
                {
                    "dimension": "实际应用",
                    "query": f"{user_query[:50]} 应用案例 实践",
                    "priority": "medium",
                    "reason": "了解实际应用"
                }
            ])
        
        # 比较/对比类问题
        if any(keyword in query_lower for keyword in ['区别', '对比', '比较', 'vs', 'versus', 'difference']):
            dimensions.extend([
                {
                    "dimension": "对比分析",
                    "query": f"{user_query[:50]} 对比 比较",
                    "priority": "high",
                    "reason": "进行对比分析"
                }
            ])
        
        # 最新/趋势类问题 - 🔥 使用当前年份
        if any(keyword in query_lower for keyword in ['最新', '趋势', '发展', '未来', str(current_year), str(current_year-1), 'latest', 'trend']):
            dimensions.extend([
                {
                    "dimension": "最新进展",
                    "query": f"{user_query[:50]} {current_year} 最新",  # 🔥 动态年份
                    "priority": "high",
                    "reason": f"获取{current_year}年最新信息"
                }
            ])
        
        # 如果还没有足够的维度，添加通用维度
        if len(dimensions) < 2:
            dimensions.append({
                "dimension": "相关信息",
                "query": f"{user_query[:60]}",
                "priority": "medium",
                "reason": "获取相关背景信息"
            })
        
        # 限制最多3个维度
        dimensions = dimensions[:3]
        
        logger.info(f"📋 生成了 {len(dimensions)} 个回退搜索维度（基于{current_year}年）")
        for dim in dimensions:
            logger.info(f"  - {dim['dimension']}: {dim['query']}")
        
        return dimensions
    
    def _execute_multi_dimension_search(self,
                                       search_dimensions: List[Dict[str, str]],
                                       context: SeedVerificationContext,
                                       streaming_output = None) -> List[Dict[str, Any]]:
        """
        执行多维度信息搜索
        
        Args:
            search_dimensions: 搜索维度列表
            context: 验证上下文
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        try:
            logger.info("🔎 开始执行多维度搜索...")
            
            self._send_streaming_output(
                streaming_output,
                stage="stage2_search_start",
                content=f"🔎 开始执行多维度信息搜索（共 {len(search_dimensions)} 个维度）...",
                metadata={"total_dimensions": len(search_dimensions)}
            )
            
            all_results = []
            
            # 检查是否有web_search工具
            if not self.tool_registry.has_tool("web_search"):
                logger.warning("⚠️ web_search工具不可用，跳过搜索")
                
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_search_unavailable",
                    content="⚠️ 搜索工具不可用，跳过信息搜索",
                    metadata={}
                )
                
                return []
            
            # 按优先级排序
            sorted_dimensions = sorted(
                search_dimensions,
                key=lambda x: {'high': 3, 'medium': 2, 'low': 1}.get(x.get('priority', 'medium'), 2),
                reverse=True
            )
            
            # 执行搜索（最多前3个维度）
            for i, dimension in enumerate(sorted_dimensions[:3]):
                try:
                    dimension_name = dimension.get('dimension', f'维度{i+1}')
                    query = dimension.get('query', '')
                    priority = dimension.get('priority', 'medium')
                    
                    if not query:
                        continue
                    
                    # 醒目的搜索开始提示
                    print(f"\n{'─'*80}", flush=True)
                    print(f"🔍 正在搜索维度 {i+1}/{min(3, len(sorted_dimensions))}: 【{dimension_name}】", flush=True)
                    print(f"   优先级: {priority.upper()}", flush=True)
                    print(f"   查询语句: {query}", flush=True)
                    print(f"{'─'*80}", flush=True)
                    
                    logger.info(f"  🔍 搜索维度 [{dimension_name}]: {query}")
                    
                    # 流式输出：开始搜索某个维度
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_searching_dimension",
                        content=f"🔍 正在搜索【{dimension_name}】({priority})...\n查询：{query}",
                        metadata={
                            "dimension": dimension_name,
                            "query": query,
                            "priority": priority,
                            "index": i + 1,
                            "total": min(3, len(sorted_dimensions))
                        }
                    )
                    
                    print("⏳ 正在调用搜索工具...", flush=True)
                    
                    # 调用搜索工具
                    search_result = self.tool_registry.execute_tool(
                        name="web_search",
                        query=query
                    )
                    
                    if search_result and search_result.success:
                        result_data = {
                            'dimension': dimension_name,
                            'query': query,
                            'content': search_result.data,  # 🔥 修复：使用 data 而不是 result
                            'metadata': search_result.metadata
                        }
                        all_results.append(result_data)
                        
                        # 提取并显示结果摘要
                        result_count = 0
                        if isinstance(search_result.data, dict):
                            if 'results' in search_result.data:
                                result_count = len(search_result.data['results'])
                            result_preview = json.dumps(search_result.data, ensure_ascii=False)[:150]
                        elif isinstance(search_result.data, str):
                            result_preview = search_result.data[:150]
                        else:
                            result_preview = str(search_result.data)[:150]
                        
                        print(f"✅ 搜索成功！找到 {result_count if result_count > 0 else '若干'} 条结果", flush=True)
                        if result_count > 0:
                            print(f"   结果预览: {result_preview}...", flush=True)
                        
                        logger.info(f"    ✅ 搜索成功，找到 {result_count} 条结果")
                        
                        # 流式输出：搜索成功
                        self._send_streaming_output(
                            streaming_output,
                            stage="stage2_search_result",
                            content=f"✅ 【{dimension_name}】搜索成功\n找到 {result_count if result_count > 0 else '若干'} 条结果\n结果预览：{result_preview}...",
                            metadata={
                                "dimension": dimension_name,
                                "success": True,
                                "result_count": result_count,
                                "result_preview": result_preview
                            }
                        )
                    else:
                        error_msg = search_result.error_message if search_result else "未知错误"
                        print(f"⚠️ 搜索失败: {error_msg}", flush=True)
                        logger.warning(f"    ⚠️ 搜索失败或无结果: {error_msg}")
                        
                        # 流式输出：搜索失败
                        self._send_streaming_output(
                            streaming_output,
                            stage="stage2_search_result",
                            content=f"⚠️ 【{dimension_name}】搜索失败或无结果\n原因：{error_msg}",
                            metadata={
                                "dimension": dimension_name,
                                "success": False,
                                "error": error_msg
                            }
                        )
                        
                except Exception as e:
                    print(f"❌ 搜索异常: {str(e)}", flush=True)
                    logger.error(f"    ❌ 搜索异常: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    
                    # 流式输出：搜索异常
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_search_error",
                        content=f"❌ 【{dimension_name}】搜索异常：{str(e)}",
                        metadata={
                            "dimension": dimension_name,
                            "error": str(e)
                        }
                    )
                    continue
            
            # 搜索完成总结
            print(f"\n{'═'*80}", flush=True)
            print(f"✅ 多维度搜索完成！", flush=True)
            print(f"   • 执行搜索维度数: {min(3, len(sorted_dimensions))}", flush=True)
            print(f"   • 成功获取结果数: {len(all_results)}", flush=True)
            print(f"{'═'*80}\n", flush=True)
            
            logger.info(f"✅ 完成多维度搜索，共 {len(all_results)} 个有效结果")
            
            # 流式输出：搜索完成
            self._send_streaming_output(
                streaming_output,
                stage="stage2_search_complete",
                content=f"✅ 多维度搜索完成，共获得 {len(all_results)} 个有效结果",
                metadata={
                    "total_results": len(all_results),
                    "searched_dimensions": min(3, len(sorted_dimensions))
                }
            )
            
            return all_results
            
        except Exception as e:
            logger.error(f"❌ 多维度搜索失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def _enhance_seed(self,
                     stage1_context: ThinkingSeedContext,
                     search_results: List[Dict[str, Any]],
                     context: SeedVerificationContext,
                     streaming_output = None) -> Optional[str]:
        """
        执行种子增强
        
        将搜索到的信息与原始种子整合，生成增强版思维种子。
        
        Args:
            stage1_context: 阶段一上下文
            search_results: 搜索结果列表
            context: 验证上下文
            
        Returns:
            Optional[str]: 增强后的思维种子，失败则返回None
        """
        try:
            logger.info("🔄 开始生成增强版思维种子...")
            
            self._send_streaming_output(
                streaming_output,
                stage="stage2_enhancement_processing",
                content="🔄 正在整合搜索信息，生成增强版思维种子...",
                metadata={"search_results_count": len(search_results)}
            )
            
            # 构建搜索结果摘要
            search_summary = self._build_search_summary(search_results)
            
            # 🔥 获取当前时间信息
            import time as time_module
            from datetime import datetime
            now = datetime.now()
            current_year = now.year
            current_date = now.strftime('%Y年%m月%d日')
            
            # 构建增强提示语
            enhancement_prompt = f"""你是一个思维种子增强专家。

📅 **重要时间信息**（生成增强种子时必须参考）:
- 当前年份: {current_year}年
- 当前日期: {current_date}
- ⚠️ 如果搜索结果提到"{current_year}年"的信息，必须优先采纳和突出

用户问题：{stage1_context.user_query}

原始思维种子：
{stage1_context.thinking_seed}

最新搜索信息：
{search_summary}

请基于上述信息，生成一个增强版的思维种子。要求：
1. **时间准确性**：优先使用{current_year}年的最新信息，避免使用过时年份
2. 保留原始种子的核心思路和结构
3. 整合最新的搜索信息，增加深度和广度
4. 确保逻辑连贯、表达清晰
5. 突出关键洞察和创新点
6. 控制在200-400字

⚠️ 特别注意：
- 如果用户问"最新"、"当前"相关的问题，必须以{current_year}年为基准
- 如果搜索结果中同时有{current_year-1}年和{current_year}年的信息，优先采用{current_year}年的
- 在描述进展时，使用"{current_year}年"而不是旧年份

请直接输出增强后的思维种子，不需要额外的解释。
"""

            self._send_streaming_output(
                streaming_output,
                stage="stage2_llm_enhancing",
                content="🤖 正在调用 LLM 进行种子增强（流式输出）...\n",
                metadata={"prompt_length": len(enhancement_prompt)}
            )

            # 🔥 修复：使用流式生成器实时输出
            enhanced_seed = ""
            
            if hasattr(self.llm_manager, 'call_api_streaming_generator'):
                logger.info("🌊 使用流式生成器进行种子增强...")
                
                try:
                    # 使用流式生成器 - 实时显示每个token
                    for chunk in self.llm_manager.call_api_streaming_generator(
                        prompt=enhancement_prompt,
                        temperature=0.7,
                        max_tokens=1500
                    ):
                        if chunk:
                            # 实时流式输出每个chunk
                            self._send_streaming_output(
                                streaming_output,
                                stage="stage2_enhancement_chunk",
                                content=chunk,
                                metadata={"is_chunk": True}
                            )
                            enhanced_seed += chunk
                    
                    # 流式输出完成提示
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_enhancement_stream_complete",
                        content="\n✅ 种子增强生成完成",
                        metadata={"total_length": len(enhanced_seed)}
                    )
                    
                except Exception as stream_error:
                    logger.warning(f"⚠️ 流式生成失败，回退到普通模式: {stream_error}")
                    # 回退到普通API
                    if hasattr(self.llm_manager, 'call_api'):
                        response = self.llm_manager.call_api(
                            prompt=enhancement_prompt,
                            temperature=0.7,
                            max_tokens=1500
                        )
                        # 提取content
                        if isinstance(response, dict) and 'content' in response:
                            enhanced_seed = response['content']
                        elif isinstance(response, str):
                            enhanced_seed = response
                        elif hasattr(response, 'content'):
                            enhanced_seed = response.content
                    else:
                        logger.warning("⚠️ LLM管理器不支持 call_api 方法")
                        
                        self._send_streaming_output(
                            streaming_output,
                            stage="stage2_enhancement_failed",
                            content="⚠️ LLM管理器不支持增强功能",
                            metadata={}
                        )
                        
                        return None
                        
            elif hasattr(self.llm_manager, 'call_api'):
                logger.info("⚠️ 流式生成器不可用，使用普通API")
                response = self.llm_manager.call_api(
                    prompt=enhancement_prompt,
                    temperature=0.7,
                    max_tokens=1500
                )
                # 提取content
                if isinstance(response, dict) and 'content' in response:
                    enhanced_seed = response['content']
                elif isinstance(response, str):
                    enhanced_seed = response
                elif hasattr(response, 'content'):
                    enhanced_seed = response.content
            else:
                logger.warning("⚠️ LLM管理器不支持任何API方法")
                
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_enhancement_failed",
                    content="⚠️ LLM管理器不支持增强功能",
                    metadata={}
                )
                
                return None
            
            if enhanced_seed:
                enhanced_seed = enhanced_seed.strip()
                
                if len(enhanced_seed) > 50:
                    # 更新可行性评分（增强后提高评分）
                    old_score = context.feasibility_score
                    context.feasibility_score = min(0.9, context.feasibility_score + 0.2)
                    context.verification_method = "llm_enhanced_verification"
                    context.verification_evidence.append("成功整合搜索信息生成增强种子")
                    
                    # 醒目的成功输出
                    print("\n" + "┏" + "━"*78 + "┓", flush=True)
                    print("┃ ✅ 增强版思维种子生成成功！                                              ┃", flush=True)
                    print("┗" + "━"*78 + "┛", flush=True)
                    print(f"📊 统计信息:", flush=True)
                    print(f"   • 种子长度: {len(enhanced_seed)} 字符", flush=True)
                    print(f"   • 可行性评分提升: {old_score:.2f} → {context.feasibility_score:.2f}", flush=True)
                    print(f"\n📝 增强种子内容预览:", flush=True)
                    print(f"{'─'*80}", flush=True)
                    print(f"{enhanced_seed[:200]}{'...' if len(enhanced_seed) > 200 else ''}", flush=True)
                    print(f"{'─'*80}\n", flush=True)
                    
                    logger.info(f"✅ 生成增强种子（长度: {len(enhanced_seed)}字符）")
                    logger.info(f"增强种子预览: {enhanced_seed[:100]}...")
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_enhancement_success",
                        content=f"✅ 成功生成增强版思维种子\n\n长度：{len(enhanced_seed)} 字符\n可行性评分提升：{old_score:.2f} → {context.feasibility_score:.2f}",
                        metadata={
                            "seed_length": len(enhanced_seed),
                            "old_score": old_score,
                            "new_score": context.feasibility_score,
                            "enhanced_seed_preview": enhanced_seed[:200]
                        }
                    )
                    
                    return enhanced_seed
                else:
                    logger.warning("⚠️ 生成的增强种子过短或为空")
                    
                    self._send_streaming_output(
                        streaming_output,
                        stage="stage2_enhancement_failed",
                        content="⚠️ 生成的增强种子过短或为空",
                        metadata={"seed_length": len(enhanced_seed) if enhanced_seed else 0}
                    )
                    
                    return None
            else:
                logger.warning("⚠️ LLM未返回有效响应")
                
                self._send_streaming_output(
                    streaming_output,
                    stage="stage2_enhancement_failed",
                    content="⚠️ LLM未返回有效响应",
                    metadata={}
                )
                
                return None
                
        except Exception as e:
            logger.error(f"❌ 种子增强失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _build_search_summary(self, search_results: List[Dict[str, Any]]) -> str:
        """
        构建搜索结果摘要
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            str: 格式化的搜索结果摘要
        """
        if not search_results:
            return "（无搜索结果）"
        
        summary_parts = []
        for i, result in enumerate(search_results, 1):
            dimension = result.get('dimension', f'维度{i}')
            content = result.get('content', '')
            
            # 提取摘要（取前200字符）
            if isinstance(content, dict):
                content_str = json.dumps(content, ensure_ascii=False)[:200]
            elif isinstance(content, str):
                content_str = content[:200]
            else:
                content_str = str(content)[:200]
            
            summary_parts.append(f"【{dimension}】\n{content_str}...")
        
        return "\n\n".join(summary_parts)
    
    def _send_streaming_output(self, 
                              streaming_output,
                              stage: str,
                              content: str,
                              metadata: Optional[Dict] = None):
        """
        发送流式输出
        
        Args:
            streaming_output: 流式输出处理器
            stage: 阶段标识
            content: 输出内容
            metadata: 元数据（可选）
        """
        if streaming_output and hasattr(streaming_output, 'send'):
            try:
                output_data = {
                    'stage': stage,
                    'content': content,
                    'metadata': metadata or {},
                    'timestamp': time.time()
                }
                streaming_output.send(output_data)
            except Exception as e:
                logger.debug(f"流式输出发送失败: {e}")

