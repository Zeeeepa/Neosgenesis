#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略解释器 - 多阶段决策链条的核心组件
完美体现LLM策略建议 → MAB数据驱动选择 → 策略解析生成工具调用的设计理念
"""

from typing import Dict, List, Any, Optional
import logging
import time
import random

logger = logging.getLogger(__name__)


class StrategyInterpreter:
    """
    策略解释器 - 将思维路径的策略特征转换为具体的工具调用策略
    
    这是连接"宏观策略"和"具体行动"的关键桥梁组件，
    避免了简单的关键词匹配，而是基于策略的深层语义特征。
    """
    
    def __init__(self):
        self.name = "StrategyInterpreter"
        
        # 策略特征到工具策略的映射表
        self.strategy_feature_mappings = {
            # 系统分析型策略特征
            'systematic_analytical': {
                'primary_tools': ['knowledge_query', 'data_analysis'],
                'secondary_tools': ['web_search'],
                'execution_pattern': 'sequential',  # 顺序执行
                'confidence_threshold': 0.7,
                'description': '逻辑分析、结构化思考'
            },
            
            # 探索研究型策略特征  
            'exploratory_investigative': {
                'primary_tools': ['web_search', 'tavily_search'],
                'secondary_tools': ['firecrawl_scrape'],
                'execution_pattern': 'parallel',  # 并行执行
                'confidence_threshold': 0.6,
                'description': '深入调研、信息收集'
            },
            
            # 批判质疑型策略特征
            'critical_questioning': {
                'primary_tools': ['idea_verification', 'text_analysis'],
                'secondary_tools': ['web_search'],
                'execution_pattern': 'validation_focused',
                'confidence_threshold': 0.8,
                'description': '质疑分析、风险评估'
            },
            
            # 实用导向型策略特征
            'practical_pragmatic': {
                'primary_tools': ['knowledge_query'],
                'secondary_tools': ['web_search'],
                'execution_pattern': 'direct',  # 直接高效
                'confidence_threshold': 0.5,
                'description': '实际可行、效率优先'
            },
            
            # 创新直觉型策略特征
            'creative_innovative': {
                'primary_tools': [],  # 主要依靠LLM创意，少用工具
                'secondary_tools': ['web_search'],
                'execution_pattern': 'creative_direct',
                'confidence_threshold': 0.9,  # 高置信度才使用工具
                'description': '创造性思维、突破常规'
            },
            
            # 综合全面型策略特征
            'holistic_comprehensive': {
                'primary_tools': ['web_search', 'knowledge_query', 'data_analysis'],
                'secondary_tools': ['idea_verification'],
                'execution_pattern': 'comprehensive',
                'confidence_threshold': 0.6,
                'description': '整体考虑、全局思维'
            },
            
            # 🚨 新增：创新绕道思考策略特征
            '创新绕道思考': {
                'primary_tools': [],  # 主要依靠直接回答，避免过度工具化
                'secondary_tools': ['knowledge_query'],
                'execution_pattern': 'direct_creative',  # 创新直接回答模式
                'confidence_threshold': 0.3,  # 低阈值，优先直接回答
                'description': '突破常规，创新思维回答'
            },
            
            # 自适应灵活型策略特征
            'adaptive_flexible': {
                'primary_tools': [],  # 根据情况灵活选择
                'secondary_tools': ['knowledge_query', 'web_search'],
                'execution_pattern': 'adaptive_direct',
                'confidence_threshold': 0.4,
                'description': '灵活适应、因情而变'
            },
            
            # 🎨 新增：视觉创意型策略特征
            'creative_visual': {
                'primary_tools': ['image_generation', 'stable_diffusion_xl_generator'],
                'secondary_tools': ['knowledge_query', 'web_search'],
                'execution_pattern': 'visual_creation',
                'confidence_threshold': 0.8,  # 高置信度确保视觉需求明确
                'description': '视觉创作、图像生成、艺术创意',
                'visual_context': {
                    'primary_purpose': 'creation',
                    'output_types': ['image', 'illustration', 'design'],
                    'style_considerations': True
                }
            },
            
            # 🖼️ 新增：设计导向型策略特征
            'design_oriented': {
                'primary_tools': ['image_generation', 'stable_diffusion_xl_generator'],
                'secondary_tools': ['web_search', 'knowledge_query'],
                'execution_pattern': 'iterative_design',
                'confidence_threshold': 0.7,
                'description': '专业设计、界面原型、品牌视觉',
                'visual_context': {
                    'primary_purpose': 'professional_design',
                    'output_types': ['logo', 'ui_mockup', 'brand_design', 'poster'],
                    'style_considerations': True,
                    'brand_awareness': True
                }
            },
            
            # 🔍 新增：概念可视化策略特征
            'conceptual_visualization': {
                'primary_tools': ['image_generation'],
                'secondary_tools': ['knowledge_query'],
                'execution_pattern': 'concept_illustration',
                'confidence_threshold': 0.6,
                'description': '概念解释、想象描绘、场景展示',
                'visual_context': {
                    'primary_purpose': 'conceptualization',
                    'output_types': ['conceptual_art', 'scene_illustration', 'explanatory_visual'],
                    'educational_value': True
                }
            }
        }
        
        # 查询上下文分析器
        self.context_analyzers = {
            'domain_specific': self._analyze_domain_context,
            'urgency_level': self._analyze_urgency_context,
            'complexity_level': self._analyze_complexity_context,
            'visual_needs': self._analyze_visual_needs_context,  # 🎨 弃用：视觉需求分析（保持兼容）
            'visual_intelligence': self._perform_visual_intelligence_decision,  # 🎨 新增：视觉智能决策
            'output_format': self._analyze_output_format_context, # 📊 新增：输出格式分析
        }
        
        # 🔍 初始化SemanticAnalyzer实例（用于视觉需求分析）
        self.semantic_analyzer = None
        try:
            from ..cognitive_engine.semantic_analyzer import create_semantic_analyzer
            self.semantic_analyzer = create_semantic_analyzer()
            logger.info("🔍 StrategyInterpreter 已集成SemanticAnalyzer")
        except ImportError as e:
            logger.warning(f"⚠️ SemanticAnalyzer不可用，使用降级分析： {e}")
        except Exception as e:
            logger.warning(f"⚠️ SemanticAnalyzer初始化失败，使用降级分析： {e}")
        
        logger.info("🧠 策略解释器初始化完成")
    
    def interpret_strategy_to_actions(self, chosen_path, query: str, 
                                    mab_confidence: float, decision_context: Dict) -> List:
        """
        核心方法：将选中的思维路径策略解释为具体的工具调用行动
        
        Args:
            chosen_path: MAB选中的最优思维路径
            query: 原始用户查询
            mab_confidence: MAB对这个选择的置信度
            decision_context: 决策上下文
            
        Returns:
            具体的Action列表
        """
        logger.info(f"🎯 开始策略解释: {chosen_path.path_type}")
        logger.info(f"   MAB置信度: {mab_confidence:.2f}")
        
        # 1. 获取策略特征
        strategy_features = self._extract_strategy_features(chosen_path)
        
        # 2. 分析查询上下文
        query_context = self._analyze_query_context(query, decision_context)
        
        # 3. 策略适配决策
        action_strategy = self._decide_action_strategy(
            strategy_features, query_context, mab_confidence
        )
        
        # 4. 生成具体行动
        actions = self._generate_concrete_actions(
            action_strategy, chosen_path, query, query_context
        )
        
        logger.info(f"✅ 策略解释完成: 生成 {len(actions)} 个行动")
        return actions
    
    def _extract_strategy_features(self, chosen_path) -> Dict[str, Any]:
        """提取思维路径的策略特征"""
        path_type = chosen_path.path_type.lower()
        
        # 从映射表获取策略特征
        if path_type in self.strategy_feature_mappings:
            base_features = self.strategy_feature_mappings[path_type].copy()
        else:
            # 未知策略类型，使用默认特征
            logger.warning(f"⚠️ 未知策略类型: {path_type}，使用默认特征")
            base_features = self.strategy_feature_mappings['practical_pragmatic'].copy()
        
        # 增强特征：分析路径描述中的语义信息
        description_features = self._analyze_path_description(chosen_path.description)
        base_features.update(description_features)
        
        # 增强特征：从prompt_template中提取执行提示
        template_features = self._analyze_prompt_template(getattr(chosen_path, 'prompt_template', ''))
        base_features.update(template_features)
        
        return base_features
    
    def _analyze_path_description(self, description: str) -> Dict[str, Any]:
        """分析路径描述中的语义特征"""
        features = {}
        description_lower = description.lower() if description else ""
        
        # 信息收集倾向分析
        if any(word in description_lower for word in ['搜索', '调研', '探索', '收集', '查找']):
            features['requires_information_gathering'] = True
            features['information_depth'] = 'deep' if '深入' in description_lower else 'surface'
        
        # 验证需求分析
        if any(word in description_lower for word in ['验证', '确认', '检查', '审查', '质疑']):
            features['requires_verification'] = True
            features['verification_strictness'] = 'high' if '严格' in description_lower else 'moderate'
        
        # 创新需求分析
        if any(word in description_lower for word in ['创新', '创意', '突破', '新颖']):
            features['innovation_focus'] = True
            features['tool_dependency'] = 'low'  # 创新型路径较少依赖工具
        
        return features
    
    def _analyze_prompt_template(self, prompt_template: str) -> Dict[str, Any]:
        """分析提示模板中的执行指示"""
        features = {}
        template_lower = prompt_template.lower() if prompt_template else ""
        
        # 分析模板中的工具使用暗示
        if '搜索' in template_lower or 'search' in template_lower:
            features['template_suggests_search'] = True
        
        if '分析' in template_lower or 'analyze' in template_lower:
            features['template_suggests_analysis'] = True
            
        if '验证' in template_lower or 'verify' in template_lower:
            features['template_suggests_verification'] = True
        
        return features
    
    # ==================== 🎨 视觉智能决策系统 ====================
    
    def _perform_visual_intelligence_decision(self, query: str, context: Dict) -> Dict[str, Any]:
        """
        🎨 执行视觉智能决策 - 从"判断需求"升级为"评估机会"
        
        这是策略解释器的核心升级：不再简单执行，而是智能决策。
        
        Args:
            query: 用户查询
            context: 决策上下文
            
        Returns:
            Dict: 综合的视觉决策报告
        """
        logger.info(f"🎨 启动视觉智能决策系统: {query[:50]}...")
        
        try:
            # 阶段1：评估视觉增强机会
            opportunity_assessment = self._assess_visual_enhancement_opportunity(query, context)
            
            # 阶段2：风险评估
            risk_assessment = self._assess_visual_generation_risks(opportunity_assessment, context)
            
            # 阶段3：机会评分
            opportunity_score = self._score_visual_opportunity(opportunity_assessment, risk_assessment)
            
            # 阶段4：最终决策
            final_decision = self._make_final_visual_decision(
                opportunity_assessment, risk_assessment, opportunity_score, context
            )
            
            logger.info(
                f"✅ 视觉智能决策完成: {final_decision['should_generate']} "
                f"(机会强度: {opportunity_score:.2f}, 决策置信度: {final_decision['decision_confidence']:.2f})"
            )
            
            return final_decision
            
        except Exception as e:
            logger.error(f"❌ 视觉智能决策异常: {e}")
            # 安全降级：返回保守决策
            return self._create_safe_fallback_decision(query, str(e))
    
    def _assess_visual_enhancement_opportunity(self, query: str, context: Dict) -> Dict[str, Any]:
        """🔍 评估视觉增强机会"""
        if not self.semantic_analyzer:
            logger.warning("⚠️ SemanticAnalyzer不可用，使用简化机会评估")
            return self._simple_opportunity_assessment(query)
        
        try:
            # 使用新的视觉增强机会评估任务
            response = self.semantic_analyzer.analyze(
                text=query,
                tasks=[
                    'visual_enhancement_opportunity',
                    'interaction_context_analysis',
                    'aesthetic_preference_inference'
                ]
            )
            
            if not response.overall_success:
                logger.warning("⚠️ 语义分析失败，使用简化评估")
                return self._simple_opportunity_assessment(query)
            
            # 提取分析结果
            opportunity_result = response.analysis_results.get('visual_enhancement_opportunity')
            context_result = response.analysis_results.get('interaction_context_analysis')
            aesthetic_result = response.analysis_results.get('aesthetic_preference_inference')
            
            # 构建综合机会评估
            assessment = {
                'has_opportunity': False,
                'opportunity_strength': 0.0,
                'opportunity_type': 'none',
                'analysis_quality': 'failed'
            }
            
            if opportunity_result and opportunity_result.success:
                opp_data = opportunity_result.result
                assessment.update({
                    'has_opportunity': opp_data.get('has_visual_opportunity', False),
                    'opportunity_strength': opp_data.get('opportunity_strength', 0.0),
                    'opportunity_type': opp_data.get('opportunity_type', 'none'),
                    'context_analysis': opp_data.get('context_analysis', {}),
                    'visual_recommendations': opp_data.get('visual_recommendations', {}),
                    'timing_assessment': opp_data.get('timing_assessment', {}),
                    'personalization': opp_data.get('personalization', {}),
                    'analysis_quality': 'high',
                    'analysis_confidence': opportunity_result.confidence
                })
            
            # 整合情境分析
            if context_result and context_result.success:
                assessment['interaction_context'] = context_result.result
            
            # 整合审美偏好
            if aesthetic_result and aesthetic_result.success:
                assessment['aesthetic_preferences'] = aesthetic_result.result
            
            logger.debug(f"🔍 机会评估完成: {assessment['opportunity_type']}, 强度={assessment['opportunity_strength']:.2f}")
            return assessment
            
        except Exception as e:
            logger.error(f"❌ 机会评估异常: {e}")
            return self._simple_opportunity_assessment(query)
    
    def _assess_visual_generation_risks(self, opportunity: Dict[str, Any], context: Dict) -> Dict[str, Any]:
        """⚠️ 评估视觉生成的风险"""
        risks = {
            'overall_risk_level': 'low',
            'risk_score': 0.0,
            'risk_factors': [],
            'mitigation_suggestions': []
        }
        
        risk_score = 0.0
        
        # 风险因字1：时机不合适
        timing = opportunity.get('timing_assessment', {})
        if timing.get('generation_timing') == 'not_recommended':
            risks['risk_factors'].append('生成时机不合适')
            risk_score += 0.3
        elif timing.get('context_appropriateness', 1.0) < 0.5:
            risks['risk_factors'].append('情境适宜度较低')
            risk_score += 0.2
        
        # 风险因字2：用户准备度不足
        if timing.get('user_readiness', 1.0) < 0.4:
            risks['risk_factors'].append('用户准备度不足')
            risk_score += 0.25
        
        # 风险因字3：低机会强度
        if opportunity.get('opportunity_strength', 0) < 0.3:
            risks['risk_factors'].append('视觉增强机会弱')
            risk_score += 0.35
        
        # 风险因字4：情绪不匹配
        context_analysis = opportunity.get('context_analysis', {})
        if context_analysis.get('user_emotional_state') in ['frustrated', 'angry', 'overwhelmed']:
            risks['risk_factors'].append('用户情绪状态不适宜')
            risk_score += 0.4
        
        # 风险因字5：复杂度过高
        if context_analysis.get('content_complexity') == 'very_high':
            risks['risk_factors'].append('内容复杂度过高，可能干扰理解')
            risk_score += 0.15
        
        # 风险级别评定
        if risk_score >= 0.7:
            risks['overall_risk_level'] = 'high'
        elif risk_score >= 0.4:
            risks['overall_risk_level'] = 'medium'
        else:
            risks['overall_risk_level'] = 'low'
        
        risks['risk_score'] = min(risk_score, 1.0)
        
        # 生成风险缓解建议
        if risks['risk_factors']:
            risks['mitigation_suggestions'] = self._generate_risk_mitigation_suggestions(
                risks['risk_factors'], opportunity
            )
        
        logger.debug(f"⚠️ 风险评估: {risks['overall_risk_level']} (分数: {risk_score:.2f})")
        return risks
    
    def _score_visual_opportunity(self, opportunity: Dict[str, Any], risks: Dict[str, Any]) -> float:
        """🎯 评分视觉机会 - 综合机会和风险"""
        base_score = opportunity.get('opportunity_strength', 0.0)
        risk_penalty = risks.get('risk_score', 0.0)
        
        # 基础机会分数
        opportunity_score = base_score
        
        # 风险惩罚
        opportunity_score *= (1.0 - risk_penalty * 0.5)  # 风险最多减半分
        
        # 情境加分
        timing = opportunity.get('timing_assessment', {})
        if timing.get('generation_timing') == 'immediate':
            opportunity_score *= 1.2  # 立即生成加分
        elif timing.get('generation_timing') == 'contextually_appropriate':
            opportunity_score *= 1.1  # 适宜时机加分
        
        # 审美匹配加分
        aesthetic = opportunity.get('aesthetic_preferences', {})
        if aesthetic.get('confidence_metrics', {}).get('preference_certainty', 0) > 0.7:
            opportunity_score *= 1.15  # 审美偏好清晰加分
        
        final_score = max(0.0, min(1.0, opportunity_score))  # 限制在 0-1 范围
        
        logger.debug(f"🎯 机会评分: {base_score:.2f} -> {final_score:.2f} (风险惩罚: {risk_penalty:.2f})")
        return final_score
    
    def _make_final_visual_decision(self, opportunity: Dict, risks: Dict, score: float, context: Dict) -> Dict[str, Any]:
        """🎯 做出最终的视觉决策"""
        
        # 决策阈值 - 可根据上下文动态调整
        decision_threshold = self._calculate_decision_threshold(opportunity, context)
        
        should_generate = score >= decision_threshold
        
        # 特殊情况处理
        if risks.get('overall_risk_level') == 'high':
            should_generate = False
            decision_reason = f"风险过高 ({', '.join(risks.get('risk_factors', [])[:2])})"
        elif not opportunity.get('has_opportunity', False):
            should_generate = False
            decision_reason = "无明显的视觉增强机会"
        elif should_generate:
            decision_reason = f"机会评分 {score:.2f} 超过阈值 {decision_threshold:.2f}"
        else:
            decision_reason = f"机会评分 {score:.2f} 低于阈值 {decision_threshold:.2f}"
        
        # 构建决策报告
        decision = {
            'should_generate': should_generate,
            'decision_confidence': self._calculate_decision_confidence(score, risks, opportunity),
            'decision_reason': decision_reason,
            'opportunity_score': score,
            'decision_threshold': decision_threshold,
            'risk_level': risks.get('overall_risk_level', 'unknown'),
            
            # 生成建议
            'recommended_visual_type': opportunity.get('visual_recommendations', {}).get('primary_visual_type', 'unknown'),
            'style_suggestions': opportunity.get('visual_recommendations', {}).get('style_suggestions', []),
            'generation_timing': opportunity.get('timing_assessment', {}).get('generation_timing', 'immediate'),
            'generation_purpose': opportunity.get('opportunity_type', 'unknown'),
            'suggested_elements': opportunity.get('personalization', {}).get('suggested_elements', []),
            
            # 调试信息
            'debug_info': {
                'opportunity_assessment': opportunity,
                'risk_assessment': risks,
                'decision_process': 'visual_intelligence_v2'
            }
        }
        
        return decision
    
    # ==================== 🛠️ 辅助决策方法 ====================
    
    def _calculate_decision_threshold(self, opportunity: Dict, context: Dict) -> float:
        """🎯 计算决策阈值 - 基于情境动态调整"""
        base_threshold = 0.6  # 默认阈值
        
        # 根据交互阶段调整
        interaction_phase = opportunity.get('context_analysis', {}).get('interaction_phase', '')
        if interaction_phase == 'creative_brainstorming':
            base_threshold -= 0.1  # 创意阶段降低阈值
        elif interaction_phase == 'problem_solving':
            base_threshold += 0.1  # 问题解决阶段提高阈值
        
        # 根据用户情绪调整
        emotional_state = opportunity.get('context_analysis', {}).get('user_emotional_state', '')
        if emotional_state in ['excited', 'inspired', 'curious']:
            base_threshold -= 0.05  # 积极情绪降低阈值
        elif emotional_state in ['frustrated', 'overwhelmed']:
            base_threshold += 0.15  # 消极情绪提高阈值
        
        # 根据机会类型调整
        opportunity_type = opportunity.get('opportunity_type', '')
        if opportunity_type == 'explicit_request':
            base_threshold = 0.3  # 明确请求显著降低阈值
        elif opportunity_type == 'emotional_resonance':
            base_threshold -= 0.1  # 情感共鸣适度降低阈值
        
        return max(0.2, min(0.9, base_threshold))  # 限制在合理范围
    
    def _calculate_decision_confidence(self, score: float, risks: Dict, opportunity: Dict) -> float:
        """🎯 计算决策置信度"""
        # 基础置信度基于分数
        base_confidence = score
        
        # 分析质量影响
        analysis_quality = opportunity.get('analysis_quality', 'low')
        if analysis_quality == 'high':
            base_confidence *= 1.1
        elif analysis_quality == 'low':
            base_confidence *= 0.8
        
        # 风险级别影响
        risk_level = risks.get('overall_risk_level', 'medium')
        if risk_level == 'low':
            base_confidence *= 1.05
        elif risk_level == 'high':
            base_confidence *= 0.7
        
        # 语义分析置信度影响
        analysis_confidence = opportunity.get('analysis_confidence', 0.5)
        base_confidence = (base_confidence + analysis_confidence) / 2
        
        return max(0.1, min(0.95, base_confidence))
    
    def _simple_opportunity_assessment(self, query: str) -> Dict[str, Any]:
        """🔄 简化的机会评估 - 当SemanticAnalyzer不可用时的降级方案"""
        logger.info("🔄 使用简化机会评估")
        
        # 基于关键词的简单判断
        explicit_keywords = ['画', '图', '设计', '生成图片', '制作', '绘制', '渲染', 'logo', '效果图']
        implicit_keywords = ['理解', '解释', '工作原理', '结构', '架构', '流程', '演示']
        creative_keywords = ['创意', '灵感', '想象', '设计理念', '品牌', '视觉']
        
        query_lower = query.lower()
        
        # 显式请求
        if any(keyword in query_lower for keyword in explicit_keywords):
            return {
                'has_opportunity': True,
                'opportunity_strength': 0.8,
                'opportunity_type': 'explicit_request',
                'analysis_quality': 'simple',
                'timing_assessment': {'generation_timing': 'immediate', 'context_appropriateness': 0.8}
            }
        
        # 隐含需求施教育
        elif any(keyword in query_lower for keyword in implicit_keywords):
            return {
                'has_opportunity': True,
                'opportunity_strength': 0.6,
                'opportunity_type': 'educational_support',
                'analysis_quality': 'simple',
                'timing_assessment': {'generation_timing': 'after_text_response', 'context_appropriateness': 0.7}
            }
        
        # 创意激发
        elif any(keyword in query_lower for keyword in creative_keywords):
            return {
                'has_opportunity': True,
                'opportunity_strength': 0.7,
                'opportunity_type': 'creative_inspiration',
                'analysis_quality': 'simple',
                'timing_assessment': {'generation_timing': 'contextually_appropriate', 'context_appropriateness': 0.75}
            }
        
        # 默认低机会
        else:
            return {
                'has_opportunity': False,
                'opportunity_strength': 0.2,
                'opportunity_type': 'minimal_visual_opportunity',
                'analysis_quality': 'simple',
                'timing_assessment': {'generation_timing': 'not_recommended', 'context_appropriateness': 0.3}
            }
    
    def _generate_risk_mitigation_suggestions(self, risk_factors: List[str], opportunity: Dict) -> List[str]:
        """🛡️ 生成风险缓解建议"""
        suggestions = []
        
        if '生成时机不合适' in risk_factors:
            suggestions.append('建议在文本回答后提供视觉补充')
        
        if '用户准备度不足' in risk_factors:
            suggestions.append('可先询问用户是否需要视觉辅助')
        
        if '视觉增强机会弱' in risk_factors:
            suggestions.append('优先提供文本解答，补充视觉元素')
        
        if '用户情绪状态不适宜' in risk_factors:
            suggestions.append('先处理情绪问题，后考虑视觉内容')
        
        return suggestions
    
    def _create_safe_fallback_decision(self, query: str, error: str) -> Dict[str, Any]:
        """🔄 创建安全的降级决策"""
        logger.warning(f"🔄 使用安全降级决策: {error}")
        
        return {
            'should_generate': False,
            'decision_confidence': 0.3,
            'decision_reason': f'系统异常，采用保守策略: {error}',
            'opportunity_score': 0.0,
            'risk_level': 'unknown',
            'recommended_visual_type': 'none',
            'generation_timing': 'not_recommended',
            'debug_info': {'fallback_reason': error}
        }
    
    def _create_intelligent_image_generation_action(self, query: str, visual_decision: Dict, context: Dict):
        """🎨 创建智能的图像生成行动 - 升级版本"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
        
        # 基于智能决策生成优化的提示词
        prompt = self._generate_intelligent_image_prompt(query, visual_decision, context)
        
        # 构建智能工具输入
        tool_input = {
            "prompt": prompt,
            "save_image": True,
            "style_hint": self._extract_intelligent_style_hint(visual_decision),
            "generation_context": {
                "opportunity_type": visual_decision.get('generation_purpose', 'unknown'),
                "timing": visual_decision.get('generation_timing', 'immediate'),
                "confidence": visual_decision.get('decision_confidence', 0.5),
                "visual_type": visual_decision.get('recommended_visual_type', 'unknown')
            }
        }
        
        logger.info(
            f"🎨 创建智能图像生成行动: {visual_decision['generation_purpose']} "
            f"(置信度: {visual_decision['decision_confidence']:.2f})"
        )
        
        return Action('stable_diffusion_xl_generator', tool_input)
    
    def _generate_intelligent_image_prompt(self, query: str, visual_decision: Dict, context: Dict) -> str:
        """🎨 生成智能化的图像提示词"""
        base_prompt = query.strip()
        
        # 根据视觉类型优化
        visual_type = visual_decision.get('recommended_visual_type', 'unknown')
        style_suggestions = visual_decision.get('style_suggestions', [])
        suggested_elements = visual_decision.get('suggested_elements', [])
        
        # 根据机会类型优化提示词
        opportunity_type = visual_decision.get('generation_purpose', 'unknown')
        
        if opportunity_type == 'explicit_request':
            # 明确请求，保持原始意图
            optimized_prompt = base_prompt
        elif opportunity_type == 'educational_support':
            # 教育支持，添加清晰的解释性元素
            optimized_prompt = f"{base_prompt}, clear educational diagram, informative illustration, step-by-step visual"
        elif opportunity_type == 'creative_inspiration':
            # 创意激发，添加创新元素
            optimized_prompt = f"{base_prompt}, creative concept art, innovative design, inspirational visual"
        elif opportunity_type == 'emotional_resonance':
            # 情感共鸣，添加温暖元素
            optimized_prompt = f"{base_prompt}, calming and soothing, emotional connection, peaceful atmosphere"
        else:
            optimized_prompt = f"{base_prompt}, high quality, detailed"
        
        # 添加风格建议
        if style_suggestions:
            style_text = ', '.join(style_suggestions[:3])
            optimized_prompt += f", {style_text}"
        
        # 添加建议元素
        if suggested_elements:
            elements_text = ', '.join(suggested_elements[:2])
            optimized_prompt += f", featuring {elements_text}"
        
        return optimized_prompt
    
    def _extract_intelligent_style_hint(self, visual_decision: Dict) -> str:
        """🎨 提取智能化的风格提示"""
        style_suggestions = visual_decision.get('style_suggestions', [])
        if style_suggestions:
            return ', '.join(style_suggestions[:2])
        
        # 默认风格基于机会类型
        opportunity_type = visual_decision.get('generation_purpose', 'unknown')
        style_mapping = {
            'explicit_request': 'high quality, detailed',
            'educational_support': 'clear, informative, structured',
            'creative_inspiration': 'creative, innovative, artistic',
            'emotional_resonance': 'calm, soothing, warm'
        }
        
        return style_mapping.get(opportunity_type, 'professional, clean')
    
    def _analyze_query_context(self, query: str, decision_context: Dict) -> Dict[str, Any]:
        """综合分析查询上下文"""
        context = {}
        
        # 应用所有上下文分析器
        for analyzer_name, analyzer_func in self.context_analyzers.items():
            try:
                context[analyzer_name] = analyzer_func(query, decision_context)
            except Exception as e:
                logger.warning(f"⚠️ 上下文分析器 {analyzer_name} 失败: {e}")
                context[analyzer_name] = {}
        
        return context
    
    def _analyze_domain_context(self, query: str, context: Dict) -> Dict[str, Any]:
        """分析领域上下文"""
        query_lower = query.lower()
        
        domain_indicators = {
            'technical': ['技术', '编程', '代码', '算法', '系统', 'python', 'java'],
            'business': ['商业', '商务', '市场', '营销', '销售', '管理'],
            'academic': ['学术', '研究', '论文', '理论', '分析'],
            'general': []  # 默认
        }
        
        for domain, keywords in domain_indicators.items():
            if any(keyword in query_lower for keyword in keywords):
                return {'domain': domain, 'specificity': 'high'}
        
        return {'domain': 'general', 'specificity': 'low'}
    
    def _analyze_urgency_context(self, query: str, context: Dict) -> Dict[str, Any]:
        """分析紧急程度上下文"""
        urgency_keywords = {
            'high': ['紧急', '急需', '立即', '马上', 'urgent', 'asap'],
            'medium': ['尽快', '较快', 'soon'],
            'low': ['什么时候', '有时间', '慢慢']
        }
        
        query_lower = query.lower()
        for level, keywords in urgency_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return {'level': level}
        
        return {'level': 'medium'}  # 默认中等紧急程度
    
    def _analyze_visual_needs_context(self, query: str, context: Dict) -> Dict[str, Any]:
        """🎨 分析查询的视觉需求 - 已弃用，请使用_perform_visual_intelligence_decision"""
        logger.warning("🚨 _analyze_visual_needs_context 已弃用，请使用新的视觉智能决策系统")
        
        # 保持向后兼容，调用新的决策系统
        visual_decision = self._perform_visual_intelligence_decision(query, context)
        
        # 转换为旧格式以保持兼容性
        return {
            'needs_visual': visual_decision['should_generate'],
            'confidence': visual_decision['decision_confidence'],
            'visual_type': visual_decision.get('recommended_visual_type', 'unknown'),
            'visual_purpose': visual_decision.get('generation_purpose', ''),
            'suggested_elements': visual_decision.get('suggested_elements', []),
            'analysis_source': 'visual_intelligence_decision_v2'
        }
    
    def _analyze_output_format_context(self, query: str, context: Dict) -> Dict[str, Any]:
        """📊 分析查询的输出格式需求"""
        format_analysis = {'preferred_format': 'text', 'confidence': 0.0}
        
        try:
            if self.semantic_analyzer:
                # 使用SemanticAnalyzer进行智能分析
                response = self.semantic_analyzer.analyze(
                    text=query,
                    tasks=['output_format_analysis']
                )
                
                if response.overall_success:
                    result = response.analysis_results.get('output_format_analysis')
                    if result and result.success:
                        format_data = result.result
                        format_analysis.update({
                            'preferred_format': format_data.get('preferred_format', 'text'),
                            'alternative_formats': format_data.get('alternative_formats', []),
                            'format_confidence': format_data.get('format_confidence', 0.0),
                            'output_medium': format_data.get('output_medium', 'text_response'),
                            'interaction_type': format_data.get('interaction_type', 'one_time_answer'),
                            'analysis_source': 'semantic_analyzer'
                        })
                        logger.debug(f"📊 SemanticAnalyzer格式分析: 首选格式={format_analysis['preferred_format']}, 置信度={format_analysis.get('format_confidence', 0.0):.2f}")
                else:
                    logger.warning("⚠️ SemanticAnalyzer格式分析失败，使用降级方法")
                    format_analysis = self._fallback_output_format_analysis(query)
            else:
                # SemanticAnalyzer不可用，使用降级分析
                format_analysis = self._fallback_output_format_analysis(query)
                
        except Exception as e:
            logger.error(f"❌ 输出格式分析失败: {e}")
            format_analysis = self._fallback_output_format_analysis(query)
        
        return format_analysis
    
    def _fallback_visual_needs_analysis(self, query: str) -> Dict[str, Any]:
        """🔄 降级视觉需求分析（基于关键词匹配）"""
        query_lower = query.lower()
        
        # 视觉相关关键词
        direct_visual_keywords = ['画', '设计', '生成图片', '创作', '制作', '绘制', 'draw', 'design', 'create image', 'generate image', 'make']
        implicit_visual_keywords = ['想象', '展示', '样子', '看起来', '外观', '风格', 'imagine', 'visualize', 'show', 'look like', 'appearance']
        design_keywords = ['logo', 'ui', '界面', '原型', '插图', '图标', '海报', '广告', 'mockup', 'prototype', 'illustration', 'banner', 'poster']
        
        if any(keyword in query_lower for keyword in direct_visual_keywords):
            return {
                'needs_visual': True,
                'confidence': 0.9,
                'visual_type': 'direct_creation',
                'visual_purpose': 'creation_request',
                'analysis_source': 'fallback_keywords'
            }
        elif any(keyword in query_lower for keyword in implicit_visual_keywords):
            return {
                'needs_visual': True,
                'confidence': 0.7,
                'visual_type': 'conceptual_illustration',
                'visual_purpose': 'concept_visualization',
                'analysis_source': 'fallback_keywords'
            }
        elif any(keyword in query_lower for keyword in design_keywords):
            return {
                'needs_visual': True,
                'confidence': 0.8,
                'visual_type': 'design_work',
                'visual_purpose': 'professional_design',
                'analysis_source': 'fallback_keywords'
            }
        else:
            return {
                'needs_visual': False,
                'confidence': 0.3,
                'visual_type': 'none',
                'visual_purpose': '',
                'analysis_source': 'fallback_keywords'
            }
    
    def _fallback_output_format_analysis(self, query: str) -> Dict[str, Any]:
        """🔄 降级输出格式分析（基于关键词匹配）"""
        query_lower = query.lower()
        
        # 格式相关关键词
        image_keywords = ['图', '画', '设计', 'image', 'picture', 'design', 'visual']
        
        if any(keyword in query_lower for keyword in image_keywords):
            return {
                'preferred_format': 'image',
                'format_confidence': 0.8,
                'output_medium': 'visual_content',
                'analysis_source': 'fallback_keywords'
            }
        else:
            return {
                'preferred_format': 'text',
                'format_confidence': 0.5,
                'output_medium': 'text_response',
                'analysis_source': 'fallback_keywords'
            }
    
    def _analyze_complexity_context(self, query: str, context: Dict) -> Dict[str, Any]:
        """分析复杂程度上下文"""
        # 基于查询长度和复杂度指标评估
        complexity_score = 0
        
        # 长度因素
        if len(query) > 100:
            complexity_score += 2
        elif len(query) > 50:
            complexity_score += 1
        
        # 复杂度关键词
        complex_keywords = ['如何实现', '设计方案', '架构', '系统', '详细', '全面']
        complexity_score += sum(1 for keyword in complex_keywords if keyword in query)
        
        if complexity_score >= 3:
            return {'level': 'high', 'requires_comprehensive_approach': True}
        elif complexity_score >= 1:
            return {'level': 'medium', 'requires_balanced_approach': True}
        else:
            return {'level': 'low', 'requires_simple_approach': True}
    
    def _decide_action_strategy(self, strategy_features: Dict, query_context: Dict, 
                              mab_confidence: float) -> Dict[str, Any]:
        """基于策略特征和查询上下文决定行动策略"""
        
        # 基础工具选择
        primary_tools = strategy_features.get('primary_tools', [])
        secondary_tools = strategy_features.get('secondary_tools', [])
        
        # 根据MAB置信度调整工具使用策略
        confidence_threshold = strategy_features.get('confidence_threshold', 0.6)
        
        if mab_confidence < confidence_threshold:
            # 低置信度：更保守，使用更多验证工具
            logger.info(f"🔍 MAB置信度 ({mab_confidence:.2f}) 低于阈值 ({confidence_threshold})，采用保守策略")
            if 'idea_verification' not in primary_tools:
                secondary_tools.append('idea_verification')
        
        # 根据查询复杂度调整策略
        complexity = query_context.get('complexity_level', {}).get('level', 'medium')
        if complexity == 'high':
            # 高复杂度：使用更全面的工具组合
            if 'web_search' not in primary_tools:
                primary_tools.append('web_search')
            if strategy_features.get('execution_pattern') != 'creative_direct':
                primary_tools.append('data_analysis')
        
        # 根据紧急程度调整策略
        urgency = query_context.get('urgency_level', {}).get('level', 'medium')
        execution_pattern = strategy_features.get('execution_pattern', 'sequential')
        
        if urgency == 'high':
            # 高紧急：优化执行模式，减少工具数量
            execution_pattern = 'direct'
            primary_tools = primary_tools[:2]  # 限制最多2个主要工具
        
        return {
            'primary_tools': primary_tools,
            'secondary_tools': secondary_tools,
            'execution_pattern': execution_pattern,
            'max_parallel_tools': 3 if urgency != 'high' else 1,
            'strategy_confidence': mab_confidence,
            'context_factors': {
                'complexity': complexity,
                'urgency': urgency,
                'domain': query_context.get('domain_specific', {}).get('domain', 'general')
            }
        }
    
    def _generate_concrete_actions(self, action_strategy: Dict, chosen_path, 
                                 query: str, query_context: Dict) -> List:
        """生成具体的工具调用行动"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            # 回退到简单的Action定义
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
                    self.execution_mode = 'sequential'
        
        actions = []
        primary_tools = action_strategy['primary_tools']
        execution_pattern = action_strategy['execution_pattern']
        
        logger.info(f"🔧 生成具体行动: {len(primary_tools)} 个主要工具")
        logger.info(f"   执行模式: {execution_pattern}")
        
        # 🎨 新增：检查是否需要视觉化工具
        visual_needs = query_context.get('visual_needs', {})
        if visual_needs.get('needs_visual', False):
            confidence = visual_needs.get('confidence', 0.0)
            visual_type = visual_needs.get('visual_type', 'unknown')
            logger.info(f"🎨 检测到视觉需求: 类型={visual_type}, 置信度={confidence:.2f}")
            
            # 优先处理视觉相关的执行模式
            if execution_pattern in ['visual_creation', 'iterative_design', 'concept_illustration']:
                logger.info(f"🎨 使用视觉化执行模式: {execution_pattern}")
                # 优先创建图像生成行动
                image_action = self._create_image_generation_action(query, visual_needs, query_context)
                if image_action:
                    actions.append(image_action)
                    logger.info("✨ 已添加图像生成行动")
                
                # 对于设计导向类型，可能还需要一些研究工具
                if visual_type == 'professional_design' and 'web_search' not in [action.tool_name for action in actions]:
                    # 添加设计灵感的搜索
                    design_search_action = self._create_design_research_action(query, visual_needs)
                    if design_search_action:
                        actions.append(design_search_action)
                        logger.info("🔍 已添加设计研究行动")
                
                return actions  # 直接返回视觉化行动组合
        
        # 🚨 对特定执行模式优先选择直接回答
        if execution_pattern in ['direct_creative', 'adaptive_direct', 'creative_direct']:
            logger.info(f"🎯 检测到直接回答优先模式: {execution_pattern}")
            # 返回空的actions列表，让planner使用直接回答
            return []
        
        # 标准工具选择逻辑
        for tool_name in primary_tools:
            try:
                action = self._create_tool_action(tool_name, query, chosen_path, query_context)
                if action:
                    actions.append(action)
            except Exception as e:
                logger.warning(f"⚠️ 创建工具行动失败 {tool_name}: {e}")
        
        # 根据执行模式调整行动属性
        if execution_pattern == 'parallel' and len(actions) > 1:
            # 标记为可并行执行
            for action in actions:
                if hasattr(action, 'execution_mode'):
                    action.execution_mode = 'parallel'
        
        return actions
    
    def _create_tool_action(self, tool_name: str, query: str, chosen_path,
                          query_context: Dict):
        """为特定工具创建行动"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
        
        # 根据工具类型生成合适的输入参数
        if tool_name == 'web_search' or tool_name == 'tavily_search':
            search_query = self._optimize_search_query(query, chosen_path, query_context)
            return Action(tool_name, {"query": search_query, "max_results": 5})
        
        elif tool_name == 'idea_verification':
            idea_to_verify = self._extract_verification_target(query, chosen_path)
            return Action(tool_name, {"idea_text": idea_to_verify})
        
        elif tool_name == 'knowledge_query':
            topic = self._extract_knowledge_topic(query, chosen_path)
            return Action(tool_name, {"topic": topic})
        
        elif tool_name == 'data_analysis':
            return Action(tool_name, {
                "data_type": "text",
                "data": query,
                "analysis_type": "comprehensive"
            })
        
        # 🎨 新增：图像生成工具支持 - 智能决策版本
        elif tool_name in ['image_generation', 'stable_diffusion_xl_generator']:
            # 使用新的视觉智能决策系统
            visual_decision = self._perform_visual_intelligence_decision(query, query_context)
            
            if visual_decision['should_generate']:
                return self._create_intelligent_image_generation_action(query, visual_decision, query_context)
            else:
                logger.info(f"🚫 视觉智能决策：不适合生成图像 - {visual_decision['decision_reason']}")
                return None
        
        else:
            logger.warning(f"⚠️ 未知工具类型: {tool_name}")
            return None
    
    def _create_image_generation_action(self, query: str, visual_needs: Dict, query_context: Dict):
        """🎨 创建图像生成工具行动"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
        
        # 生成优化的提示词
        prompt = self._generate_image_prompt(query, visual_needs, query_context)
        
        # 使用stable_diffusion_xl_generator工具
        tool_input = {
            "prompt": prompt,
            "save_image": True,
            "style_hint": self._extract_style_hint(visual_needs, query_context)
        }
        
        logger.info(f"🎨 创建图像生成行动: {prompt[:50]}...")
        return Action('stable_diffusion_xl_generator', tool_input)
    
    def _create_design_research_action(self, query: str, visual_needs: Dict):
        """🔍 为设计项目创建研究行动"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
        
        # 为设计项目优化的搜索查询
        visual_type = visual_needs.get('visual_type', 'design')
        
        if visual_type == 'professional_design':
            search_query = f"{query} 设计灵感 最佳实践 最新趋势"
        elif visual_type == 'logo':
            search_query = f"{query} logo设计 品牌视觉 设计理念"
        elif visual_type == 'ui_mockup':
            search_query = f"{query} UI设计 用户体验 界面设计"
        else:
            search_query = f"{query} 视觉设计 创意灵感"
        
        return Action('web_search', {
            "query": search_query,
            "max_results": 3  # 限制结果数量，优先图像生成
        })
    
    def _generate_image_prompt(self, query: str, visual_needs: Dict, query_context: Dict) -> str:
        """🎨 为图像生成生成优化的提示词"""
        visual_type = visual_needs.get('visual_type', 'unknown')
        visual_purpose = visual_needs.get('visual_purpose', '')
        suggested_elements = visual_needs.get('suggested_elements', [])
        
        # 基础提示词
        base_prompt = query.strip()
        
        # 根据视觉类型优化提示词
        if visual_type == 'direct_creation':
            # 直接创作请求，保持原始意图
            optimized_prompt = base_prompt
        
        elif visual_type == 'professional_design':
            # 专业设计，添加设计要素
            optimized_prompt = f"{base_prompt}, professional design, clean and modern, high quality"
            
        elif visual_type == 'conceptual_illustration':
            # 概念插图，添加描述性元素
            optimized_prompt = f"{base_prompt}, conceptual illustration, detailed, explanatory visual"
            
        elif visual_type == 'design_work':
            # 设计作品，根据具体类型优化
            if 'logo' in base_prompt.lower():
                optimized_prompt = f"{base_prompt}, minimalist logo design, vector style, brand identity"
            elif any(ui_word in base_prompt.lower() for ui_word in ['ui', '界面', 'interface']):
                optimized_prompt = f"{base_prompt}, UI design mockup, user interface, clean layout"
            else:
                optimized_prompt = f"{base_prompt}, professional design, creative, high quality"
        
        else:
            # 默认处理
            optimized_prompt = f"{base_prompt}, artistic, detailed, high quality"
        
        # 添加建议元素
        if suggested_elements:
            elements_text = ', '.join(suggested_elements[:3])  # 限制元素数量
            optimized_prompt += f", {elements_text}"
        
        # 添加通用质量提升关键词
        optimized_prompt += ", detailed, professional quality, realistic"
        
        logger.debug(f"🎨 生成的图像提示词: {optimized_prompt}")
        return optimized_prompt
    
    def _extract_style_hint(self, visual_needs: Dict, query_context: Dict) -> str:
        """🎨 提取风格提示"""
        visual_type = visual_needs.get('visual_type', 'unknown')
        domain = query_context.get('domain_specific', {}).get('domain', 'general')
        
        # 根据类型和领域提供风格提示
        style_hints = {
            'professional_design': 'clean, modern, professional',
            'conceptual_illustration': 'artistic, conceptual, detailed',
            'direct_creation': 'creative, artistic',
            'design_work': 'design-focused, brand-appropriate'
        }
        
        domain_hints = {
            'technical': 'tech-oriented, clean, futuristic',
            'business': 'professional, corporate, sophisticated',
            'academic': 'scholarly, detailed, informative',
            'creative': 'artistic, expressive, imaginative'
        }
        
        style = style_hints.get(visual_type, 'artistic, detailed')
        if domain != 'general':
            style += f", {domain_hints.get(domain, '')}"
        
        return style
    
    def _optimize_search_query(self, original_query: str, chosen_path, query_context: Dict) -> str:
        """优化搜索查询"""
        # 基础查询
        optimized_query = original_query
        
        # 根据策略类型优化
        if chosen_path.path_type == 'exploratory_investigative':
            optimized_query += " 深入分析 最新发展"
        elif chosen_path.path_type == 'critical_questioning':
            optimized_query += " 风险 挑战 问题"
        elif chosen_path.path_type == 'systematic_analytical':
            optimized_query += " 系统方法 解决方案"
        
        # 根据领域优化
        domain = query_context.get('domain_specific', {}).get('domain', 'general')
        if domain == 'technical':
            optimized_query += " 技术实现"
        elif domain == 'business':
            optimized_query += " 商业应用"
        
        return optimized_query
    
    def _extract_verification_target(self, query: str, chosen_path) -> str:
        """提取需要验证的目标"""
        # 如果查询中包含明确的想法或方案，提取出来
        verification_phrases = ['这个想法', '这个方案', '这种方法', '可行吗', '是否可行']
        
        for phrase in verification_phrases:
            if phrase in query:
                return query
        
        # 否则基于路径类型构造验证目标
        return f"关于'{query}'的可行性和潜在风险"
    
    def _extract_knowledge_topic(self, query: str, chosen_path) -> str:
        """提取知识查询主题"""
        return query[:100]  # 限制长度
    
    def _extract_analysis_target(self, query: str) -> str:
        """提取分析目标"""
        return query


class ImprovedMockNeogenesisPlanner:
    """
    改进的Mock规划器 - 在简化环境下也体现多阶段决策思想
    
    即使在Mock环境中，也要体现:
    1. 策略生成 (简化版PathGenerator)
    2. 策略选择 (简化版MAB)  
    3. 策略解析 (使用StrategyInterpreter)
    """
    
    def __init__(self):
        self.name = "ImprovedMockNeogenesisPlanner"
        self.strategy_interpreter = StrategyInterpreter()
        
        # 简化的策略模板
        self.mock_strategy_templates = {
            'search_focused': {
                'path_type': 'exploratory_investigative',
                'description': '信息搜索和调研导向的策略',
                'prompt_template': '深入搜索和研究关于{task}的信息',
                'trigger_keywords': ['搜索', '查找', '信息', '资料', '了解', '什么是']
            },
            'verification_focused': {
                'path_type': 'critical_questioning',
                'description': '验证和质疑导向的策略',
                'prompt_template': '批判性分析和验证{task}的可行性',
                'trigger_keywords': ['验证', '可行', '风险', '问题', '缺点', '是否']
            },
            'analysis_focused': {
                'path_type': 'systematic_analytical',
                'description': '系统分析导向的策略',
                'prompt_template': '系统性分析{task}的各个方面',
                'trigger_keywords': ['分析', '如何', '方法', '步骤', '实现', '设计']
            },
            'direct_answer': {
                'path_type': 'practical_pragmatic',
                'description': '实用直接回答策略',
                'prompt_template': '基于现有知识直接回答{task}',
                'trigger_keywords': ['你好', 'hello', '介绍', '帮助']
            }
        }
        
        # 简化的选择统计 (模拟MAB)
        self.strategy_success_stats = {
            'search_focused': {'success_count': 10, 'total_count': 15},
            'verification_focused': {'success_count': 8, 'total_count': 12},
            'analysis_focused': {'success_count': 12, 'total_count': 18},
            'direct_answer': {'success_count': 20, 'total_count': 25}
        }
        
        logger.info("🤖 改进的Mock规划器初始化完成")
    
    def create_plan(self, query: str, memory, context=None):
        """改进的计划创建 - 体现简化的多阶段决策"""
        try:
            from neogenesis_system.abstractions import Plan
        except ImportError:
            class Plan:
                def __init__(self, thought, final_answer=None, actions=None):
                    self.thought = thought
                    self.final_answer = final_answer
                    self.actions = actions or []
                    self.is_direct_answer = final_answer is not None
        
        logger.info(f"🤖 Mock规划器开始多阶段决策: {query[:50]}...")
        
        # 阶段1: 策略候选生成 (简化的PathGenerator)
        candidate_strategies = self._generate_candidate_strategies(query)
        logger.info(f"🧠 生成策略候选: {[s['path_type'] for s in candidate_strategies]}")
        
        # 阶段2: 策略选择 (简化的MAB)
        chosen_strategy = self._select_best_strategy(candidate_strategies, query)
        logger.info(f"🎯 选择策略: {chosen_strategy['path_type']}")
        
        # 阶段3: 策略解析为行动 (使用StrategyInterpreter)
        mock_reasoning_path = self._create_mock_reasoning_path(chosen_strategy, query)
        
        # 使用策略解释器生成行动
        try:
            actions = self.strategy_interpreter.interpret_strategy_to_actions(
                chosen_path=mock_reasoning_path,
                query=query,
                mab_confidence=0.8,  # Mock置信度
                decision_context=context or {}
            )
        except Exception as e:
            logger.warning(f"⚠️ 策略解释器调用失败，使用简化逻辑: {e}")
            actions = self._fallback_action_generation(chosen_strategy, query)
        
        # 构建最终计划
        if not actions:
            # 🔧 关键修复：恢复直接回答模式，针对简单问候和介绍类问题
            # 避免所有问题都被强制进入工具执行路径
            
            # 检查是否为简单的直接回答类型
            query_lower = query.lower().strip()
            is_simple_greeting = any(greeting in query_lower for greeting in ['你好', 'hello', 'hi', '您好'])
            is_simple_intro = "介绍" in query_lower and ("自己" in query_lower or "你" in query_lower)
            is_simple_thanks = any(thanks in query_lower for thanks in ['谢谢', 'thanks', 'thank you', '感谢'])
            is_simple_help = any(help_word in query_lower for help_word in ['帮助', '能做什么', '功能'])
            
            if is_simple_greeting or is_simple_intro or is_simple_thanks or is_simple_help:
                # 使用直接回答模式 - 不需要工具调用
                return Plan(
                    thought=f"基于多阶段决策，识别为简单问候/介绍类查询，选择直接回答策略",
                    final_answer=self._generate_direct_answer_for_simple_query(query)
                )
            
            # 对于其他复杂问题，生成工具调用
            if chosen_strategy['path_type'] == 'practical_pragmatic':
                actions = [Action("knowledge_query", {"topic": query})]
            elif chosen_strategy['path_type'] == 'exploratory_investigative':
                actions = [Action("web_search", {"query": query})]
            elif chosen_strategy['path_type'] == 'critical_questioning':
                actions = [Action("idea_verification", {"idea_text": query})]
            else:
                # 默认使用knowledge_query工具
                actions = [Action("knowledge_query", {"topic": query})]
        
        # 工具执行模式
        return Plan(
            thought=f"基于多阶段决策，选择'{chosen_strategy['path_type']}'策略，通过工具调用生成专业回答（{len(actions)}个行动）",
            actions=actions
        )
    
    def _generate_direct_answer_for_simple_query(self, query: str) -> str:
        """为简单查询生成直接回答"""
        query_lower = query.lower().strip()
        
        # 问候类
        if any(greeting in query_lower for greeting in ['你好', 'hello', 'hi', '您好']):
            return "你好！我是Neogenesis智能助手，很高兴为您服务。有什么我可以帮助您的吗？"
        
        # 介绍类  
        if "介绍" in query_lower and ("自己" in query_lower or "你" in query_lower):
            return "我是Neogenesis智能助手，可以帮助您进行信息查询、问题分析、创意思考等多种任务。我会根据不同问题智能选择最合适的处理方式，为您提供准确有用的帮助。"
        
        # 感谢类
        if any(thanks in query_lower for thanks in ['谢谢', 'thanks', 'thank you', '感谢']):
            return "不客气！如果还有其他问题，随时可以问我。"
        
        # 功能查询类
        if any(help_word in query_lower for help_word in ['帮助', '能做什么', '功能']):
            return "我可以帮您搜索信息、分析问题、验证想法、回答各领域问题等。我的特点是能根据不同问题智能选择最合适的处理方式，为您提供有价值的帮助。"
        
        # 默认回答 - 使用LLM或诚实说明限制，避免预设模板
        try:
            # 🔥 修复：使用统一的LLMConfig而不是ClientConfig
            from neogenesis_system.providers.llm_base import LLMConfig, LLMProvider
            from neogenesis_system.providers.impl.deepseek_client import DeepSeekClient
            import os
            
            api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('NEOGENESIS_API_KEY')
            if api_key:
                llm_config = LLMConfig(
                    provider=LLMProvider.DEEPSEEK,
                    api_key=api_key,
                    model_name="deepseek-chat",
                    temperature=0.7,
                    max_tokens=300,
                    base_url="https://api.deepseek.com/v1",
                    timeout=(60, 300),
                    max_retries=3,
                    retry_delay_base=2.0,
                    enable_cache=True,
                    enable_metrics=False
                )
                client = DeepSeekClient(llm_config)
                
                prompt = f"""请简洁回答用户问题：{query}

如果无法准确回答，请诚实说明限制。保持友好语气："""
                
                # 使用chat_completion而不是simple_chat
                messages = [{"role": "user", "content": prompt}]
                api_response = client.chat_completion(messages=messages, max_tokens=300, temperature=0.7)
                llm_response = api_response.content if hasattr(api_response, 'content') else str(api_response)
                
                if llm_response and llm_response.strip():
                    return llm_response.strip()
                    
        except Exception as e:
            logger.warning(f"⚠️ 策略解释器默认LLM调用失败: {e}")
            logger.debug(f"   错误详情: {type(e).__name__}: {str(e)}")
        
        # 最终诚实回答 - 不使用预设模板
        if "时间" in query_lower or "几点" in query_lower:
            return "抱歉，我无法获取当前的实时时间信息。建议您查看您的设备时钟或搜索引擎获取准确时间。"
        elif "天气" in query_lower:
            return "抱歉，我无法获取实时天气信息。建议您查看天气应用或网站获取最新天气预报。"
        else:
            return f"关于您的问题「{query}」，我很愿意帮助您，但我可能需要更多信息才能提供准确的回答。请问您能提供更多具体细节吗？"

    def _generate_candidate_strategies(self, query: str) -> List[Dict]:
        """生成候选策略 - 简化版PathGenerator"""
        candidates = []
        query_lower = query.lower()
        
        # 为每个策略模板计算相关度
        for strategy_id, template in self.mock_strategy_templates.items():
            relevance_score = 0
            
            # 基于关键词匹配计算相关度
            for keyword in template['trigger_keywords']:
                if keyword in query_lower:
                    relevance_score += 1
            
            # 标准化相关度分数
            max_possible_score = len(template['trigger_keywords'])
            normalized_score = relevance_score / max_possible_score if max_possible_score > 0 else 0.1
            
            candidates.append({
                'strategy_id': strategy_id,
                'relevance_score': normalized_score,
                **template
            })
        
        # 按相关度排序
        candidates.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # 返回前3个最相关的策略
        return candidates[:3]
    
    def _select_best_strategy(self, candidates: List[Dict], query: str) -> Dict:
        """选择最佳策略 - 简化版MAB"""
        if not candidates:
            return self.mock_strategy_templates['direct_answer']
        
        best_strategy = None
        best_score = -1
        
        for candidate in candidates:
            strategy_id = candidate['strategy_id']
            
            # 获取历史成功率 (模拟MAB数据)
            stats = self.strategy_success_stats.get(strategy_id, {'success_count': 1, 'total_count': 2})
            success_rate = stats['success_count'] / stats['total_count']
            
            # 结合相关度和成功率 (简化的UCB算法)
            exploration_bonus = 0.1  # 简化的探索奖励
            combined_score = (
                candidate['relevance_score'] * 0.6 +  # 相关度权重
                success_rate * 0.3 +                  # 成功率权重
                exploration_bonus * 0.1               # 探索奖励权重
            )
            
            if combined_score > best_score:
                best_score = combined_score
                best_strategy = candidate
        
        # 更新选择统计 (模拟MAB学习)
        if best_strategy:
            strategy_id = best_strategy['strategy_id']
            self.strategy_success_stats[strategy_id]['total_count'] += 1
        
        return best_strategy or self.mock_strategy_templates['direct_answer']
    
    def _create_mock_reasoning_path(self, strategy: Dict, query: str):
        """创建Mock的ReasoningPath对象"""
        try:
            from neogenesis_system.cognitive_engine.path_generator import ReasoningPath
        except ImportError:
            # 简单的Mock ReasoningPath
            class ReasoningPath:
                def __init__(self, path_id, path_type, description, prompt_template, strategy_id):
                    self.path_id = path_id
                    self.path_type = path_type
                    self.description = description
                    self.prompt_template = prompt_template
                    self.strategy_id = strategy_id
        
        return ReasoningPath(
            path_id=f"mock_{strategy['strategy_id']}",
            path_type=strategy['path_type'],
            description=strategy['description'],
            prompt_template=strategy['prompt_template'].format(task=query),
            strategy_id=strategy['strategy_id']
        )
    
    def _fallback_action_generation(self, strategy: Dict, query: str) -> List:
        """简化的行动生成回退逻辑"""
        try:
            from neogenesis_system.abstractions import Action
        except ImportError:
            class Action:
                def __init__(self, tool_name, tool_input):
                    self.tool_name = tool_name
                    self.tool_input = tool_input
        
        actions = []
        strategy_type = strategy['path_type']
        
        if strategy_type == 'exploratory_investigative':
            actions.append(Action("web_search", {"query": query}))
        elif strategy_type == 'critical_questioning':
            actions.append(Action("idea_verification", {"idea_text": query}))
        elif strategy_type == 'systematic_analytical':
            actions.append(Action("knowledge_query", {"topic": query}))
        
        return actions
    
    def _generate_mock_direct_answer(self, strategy: Dict, query: str) -> str:
        """生成Mock直接回答 - 移除预设回答，确保使用真实的多决策链条"""
        strategy_type = strategy['path_type']
        
        # 🔧 重要修改：移除所有预设回答，包括问候语的预设回复
        # 确保所有问题都通过真正的多阶段决策和工具调用来处理
        
        # 不再提供预设的问候回答，而是返回None或空字符串，
        # 这样会强制系统使用工具执行流程
        return ""  # 返回空字符串，强制走工具执行流程
    
    def validate_plan(self, plan):
        """验证计划"""
        return True
    
    def get_stats(self):
        """获取统计信息"""
        return {
            "name": self.name,
            "total_rounds": 0,
            "strategy_success_stats": self.strategy_success_stats
        }   
        
