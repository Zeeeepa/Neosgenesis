"""
Tools Package - 工具包

提供统一的工具抽象接口和工具管理功能。
所有工具都遵循相同的接口规范，便于系统统一调用和管理。
"""

# 从 tool_abstraction 导入实际存在的类和函数
from .tool_abstraction import (
    BaseTool,
    tool,
    ToolResult,
    ToolRegistry,
    ToolCategory,
    ToolStatus,
    ToolCapability,
    FunctionTool,
    AsyncBaseTool,
    BatchProcessingTool,
    global_tool_registry,
    register_tool,
    unregister_tool,
    get_tool,
    execute_tool,
    list_available_tools,
    search_tools,
    get_tools_by_category,
    disable_tool,
    enable_tool,
    get_tool_info,
    get_registry_stats,
    health_check,
    export_registry_config,
    is_tool,
    get_tool_instance
)

# 从 default_tools 导入工具管理函数
from .default_tools import get_all_default_tools, initialize_default_tools

# 从 image_generation_tools 导入图像生成工具（可选导入）
try:
    from .image_generation_tools import (
        ImageGenerationTool, 
        generate_image_simple, 
        batch_generate_images,
        get_image_generation_tools,
        get_prompt_template,
        IMAGE_PROMPT_TEMPLATES
    )
    IMAGE_TOOLS_AVAILABLE = True
except ImportError:
    IMAGE_TOOLS_AVAILABLE = False

__all__ = [
    # 核心工具抽象
    "BaseTool",
    "tool", 
    "ToolResult",
    "ToolCategory",
    "ToolStatus", 
    "ToolCapability",
    "FunctionTool",
    "AsyncBaseTool",
    "BatchProcessingTool",
    
    # 工具注册表和管理
    "ToolRegistry",
    "global_tool_registry",
    "register_tool",
    "unregister_tool", 
    "get_tool",
    "execute_tool",
    "list_available_tools",
    "search_tools",
    "get_tools_by_category",
    "disable_tool",
    "enable_tool",
    "get_tool_info",
    "get_registry_stats",
    "health_check",
    "export_registry_config",
    
    # 工具装饰器相关
    "is_tool",
    "get_tool_instance",
    
    # 默认工具管理函数
    "get_all_default_tools",
    "initialize_default_tools"
]

# 如果图像生成工具可用，添加到__all__中
if IMAGE_TOOLS_AVAILABLE:
    __all__.extend([
        "ImageGenerationTool",
        "generate_image_simple", 
        "batch_generate_images",
        "get_image_generation_tools",
        "get_prompt_template",
        "IMAGE_PROMPT_TEMPLATES"
    ])
