#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default Tools - 默认工具定义

这个模块定义了系统的内置工具，使用 @tool 装饰器实现统一的工具抽象。
所有工具现在都是 BaseTool 的子类，可以被 ToolRegistry 统一管理。

重构说明：
- 删除了临时的 Tool 类和 DefaultTools 类
- 使用 @tool 装饰器重写所有工具函数
- 工具的参数、类型、描述都从函数签名和文档字符串中自动提取
- LLM 可以更好地理解和使用这些工具
"""

from typing import Dict, Any, List, Optional
from .tool_abstraction import tool, ToolCategory, ToolResult

# 导入图像生成工具
try:
    from .image_generation_tools import ImageGenerationTool, batch_generate_images as batch_generate
    IMAGE_TOOLS_AVAILABLE = True
except ImportError:
    IMAGE_TOOLS_AVAILABLE = False

# ============================================================================
# 核心工具函数 - 使用 @tool 装饰器实现统一抽象
# ============================================================================

@tool(category=ToolCategory.SYSTEM, name="idea_verification", overwrite=True)
def verify_idea(idea: str, criteria: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    验证思想的可行性、新颖性和影响力
    
    这个工具会根据指定的标准对思想进行多维度评估，
    提供量化的评分和具体的改进建议。
    
    Args:
        idea: 要验证的思想或概念
        criteria: 验证标准列表，默认包括可行性、新颖性、影响力、清晰度
        
    Returns:
        包含验证结果、评分和建议的详细报告
    """
    if criteria is None:
        criteria = ["feasibility", "novelty", "impact", "clarity"]
    
    # 基础验证逻辑（可扩展）
    results = {
        "idea": idea,
        "verification_results": {},
        "overall_score": 0.0,
        "recommendations": []
    }
    
    for criterion in criteria:
        # 简化的评分逻辑（实际实现可以更复杂）
        if criterion == "feasibility":
            score = 0.8 if len(idea.split()) > 5 else 0.5
        elif criterion == "novelty":
            score = 0.7 if "创新" in idea or "新" in idea else 0.6
        elif criterion == "impact":
            score = 0.9 if "影响" in idea or "改进" in idea else 0.7
        elif criterion == "clarity":
            score = 0.8 if len(idea) > 20 else 0.6
        else:
            score = 0.7
        
        results["verification_results"][criterion] = score
    
    # 计算总体分数
    results["overall_score"] = sum(results["verification_results"].values()) / len(criteria)
    
    # 生成建议
    if results["overall_score"] < 0.6:
        results["recommendations"].append("需要进一步完善思想")
    if results["verification_results"].get("feasibility", 0) < 0.7:
        results["recommendations"].append("考虑提高可行性")
    
    return results

@tool(category=ToolCategory.SEARCH, name="search_knowledge", overwrite=True)
def search_knowledge(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    搜索相关知识和信息
    
    这个工具可以在知识库中搜索与查询相关的信息，
    返回按相关性排序的搜索结果。
    
    Args:
        query: 搜索查询字符串
        max_results: 返回的最大结果数量，默认为5
        
    Returns:
        包含搜索结果列表和元数据的字典
    """
    # 模拟搜索结果
    return {
        "query": query,
        "results": [
            {
                "title": f"关于'{query}'的研究",
                "content": f"这是关于{query}的详细信息...",
                "relevance": 0.9,
                "source": "知识库"
            }
            # 可以添加更多模拟结果
        ],
        "total_found": max_results
    }
@tool(category=ToolCategory.DATA_PROCESSING, name="analyze_text", overwrite=True)
def analyze_text(text: str, analysis_type: str = "sentiment") -> Dict[str, Any]:
    """
    分析文本内容的情感、复杂度等特征
    
    这个工具可以对文本进行多种类型的分析，包括情感分析、
    复杂度分析等，帮助理解文本的特征和质量。
    
    Args:
        text: 要分析的文本内容
        analysis_type: 分析类型，支持 "sentiment"（情感分析）和 "complexity"（复杂度分析）
        
    Returns:
        包含分析结果和详细指标的字典
    """
    results = {
        "text": text,
        "analysis_type": analysis_type,
        "results": {}
    }
    
    if analysis_type == "sentiment":
        # 简化的情感分析
        positive_words = ["好", "优秀", "成功", "有效", "创新"]
        negative_words = ["差", "失败", "问题", "困难", "错误"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = 0.7 + (positive_count - negative_count) * 0.1
        elif negative_count > positive_count:
            sentiment = "negative" 
            score = 0.3 - (negative_count - positive_count) * 0.1
        else:
            sentiment = "neutral"
            score = 0.5
        
        results["results"] = {
            "sentiment": sentiment,
            "score": max(0.0, min(1.0, score)),
            "positive_indicators": positive_count,
            "negative_indicators": negative_count
        }
    
    elif analysis_type == "complexity":
        # 文本复杂度分析
        word_count = len(text.split())
        char_count = len(text)
        avg_word_length = char_count / max(word_count, 1)
        
        results["results"] = {
            "word_count": word_count,
            "character_count": char_count,
            "average_word_length": avg_word_length,
            "complexity_score": min(1.0, (word_count * 0.01 + avg_word_length * 0.1))
        }
    
    return results
@tool(category=ToolCategory.MEDIA, name="generate_image", overwrite=True)
def generate_image(prompt: str, save_image: bool = True) -> Dict[str, Any]:
    """
    使用Stable Diffusion XL 1.0模型生成高质量图像，支持中英文提示词
    
    这个工具可以根据文本描述生成相应的图像，支持各种艺术风格
    和创意表达。生成的图像质量高，适合用于创意设计和概念可视化。
    
    Args:
        prompt: 图像生成提示词，描述要生成的图像内容
        save_image: 是否保存图像到本地，默认为True
        
    Returns:
        包含生成结果、执行状态和图像信息的字典
    """
    if not IMAGE_TOOLS_AVAILABLE:
        return {
            "success": False,
            "error": "图像生成功能不可用。请安装依赖: pip install huggingface_hub Pillow",
            "result": None
        }
    
    try:
        tool_instance = ImageGenerationTool()
        result = tool_instance.execute(prompt=prompt, save_image=save_image)
        
        return {
            "success": result.success,
            "error": result.error_message if not result.success else "",
            "execution_time": result.execution_time,
            "result": result.data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"图像生成失败: {str(e)}",
            "result": None
        }
@tool(category=ToolCategory.MEDIA, name="batch_generate_images", overwrite=True)
def batch_generate_images(prompts: List[str], save_images: bool = True) -> Dict[str, Any]:
    """
    批量生成多张图像，输入多个提示词，返回所有生成结果
    
    这个工具可以一次性处理多个图像生成请求，提高效率。
    适合用于批量创作、概念设计等场景。
    
    Args:
        prompts: 提示词列表，每个提示词对应一张图像
        save_images: 是否保存所有图像到本地，默认为True
        
    Returns:
        包含所有生成结果的批量处理报告
    """
    if not IMAGE_TOOLS_AVAILABLE:
        return {
            "success": False,
            "error": "图像生成功能不可用。请安装依赖: pip install huggingface_hub Pillow",
            "results": []
        }
    
    if not prompts:
        return {
            "success": False,
            "error": "提示词列表不能为空",
            "results": []
        }
    
    try:
        return batch_generate(prompts, save_images)
    except Exception as e:
        return {
            "success": False,
            "error": f"批量图像生成失败: {str(e)}",
            "results": []
        }


# ============================================================================
# 工具注册和管理函数
# ============================================================================

def get_all_default_tools() -> List[str]:
    """
    获取所有默认工具的名称列表
    
    由于使用了 @tool 装饰器，所有工具都会自动注册到全局工具注册表中。
    这个函数返回所有默认工具的名称，方便查询和管理。
    
    Returns:
        所有默认工具名称的列表
    """
    tool_names = [
        "idea_verification",
        "search_knowledge", 
        "analyze_text"
    ]
    
    # 如果图像生成工具可用，添加到列表中
    if IMAGE_TOOLS_AVAILABLE:
        tool_names.extend([
            "generate_image",
            "batch_generate_images"
        ])
    
    return tool_names


def initialize_default_tools():
    """
    初始化所有默认工具
    
    这个函数确保所有默认工具都已经通过 @tool 装饰器注册到系统中。
    由于装饰器在模块导入时就会执行，通常不需要显式调用此函数。
    """
    # 由于使用了 @tool 装饰器的 auto_register=True，
    # 所有工具在模块导入时就已经自动注册了
    from .tool_abstraction import global_tool_registry
    
    registered_tools = get_all_default_tools()
    available_tools = []
    
    for tool_name in registered_tools:
        if global_tool_registry.has_tool(tool_name):
            available_tools.append(tool_name)
    
    return {
        "total_tools": len(registered_tools),
        "available_tools": len(available_tools),
        "tool_names": available_tools
    }
