#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图像生成工具 - Image Generation Tools

集成Stable Diffusion XL模型的图像生成功能到Neogenesis框架中，
使Agent能够通过文本描述生成高质量图像。

核心功能：
- 使用Hugging Face无服务器推理
- 通过Replicate提供商调用Stable Diffusion XL
- 自动图像保存和管理
- 丰富的错误处理和日志记录
"""

import os
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

try:
    from huggingface_hub import InferenceClient
    from PIL import Image
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

from .tool_abstraction import (
    BaseTool, 
    tool, 
    ToolResult, 
    ToolCategory, 
    ToolCapability
)

logger = logging.getLogger(__name__)


class ImageGenerationTool(BaseTool):
    """
    图像生成工具类
    
    使用Stable Diffusion XL 1.0模型通过文本描述生成图像。
    支持多种配置选项和自动结果管理。
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化图像生成工具
        
        Args:
            api_key: Hugging Face API密钥，如果未提供则从环境变量获取
        """
        super().__init__(
            name="stable_diffusion_xl_generator",
            description="使用Stable Diffusion XL 1.0模型生成高质量图像。支持中英文提示词，自动保存结果。",
            category=ToolCategory.MEDIA
        )
        
        # 设置API密钥
        if api_key:
            os.environ["HF_TOKEN"] = api_key
        
        self.api_key = api_key or os.getenv("HF_TOKEN")
        self.client = None
        self.output_dir = Path("generated_images")
        self.model_name = "stabilityai/stable-diffusion-xl-base-1.0"
        
        # 创建输出目录
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"🎨 图像生成工具初始化完成: {self.name}")
    
    @property 
    def capabilities(self) -> ToolCapability:
        """返回工具能力描述"""
        return ToolCapability(
            concurrent_execution=False,  # 图像生成比较耗时，不建议并发
            requires_auth=True,         # 需要HF API密钥
            rate_limited=True           # 受API调用限制
        )
    
    def _initialize_client(self):
        """初始化HuggingFace客户端"""
        if not HF_AVAILABLE:
            raise ImportError("缺少必要依赖。请运行: pip install huggingface_hub Pillow")
        
        if not self.api_key:
            raise ValueError("未找到Hugging Face API密钥。请设置HF_TOKEN环境变量或在初始化时提供api_key参数。")
        
        try:
            self.client = InferenceClient(
                provider="replicate",
                api_key=self.api_key,
            )
            logger.debug("✅ HuggingFace客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ HuggingFace客户端初始化失败: {e}")
            raise
    
    def _generate_filename(self, prompt: str) -> str:
        """
        生成唯一的文件名
        
        Args:
            prompt: 图像生成提示词
            
        Returns:
            str: 生成的文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 清理提示词作为文件名的一部分（取前20个字符）
        clean_prompt = "".join(c for c in prompt[:20] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_prompt = clean_prompt.replace(' ', '_')
        
        if clean_prompt:
            filename = f"{clean_prompt}_{timestamp}.png"
        else:
            filename = f"generated_image_{timestamp}.png"
            
        return filename
    
    def _save_image(self, image: Image.Image, filename: str) -> Path:
        """
        保存图像到本地
        
        Args:
            image: PIL图像对象
            filename: 文件名
            
        Returns:
            Path: 保存的文件路径
        """
        filepath = self.output_dir / filename
        try:
            image.save(filepath, "PNG", quality=95)
            logger.info(f"✅ 图像已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"❌ 保存图像失败: {e}")
            raise
    
    def execute(self, prompt: str, save_image: bool = True, **kwargs) -> ToolResult:
        """
        执行图像生成
        
        Args:
            prompt: 图像生成提示词（中英文均可）
            save_image: 是否保存图像到本地，默认True
            **kwargs: 其他参数（预留扩展）
            
        Returns:
            ToolResult: 执行结果，包含图像信息和文件路径
        """
        if not prompt or not prompt.strip():
            return ToolResult(
                success=False,
                data=None,
                error_message="提示词不能为空",
                execution_time=0.0
            )
        
        start_time = datetime.now()
        
        try:
            # 初始化客户端（如果还未初始化）
            if self.client is None:
                self._initialize_client()
            
            logger.info(f"🚀 开始生成图像: {prompt}")
            
            # 生成图像
            image = self.client.text_to_image(
                prompt=prompt.strip(),
                model=self.model_name,
            )
            
            # 准备结果数据
            result_data = {
                "prompt": prompt.strip(),
                "model": self.model_name,
                "image_size": image.size,
                "generated_at": datetime.now().isoformat(),
                "image_format": "PNG"
            }
            
            # 保存图像（如果需要）
            if save_image:
                filename = self._generate_filename(prompt)
                filepath = self._save_image(image, filename)
                result_data["saved_path"] = str(filepath.absolute())
                result_data["filename"] = filename
            else:
                result_data["saved_path"] = None
            
            # 将PIL图像对象也包含在结果中，以便后续处理
            result_data["image_object"] = image
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ 图像生成成功: {image.size}, 耗时: {execution_time:.2f}秒")
            
            return ToolResult(
                success=True,
                data=result_data,
                error_message="",
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 图像生成失败: {e}")
            
            return ToolResult(
                success=False,
                data=None,
                error_message=f"图像生成失败: {str(e)}",
                execution_time=execution_time
            )


# ============================================================================
# 使用装饰器方式定义的便捷图像生成工具函数
# ============================================================================

@tool(
    category=ToolCategory.MEDIA,
    name="generate_image",
    description="使用Stable Diffusion XL生成图像。输入文本描述，返回生成的图像文件路径。支持中英文提示词。"
)
def generate_image_simple(
    prompt: str, 
    save_to_disk: bool = True
) -> Dict[str, Any]:
    """
    简化的图像生成函数（装饰器方式）
    
    Args:
        prompt: 图像生成提示词
        save_to_disk: 是否保存到磁盘
        
    Returns:
        Dict[str, Any]: 包含生成结果的字典
    """
    if not HF_AVAILABLE:
        return {
            "success": False,
            "error": "缺少必要依赖。请运行: pip install huggingface_hub Pillow",
            "result": None
        }
    
    # 创建工具实例
    tool_instance = ImageGenerationTool()
    
    # 执行生成
    result = tool_instance.execute(prompt=prompt, save_image=save_to_disk)
    
    # 转换为简单字典格式
    return {
        "success": result.success,
        "error": result.error,
        "execution_time": result.execution_time,
        "result": result.result
    }


@tool(
    category=ToolCategory.MEDIA,
    name="batch_generate_images", 
    description="批量生成多张图像。输入多个提示词，返回所有生成结果。"
)
def batch_generate_images(
    prompts: list[str],
    save_to_disk: bool = True
) -> Dict[str, Any]:
    """
    批量图像生成函数
    
    Args:
        prompts: 提示词列表
        save_to_disk: 是否保存到磁盘
        
    Returns:
        Dict[str, Any]: 批量生成结果
    """
    if not HF_AVAILABLE:
        return {
            "success": False,
            "error": "缺少必要依赖。请运行: pip install huggingface_hub Pillow",
            "results": []
        }
    
    if not prompts:
        return {
            "success": False,
            "error": "提示词列表不能为空",
            "results": []
        }
    
    tool_instance = ImageGenerationTool()
    results = []
    total_start = datetime.now()
    
    logger.info(f"🚀 开始批量生成 {len(prompts)} 张图像")
    
    for i, prompt in enumerate(prompts, 1):
        logger.info(f"📝 处理第 {i}/{len(prompts)} 个提示词: {prompt}")
        result = tool_instance.execute(prompt=prompt, save_image=save_to_disk)
        results.append({
            "prompt": prompt,
            "success": result.success,
            "error": result.error,
            "result": result.result,
            "execution_time": result.execution_time
        })
    
    total_time = (datetime.now() - total_start).total_seconds()
    successful_count = sum(1 for r in results if r["success"])
    
    logger.info(f"✅ 批量生成完成: {successful_count}/{len(prompts)} 成功, 总耗时: {total_time:.2f}秒")
    
    return {
        "success": True,
        "total_prompts": len(prompts),
        "successful_count": successful_count,
        "failed_count": len(prompts) - successful_count,
        "total_execution_time": total_time,
        "results": results
    }


# ============================================================================
# 工具注册和导出
# ============================================================================

def get_image_generation_tools() -> list:
    """获取所有图像生成工具"""
    return [
        ImageGenerationTool(),
        # 装饰器定义的工具会自动注册，无需在这里手动添加
    ]


# 预设一些常用的图像生成提示词模板
IMAGE_PROMPT_TEMPLATES = {
    "portrait": "A professional portrait of {subject}, high quality, detailed, studio lighting",
    "landscape": "A beautiful landscape of {location}, {time_of_day}, high resolution, detailed",
    "artwork": "Digital artwork of {subject}, {art_style}, high quality, detailed",
    "sci_fi": "A futuristic {subject}, sci-fi style, detailed, high quality rendering",
    "fantasy": "A magical {subject}, fantasy art style, detailed, vibrant colors",
}


def get_prompt_template(template_name: str, **kwargs) -> str:
    """
    获取预设的提示词模板
    
    Args:
        template_name: 模板名称
        **kwargs: 模板参数
        
    Returns:
        str: 格式化后的提示词
    """
    if template_name not in IMAGE_PROMPT_TEMPLATES:
        available_templates = ", ".join(IMAGE_PROMPT_TEMPLATES.keys())
        raise ValueError(f"未知的模板名称: {template_name}。可用模板: {available_templates}")
    
    try:
        return IMAGE_PROMPT_TEMPLATES[template_name].format(**kwargs)
    except KeyError as e:
        raise ValueError(f"模板 '{template_name}' 缺少必要参数: {e}")


if __name__ == "__main__":
    # 测试代码
    print("🎨 图像生成工具测试")
    
    # 测试工具是否可以正常初始化
    try:
        tool = ImageGenerationTool()
        print(f"✅ 工具初始化成功: {tool.name}")
        print(f"📁 输出目录: {tool.output_dir}")
        
        # 测试模板功能
        template = get_prompt_template("portrait", subject="a friendly robot")
        print(f"📝 生成的提示词模板: {template}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
