
"""
路径生成器 - 负责基于思维种子生成多样化思维路径
Path Generator - responsible for generating diverse reasoning paths from thinking seeds

改造后支持：
1. 阶段二：接收思维种子，生成思维路径列表
2. 预定义路径模板库，覆盖多种思考范式  
3. 基于关键词的智能路径选择算法
4. 向后兼容性保持
"""

import json
import time
import random
import logging
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass

from .data_structures import ReasoningPath, TaskComplexity
# from .utils.client_adapter import DeepSeekClientAdapter  # 不再需要，使用依赖注入
from ..shared.common_utils import parse_json_response, extract_context_factors
try:
    from neogenesis_system.config import PROMPT_TEMPLATES
except ImportError:
    try:
        from ..config import PROMPT_TEMPLATES
    except ImportError:
        PROMPT_TEMPLATES = {}

logger = logging.getLogger(__name__)


class LLMDrivenDimensionCreator:
    """LLM驱动的动态维度创建器"""
    
    def __init__(self, api_key: str = "", llm_client=None):
        """
        初始化LLM驱动的维度创建器
        
        Args:
            api_key: API密钥（向后兼容）
            llm_client: 共享的LLM客户端（依赖注入）
        """
        self.api_key = api_key
        
        # 🔧 依赖注入：使用传入的客户端（纯依赖注入模式）
        self.api_caller = llm_client
        if self.api_caller:
            logger.debug("🔧 维度创建器使用共享LLM客户端")
        else:
            logger.warning("⚠️ 未提供LLM客户端，维度创建器将无法使用AI功能")
            logger.info("💡 请确保从上层（MainController）传入有效的llm_client")
        
        # 性能和历史记录
        self.performance_history = defaultdict(list)
        self.discovered_dimensions = defaultdict(dict)  # 存储LLM发现的维度
        self.dimension_usage_frequency = defaultdict(int)  # 维度使用频率
        self.dimension_creation_patterns = defaultdict(list)  # 维度创建模式
        self.task_dimension_mapping = defaultdict(list)  # 任务-维度映射关系
        
        # LLM专用属性
        self.llm_session_history = []  # LLM会话历史
        self.dimension_quality_scores = defaultdict(float)  # 维度质量评分
        self.creative_dimension_cache = {}  # 创新维度缓存
        
        # 🚀 LLM元优势函数评估系统
        self.llm_capability_tracking = {
            'task_type_advantages': defaultdict(lambda: {'success_count': 0, 'total_count': 0, 'avg_quality': 0.5}),
            'domain_expertise_scores': defaultdict(float),
            'complexity_handling_ability': defaultdict(float),
            'creative_dimension_success_rate': 0.5,
            'historical_limitation_patterns': [],
            'advantage_compensation_strategies': {}
        }
        
        logger.info("🤖 LLM驱动的维度创建器已初始化 (使用统一客户端接口)")

    def create_dynamic_dimensions(self, 
                                task_description: str = None,
                                user_query: str = None,
                                execution_context: Optional[Dict] = None,
                                num_dimensions: int = 3,
                                creativity_level: str = "medium",
                                context: Optional[Dict] = None) -> List[ReasoningPath]:
        """
        使用LLM创建动态维度
     
        
        增强版本，支持回顾性分析和灵活的维度创建需求
        
        Args:
            task_description: 任务描述（优先使用，支持回顾性Prompt）
            user_query: 用户查询（向后兼容）
            execution_context: 执行上下文（传统格式）
            num_dimensions: 需要生成的维度数量
            creativity_level: 创意级别 ("low", "medium", "high")
            context: 增强上下文信息（支持回顾性分析）
            
        Returns:
            生成的思维路径列表
        """
        # 参数兼容性处理
        effective_query = task_description or user_query
        if not effective_query:
            raise ValueError("必须提供 task_description 或 user_query")
        
        # 合并上下文信息
        merged_context = execution_context or {}
        if context:
            merged_context.update(context)
        
        # 判断是否为回顾性分析模式
        is_retrospective = (merged_context.get("mode") == "retrospective_analysis")
        
        logger.info(f"🤖 开始LLM维度创建: {effective_query[:50]}...")
        if is_retrospective:
            logger.info("🔍 回顾性分析模式已激活")
        
        try:
            # 构建维度创建提示（增强版）
            llm_prompt = self._build_enhanced_dimension_creation_prompt(
                effective_query, merged_context, num_dimensions, creativity_level
            )
            
            # 根据创意级别调整温度
            temperature_map = {"low": 0.6, "medium": 0.8, "high": 0.9}
            temperature = temperature_map.get(creativity_level, 0.8)
            
            # 调用LLM进行推理
            llm_response = self.api_caller.call_api(llm_prompt, temperature=temperature)
            
            # 解析LLM响应（增强版）
            dimension_result = self._parse_enhanced_llm_dimension_response(
                llm_response, is_retrospective, num_dimensions
            )
            
            # 基于LLM分析生成思维路径（增强版）
            reasoning_paths = self._create_enhanced_reasoning_paths_from_analysis(
                dimension_result, effective_query, merged_context, num_dimensions
            )
            
            # 记录创建历史
            self._record_dimension_creation(effective_query, reasoning_paths, is_retrospective)
            
            logger.info(f"🧠 生成 {len(reasoning_paths)} 条思维路径")
            if is_retrospective:
                logger.info("✨ 回顾性创新维度生成完成")
            
            return reasoning_paths
            
        except Exception as e:
            logger.error(f"❌ LLM维度创建失败: {e}")
            # 回退到智能维度生成
            return self._create_fallback_reasoning_paths(
                effective_query, merged_context, str(e)
            )
        
    def _build_dimension_creation_prompt(self, user_query: str, execution_context: Optional[Dict] = None) -> str:
        """构建LLM维度创建提示"""
        
        context_info = ""
        if execution_context:
            context_info = f"\n🔧 执行环境信息: {json.dumps(execution_context, ensure_ascii=False, indent=2)}"
        
        # 添加历史学习信息
        historical_insights = self._get_historical_insights(user_query)
        
        # 使用配置中的提示模板
        prompt = PROMPT_TEMPLATES["dimension_creation"].format(
            user_query=user_query,
            context_info=context_info,
            historical_insights=historical_insights
        )
        
        return prompt
    
    def _build_enhanced_dimension_creation_prompt(self, 
                                                query: str, 
                                                context: Dict[str, Any], 
                                                num_dimensions: int,
                                                creativity_level: str) -> str:
        """
        构建增强版LLM维度创建提示，专门支持回顾性分析
        
        Args:
            query: 查询内容（可能是回顾性Prompt）
            context: 合并后的上下文信息
            num_dimensions: 需要生成的维度数量
            creativity_level: 创意级别
            
        Returns:
            增强版提示词
        """
        is_retrospective = (context.get("mode") == "retrospective_analysis")
        
        if is_retrospective:
            # 🔍 回顾性分析专用Prompt
            original_task = context.get("original_task", "未知任务")
            original_response = context.get("original_response", "未知回答")
            task_metadata = context.get("task_metadata", {})
            
            creativity_instruction = {
                "low": "保持实用性的前提下提供新视角",
                "medium": "平衡实用性与创新性，提供多样化思路", 
                "high": "优先考虑创新性和突破性，敢于提出大胆想法"
            }
            
            prompt = f"""
🔍 任务回溯与创新分析

原始任务：{original_task}
历史解决方案：{original_response[:300]}...
任务执行情况：{'成功' if task_metadata.get('success', False) else '失败'}
复杂度评估：{task_metadata.get('complexity', 0.5):.2f}

📋 分析要求：
{query}

🎯 创新指令：
请从全新角度重新审视这个历史任务，{creativity_instruction.get(creativity_level, '提供新思路')}。

📐 输出要求：
生成 {num_dimensions} 个不同的解决维度，每个维度应该：
1. 与历史方案明显不同
2. 具备可操作性
3. 体现独特的思考角度
4. 包含具体的实施步骤

格式：
维度1: [维度名称] - [核心思路] - [关键步骤]
维度2: [维度名称] - [核心思路] - [关键步骤]
...

请确保每个维度都是独立且创新的解决方案。
            """
            
        else:
            # 🎯 常规维度创建Prompt
            context_info = ""
            if context:
                context_info = f"\n🔧 执行环境信息: {json.dumps(context, ensure_ascii=False, indent=2)}"
            
            historical_insights = self._get_historical_insights(query)
            
            creativity_instruction = {
                "low": "基于现有最佳实践",
                "medium": "结合经验与创新",
                "high": "追求突破性解决方案"
            }
            
            prompt = f"""
🧠 智能维度分析与生成

用户查询：{query}
{context_info}

📚 历史洞察：
{historical_insights}

🎯 创新级别：{creativity_level} - {creativity_instruction.get(creativity_level, '平衡发展')}

📐 任务要求：
为上述查询生成 {num_dimensions} 个不同的思考维度，每个维度应该提供独特的解决角度。

输出格式：
维度1: [维度名称] - [核心思路] - [实施要点]
维度2: [维度名称] - [核心思路] - [实施要点]
...

请确保维度之间具有明显差异和互补性。
            """
        
        return prompt.strip()
    
    def _get_historical_insights(self, user_query: str) -> str:
        """获取历史学习洞察"""
        
        insights = []
        
        # 分析相似任务的历史维度创建
        similar_tasks = self._find_similar_tasks(user_query)
        if similar_tasks:
            insights.append(f"📈 发现{len(similar_tasks)}个相似任务的历史记录")
            
            # 分析高质量维度
            high_quality_dimensions = []
            for task_record in similar_tasks:
                for dim_name, score in task_record.get('dimension_scores', {}).items():
                    if score > 0.7:
                        high_quality_dimensions.append(dim_name)
            
            if high_quality_dimensions:
                unique_dims = list(set(high_quality_dimensions))
                insights.append(f"✅ 历史高质量维度: {', '.join(unique_dims[:5])}")
        
        # 分析维度创建模式
        if self.dimension_creation_patterns:
            common_patterns = []
            for pattern_type, patterns in self.dimension_creation_patterns.items():
                if len(patterns) >= 3:  # 至少出现3次的模式
                    common_patterns.append(pattern_type)
            
            if common_patterns:
                insights.append(f"🔄 常见创建模式: {', '.join(common_patterns[:3])}")
        
        return '\n'.join(insights) if insights else "🆕 首次处理此类任务，基于专业知识创建维度"
    
    def _find_similar_tasks(self, user_query: str) -> List[Dict]:
        """查找相似任务的历史记录"""
        
        similar_tasks = []
        query_keywords = set(user_query.lower().split())
        
        for task_key, task_records in self.task_dimension_mapping.items():
            task_keywords = set(task_key.lower().split())
            
            # 计算关键词重叠度
            if query_keywords and task_keywords:
                overlap = len(query_keywords.intersection(task_keywords))
                total = len(query_keywords.union(task_keywords))
                similarity = overlap / total if total > 0 else 0.0
                
                if similarity > 0.3:  # 相似度阈值
                    for record in task_records[-3:]:  # 取最近3条记录
                        record['similarity'] = similarity
                        similar_tasks.append(record)
        
        # 按相似度排序
        similar_tasks.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return similar_tasks[:5]  # 返回最相似的5个任务
    
    def _parse_llm_dimension_response(self, response: str) -> Dict[str, Any]:
        """解析LLM的维度创建响应"""
        
        try:
            result = parse_json_response(response)
            
            # 检查解析结果是否有效
            if result is None:
                logger.warning("⚠️ DeepSeek响应解析失败，使用默认结构")
                result = {
                    "task_analysis": {
                        "complexity": 0.5,
                        "domain": "unknown",
                        "key_challenges": ["代码实现", "错误处理"]
                    },
                    "suggested_dimensions": {},
                    "reasoning": "DeepSeek响应解析失败，使用默认结构"
                }
            
            # 验证响应结构
            if 'suggested_dimensions' not in result:
                logger.warning("⚠️ DeepSeek响应缺少suggested_dimensions字段")
                result['suggested_dimensions'] = self._create_fallback_dimensions(response)
            
            if 'task_analysis' not in result:
                result['task_analysis'] = {
                    "complexity": 0.5,
                    "domain": "unknown",
                    "key_challenges": ["代码实现", "错误处理"]
                }
            
            if 'reasoning' not in result:
                result['reasoning'] = "DeepSeek智能推理"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 解析DeepSeek响应失败: {e}")
            # 返回回退结构
            return {
                "task_analysis": {
                    "complexity": 0.5,
                    "domain": "unknown",
                    "key_challenges": ["代码实现", "错误处理"]
                },
                "suggested_dimensions": self._create_fallback_dimensions(response),
                "reasoning": "DeepSeek响应解析失败，使用智能回退维度"
            }
    
    def _parse_enhanced_llm_dimension_response(self, 
                                             response: str, 
                                             is_retrospective: bool,
                                             num_dimensions: int) -> Dict[str, Any]:
        """
        解析增强版LLM维度创建响应，支持回顾性分析格式
        
        Args:
            response: LLM的响应文本
            is_retrospective: 是否为回顾性分析模式
            num_dimensions: 期望的维度数量
            
        Returns:
            解析后的维度结果
        """
        try:
            if is_retrospective:
                # 🔍 解析回顾性分析响应
                dimensions = self._parse_retrospective_dimensions(response, num_dimensions)
                return {
                    "task_analysis": {
                        "mode": "retrospective",
                        "total_dimensions": len(dimensions),
                        "innovation_level": "high"
                    },
                    "suggested_dimensions": dimensions,
                    "reasoning": "回顾性分析生成的创新维度"
                }
            else:
                # 🎯 解析常规响应（向后兼容）
                return self._parse_llm_dimension_response(response)
                
        except Exception as e:
            logger.error(f"❌ 增强版响应解析失败: {e}")
            # 回退到基础解析
            fallback_dimensions = self._create_fallback_dimensions(response)
            return {
                "task_analysis": {
                    "complexity": 0.6,
                    "domain": "enhanced_analysis", 
                    "key_challenges": ["创新思维", "维度生成"]
                },
                "suggested_dimensions": fallback_dimensions,
                "reasoning": "增强版解析失败，使用智能回退"
            }
    
    def _parse_retrospective_dimensions(self, response: str, expected_count: int) -> Dict[str, Dict[str, str]]:
        """
        解析回顾性分析的维度响应
        
        Args:
            response: 回顾性分析的LLM响应
            expected_count: 期望的维度数量
            
        Returns:
            解析后的维度字典
        """
        dimensions = {}
        lines = response.split('\n')
        
        dimension_count = 0
        current_dimension = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检测维度格式：维度N: [维度名称] - [核心思路] - [关键步骤]
            import re
            dimension_match = re.match(r'维度(\d+):\s*(.+)', line)
            if dimension_match:
                dimension_num = dimension_match.group(1)
                content = dimension_match.group(2)
                
                # 解析维度内容
                parts = content.split(' - ')
                if len(parts) >= 3:
                    dimension_name = parts[0].strip()
                    core_idea = parts[1].strip()
                    key_steps = parts[2].strip()
                else:
                    dimension_name = f"创新维度{dimension_num}"
                    core_idea = content
                    key_steps = "待细化实施步骤"
                
                dimensions[f"retrospective_dim_{dimension_num}"] = {
                    "name": dimension_name,
                    "description": core_idea,
                    "implementation": key_steps,
                    "source": "retrospective_analysis",
                    "innovation_score": 0.8
                }
                
                dimension_count += 1
                
                if dimension_count >= expected_count:
                    break
        
        # 如果解析出的维度数量不足，补充创建
        while len(dimensions) < expected_count:
            fallback_id = f"retrospective_fallback_{len(dimensions) + 1}"
            dimensions[fallback_id] = {
                "name": f"创新突破维度{len(dimensions) + 1}",
                "description": "基于回顾性分析的创新思路",
                "implementation": "需要进一步具体化实施方案",
                "source": "retrospective_fallback",
                "innovation_score": 0.6
            }
        
        return dimensions
    
    def _create_fallback_dimensions(self, response: str) -> Dict[str, Dict[str, str]]:
        """🚀 创建完全动态的回退维度 - 基于任务语义零预设"""
        
        # 基于响应内容的关键词分析创建维度
        response_lower = response.lower()
        dimensions = {}
        
        # 🧠 动态提取核心概念生成维度名称
        core_concepts = []
        
        # 从响应中提取技术概念
        tech_concepts = {
            '网络': ['连接方式', '通信协议', '请求模式'],
            'api': ['接口设计', '调用策略', '响应处理'],
            '数据': ['存储方案', '处理流程', '访问模式'],
            '算法': ['计算方法', '优化策略', '执行路径'],
            '系统': ['架构设计', '运行模式', '扩展方案'],
            '用户': ['交互模式', '体验设计', '响应策略'],
            '安全': ['防护机制', '验证方式', '权限控制'],
            '性能': ['优化方向', '资源策略', '响应速度'],
            '存储': ['数据管理', '持久化方案', '访问优化'],
            '并发': ['处理模式', '同步策略', '资源分配']
        }
        
        # 动态识别相关概念
        for keyword, possible_dims in tech_concepts.items():
            if keyword in response_lower:
                selected_dim = random.choice(possible_dims)
                core_concepts.append((keyword, selected_dim))
        
        # 如果没有识别到特定概念，使用通用概念
        if not core_concepts:
            generic_concepts = [
                ('实现', '执行方式'),
                ('处理', '运行模式'),
                ('管理', '控制策略'),
                ('设计', '构建方案'),
                ('优化', '改进路径')
            ]
            core_concepts = random.sample(generic_concepts, random.randint(2, 3))
        
        # 🎯 基于核心概念生成维度和选项
        for concept_key, dimension_name in core_concepts[:4]:  # 最多4个维度
            # 动态生成选项
            if concept_key in ['网络', 'api', '请求']:
                options = {
                    "高效连接": f"采用高效的{dimension_name}方案",
                    "稳定连接": f"确保{dimension_name}的稳定性",
                    "智能连接": f"实现智能化的{dimension_name}"
                }
            elif concept_key in ['数据', '信息', '内容']:
                options = {
                    "流式方案": f"采用流式的{dimension_name}",
                    "批量方案": f"采用批量的{dimension_name}",
                    "实时方案": f"采用实时的{dimension_name}"
                }
            elif concept_key in ['算法', '计算', '处理']:
                options = {
                    "优化算法": f"使用优化的{dimension_name}",
                    "标准算法": f"使用标准的{dimension_name}",
                    "创新算法": f"采用创新的{dimension_name}"
                }
            elif concept_key in ['系统', '架构', '设计']:
                options = {
                    "模块化设计": f"采用模块化的{dimension_name}",
                    "集成化设计": f"采用集成化的{dimension_name}",
                    "分布式设计": f"采用分布式的{dimension_name}"
                }
            else:
                # 通用选项生成模式
                approaches = ["高效", "稳定", "智能", "优化", "标准", "创新"]
                selected_approaches = random.sample(approaches, 3)
                options = {
                    f"{approach}方案": f"采用{approach}的{dimension_name}方案"
                    for approach in selected_approaches
                }
            
            dimensions[dimension_name] = options
        
        # 确保至少有2个维度
        if len(dimensions) < 2:
            fallback_dims = {
                "执行方式": {
                    "直接执行": "采用直接的执行方式",
                    "分步执行": "采用分步的执行方式",
                    "智能执行": "采用智能的执行方式"
                },
                "资源管理": {
                    "高效管理": "实现高效的资源管理",
                    "均衡管理": "实现均衡的资源管理",
                    "智能管理": "实现智能的资源管理"
                }
            }
            for dim_name, options in fallback_dims.items():
                if dim_name not in dimensions:
                    dimensions[dim_name] = options
                    if len(dimensions) >= 2:
                        break
        
        return dimensions
    
    def _optimize_dimension_selection_traditional(self, suggested_dimensions: Dict[str, Dict[str, str]], 
                                                user_query: str, execution_context: Optional[Dict]) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """基于传统方法的维度选择优化"""
        
        logger.info("🎯 开始传统维度选择优化")
        
        optimized_selection = {}
        semantic_tracking = {
            'semantic_matching_results': {},
            'semantic_raw_responses': {},
            'fallback_dimensions': [],
            'success_count': 0,
            'total_count': 0
        }
        
        for dim_name, dim_options in suggested_dimensions.items():
            logger.info(f"🎯 优化维度选择：{dim_name}")
            
            # 使用简单的选项选择逻辑
            best_option = self._select_best_option_for_dimension_simple(
                dim_name, dim_options, user_query
            )
            optimized_selection[dim_name] = best_option
            
            # 记录基础跟踪信息
            semantic_tracking['total_count'] += 1
            semantic_tracking['success_count'] += 1  # 简化实现，假设成功
            semantic_tracking['semantic_matching_results'][dim_name] = {"method": "simple_selection"}
            semantic_tracking['semantic_raw_responses'][dim_name] = f"选择了 {best_option}"
            
            logger.debug(f"🎯 最终选择: {dim_name} -> {optimized_selection[dim_name]}")
        
        # 计算语义匹配成功率
        if semantic_tracking['total_count'] > 0:
            semantic_tracking['success_rate'] = semantic_tracking['success_count'] / semantic_tracking['total_count']
        else:
            semantic_tracking['success_rate'] = 0.0
        
        logger.info(f"🎉 传统维度选择完成 - 成功率：{semantic_tracking['success_rate']:.3f}")
            
        return optimized_selection, semantic_tracking
    
    def _select_best_option_for_dimension_simple(self, dim_name: str, dim_options: Dict[str, str], user_query: str) -> str:
        """简单的维度选项选择方法"""
        
        # 如果只有一个选项，直接返回
        if len(dim_options) == 1:
            return list(dim_options.keys())[0]
        
        # 简单的关键词匹配逻辑
        user_query_lower = user_query.lower()
        best_option = None
        best_score = 0
        
        for option_name, option_desc in dim_options.items():
            score = 0
            option_lower = (option_name + " " + option_desc).lower()
            
            # 基于简单的关键词匹配计分
            common_words = ['简单', '快速', '标准', '基础', '默认', '常规']
            if any(word in user_query_lower for word in common_words):
                if any(word in option_lower for word in common_words):
                    score += 2
            
            # 技术关键词匹配
            tech_words = ['技术', '算法', '系统', '架构', '开发', '实现']
            if any(word in user_query_lower for word in tech_words):
                if any(word in option_lower for word in tech_words):
                    score += 1
            
            # 性能关键词匹配
            perf_words = ['高效', '快速', '优化', '性能']
            if any(word in user_query_lower for word in perf_words):
                if any(word in option_lower for word in perf_words):
                    score += 1.5
            
            if score > best_score:
                best_score = score
                best_option = option_name
        
        # 如果没有匹配到，返回第一个选项
        return best_option or list(dim_options.keys())[0]
    
    def _calculate_dimension_confidences(self, selected_dimensions: Dict[str, str], 
                                       dimension_result: Dict[str, Any],
                                       user_query: str) -> Dict[str, float]:
        """计算维度选择的置信度"""
        
        confidence_scores = {}
        base_confidence = 0.7  # DeepSeek推理的基础置信度
        
        for dim_name, selected_option in selected_dimensions.items():
            confidence = base_confidence
            
            # 基于DeepSeek分析的复杂度调整
            task_complexity = dimension_result.get('task_analysis', {}).get('complexity', 0.5)
            complexity_adjustment = (1.0 - task_complexity) * 0.1  # 复杂度越低，置信度越高
            
            # 基于历史使用频率调整
            frequency_boost = min(0.2, self.dimension_usage_frequency[dim_name] * 0.02)
            
            # 基于维度质量评分调整
            quality_boost = self.dimension_quality_scores.get(dim_name, 0.5) * 0.2
            
            # 基于选项匹配度调整
            option_match_boost = self._calculate_option_match_confidence(
                dim_name, selected_option, user_query
            ) * 0.15
            
            # 综合计算最终置信度
            final_confidence = confidence + complexity_adjustment + frequency_boost + quality_boost + option_match_boost
            confidence_scores[dim_name] = min(1.0, max(0.1, final_confidence))
            
            logger.debug(f"🎯 置信度计算: {dim_name} = {final_confidence:.3f}")
        
        return confidence_scores
    
    def _calculate_option_match_confidence(self, dim_name: str, selected_option: str, user_query: str) -> float:
        """计算选项与查询的匹配置信度"""
        
        query_words = set(user_query.lower().split())
        option_words = set(selected_option.lower().split())
        
        # 计算词汇重叠度
        if query_words and option_words:
            overlap = len(query_words.intersection(option_words))
            total = len(query_words.union(option_words))
            word_overlap = overlap / total if total > 0 else 0.0
        else:
            word_overlap = 0.0
        
        # 计算语义匹配度（简化版本）
        semantic_match = 0.5  # 默认中等匹配
        
        # 基于关键词的语义匹配
        if "快速" in user_query.lower() and any(word in selected_option.lower() for word in ["快速", "高效", "速度"]):
            semantic_match = 0.9
        elif "稳定" in user_query.lower() and any(word in selected_option.lower() for word in ["稳定", "可靠"]):
            semantic_match = 0.9
        elif "简单" in user_query.lower() and any(word in selected_option.lower() for word in ["简洁", "轻量"]):
            semantic_match = 0.8
        
        return (word_overlap + semantic_match) / 2
    
    def _update_dimension_usage_history(self, selected_dimensions: Dict[str, str], 
                                      user_query: str, dimension_result: Dict[str, Any]):
        """更新维度使用历史"""
        
        # 更新使用频率
        for dim_name in selected_dimensions.keys():
            self.dimension_usage_frequency[dim_name] += 1
        
        # 记录任务-维度映射
        task_key = self._generate_task_key(user_query)
        if task_key not in self.task_dimension_mapping:
            self.task_dimension_mapping[task_key] = []
        
        task_record = {
            'timestamp': time.time(),
            'selected_dimensions': selected_dimensions,
            'task_analysis': dimension_result.get('task_analysis', {}),
            'dimension_scores': {},  # 将在反馈时更新
            'user_query_length': len(user_query)
        }
        
        self.task_dimension_mapping[task_key].append(task_record)
        
        # 限制历史记录大小
        if len(self.task_dimension_mapping[task_key]) > 10:
            self.task_dimension_mapping[task_key] = self.task_dimension_mapping[task_key][-10:]
        
        # 记录维度创建模式
        pattern_key = f"{len(selected_dimensions)}维度_{dimension_result.get('task_analysis', {}).get('domain', 'unknown')}"
        if pattern_key not in self.dimension_creation_patterns:
            self.dimension_creation_patterns[pattern_key] = []
        
        self.dimension_creation_patterns[pattern_key].append({
            'timestamp': time.time(),
            'dimensions': list(selected_dimensions.keys()),
            'complexity': dimension_result.get('task_analysis', {}).get('complexity', 0.5)
        })
        
        logger.info(f"📊 更新维度使用历史: {len(selected_dimensions)}个维度")
    
    def _generate_task_key(self, user_query: str) -> str:
        """生成任务关键字"""
        
        # 提取关键词生成任务键
        words = user_query.lower().split()
        
        # 过滤停用词
        stop_words = {'的', '是', '在', '有', '和', '或', '但', '如果', '请', '帮', '我', '一个', '这个', '那个'}
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        # 取前5个关键词
        key_words = keywords[:5]
        return '_'.join(key_words) if key_words else 'general_task'
    
    def _create_reasoning_paths_from_analysis(self, dimension_result: Dict[str, Any], 
                                             user_query: str, execution_context: Optional[Dict]) -> List[ReasoningPath]:
        """基于DeepSeek分析结果创建思维路径"""
        
        reasoning_paths = []
        task_analysis = dimension_result.get('task_analysis', {})
        domain = task_analysis.get('domain', 'general')
        complexity = task_analysis.get('complexity', 0.5)
        
        # 基于任务特性生成不同的思维路径
        if complexity < 0.3:
            # 简单任务：使用直接实用的路径
            reasoning_paths.append(ReasoningPath(
                path_id=f"practical_simple_{domain}_v1",
                path_type="实用直接型",
                description="适用于简单任务的直接实用方法",
                prompt_template="请直接提供解决方案：{task}。要求：1) 简洁明了 2) 立即可用"
            ))
        elif complexity > 0.7:
            # 复杂任务：使用系统分析路径
            reasoning_paths.append(ReasoningPath(
                path_id=f"systematic_complex_{domain}_v1", 
                path_type="系统分析型",
                description="适用于复杂任务的系统性分析方法",
                prompt_template="请系统性分析任务：{task}。步骤：1) 分解问题 2) 分析依赖 3) 制定方案 4) 评估风险"
            ))
            reasoning_paths.append(ReasoningPath(
                path_id=f"creative_complex_{domain}_v1",
                path_type="创新突破型", 
                description="适用于复杂任务的创新思维方法",
                prompt_template="请创新性解决：{task}。要求：1) 跳出传统思路 2) 寻找突破点 3) 提供新颖方案"
            ))
        else:
            # 中等复杂度：平衡的方法
            reasoning_paths.append(ReasoningPath(
                path_id=f"balanced_moderate_{domain}_v1",
                path_type="平衡综合型",
                description="适用于中等复杂度任务的平衡方法",
                prompt_template="请综合分析解决：{task}。方法：1) 理解需求 2) 评估方案 3) 实施建议"
            ))
        
        # 总是添加一个批判分析的路径作为备选
        reasoning_paths.append(ReasoningPath(
            path_id=f"critical_analysis_{domain}_v1",
            path_type="批判分析型",
            description="质疑假设、深度分析的批判性思维方法",
            prompt_template="请批判性分析：{task}。要求：1) 质疑基本假设 2) 分析潜在问题 3) 提供改进建议"
        ))
        
        return reasoning_paths
    
    def _create_enhanced_reasoning_paths_from_analysis(self, dimension_result: Dict[str, Any], 
                                                     effective_query: str, merged_context: Optional[Dict], 
                                                     num_dimensions: int) -> List[ReasoningPath]:
        """
        基于LLM分析生成思维路径（增强版）
        
        Args:
            dimension_result: LLM维度分析结果
            effective_query: 有效查询
            merged_context: 合并的上下文
            num_dimensions: 维度数量
            
        Returns:
            List[ReasoningPath]: 生成的思维路径列表
        """
        try:
            logger.info(f"🧠 基于增强版LLM分析生成思维路径")
            
            # 提取任务分析结果
            task_analysis = dimension_result.get('task_analysis', {})
            domain = task_analysis.get('domain', 'general')
            complexity = task_analysis.get('complexity', 0.5)
            creativity_required = task_analysis.get('creativity_required', False)
            
            reasoning_paths = []
            
            # 基于复杂度和创造性需求生成不同的思维路径
            if creativity_required or complexity > 0.8:
                # 高复杂度或需要创造性：生成创新路径
                reasoning_paths.append(ReasoningPath(
                    path_id=f"enhanced_creative_{domain}_v1",
                    path_type="创新突破型",
                    description=f"针对{domain}领域的创新思维路径",
                    prompt_template="请用创新思维解决：{task}。要求：1) 突破传统思路 2) 寻找新颖角度 3) 提供创造性方案"
                ))
                
                reasoning_paths.append(ReasoningPath(
                    path_id=f"enhanced_systematic_{domain}_v1", 
                    path_type="系统分析型",
                    description=f"针对{domain}领域的系统性分析路径",
                    prompt_template="请系统性分析：{task}。步骤：1) 问题分解 2) 要素分析 3) 关联梳理 4) 方案构建"
                ))
                
            if complexity < 0.3:
                # 低复杂度：生成直接路径
                reasoning_paths.append(ReasoningPath(
                    path_id=f"enhanced_direct_{domain}_v1",
                    path_type="直接实用型",
                    description=f"针对{domain}领域的直接实用路径",
                    prompt_template="请直接解决：{task}。要求：1) 简洁明了 2) 立即可用 3) 效果明显"
                ))
            else:
                # 中等复杂度：生成平衡路径
                reasoning_paths.append(ReasoningPath(
                    path_id=f"enhanced_balanced_{domain}_v1",
                    path_type="平衡综合型", 
                    description=f"针对{domain}领域的平衡综合路径",
                    prompt_template="请综合分析解决：{task}。方法：1) 需求理解 2) 方案评估 3) 优化实施"
                ))
            
            # 总是添加批判性思维路径
            reasoning_paths.append(ReasoningPath(
                path_id=f"enhanced_critical_{domain}_v1",
                path_type="批判分析型",
                description=f"针对{domain}领域的批判性分析路径",
                prompt_template="请批判性分析：{task}。要求：1) 质疑基本假设 2) 识别潜在问题 3) 提供改进方案"
            ))
            
            # 限制返回路径数量
            if len(reasoning_paths) > num_dimensions:
                reasoning_paths = reasoning_paths[:num_dimensions]
            
            logger.info(f"✅ 增强版分析生成 {len(reasoning_paths)} 条思维路径")
            return reasoning_paths
            
        except Exception as e:
            logger.error(f"❌ 增强版思维路径生成失败: {e}")
            # 回退到基础版本
            return self._create_reasoning_paths_from_analysis(dimension_result, effective_query, merged_context)

    def _create_fallback_reasoning_paths(self, user_query: str, execution_context: Optional[Dict], error_msg: str) -> List[ReasoningPath]:
        """创建回退思维路径"""
        
        logger.warning(f"🔄 使用回退思维路径创建: {error_msg}")
        
        # 提供基础的通用思维路径
        return [
            ReasoningPath(
                path_id="fallback_systematic_v1",
                path_type="系统方法型",
                description="通用的系统性方法（回退）",
                prompt_template="请系统性处理以下任务：{task}。步骤：1) 分析 2) 计划 3) 执行"
            ),
            ReasoningPath(
                path_id="fallback_practical_v1", 
                path_type="实用解决型",
                description="通用的实用解决方法（回退）",
                prompt_template="请提供实用解决方案：{task}。要求：简单可行，立即实施"
            )
        ]

    def _record_dimension_creation(self, query: str, reasoning_paths: List[ReasoningPath], is_retrospective: bool = False):
        """记录维度创建历史和统计信息"""
        try:
            # 记录基本统计
            creation_record = {
                "query": query[:100],  # 限制长度避免过长
                "paths_created": len(reasoning_paths),
                "is_retrospective": is_retrospective,
                "timestamp": time.time(),
                "path_types": [path.path_type for path in reasoning_paths]
            }
            
            # 添加到创建模式历史
            self.dimension_creation_patterns["all_creations"].append(creation_record)
            
            # 更新任务-维度映射
            query_key = query[:50]  # 使用查询的前50个字符作为键
            self.task_dimension_mapping[query_key].extend([path.path_id for path in reasoning_paths])
            
            # 更新维度使用频率
            for path in reasoning_paths:
                self.dimension_usage_frequency[path.path_type] += 1
                
                # 存储发现的维度详情
                self.discovered_dimensions[path.path_type][path.path_id] = {
                    "description": path.description,
                    "created_at": time.time(),
                    "query_context": query_key,
                    "is_retrospective": is_retrospective
                }
            
            # 更新LLM会话历史
            session_record = {
                "query": query_key,
                "result_count": len(reasoning_paths),
                "success": True,
                "timestamp": time.time()
            }
            self.llm_session_history.append(session_record)
            
            # 限制历史记录长度，避免内存占用过多
            if len(self.llm_session_history) > 100:
                self.llm_session_history = self.llm_session_history[-50:]  # 保留最近50条
            if len(self.dimension_creation_patterns["all_creations"]) > 100:
                self.dimension_creation_patterns["all_creations"] = self.dimension_creation_patterns["all_creations"][-50:]
                
            logger.debug(f"✅ 记录维度创建: {len(reasoning_paths)} 个路径")
            
        except Exception as e:
            logger.warning(f"⚠️ 记录维度创建失败: {e}")


class ReasoningPathTemplates:
    """
    🧠 动态思维路径模板管理器 - 可成长的"大脑皮层"
    
    从静态模板升级为动态管理实例，支持：
    1. 持久化存储和加载
    2. 运行时动态添加新路径
    3. 性能跟踪和智能推荐
    4. 版本管理和演化追踪
    
    向后兼容：保持原有API接口不变
    """
    
    _instance = None
    _initialized = False
    
    def __init__(self, 
                 storage_backend: str = "json",
                 storage_path: str = "data/reasoning_paths",
                 enable_learning: bool = True):
        """
        初始化动态路径模板管理器
        
        Args:
            storage_backend: 存储后端 ("json", "sqlite", "memory")
            storage_path: 存储路径
            enable_learning: 是否启用自学习功能
        """
        if not ReasoningPathTemplates._initialized:
            # 延迟导入以避免循环依赖
            from .path_library import DynamicPathLibrary, StorageBackend
            
            # 创建动态路径库
            backend_map = {
                "json": StorageBackend.JSON,
                "sqlite": StorageBackend.SQLITE,
                "memory": StorageBackend.MEMORY
            }
            
            self.path_library = DynamicPathLibrary(
                storage_backend=backend_map.get(storage_backend, StorageBackend.JSON),
                storage_path=storage_path
            )
            
            self.enable_learning = enable_learning
            
            # 检查是否需要从静态模板迁移
            if len(self.path_library._cache) == 0:
                logger.info("🚚 检测到空的路径库，执行静态模板迁移...")
                static_templates = self._get_static_templates()
                migrated_count = self.path_library.migrate_from_templates(static_templates)
                logger.info(f"✅ 静态模板迁移完成: {migrated_count} 个路径")
            
            ReasoningPathTemplates._initialized = True
            logger.info("🧠 动态路径模板管理器已初始化")
    
    @classmethod
    def get_instance(cls, **kwargs):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance
    
    def get_all_templates(self) -> Dict[str, ReasoningPath]:
        """
        获取所有可用的路径模板
        
        保持向后兼容性的接口方法
        
        Returns:
            路径模板字典 {template_id: ReasoningPath}
        """
        templates = {}
        
        # 🔧 根源修复：首先检查动态路径库状态
        all_paths = self.path_library.get_all_paths(include_retired=False)
        logger.debug(f"🔍 动态路径库状态: {len(all_paths)} 个路径")
        
        if not all_paths:
            logger.warning("⚠️ 动态路径库为空，直接返回静态模板")
            return self._get_static_templates()
        
        for path_id, enhanced_path in all_paths.items():
            try:
                # 转换为标准ReasoningPath对象
                reasoning_path = enhanced_path.to_reasoning_path()
                
                # 🔧 根源修复：正确的键名映射逻辑
                # 需要保证键名与路径选择器的期望一致
                if enhanced_path.strategy_id and not enhanced_path.strategy_id.endswith('_v1'):
                    # 如果strategy_id不带版本后缀，直接使用
                    template_key = enhanced_path.strategy_id
                else:
                    # 从path_id中提取策略名（去掉版本后缀）
                    template_key = path_id.replace('_v1', '') if '_v1' in path_id else path_id
                
                templates[template_key] = reasoning_path
                logger.debug(f"✅ 模板映射: {template_key} -> {reasoning_path.path_type}")
                
            except Exception as e:
                logger.warning(f"⚠️ 转换路径模板失败 {path_id}: {e}")
        
        logger.info(f"✅ 成功加载 {len(templates)} 个路径模板: {list(templates.keys())}")
        
        # 🔧 如果转换后仍为空，返回静态模板
        if not templates:
            logger.warning("⚠️ 路径模板转换后为空，返回静态模板")
            return self._get_static_templates()
        
        return templates
    
    @staticmethod  
    def get_all_templates_static() -> Dict[str, ReasoningPath]:
        """
        静态方法版本 - 向后兼容
        
        这个方法保持了原有的静态调用方式，但内部使用动态库
        """
        instance = ReasoningPathTemplates.get_instance()
        return instance.get_all_templates()
    
    def _get_static_templates(self) -> Dict[str, ReasoningPath]:
        """获取原有的静态模板 - 用于迁移"""
        return {
            # 系统性思维
            "systematic_analytical": ReasoningPath(
                path_id="systematic_analytical_v1",
                path_type="系统分析型",
                description="系统性分解和分析问题，适用于复杂任务和技术问题",
                prompt_template="""请系统性分析任务：{task}

🔍 **分析步骤**:
1. **问题分解**: 将复杂问题拆分为可管理的子问题
2. **关键要素识别**: 找出影响成功的关键因素
3. **依赖关系分析**: 分析各部分之间的关联和依赖
4. **风险评估**: 识别潜在风险和挑战
5. **解决方案设计**: 基于分析制定系统性解决方案

基于思维种子：{thinking_seed}
请提供结构化、系统性的分析和解决方案。"""
            ),
            
            # 创新性思维
            "creative_innovative": ReasoningPath(
                path_id="creative_innovative_v1", 
                path_type="创新突破型",
                description="跳出传统思路，寻求创新和突破，适用于需要创意的任务",
                prompt_template="""请创新性解决任务：{task}

💡 **创新方法**:
1. **打破常规**: 质疑传统方法和假设
2. **跨领域思考**: 从其他领域寻找灵感和方法
3. **逆向思维**: 考虑反向或非常规的解决路径  
4. **组合创新**: 将不同概念、技术或方法进行创新组合
5. **未来前瞻**: 考虑新兴技术和趋势的应用

基于思维种子：{thinking_seed}
请提供创新、独特且可行的解决方案。"""
            ),
            
            # 批判性思维
            "critical_questioning": ReasoningPath(
                path_id="critical_questioning_v1",
                path_type="批判质疑型", 
                description="深度质疑和批判分析，适用于需要严谨论证的任务",
                prompt_template="""请批判性分析任务：{task}

🤔 **批判要点**:
1. **假设质疑**: 质疑基本假设和前提条件
2. **证据评估**: 分析现有证据的可靠性和充分性
3. **逻辑检验**: 检查推理过程的逻辑严密性
4. **多角度审视**: 从不同立场和角度审视问题
5. **反驳论证**: 考虑可能的反对意见和反驳

基于思维种子：{thinking_seed}
请提供严谨的批判性分析和论证。"""
            ),
            
            # 实用性思维
            "practical_pragmatic": ReasoningPath(
                path_id="practical_pragmatic_v1",
                path_type="实用务实型",
                description="注重实际可行性和立即执行，适用于需要快速解决的实际问题",
                prompt_template="""请务实地解决任务：{task}

⚡ **实用策略**:
1. **快速可行**: 优先考虑立即可实施的方案
2. **资源约束**: 在现有资源和限制下寻找解决方案
3. **风险可控**: 选择风险低、成功率高的方法
4. **效果导向**: 专注于能产生实际效果的行动
5. **迭代改进**: 采用小步快跑、持续改进的方式

基于思维种子：{thinking_seed}
请提供简单直接、立即可行的实用解决方案。"""
            ),
            
            # 整体性思维
            "holistic_comprehensive": ReasoningPath(
                path_id="holistic_comprehensive_v1",
                path_type="整体综合型",
                description="从全局和整体角度考虑问题，适用于需要平衡多方因素的复杂情况",
                prompt_template="""请整体性分析任务：{task}

🌐 **整体视角**:
1. **全局考量**: 从更大的背景和环境中理解问题
2. **多元平衡**: 平衡不同利益相关者的需求和关切
3. **长远影响**: 考虑决策的长期影响和后果
4. **系统互动**: 理解各部分之间的复杂互动关系
5. **综合权衡**: 综合考虑各种因素，寻找最佳平衡点

基于思维种子：{thinking_seed}
请提供全面、平衡的整体性分析和建议。"""
            ),
            
            # 探索性思维
            "exploratory_investigative": ReasoningPath(
                path_id="exploratory_investigative_v1",
                path_type="探索调研型",
                description="深入调研和探索未知领域，适用于研究性和学习性任务",
                prompt_template="""请探索性研究任务：{task}

🔬 **探索方法**:
1. **深度调研**: 广泛收集和分析相关信息
2. **多源验证**: 从多个来源验证信息的准确性
3. **模式识别**: 寻找数据中的模式和规律
4. **假设验证**: 提出假设并设计验证方法
5. **知识整合**: 将发现整合为系统性的理解

基于思维种子：{thinking_seed}
请提供深入、全面的探索性分析和发现。"""
            ),
            
            # 协作性思维
            "collaborative_consultative": ReasoningPath(
                path_id="collaborative_consultative_v1",
                path_type="协作咨询型",
                description="考虑多方参与和协作，适用于需要团队合作的任务",
                prompt_template="""请协作性解决任务：{task}

🤝 **协作策略**:
1. **利益相关者分析**: 识别关键参与者和利益相关者
2. **沟通机制设计**: 建立有效的沟通和协调机制
3. **共识建立**: 寻找各方都能接受的解决方案
4. **分工协作**: 合理分配任务和责任
5. **冲突解决**: 预见并解决可能的冲突和分歧

基于思维种子：{thinking_seed}
请提供促进协作、建立共识的解决方案。"""
            ),
            
            # 适应性思维  
            "adaptive_flexible": ReasoningPath(
                path_id="adaptive_flexible_v1",
                path_type="适应灵活型",
                description="灵活适应变化，适用于不确定性高的动态环境",
                prompt_template="""请灵活地应对任务：{task}

🔄 **适应策略**:
1. **情况评估**: 分析当前情况的不确定性和变化性
2. **多方案准备**: 准备多个备选方案以应对不同情况
3. **敏捷响应**: 建立快速响应和调整的机制
4. **学习迭代**: 从实践中学习并持续调整策略
5. **弹性设计**: 设计具有弹性和韧性的解决方案

基于思维种子：{thinking_seed}
请提供灵活、可适应的解决方案。"""
            )
        }
    
    def add_learned_path(self, 
                        path: ReasoningPath, 
                        learning_source: str = "unknown",
                        effectiveness_score: float = 0.5) -> bool:
        """
        添加学习到的新路径
        
        Args:
            path: 新的推理路径
            learning_source: 学习来源
            effectiveness_score: 初始效果评分
            
        Returns:
            bool: 是否添加成功
        """
        if not self.enable_learning:
            logger.warning("⚠️ 学习功能未启用，跳过添加新路径")
            return False
        
        try:
            # 延迟导入
            from .path_library import EnhancedReasoningPath, PathMetadata, PathCategory, PathStatus
            
            # 创建增强路径
            enhanced_path = EnhancedReasoningPath(
                path_id=path.path_id,
                path_type=path.path_type,
                description=path.description,
                prompt_template=path.prompt_template,
                strategy_id=path.strategy_id,
                instance_id=path.instance_id,
                metadata=PathMetadata(
                    created_at=time.time(),
                    author=learning_source,
                    category=PathCategory.EXPERIMENTAL,
                    status=PathStatus.EXPERIMENTAL,
                    tags=["learned", "adaptive"],
                    complexity_level="medium"
                ),
                is_learned=True,
                learning_source=learning_source,
                effectiveness_score=effectiveness_score
            )
            
            # 添加到库中
            success = self.path_library.add_path(enhanced_path)
            
            if success:
                logger.info(f"🌱 新增学习路径: {path.path_type}")
                logger.debug(f"   来源: {learning_source}")
                logger.debug(f"   路径ID: {path.path_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 添加学习路径失败: {e}")
            return False
    
    def learn_from_exploration(self, exploration_result: Dict[str, Any]) -> int:
        """
        从知识探索结果中学习新路径
        
        Args:
            exploration_result: 探索结果
            
        Returns:
            int: 新增路径数量
        """
        if not self.enable_learning:
            return 0
        
        new_path_count = len(self.path_library.learn_from_exploration(
            exploration_result, 
            source="knowledge_exploration"
        ))
        
        if new_path_count > 0:
            logger.info(f"🌐 从探索结果学习到 {new_path_count} 个新路径")
        
        return new_path_count
    
    def get_recommended_paths(self, 
                            task_context: Optional[Dict[str, Any]] = None,
                            max_recommendations: int = 3) -> List[ReasoningPath]:
        """
        获取推荐的路径
        
        Args:
            task_context: 任务上下文
            max_recommendations: 最大推荐数量
            
        Returns:
            推荐的路径列表
        """
        enhanced_paths = self.path_library.recommend_paths(
            task_context=task_context,
            max_recommendations=max_recommendations
        )
        
        # 转换为标准ReasoningPath对象
        return [ep.to_reasoning_path() for ep in enhanced_paths]
    
    def update_path_performance(self, 
                               path_id: str, 
                               success: bool, 
                               execution_time: float,
                               rating: Optional[float] = None) -> bool:
        """
        更新路径性能
        
        Args:
            path_id: 路径ID
            success: 是否成功
            execution_time: 执行时间
            rating: 用户评分
            
        Returns:
            bool: 是否更新成功
        """
        return self.path_library.update_path_performance(
            path_id, success, execution_time, rating
        )
    
    def get_library_stats(self) -> Dict[str, Any]:
        """获取路径库统计信息"""
        return self.path_library.get_library_stats()
    
    def backup_library(self, backup_path: Optional[str] = None) -> bool:
        """
        备份路径库
        
        Args:
            backup_path: 备份路径
            
        Returns:
            bool: 备份是否成功
        """
        return self.path_library.backup(backup_path)
    
    # 🗑️ 已删除：关键词映射方法 - 改用LLM智能分析
    # 原有的 get_keyword_mapping() 方法已被 LLM 自然语言分析替代
    # 这大大提高了语义理解能力，无需维护静态关键词列表


@dataclass  
class PathGenerator:
    """路径生成器 - 基于思维种子生成多样化思维路径 (阶段二)"""
    
    def __init__(self, api_key: str = "", llm_client=None):
        """
        初始化路径生成器
        
        Args:
            api_key: API密钥（向后兼容）
            llm_client: 共享的LLM客户端（依赖注入）
        """
        self.api_key = api_key
        
        # 🔧 依赖注入：使用传入的LLM客户端（纯依赖注入模式）
        self.llm_analyzer = llm_client
        if self.llm_analyzer:
            logger.info("🧠 LLM思维种子分析器已启用 (使用共享客户端)")
        else:
            logger.warning("⚠️ 未提供LLM客户端，思维种子分析将无法使用AI功能")
            logger.info("💡 请确保从上层（MainController）传入有效的llm_client")
        
        # 🔧 依赖注入：为维度创建器传入共享客户端
        self.dimension_selector = None
        if llm_client:
            self.dimension_selector = LLMDrivenDimensionCreator(api_key, llm_client=llm_client)
        else:
            logger.warning("⚠️ 维度创建器无法初始化，缺少LLM客户端")
        
        self.generation_cache = {}
        
        # 🧠 新增：动态路径模板管理器
        self.path_template_manager = ReasoningPathTemplates.get_instance()
        
        # 新增：思维路径相关缓存和统计
        self.path_generation_cache = {}
        self.path_templates = self.path_template_manager.get_all_templates()
        # 删除关键词映射，改用LLM分析
        # self.keyword_mapping = ReasoningPathTemplates.get_keyword_mapping()
        self.path_selection_stats = defaultdict(int)
        
        logger.info("🛤️ PathGenerator 已初始化 (支持LLM增强的思维种子→路径生成)")
    
    def generate_reasoning_paths(self, thinking_seed: str, user_query: str, max_paths: int = 4, 
                               execution_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        生成推理路径 - NeogenesisPlanner兼容接口
        
        这个方法是为了兼容NeogenesisPlanner中的调用，将generate_paths的结果
        包装成期望的字典格式。
        
        Args:
            thinking_seed: 思维种子
            user_query: 用户查询
            max_paths: 最大路径数
            execution_context: 执行上下文
            
        Returns:
            Dict: 包含paths和diversity_score的字典
        """
        try:
            logger.info(f"🛤️ 生成推理路径 (兼容接口): {thinking_seed[:50]}...")
            
            # 调用核心的generate_paths方法
            reasoning_paths = self.generate_paths(
                thinking_seed=thinking_seed,
                task=user_query,
                max_paths=max_paths,
                mode='normal'
            )
            
            # 计算多样性评分
            diversity_score = self._calculate_diversity_score(reasoning_paths)
            
            # 包装成期望的格式
            result = {
                "paths": reasoning_paths,
                "diversity_score": diversity_score,
                "generation_method": "llm_enhanced_path_generation",
                "total_paths": len(reasoning_paths),
                "thinking_seed": thinking_seed,
                "user_query": user_query
            }
            
            logger.info(f"✅ 推理路径生成完成: {len(reasoning_paths)}条路径, 多样性: {diversity_score:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 推理路径生成失败: {e}")
            # 返回空结果但保持格式一致
            return {
                "paths": [],
                "diversity_score": 0.0,
                "generation_method": "fallback",
                "total_paths": 0,
                "error": str(e)
            }
    
    def _calculate_diversity_score(self, paths: List[ReasoningPath]) -> float:
        """
        计算路径多样性评分
        
        Args:
            paths: 路径列表
            
        Returns:
            float: 多样性评分 (0.0-1.0)
        """
        if not paths or len(paths) <= 1:
            return 0.0
        
        try:
            # 基于路径类型的多样性
            path_types = set(path.path_type for path in paths)
            type_diversity = len(path_types) / len(paths)
            
            # 基于复杂度的多样性
            complexities = [getattr(path, 'complexity_level', 3) for path in paths]
            if len(set(complexities)) > 1:
                complexity_diversity = len(set(complexities)) / len(complexities)
            else:
                complexity_diversity = 0.5
            
            # 基于描述长度的多样性（简单指标）
            desc_lengths = [len(path.description) for path in paths]
            if max(desc_lengths) > min(desc_lengths):
                length_diversity = (max(desc_lengths) - min(desc_lengths)) / max(desc_lengths)
            else:
                length_diversity = 0.5
            
            # 综合评分
            diversity_score = (type_diversity * 0.5 + complexity_diversity * 0.3 + length_diversity * 0.2)
            
            return min(diversity_score, 1.0)
            
        except Exception as e:
            logger.warning(f"⚠️ 多样性评分计算失败: {e}")
            return 0.5  # 默认中等多样性
        
    def generate_paths(self, thinking_seed: str, task: str = "", max_paths: int = 4, mode: str = 'normal') -> List[ReasoningPath]:
        """
        阶段二核心方法：基于思维种子生成多样化思维路径列表
        
        Args:
            thinking_seed: 来自阶段一的思维种子
            task: 原始任务描述 (用于填充路径模板)
            max_paths: 最大生成路径数
            mode: 生成模式 ('normal' | 'creative_bypass')
            
        Returns:
            多样化的思维路径列表
        """
        # 💡 Aha-Moment决策：creative_bypass模式跳过缓存，确保创造性
        use_cache = (mode != 'creative_bypass')
        
        # 检查缓存
        cache_key = f"paths_{hash(thinking_seed)}_{hash(task)}_{max_paths}_{mode}"
        if use_cache and cache_key in self.path_generation_cache:
            logger.debug(f"🎯 使用缓存的路径生成: {cache_key[:20]}...")
            return self.path_generation_cache[cache_key]
        
        if mode == 'creative_bypass':
            logger.info(f"💡 Aha-Moment创造性绕道模式: {thinking_seed[:50]}...")
        else:
            logger.info(f"🌱 开始基于思维种子生成路径: {thinking_seed[:50]}...")
        
        try:
            # 分析思维种子，识别关键信息
            seed_analysis = self._analyze_thinking_seed(thinking_seed)
            logger.debug(f"🔍 种子分析结果: {seed_analysis}")
            
            # 💡 根据模式选择路径类型策略
            if mode == 'creative_bypass':
                # Aha-Moment模式：优先选择创造性和突破性路径类型
                selected_path_types = self._select_creative_bypass_path_types(seed_analysis, max_paths)
                logger.info(f"🌟 创造性绕道路径类型: {selected_path_types}")
            else:
                # 常规模式：根据分析结果选择合适的路径模板
                selected_path_types = self._select_path_types(seed_analysis, max_paths)
                logger.info(f"📋 选择的路径类型: {selected_path_types}")
            
            # 生成具体的思维路径实例
            reasoning_paths = self._instantiate_reasoning_paths(
                selected_path_types, thinking_seed, task
            )
            
            # 缓存结果（creative_bypass模式下可以缓存，但缓存键包含模式信息）
            if use_cache or mode == 'creative_bypass':
                self.path_generation_cache[cache_key] = reasoning_paths
                self._manage_path_cache()
            
            # 更新统计信息
            for path in reasoning_paths:
                self.path_selection_stats[path.path_type] += 1
            
            logger.info(f"✅ 生成 {len(reasoning_paths)} 条思维路径")
            return reasoning_paths
            
        except Exception as e:
            logger.error(f"❌ 思维路径生成失败: {e}")
            # fallback到默认路径
            return self._generate_fallback_paths(thinking_seed, task)
    
    def _analyze_thinking_seed(self, thinking_seed: str) -> Dict[str, Any]:
        """
         LLM增强的思维种子分析 - 替代关键词匹配的智能分析
        
        Args:
            thinking_seed: 思维种子字符串
            
        Returns:
            分析结果字典
        """
        logger.debug(f" 开始LLM分析思维种子: {thinking_seed[:50]}...")
        
        # 如果LLM分析器可用，使用智能分析
        if self.llm_analyzer:
            try:
                return self._llm_analyze_thinking_seed(thinking_seed)
            except Exception as e:
                logger.warning(f"⚠️ LLM分析失败，回退到启发式分析: {e}")
                return self._heuristic_analyze_thinking_seed(thinking_seed)
        else:
            logger.info("🔄 LLM分析器不可用，使用启发式分析")
            return self._heuristic_analyze_thinking_seed(thinking_seed)
    
    def _llm_analyze_thinking_seed(self, thinking_seed: str) -> Dict[str, Any]:
        """
        使用LLM进行智能思维种子分析
        
        Args:
            thinking_seed: 思维种子
            
        Returns:
            分析结果字典
        """
        # 构建LLM分析提示
        analysis_prompt = self._build_seed_analysis_prompt(thinking_seed)
        
        # 调用LLM进行分析
        llm_response = self.llm_analyzer.call_api(
            prompt=analysis_prompt,
            temperature=0.3,  # 较低温度确保稳定性
            system_message="你是一个专业的思维模式分析师，能够准确识别文本中的思考特征和需求。"
        )
        
        # 解析LLM响应
        analysis_result = self._parse_llm_analysis_response(llm_response)
        
        logger.debug(f"✅ LLM分析完成: {len(analysis_result['path_relevance'])}个路径类型被评估")
        return analysis_result
    
    def _build_seed_analysis_prompt(self, thinking_seed: str) -> str:
        """
        构建思维种子分析的LLM提示
        
        Args:
            thinking_seed: 思维种子
            
        Returns:
            格式化的提示字符串
        """
        # 获取所有可用的思维路径类型及其描述
        path_descriptions = {
            "systematic_analytical": "系统方法型 - 逻辑分析、结构化思考、工程方法",
            "creative_innovative": "创新直觉型 - 创造性思维、突破常规、艺术灵感",
            "critical_questioning": "批判质疑型 - 质疑分析、风险评估、审视检验",
            "practical_pragmatic": "实用导向型 - 实际可行、简单直接、效率优先",
            "holistic_comprehensive": "综合全面型 - 整体考虑、全局思维、平衡协调",
            "exploratory_investigative": "探索研究型 - 研究学习、深入调查、知识获取",
            "collaborative_consultative": "协作咨询型 - 团队合作、沟通交流、集体智慧",
            "adaptive_flexible": "适应灵活型 - 灵活应变、动态调整、敏捷响应"
        }
        
        path_list = "\n".join([f"- {key}: {desc}" for key, desc in path_descriptions.items()])
        
        prompt = f"""
作为思维模式分析专家，请深度分析以下思维种子，识别其思考特征和需求。

 **待分析的思维种子**:
{thinking_seed}

 **分析任务**:
1. 评估这个思维种子与以下8种思维路径类型的相关程度（0.0-1.0评分）
2. 识别思维种子中体现的特殊需求和特征
3. 判断问题的复杂度和紧急程度

 **思维路径类型说明**:
{path_list}

 **请按以下JSON格式严格返回分析结果**:
{{
    "path_relevance": {{
        "systematic_analytical": 0.0到1.0的相关度评分,
        "creative_innovative": 0.0到1.0的相关度评分,
        "critical_questioning": 0.0到1.0的相关度评分,
        "practical_pragmatic": 0.0到1.0的相关度评分,
        "holistic_comprehensive": 0.0到1.0的相关度评分,
        "exploratory_investigative": 0.0到1.0的相关度评分,
        "collaborative_consultative": 0.0到1.0的相关度评分,
        "adaptive_flexible": 0.0到1.0的相关度评分
    }},
    "characteristics": {{
        "urgency_level": "low|normal|high",
        "collaborative_need": true或false,
        "innovation_requirement": true或false,
        "critical_analysis_need": true或false,
        "practical_focus": true或false,
        "comprehensive_scope": true或false,
        "research_oriented": true或false,
        "adaptive_requirement": true或false
    }},
    "complexity_assessment": {{
        "complexity_score": 0.0到1.0的复杂度评分,
        "complexity_indicators": ["指标1", "指标2", "指标3"],
        "domain_hints": ["领域1", "领域2"]
    }},
    "reasoning": "简要解释你的分析依据和思路"
}}

请基于思维种子的语义内容、隐含需求和上下文进行深度分析，而不是简单的关键词匹配。
"""
        return prompt.strip()
    
    def _parse_llm_analysis_response(self, llm_response: str) -> Dict[str, Any]:
        """
        解析LLM的分析响应，转换为标准格式
        
        Args:
            llm_response: LLM响应字符串
            
        Returns:
            标准格式的分析结果
        """
        try:
            # 尝试解析JSON响应
            import json
            import re
            
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                llm_analysis = json.loads(json_str)
                
                # 转换为兼容原有接口的格式
                analysis = {
                    'path_relevance': llm_analysis.get('path_relevance', {}),
                    'complexity_indicators': llm_analysis.get('complexity_assessment', {}).get('complexity_indicators', []),
                    'domain_hints': llm_analysis.get('complexity_assessment', {}).get('domain_hints', []),
                    'complexity_score': llm_analysis.get('complexity_assessment', {}).get('complexity_score', 0.5),
                    'llm_reasoning': llm_analysis.get('reasoning', ''),
                    
                    # 特殊需求 - 从LLM分析中提取
                    'urgency_level': llm_analysis.get('characteristics', {}).get('urgency_level', 'normal'),
                    'collaborative_need': llm_analysis.get('characteristics', {}).get('collaborative_need', False),
                    'innovation_requirement': llm_analysis.get('characteristics', {}).get('innovation_requirement', False),
                    'critical_analysis_need': llm_analysis.get('characteristics', {}).get('critical_analysis_need', False),
                    'practical_focus': llm_analysis.get('characteristics', {}).get('practical_focus', False),
                    'comprehensive_scope': llm_analysis.get('characteristics', {}).get('comprehensive_scope', False),
                    'research_oriented': llm_analysis.get('characteristics', {}).get('research_oriented', False),
                    'adaptive_requirement': llm_analysis.get('characteristics', {}).get('adaptive_requirement', False),
                    
                    # 兼容性字段：模拟keywords_found格式
                    'keywords_found': self._convert_relevance_to_keywords(llm_analysis.get('path_relevance', {})),
                    
                    # 标记分析来源
                    'analysis_source': 'llm'
                }
                
                return analysis
            else:
                logger.warning("⚠️ LLM响应中未找到有效JSON，使用启发式分析")
                return self._create_fallback_analysis(llm_response)
                
        except Exception as e:
            logger.error(f"❌ 解析LLM分析响应失败: {e}")
            return self._create_fallback_analysis(llm_response)
    
    def _convert_relevance_to_keywords(self, path_relevance: Dict[str, float]) -> Dict[str, Dict]:
        """
        将LLM的相关度评分转换为兼容keywords_found格式
        
        Args:
            path_relevance: 路径相关度字典
            
        Returns:
            兼容格式的关键词字典
        """
        keywords_found = {}
        
        for path_type, relevance_score in path_relevance.items():
            if relevance_score > 0.1:  # 只保留相关度较高的路径
                keywords_found[path_type] = {
                    'keywords': ['llm_analyzed'],  # 标记为LLM分析
                    'weight': relevance_score * 10,  # 转换为权重
                    'relevance_score': relevance_score
                }
        
        return keywords_found
    
    def _get_default_analysis(self, error_note: str = None) -> Dict[str, Any]:
        """
        获取默认的分析结果 - 避免代码重复
        
        Args:
            error_note: 错误说明（可选）
            
        Returns:
            默认分析结果字典
        """
        # 均匀分配相关度评分
        uniform_score = 0.4
        path_relevance = {
            'systematic_analytical': uniform_score,
            'creative_innovative': uniform_score,
            'critical_questioning': uniform_score,
            'practical_pragmatic': uniform_score,
            'holistic_comprehensive': uniform_score,
            'exploratory_investigative': uniform_score,
            'collaborative_consultative': uniform_score,
            'adaptive_flexible': uniform_score
        }
        
        analysis = {
            'path_relevance': path_relevance,
            'keywords_found': self._convert_relevance_to_keywords(path_relevance),
            'complexity_indicators': ['默认复杂度'],
            'domain_hints': ['通用领域'],
            'urgency_level': 'normal',
            'collaborative_need': False,
            'innovation_requirement': False,
            'critical_analysis_need': True,  # 默认包含批判性分析
            'practical_focus': True,       # 默认实用导向
            'comprehensive_scope': False,
            'research_oriented': False,
            'adaptive_requirement': False
        }
        
        if error_note:
            analysis['error_note'] = error_note
            
        return analysis

    def _heuristic_analyze_thinking_seed(self, thinking_seed: str) -> Dict[str, Any]:
        """
        简化的备用分析 (LLM不可用时的默认方案)
        
        Args:
            thinking_seed: 思维种子
            
        Returns:
            默认分析结果字典
        """
        # 🗑️ 已删除所有启发式规则，直接使用默认分析
        logger.info("🔄 LLM不可用，使用默认均匀分配策略")
        result = self._get_default_analysis()
        result['analysis_source'] = 'heuristic'
        return result
    
    def _create_fallback_analysis(self, raw_response: str) -> Dict[str, Any]:
        """
        创建默认的分析结果
        
        Args:
            raw_response: 原始响应
            
        Returns:
            默认分析结果
        """
        error_note = f"LLM分析失败，使用默认设置，原始响应长度: {len(raw_response)}"
        result = self._get_default_analysis(error_note)
        result['analysis_source'] = 'fallback'
        return result
    
    def _select_path_types(self, seed_analysis: Dict[str, Any], max_paths: int) -> List[str]:
        """
        根据LLM分析结果选择合适的路径类型
        
        Args:
            seed_analysis: LLM分析的种子结果
            max_paths: 最大路径数
            
        Returns:
            选择的路径类型列表
        """
        path_scores = {}
        
        # 1. 基于LLM相关度评分的基础评分（替代关键词匹配）
        if 'path_relevance' in seed_analysis and seed_analysis['path_relevance']:
            # 使用LLM的直接相关度评分
            for path_type, relevance_score in seed_analysis['path_relevance'].items():
                path_scores[path_type] = relevance_score * 10  # 缩放到原有权重范围
        else:
            # 回退到keywords_found格式（兼容性）
            for path_type, keyword_info in seed_analysis.get('keywords_found', {}).items():
                path_scores[path_type] = keyword_info['weight'] * keyword_info['relevance_score']
        
        # 2. 基于特殊需求的加权调整
        adjustments = {
            'collaborative_consultative': seed_analysis['collaborative_need'] * 2,
            'creative_innovative': seed_analysis['innovation_requirement'] * 2,
            'critical_questioning': seed_analysis['critical_analysis_need'] * 2,
            'practical_pragmatic': seed_analysis['practical_focus'] * 2,
            'holistic_comprehensive': seed_analysis['comprehensive_scope'] * 2,
            'exploratory_investigative': seed_analysis['research_oriented'] * 2,
            'adaptive_flexible': seed_analysis['adaptive_requirement'] * 2,
            'systematic_analytical': len(seed_analysis['complexity_indicators']) * 0.5
        }
        
        for path_type, adjustment in adjustments.items():
            path_scores[path_type] = path_scores.get(path_type, 0) + adjustment
        
        # 3. 紧急程度影响路径选择
        if seed_analysis['urgency_level'] == 'high':
            path_scores['practical_pragmatic'] = path_scores.get('practical_pragmatic', 0) + 1
        elif seed_analysis['urgency_level'] == 'low':
            path_scores['exploratory_investigative'] = path_scores.get('exploratory_investigative', 0) + 1
            path_scores['holistic_comprehensive'] = path_scores.get('holistic_comprehensive', 0) + 1
        
        # 4. 确保多样性：选择不同类型的路径
        selected_paths = []
        
        # 按评分排序
        sorted_paths = sorted(path_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 选择评分最高的路径，同时确保多样性
        for path_type, score in sorted_paths:
            if len(selected_paths) >= max_paths:
                break
            if score > 0:  # 只选择有相关性的路径
                selected_paths.append(path_type)
        
        # 5. 如果选择的路径不足，添加通用路径
        if len(selected_paths) < 2:
            default_paths = ['systematic_analytical', 'practical_pragmatic']
            for default_path in default_paths:
                if default_path not in selected_paths and len(selected_paths) < max_paths:
                    selected_paths.append(default_path)
        
        # 6. 确保总是包含至少一个批判性路径（质量保证）
        if 'critical_questioning' not in selected_paths and len(selected_paths) < max_paths:
            selected_paths.append('critical_questioning')
        
        return selected_paths[:max_paths]
    
    def _instantiate_reasoning_paths(self, path_types: List[str], thinking_seed: str, task: str) -> List[ReasoningPath]:
        """
        实例化选择的思维路径 - 🎯 根源修复：在源头生成正确的确定性策略ID
        
        Args:
            path_types: 选择的路径类型列表
            thinking_seed: 思维种子
            task: 任务描述
            
        Returns:
            实例化的思维路径列表
        """
        reasoning_paths = []
        
            # 🔧 修复：如果路径模板为空，强制重新加载
        if not self.path_templates:
            logger.warning("⚠️ 检测到空的路径模板，尝试重新加载...")
            self.path_templates = self.path_template_manager.get_all_templates()
            
            # 如果仍然为空，使用静态回退模板
            if not self.path_templates:
                logger.warning("⚠️ 动态路径库加载失败，使用静态回退模板...")
                static_templates = self.path_template_manager._get_static_templates()
                # 🔧 确保键名匹配：同时使用原始键和策略ID作为键
                self.path_templates = {}
                for key, template in static_templates.items():
                    self.path_templates[key] = template
                    # 如果有不同的strategy_id，也添加为键
                    if template.strategy_id and template.strategy_id != key:
                        self.path_templates[template.strategy_id] = template
                logger.info(f"✅ 静态回退模板已加载: {len(static_templates)} 个模板，{len(self.path_templates)} 个键")
            
        for path_type in path_types:
            if path_type in self.path_templates:
                template = self.path_templates[path_type]
                
                # 🎯 根源修复：直接使用模板键作为确定性策略ID
                strategy_id = path_type  # 使用模板键，确保确定性和幂等性
                
                # 生成实例级别的唯一ID，用于会话追踪和调试
                unique_suffix = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
                instance_id = f"{strategy_id}_{unique_suffix}"
                
                instantiated_path = ReasoningPath(
                    path_id=instance_id,  # 保持向后兼容性，但现在这是实例ID
                    path_type=template.path_type,
                    description=template.description,
                    prompt_template=template.prompt_template.format(
                        task=task,
                        thinking_seed=thinking_seed
                    ),
                    # 🎯 源头生成：直接赋值正确的ID，无需后处理
                    strategy_id=strategy_id,  # 确定性策略标识符，用于MAB学习
                    instance_id=instance_id   # 唯一实例标识符，用于追踪和调试
                )
                
                reasoning_paths.append(instantiated_path)
                logger.debug(f"✅ 实例化路径: {template.path_type}")
                logger.debug(f"   策略ID: {strategy_id} (确定性，MAB学习)")
                logger.debug(f"   实例ID: {instance_id} (唯一性，追踪)")
            else:
                logger.warning(f"⚠️ 未找到路径模板: {path_type}")
        
        return reasoning_paths
    
    def _generate_fallback_paths(self, thinking_seed: str, task: str) -> List[ReasoningPath]:
        """
        生成fallback思维路径
        
        Args:
            thinking_seed: 思维种子
            task: 任务描述
            
        Returns:
            基础思维路径列表
        """
        logger.warning("🔄 使用fallback路径生成")
        
        fallback_types = ['systematic_analytical', 'practical_pragmatic']
        return self._instantiate_reasoning_paths(fallback_types, thinking_seed, task)
    
    def _manage_path_cache(self):
        """管理路径生成缓存"""
        if len(self.path_generation_cache) > 100:
            # 移除最旧的50个缓存项
            oldest_keys = list(self.path_generation_cache.keys())[:50]
            for key in oldest_keys:
                del self.path_generation_cache[key]
            logger.debug("🧹 清理路径生成缓存")
        
    def generate_decision_path(self, user_query: str, complexity_info: Dict[str, Any], 
                             execution_context: Optional[Dict] = None) -> List[ReasoningPath]:
        """
        生成决策路径和维度
        
        Args:
            user_query: 用户查询
            complexity_info: 复杂度信息
            execution_context: 执行上下文
            
        Returns:
            动态维度选择结果
        """
        # 检查缓存
        cache_key = f"{user_query}_{hash(str(complexity_info))}_{hash(str(execution_context))}"
        if cache_key in self.generation_cache:
            logger.debug(f"📋 使用缓存的路径生成: {cache_key[:20]}...")
            return self.generation_cache[cache_key]
        
        try:
            if self.dimension_selector and self.api_key:
                result = self.dimension_selector.create_dynamic_dimensions(user_query, execution_context)
            else:
                logger.warning("⚠️ 未配置API密钥或维度选择器，使用简单维度生成")
                result = self._create_simple_dimensions(user_query, complexity_info)
            
            # 缓存结果
            self.generation_cache[cache_key] = result
            
            # 限制缓存大小
            if len(self.generation_cache) > 50:
                # 移除最旧的缓存项
                oldest_key = next(iter(self.generation_cache))
                del self.generation_cache[oldest_key]
            
            logger.info(f"🛤️ 路径生成完成: {len(result)}条思维路径")
            return result
            
        except Exception as e:
            logger.error(f"❌ 路径生成失败: {e}")
            return self._create_simple_reasoning_paths(user_query, complexity_info)
    
    def _create_simple_reasoning_paths(self, user_query: str, complexity_info: Dict[str, Any]) -> List[ReasoningPath]:
        """创建简单的思维路径"""
        
        logger.info("🔄 使用简单思维路径生成")
        
        query_lower = user_query.lower()
        complexity_score = complexity_info.get('complexity_score', 0.5)
        
        reasoning_paths = []
        
        # 基于复杂度选择主要思维路径
        if complexity_score < 0.3:
            # 简单任务：实用直接
            reasoning_paths.append(ReasoningPath(
                path_id="simple_direct_v1",
                path_type="简单直接型",
                description="适用于简单任务的直接方法",
                prompt_template="请直接解决：{task}。要求简洁实用，立即可行。"
            ))
        elif complexity_score > 0.7:
            # 复杂任务：系统分析
            reasoning_paths.append(ReasoningPath(
                path_id="complex_systematic_v1",
                path_type="复杂系统型",
                description="适用于复杂任务的系统方法",
                prompt_template="请系统性分析：{task}。步骤：1) 分解问题 2) 制定策略 3) 实施方案"
            ))
        else:
            # 中等复杂度：平衡方法
            reasoning_paths.append(ReasoningPath(
                path_id="moderate_balanced_v1",
                path_type="平衡适中型",
                description="适用于中等复杂度任务的平衡方法",
                prompt_template="请合理分析解决：{task}。方法：1) 理解需求 2) 评估方案 3) 提供建议"
            ))
        
        # 基于查询内容添加特定的思维路径
        if any(word in query_lower for word in ['创新', '创意', '新颖', '独特']):
            reasoning_paths.append(ReasoningPath(
                path_id="creative_innovative_v1",
                path_type="创新创意型",
                description="专注于创新和创意的思维方法",
                prompt_template="请创新性思考：{task}。要求：1) 跳出传统 2) 寻找突破 3) 提供新思路"
            ))
        
        if any(word in query_lower for word in ['分析', '评估', '研究', '深入']):
            reasoning_paths.append(ReasoningPath(
                path_id="analytical_deep_v1",
                path_type="深度分析型",
                description="专注于深度分析的思维方法",
                prompt_template="请深度分析：{task}。要求：1) 全面调研 2) 多角度思考 3) 深入洞察"
            ))
        
        # 确保至少有一个思维路径
        if not reasoning_paths:
            reasoning_paths.append(ReasoningPath(
                path_id="default_general_v1",
                path_type="通用方法型",
                description="通用的问题解决方法",
                prompt_template="请处理以下任务：{task}。采用合适的方法进行分析和解决。"
            ))
        
        return reasoning_paths
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """获取生成统计信息"""
        
        stats = {
            # 传统维度生成统计 (向后兼容)
            'total_generations': len(self.generation_cache),
            'cache_hit_rate': 0.0,  # 需要额外追踪
            'avg_paths_per_generation': 0.0,
            'fallback_usage_rate': 0.0,
            'avg_dimensions_per_generation': 0.0,  # 兼容性字段
            
            # 新增：思维路径生成统计
            'path_generation_stats': {
                'total_path_generations': len(self.path_generation_cache),
                'path_type_distribution': dict(self.path_selection_stats),
                'most_used_path_types': [],
                'avg_paths_per_seed': 0.0
            }
        }
        
        # 传统统计
        if self.generation_cache:
            # 现在缓存的是List[ReasoningPath]，所以计算平均路径数
            total_paths = sum(len(paths) for paths in self.generation_cache.values())
            stats['avg_paths_per_generation'] = total_paths / len(self.generation_cache)
            
            # 检查是否有回退路径（通常ID包含"fallback"）
            fallback_count = sum(1 for paths in self.generation_cache.values() 
                               if any("fallback" in path.path_id for path in paths))
            stats['fallback_usage_rate'] = fallback_count / len(self.generation_cache)
            
            # 兼容性字段
            stats['avg_dimensions_per_generation'] = stats['avg_paths_per_generation']
        
        # 思维路径统计
        if self.path_generation_cache:
            total_paths = sum(len(paths) for paths in self.path_generation_cache.values())
            stats['path_generation_stats']['avg_paths_per_seed'] = total_paths / len(self.path_generation_cache)
            
            # 最常用的路径类型 (前3名)
            if self.path_selection_stats:
                sorted_types = sorted(
                    self.path_selection_stats.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )
                stats['path_generation_stats']['most_used_path_types'] = sorted_types[:3]
        
        return stats
    
    def get_path_generation_insights(self) -> Dict[str, Any]:
        """获取路径生成深度洞察"""
        
        insights = {
            'template_coverage': {},  # 模板使用覆盖率
            'keyword_effectiveness': {},  # 关键词匹配效果
            'path_diversity_score': 0.0,  # 路径多样性评分
            'generation_efficiency': {
                'cache_hit_rate': 0.0,
                'avg_generation_time': 0.0,
                'fallback_rate': 0.0
            }
        }
        
        # 模板使用覆盖率
        total_templates = len(self.path_templates)
        used_templates = len(set(
            path_type for path_type in self.path_selection_stats.keys()
        ))
        insights['template_coverage'] = {
            'total_templates': total_templates,
            'used_templates': used_templates,
            'coverage_rate': used_templates / total_templates if total_templates > 0 else 0.0
        }
        
        # 路径多样性评分 (基于熵计算)
        if self.path_selection_stats:
            total_selections = sum(self.path_selection_stats.values())
            diversity_score = 0.0
            for count in self.path_selection_stats.values():
                if count > 0:
                    p = count / total_selections
                    diversity_score -= p * (p**0.5)  # 简化的多样性指标
            insights['path_diversity_score'] = diversity_score
        
        return insights
    
    # ==================== 💡 Aha-Moment创造性绕道路径生成 ====================
    
    def _select_creative_bypass_path_types(self, seed_analysis: Dict[str, Any], max_paths: int) -> List[str]:
        """
        Aha-Moment模式：选择创造性和突破性的路径类型
        
        Args:
            seed_analysis: 思维种子分析结果
            max_paths: 最大路径数
            
        Returns:
            创造性路径类型列表
        """
        # 💡 优先选择的创造性路径类型（通常在常规模式下得分较低）
        creative_priority_paths = [
            "创新突破型",      # 最具创造性
            "批判质疑型",      # 挑战常规思维
            "艺术创意型",      # 跳出逻辑框架
            "哲学思辨型",      # 深层次思考
            "直觉洞察型",      # 非线性思维
            "逆向思维型",      # 反常规路径
            "跨界融合型",      # 多领域结合
            "实验探索型"       # 尝试新方法
        ]
        
        # 💡 中等创造性路径（平衡创造性和实用性）
        balanced_creative_paths = [
            "协作共创型",
            "适应演进型",
            "综合集成型",
            "系统优化型"
        ]
        
        # 获取所有可用的路径类型
        all_available_paths = list(self.path_templates.keys())
        
        selected_paths = []
        
        # Step 1: 优先选择高创造性路径（至少50%）
        high_creative_count = max(1, max_paths // 2)
        available_high_creative = [p for p in creative_priority_paths if p in all_available_paths]
        
        if available_high_creative:
            # 随机选择，增加不确定性和创造性
            import random
            selected_high_creative = random.sample(
                available_high_creative, 
                min(high_creative_count, len(available_high_creative))
            )
            selected_paths.extend(selected_high_creative)
            
            logger.info(f"🌟 选择高创造性路径: {selected_high_creative}")
        
        # Step 2: 补充中等创造性路径
        remaining_slots = max_paths - len(selected_paths)
        if remaining_slots > 0:
            available_balanced = [p for p in balanced_creative_paths 
                                if p in all_available_paths and p not in selected_paths]
            
            if available_balanced:
                import random
                selected_balanced = random.sample(
                    available_balanced,
                    min(remaining_slots, len(available_balanced))
                )
                selected_paths.extend(selected_balanced)
                
                logger.info(f"🔄 补充平衡路径: {selected_balanced}")
        
        # Step 3: 如果还有空位，随机选择其他路径
        remaining_slots = max_paths - len(selected_paths)
        if remaining_slots > 0:
            other_paths = [p for p in all_available_paths 
                          if p not in selected_paths]
            
            if other_paths:
                import random
                additional_paths = random.sample(
                    other_paths,
                    min(remaining_slots, len(other_paths))
                )
                selected_paths.extend(additional_paths)
                
                logger.info(f"➕ 补充其他路径: {additional_paths}")
        
        # 确保至少有一个路径
        if not selected_paths and all_available_paths:
            selected_paths = [all_available_paths[0]]
            logger.warning(f"⚠️ 回退到默认路径: {selected_paths}")
        
        logger.info(f"💡 Aha-Moment最终路径选择: {selected_paths}")
        return selected_paths[:max_paths]
    
    def get_creative_bypass_stats(self) -> Dict[str, Any]:
        """
        获取创造性绕道模式的统计信息
        
        Returns:
            统计信息字典
        """
        # 统计创造性路径类型的使用频率
        creative_paths = [
            "创新突破型", "批判质疑型", "艺术创意型", "哲学思辨型",
            "直觉洞察型", "逆向思维型", "跨界融合型", "实验探索型"
        ]
        
        creative_usage = {}
        total_creative_usage = 0
        
        for path_type in creative_paths:
            usage_count = self.path_selection_stats.get(path_type, 0)
            creative_usage[path_type] = usage_count
            total_creative_usage += usage_count
        
        total_usage = sum(self.path_selection_stats.values())
        creative_ratio = total_creative_usage / max(total_usage, 1)
        
        return {
            'creative_path_usage': creative_usage,
            'total_creative_usage': total_creative_usage,
            'total_usage': total_usage,
            'creative_ratio': creative_ratio,
            'most_used_creative_path': max(creative_usage.items(), key=lambda x: x[1])[0] if creative_usage else None,
            'available_creative_paths': len([p for p in creative_paths if p in self.path_templates])
        }
    
    def clear_cache(self):
        """清除生成缓存"""
        old_generation_count = len(self.generation_cache)
        old_path_count = len(self.path_generation_cache)
        
        self.generation_cache.clear()
        self.path_generation_cache.clear()
        
        logger.info(f"🔄 缓存已清除: 传统生成({old_generation_count}), 路径生成({old_path_count})")
    
    def reset_statistics(self):
        """重置统计信息"""
        self.path_selection_stats.clear()
        logger.info("📊 路径生成统计已重置")
    
    # ==================== 🌱 学习和成长接口 ====================
    
    def learn_path_from_exploration(self, exploration_result: Dict[str, Any]) -> int:
        """
        从知识探索结果中学习新的思维路径
        
        Args:
            exploration_result: 知识探索结果
            
        Returns:
            新增路径数量
        """
        new_path_count = self.path_template_manager.learn_from_exploration(exploration_result)
        
        if new_path_count > 0:
            # 刷新本地路径模板缓存
            self.path_templates = self.path_template_manager.get_all_templates()
            logger.info(f"🌱 PathGenerator学习到 {new_path_count} 个新路径")
        
        return new_path_count
    
    def add_custom_path(self, 
                       path: ReasoningPath, 
                       learning_source: str = "manual",
                       effectiveness_score: float = 0.5) -> bool:
        """
        手动添加自定义思维路径
        
        Args:
            path: 要添加的路径
            learning_source: 学习来源
            effectiveness_score: 初始效果评分
            
        Returns:
            bool: 是否添加成功
        """
        success = self.path_template_manager.add_learned_path(
            path, learning_source, effectiveness_score
        )
        
        if success:
            # 刷新本地路径模板缓存
            self.path_templates = self.path_template_manager.get_all_templates()
            logger.info(f"➕ 手动添加路径成功: {path.path_type}")
        
        return success
    
    def update_path_performance(self, 
                               path_id: str, 
                               success: bool, 
                               execution_time: float,
                               user_rating: Optional[float] = None) -> bool:
        """
        更新路径使用性能
        
        Args:
            path_id: 路径ID或策略ID
            success: 执行是否成功
            execution_time: 执行时间（秒）
            user_rating: 用户评分（0-1）
            
        Returns:
            bool: 是否更新成功
        """
        # 尝试按路径ID更新
        updated = self.path_template_manager.update_path_performance(
            path_id, success, execution_time, user_rating
        )
        
        if not updated:
            # 如果按路径ID失败，尝试按策略ID查找并更新
            for template_path in self.path_templates.values():
                if template_path.strategy_id == path_id:
                    updated = self.path_template_manager.update_path_performance(
                        template_path.path_id, success, execution_time, user_rating
                    )
                    break
        
        if updated:
            logger.debug(f"📊 更新路径性能: {path_id}")
        else:
            logger.warning(f"⚠️ 未找到要更新的路径: {path_id}")
        
        return updated
    
    def get_recommended_paths_by_context(self, 
                                       task_context: Dict[str, Any],
                                       max_recommendations: int = 3) -> List[ReasoningPath]:
        """
        基于任务上下文获取推荐的路径
        
        Args:
            task_context: 任务上下文信息
            max_recommendations: 最大推荐数量
            
        Returns:
            推荐的路径列表
        """
        recommended_paths = self.path_template_manager.get_recommended_paths(
            task_context, max_recommendations
        )
        
        logger.info(f"💡 获取到 {len(recommended_paths)} 个推荐路径")
        for i, path in enumerate(recommended_paths, 1):
            logger.debug(f"   {i}. {path.path_type}")
        
        return recommended_paths
    
    def get_path_library_stats(self) -> Dict[str, Any]:
        """获取路径库统计信息"""
        return self.path_template_manager.get_library_stats()
    
    def backup_path_library(self, backup_path: Optional[str] = None) -> bool:
        """
        备份路径库
        
        Args:
            backup_path: 备份路径
            
        Returns:
            bool: 备份是否成功
        """
        return self.path_template_manager.backup_library(backup_path)
    
    def refresh_path_templates(self):
        """刷新路径模板缓存"""
        old_count = len(self.path_templates)
        self.path_templates = self.path_template_manager.get_all_templates()
        new_count = len(self.path_templates)
        
        logger.info(f"🔄 路径模板已刷新: {old_count} -> {new_count}")
        
        if new_count != old_count:
            logger.info(f"   变化: {'+' if new_count > old_count else ''}{new_count - old_count}")
    
    def get_growth_insights(self) -> Dict[str, Any]:
        """
        获取路径生成器的成长洞察
        
        Returns:
            成长洞察数据
        """
        library_stats = self.get_path_library_stats()
        generation_stats = self.get_generation_statistics()
        
        insights = {
            # 库成长情况
            "library_growth": {
                "total_paths": library_stats["total_paths"],
                "learned_paths": library_stats["learned_paths"],
                "learning_ratio": library_stats["learned_paths"] / max(library_stats["total_paths"], 1)
            },
            
            # 路径使用情况
            "usage_patterns": {
                "total_generations": generation_stats["path_generation_stats"]["total_path_generations"],
                "avg_paths_per_generation": generation_stats["path_generation_stats"]["avg_paths_per_seed"],
                "most_used_paths": generation_stats["path_generation_stats"]["most_used_path_types"]
            },
            
            # 成长建议
            "growth_recommendations": self._generate_growth_recommendations(library_stats, generation_stats)
        }
        
        return insights
    
    def _generate_growth_recommendations(self, 
                                       library_stats: Dict[str, Any],
                                       generation_stats: Dict[str, Any]) -> List[str]:
        """生成成长建议"""
        recommendations = []
        
        # 基于学习路径比例
        learning_ratio = library_stats.get("learned_paths", 0) / max(library_stats.get("total_paths", 1), 1)
        if learning_ratio < 0.2:
            recommendations.append("建议增加从知识探索中学习的路径，提升适应性")
        
        # 基于路径使用多样性
        path_types = generation_stats["path_generation_stats"]["path_type_distribution"]
        if len(path_types) < 5:
            recommendations.append("路径类型使用较少，建议丰富思维模式的多样性")
        
        # 基于缓存效率
        if generation_stats.get("cache_hit_rate", 0) < 0.3:
            recommendations.append("缓存命中率较低，可能需要优化路径选择策略")
        
        return recommendations
