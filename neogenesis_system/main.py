#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Neogenesis System - 启动入口
智能思维路径决策系统的主要入口点

使用示例:
    # 思维发散：探索问题的多种思考角度
    python -m neogenesis_system.main --query "如何提升团队创新能力" --api-key "your_api_key"
    
    # 思维收敛：在复杂情境下选择最优思维路径
    python -m neogenesis_system.main --query "分析市场变化的深层原因" --context '{"thinking_depth": "deep", "perspective_diversity": true}' --api-key "your_api_key"
    
    # 交互式思维训练模式
    python -m neogenesis_system.main --interactive --api-key "your_api_key"
"""

import os
import sys
import json
import time
import logging
import argparse
from typing import Dict, Any, Optional

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()  # 加载项目根目录的 .env 文件
except ImportError:
    pass  # 如果没有安装 python-dotenv，则跳过

# 使用相对导入，因为main.py位于包内
# from .meta_mab.controller import MainController  # 已废弃，使用 NeogenesisPlanner
from .core.neogenesis_planner import NeogenesisPlanner
from .cognitive_engine.reasoner import PriorReasoner
from .cognitive_engine.path_generator import PathGenerator
from .cognitive_engine.mab_converger import MABConverger
from .config import LOGGING_CONFIG, FEATURE_FLAGS


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """设置日志配置"""
    
    # 配置日志格式
    formatter = logging.Formatter(LOGGING_CONFIG["format"])
    
    # 设置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


class NeogenesisSystem:
    """Neogenesis智能决策系统"""
    
    def __init__(self, api_key: str, config: Optional[Dict] = None):
        """
        初始化系统
        
        Args:
            api_key: DeepSeek API密钥  
            config: 系统配置
        """
        self.api_key = api_key
        self.config = config or {}
        
        # 初始化NeogenesisPlanner及其组件
        prior_reasoner = PriorReasoner(api_key)
        
        # 创建LLM客户端（智能选择最佳可用客户端）
        llm_client = None
        if api_key:
            try:
                # 优先尝试使用LLM管理器来自动选择最佳客户端
                from .providers.llm_manager import LLMManager
                llm_manager = LLMManager()
                if llm_manager.initialized and llm_manager.providers:
                    llm_client = llm_manager
                    print(f"✅ LLM管理器创建成功，使用提供商: {list(llm_manager.providers.keys())}")
                else:
                    # 回退到DeepSeek客户端
                    from .providers.impl.deepseek_client import create_llm_client
                    llm_client = create_llm_client(api_key)
                    print("✅ LLM客户端创建成功（DeepSeek），PathGenerator将启用智能分析")
            except Exception as e:
                print(f"⚠️ LLM客户端创建失败，使用离线模式: {e}")
        else:
            print("⚠️ 未提供API密钥，PathGenerator将使用离线分析模式")
        
        path_generator = PathGenerator(api_key, llm_client=llm_client)
        mab_converger = MABConverger()
        
        self.planner = NeogenesisPlanner(
            prior_reasoner=prior_reasoner,
            path_generator=path_generator,
            mab_converger=mab_converger
        )
        
        # 系统统计
        self.session_stats = {
            'start_time': time.time(),
            'total_queries': 0,
            'successful_queries': 0,
            'total_time': 0.0
        }
        
        print("🌟 Neogenesis智能思维路径决策系统已启动")
        print(f"🧠 思维发散组件: {'✅' if prior_reasoner else '❌'}")
        print(f"🤖 DeepSeek思维引擎: {'✅' if api_key else '❌'}")
        print(f"🎯 MAB收敛算法: {'✅' if mab_converger else '❌'}")
        print(f"🔧 规划器模块: {'✅' if self.planner else '❌'}")
        print("-" * 50)
    
    def process_query(self, user_query: str, execution_context: Optional[Dict] = None, 
                     deepseek_confidence: float = 0.5) -> Dict[str, Any]:
        """
        处理单个查询
        
        Args:
            user_query: 用户查询
            execution_context: 执行上下文
            deepseek_confidence: DeepSeek置信度
            
        Returns:
            处理结果
        """
        start_time = time.time()
        self.session_stats['total_queries'] += 1
        
        print(f"\n🎯 开始思维路径分析: {user_query}")
        print(f"📝 认知上下文: {execution_context or '无'}")
        
        try:
            # 使用NeogenesisPlanner进行规划
            plan_result = self.planner.create_plan(
                query=user_query,
                memory=None,
                context=execution_context or {}
            )
            
            # 模拟执行（在实际应用中，这里会调用具体的执行逻辑）
            execution_result = self._simulate_execution_from_plan(plan_result)
            
            # NeogenesisPlanner的学习反馈通过执行器实现，这里我们模拟记录
            
            # 更新统计
            processing_time = time.time() - start_time
            self.session_stats['total_time'] += processing_time
            
            if execution_result['success']:
                self.session_stats['successful_queries'] += 1
            
            # 构建完整结果
            complete_result = {
                'query': user_query,
                'plan': plan_result,
                'execution': execution_result,
                'processing_time': processing_time,
                'session_stats': self.session_stats.copy()
            }
            
            self._print_result_summary(complete_result)
            return complete_result
            
        except Exception as e:
            error_time = time.time() - start_time
            self.session_stats['total_time'] += error_time
            
            error_result = {
                'query': user_query,
                'error': str(e),
                'processing_time': error_time,
                'session_stats': self.session_stats.copy()
            }
            
            print(f"❌ 处理失败: {e}")
            return error_result
    
    def _simulate_execution_from_plan(self, plan_result) -> Dict[str, Any]:
        """
        模拟执行过程（在实际应用中，这里会调用真实的执行逻辑）
        
        Args:
            plan_result: Plan对象
            
        Returns:
            执行结果
        """
        # 基于Plan质量模拟执行结果
        import random
        
        # 从Plan的元数据中提取置信度信息
        metadata = plan_result.metadata or {}
        neogenesis_data = metadata.get('neogenesis_decision', {})
        performance_metrics = neogenesis_data.get('performance_metrics', {})
        avg_confidence = performance_metrics.get('avg_confidence', 0.7)
        
        # 模拟执行时间
        base_time = 2.0
        action_count = len(plan_result.actions) if not plan_result.is_direct_answer else 1
        execution_time = base_time + action_count * 1.5
        
        # 模拟成功率（基于置信度）
        success_probability = avg_confidence * 0.8 + 0.1  # 0.1 到 0.9 之间
        success = random.random() < success_probability
        
        # 模拟用户满意度
        if success:
            user_satisfaction = min(1.0, avg_confidence + random.uniform(-0.1, 0.2))
        else:
            user_satisfaction = max(0.0, avg_confidence - random.uniform(0.2, 0.4))
        
        # 计算RL奖励
        rl_reward = self._calculate_rl_reward(success, execution_time, user_satisfaction)
        
        return {
            'success': success,
            'execution_time': execution_time,
            'user_satisfaction': user_satisfaction,
            'rl_reward': rl_reward,
            'output': f"模拟执行结果 - 成功: {success}, 满意度: {user_satisfaction:.2f}",
            'simulated': True
        }
    
    def _calculate_rl_reward(self, success: bool, execution_time: float, user_satisfaction: float) -> float:
        """计算强化学习奖励"""
        if not success:
            return -0.5 - (execution_time / 10.0)  # 失败惩罚
        
        # 成功奖励
        base_reward = 1.0
        
        # 时间惩罚
        time_penalty = max(0, (execution_time - 2.0) / 10.0)
        
        # 满意度奖励
        satisfaction_bonus = (user_satisfaction - 0.5) * 0.5
        
        return base_reward - time_penalty + satisfaction_bonus
    
    def _print_result_summary(self, result: Dict[str, Any]):
        """打印结果摘要"""
        plan = result['plan']
        execution = result['execution']
        
        print(f"\n🧠 智能规划结果:")
        print(f"   规划类型: {'直接回答' if plan.is_direct_answer else '行动计划'}")
        print(f"   思考过程: {plan.thought[:100]}..." if len(plan.thought) > 100 else f"   思考过程: {plan.thought}")
        
        if plan.is_direct_answer:
            print(f"   直接回答: {plan.final_answer[:100]}..." if len(plan.final_answer) > 100 else f"   直接回答: {plan.final_answer}")
        else:
            print(f"   计划行动: {len(plan.actions)}个")
            for i, action in enumerate(plan.actions[:3], 1):  # 只显示前3个
                print(f"   - 行动{i}: {action.tool_name}({action.tool_input})")
        
        # 显示NeogenesisPlanner的决策信息
        metadata = plan.metadata or {}
        neogenesis_data = metadata.get('neogenesis_decision', {})
        if neogenesis_data:
            chosen_path = neogenesis_data.get('chosen_path')
            if chosen_path:
                path_type = getattr(chosen_path, 'path_type', '未知')
                print(f"   选择的思维路径: {path_type}")
        
        print(f"\n⚡ 执行结果:")
        print(f"   成功: {'✅' if execution['success'] else '❌'}")
        print(f"   执行时间: {execution['execution_time']:.2f}秒")
        print(f"   用户满意度: {execution['user_satisfaction']:.2f}")
        print(f"   RL奖励: {execution['rl_reward']:.2f}")
        
        print(f"\n📈 性能指标:")
        print(f"   处理时间: {result['processing_time']:.3f}秒")
        print(f"   会话成功率: {self.session_stats['successful_queries']}/{self.session_stats['total_queries']}")
    
    def interactive_mode(self):
        """交互模式"""
        print("\n🔥 进入思维训练交互模式")
        print("输入思维问题进行路径分析，'help' 查看帮助，'quit' 退出")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n💭 请输入思维问题 (或命令): ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                elif user_input.lower() == 'help':
                    self._print_help()
                elif user_input.lower() == 'status':
                    self._print_system_status()
                elif user_input.lower() == 'stats':
                    self._print_session_stats()
                elif user_input.lower() == 'reset':
                    self._reset_system()
                else:
                    # 处理普通查询
                    context_input = input("🧠 认知上下文 (JSON格式，直接回车跳过): ").strip()
                    execution_context = None
                    
                    if context_input:
                        try:
                            execution_context = json.loads(context_input)
                        except json.JSONDecodeError:
                            print("⚠️ 上下文格式错误，将忽略")
                    
                    self.process_query(user_input, execution_context)
                    
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出交互模式")
                break
            except Exception as e:
                print(f"❌ 交互错误: {e}")
        
        self._print_session_summary()
    
    def _print_help(self):
        """打印帮助信息"""
        print("\n📖 可用命令:")
        print("  help   - 显示此帮助信息")
        print("  status - 显示系统状态")
        print("  stats  - 显示会话统计")
        print("  reset  - 重置系统")
        print("  quit   - 退出程序")
        print("\n💡 思维训练示例:")
        print("  - 如何从多个角度理解这个问题")
        print("  - 探索创新思维的不同路径")
        print("  - 在复杂情况下寻找最优认知策略")
    
    def _print_system_status(self):
        """打印系统状态"""
        try:
            print("\n🏥 系统状态:")
            print(f"   规划器类型: NeogenesisPlanner")
            print(f"   总查询数: {self.session_stats['total_queries']}")
            print(f"   成功率: {self.session_stats['successful_queries']/max(self.session_stats['total_queries'],1):.1%}")
            print(f"   平均处理时间: {self.session_stats['total_time']/max(self.session_stats['total_queries'],1):.3f}秒")
            print(f"   组件状态: 思维种子✅ 路径生成✅ MAB收敛✅")
        except Exception as e:
            print(f"❌ 获取系统状态失败: {e}")
    
    def _print_session_stats(self):
        """打印会话统计"""
        stats = self.session_stats
        duration = time.time() - stats['start_time']
        
        print("\n📊 会话统计:")
        print(f"   运行时间: {duration:.1f}秒")
        print(f"   总查询数: {stats['total_queries']}")
        print(f"   成功查询: {stats['successful_queries']}")
        print(f"   成功率: {stats['successful_queries']/max(stats['total_queries'],1):.1%}")
        print(f"   总处理时间: {stats['total_time']:.3f}秒")
        print(f"   平均处理时间: {stats['total_time']/max(stats['total_queries'],1):.3f}秒")
    
    def _reset_system(self):
        """重置系统"""
        confirm = input("⚠️ 确认重置系统? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            # 重置会话统计
            self.session_stats = {
                'start_time': time.time(),
                'total_queries': 0,
                'successful_queries': 0,
                'total_time': 0.0
            }
            print("✅ 系统已重置")
        else:
            print("❌ 取消重置")
    
    def _print_session_summary(self):
        """打印会话摘要"""
        print("\n" + "="*50)
        print("📋 会话摘要")
        print("="*50)
        self._print_session_stats()
        
        if self.session_stats['total_queries'] > 0:
            try:
                print("\n💡 使用建议:")
                success_rate = self.session_stats['successful_queries']/self.session_stats['total_queries']
                if success_rate < 0.8:
                    print("   - 考虑为复杂查询提供更多上下文信息")
                avg_time = self.session_stats['total_time']/self.session_stats['total_queries']
                if avg_time > 5.0:
                    print("   - 查询可能过于复杂，尝试分解为更简单的问题")
                print("   - NeogenesisPlanner会随着使用不断优化")
            except:
                pass
        
        print("\n👋 感谢使用Neogenesis智能思维路径决策系统！")
    
    def _make_serializable(self, obj):
        """将复杂对象转换为JSON可序列化的格式"""
        if hasattr(obj, '__dict__'):
            return {k: self._make_serializable(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)  # 将其他类型转换为字符串


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Neogenesis智能思维路径决策系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s --query "如何提升团队创新能力" --api-key "your_api_key"
  %(prog)s --interactive --api-key "your_api_key"
  %(prog)s --query "分析市场变化的深层原因" --context '{"thinking_depth": "deep"}' --api-key "your_api_key"
        """
    )
    
    parser.add_argument(
        '--api-key', 
        type=str, 
        default=os.getenv('DEEPSEEK_API_KEY', ''),
        help='DeepSeek API密钥 (也可以通过环境变量DEEPSEEK_API_KEY设置)'
    )
    
    parser.add_argument(
        '--query', 
        type=str,
        help='要处理的查询'
    )
    
    parser.add_argument(
        '--context',
        type=str,
        help='执行上下文 (JSON格式)'
    )
    
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.5,
        help='DeepSeek置信度 (0.0-1.0, 默认0.5)'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='启动交互模式'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        help='日志文件路径'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='配置文件路径 (JSON格式)'
    )
    
    return parser.parse_args()


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 加载配置文件失败: {e}")
        return {}


def main():
    """主函数"""
    args = parse_arguments()
    
    # 设置日志
    setup_logging(args.log_level, args.log_file)
    
    # 检查API密钥
    if not args.api_key:
        print("❌ 错误: 请提供DeepSeek API密钥")
        print("   方法1: --api-key your_api_key")
        print("   方法2: 设置环境变量 DEEPSEEK_API_KEY")
        return 1
    
    # 加载配置
    config = {}
    if args.config:
        config = load_config(args.config)
    
    try:
        # 初始化系统
        system = NeogenesisSystem(args.api_key, config)
        
        if args.interactive:
            # 交互模式
            system.interactive_mode()
        elif args.query:
            # 单次查询模式
            execution_context = None
            if args.context:
                try:
                    execution_context = json.loads(args.context)
                except json.JSONDecodeError as e:
                    print(f"⚠️ 上下文格式错误: {e}")
                    return 1
            
            result = system.process_query(args.query, execution_context, args.confidence)
            
            # 输出JSON结果（用于脚本集成）
            if args.log_level == 'ERROR':  # 静默模式，只输出结果
                try:
                    # 转换复杂对象为可序列化的格式
                    serializable_result = system._make_serializable(result)
                    print(json.dumps(serializable_result, ensure_ascii=False, indent=2))
                except Exception as e:
                    print(json.dumps({"error": f"结果序列化失败: {str(e)}"}, ensure_ascii=False, indent=2))
        else:
            print("❌ 错误: 请指定 --query 或 --interactive")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n👋 用户中断程序")
        return 0
    except Exception as e:
        print(f"❌ 系统错误: {e}")
        logging.exception("系统错误详情:")
        return 1


if __name__ == "__main__":
    sys.exit(main())