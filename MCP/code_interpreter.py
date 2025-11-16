# -*- coding: utf-8 -*-
"""本地 Code Interpreter MCP Provider 封装（StdIO 版）。

该模块提供一组辅助函数，方便项目以标准输入输出方式连接并使用
`code-interpreter` 类型的 MCP 服务。主要特性包括：

* ``CodeInterpreterMCPConfig``: 配置数据类，支持从环境变量读取命令、
  运行参数、工作目录等信息；
* ``create_code_interpreter_client``: 生成未连接的
  :class:`~MCP._stdio_stateful_client.StdIOStatefulClient` 实例；
* ``code_interpreter_client_session``: 异步上下文管理器，负责建立和关闭 MCP 连接；
* ``discover_code_interpreter_tool_catalog`` / ``list_code_interpreter_tools``:
  辅助工具，可列出本地 MCP Server 暴露的工具列表；
* ``code_interpreter_tool``: 异步上下文管理器，直接返回指定工具的
  :class:`~MCP._mcp_function.MCPToolFunction`，可直接在 ``async with`` 块中调用。
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterable, Literal

import mcp.types

from ._mcp_function import MCPToolFunction
from ._stdio_stateful_client import StdIOStatefulClient

DEFAULT_CLIENT_NAME = "code-interpreter"
DEFAULT_COMMAND = sys.executable
DEFAULT_MODULE_ARGS = ["-m", "mcp_server_code_interpreter"]
_ENCODING_ERROR_HANDLERS = {"strict", "ignore", "replace"}


def _parse_args(raw: str | None) -> list[str]:
    """将 ``CODE_INTERPRETER_MCP_ARGS`` 解析为参数列表。

    支持两种形式：

    1. JSON 数组字符串，例如 ``'["--foo", "bar"]'``；
    2. shell 风格的命令行字符串，例如 ``"--foo bar"``。
    """

    if raw is None:
        return []

    raw = raw.strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return shlex.split(raw, posix=os.name != "nt")

    if not isinstance(parsed, list):
        raise ValueError(
            "CODE_INTERPRETER_MCP_ARGS 必须是 JSON 数组或可被 shell 风格解析的字符串。",
        )

    return [str(item) for item in parsed]


def _parse_env(raw: str | None) -> dict[str, str]:
    """解析 ``CODE_INTERPRETER_MCP_ENV`` 环境变量。"""

    if raw is None:
        return {}

    raw = raw.strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - 防御性校验
        raise ValueError(
            "CODE_INTERPRETER_MCP_ENV 必须是一个 JSON 对象，形如 {\"KEY\": \"VALUE\"}。",
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("CODE_INTERPRETER_MCP_ENV 必须解析为 JSON 对象。")

    return {str(key): str(value) for key, value in parsed.items()}


def _coerce_error_handler(value: str | None) -> Literal["strict", "ignore", "replace"]:
    normalized = (value or "strict").strip().lower()
    if normalized not in _ENCODING_ERROR_HANDLERS:
        raise ValueError(
            "CODE_INTERPRETER_MCP_ENCODING_ERRORS 仅支持 'strict'、'ignore'、'replace'。",
        )
    return normalized  # type: ignore[return-value]


@dataclass(slots=True)
class CodeInterpreterMCPConfig:
    """Code Interpreter MCP Provider 配置容器。"""

    name: str = DEFAULT_CLIENT_NAME
    command: str = DEFAULT_COMMAND
    args: list[str] = field(default_factory=lambda: list(DEFAULT_MODULE_ARGS))
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    encoding: str = "utf-8"
    encoding_error_handler: Literal["strict", "ignore", "replace"] = "strict"

    @classmethod
    def from_env(cls) -> "CodeInterpreterMCPConfig":
        """从环境变量构建配置对象。"""

        command = os.getenv("CODE_INTERPRETER_MCP_COMMAND") or DEFAULT_COMMAND

        args_env = os.getenv("CODE_INTERPRETER_MCP_ARGS")
        args = (
            list(DEFAULT_MODULE_ARGS)
            if args_env is None
            else _parse_args(args_env)
        )

        env = _parse_env(os.getenv("CODE_INTERPRETER_MCP_ENV"))
        cwd = os.getenv("CODE_INTERPRETER_MCP_CWD")
        encoding = os.getenv("CODE_INTERPRETER_MCP_ENCODING") or "utf-8"
        encoding_error_handler = _coerce_error_handler(
            os.getenv("CODE_INTERPRETER_MCP_ENCODING_ERRORS"),
        )
        name = os.getenv("CODE_INTERPRETER_MCP_NAME") or DEFAULT_CLIENT_NAME

        return cls(
            name=name,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            encoding=encoding,
            encoding_error_handler=encoding_error_handler,
        )


def create_code_interpreter_client(
    config: CodeInterpreterMCPConfig | None = None,
) -> StdIOStatefulClient:
    """返回未连接的 ``StdIOStatefulClient`` 实例。"""

    cfg = config or CodeInterpreterMCPConfig.from_env()

    return StdIOStatefulClient(
        name=cfg.name,
        command=cfg.command,
        args=cfg.args,
        env=cfg.env or None,
        cwd=cfg.cwd,
        encoding=cfg.encoding,
        encoding_error_handler=cfg.encoding_error_handler,
    )


async def create_connected_code_interpreter_client(
    config: CodeInterpreterMCPConfig | None = None,
) -> StdIOStatefulClient:
    """创建并连接 MCP 客户端，调用方需负责关闭连接。"""

    client = create_code_interpreter_client(config)
    try:
        await client.connect()
    except Exception:
        # 连接失败时及时清理资源
        if client.stack is not None:
            await client.stack.aclose()
        raise

    return client


@asynccontextmanager
async def code_interpreter_client_session(
    config: CodeInterpreterMCPConfig | None = None,
) -> AsyncIterator[StdIOStatefulClient]:
    """异步上下文管理器：自动建立并关闭 MCP 连接。"""

    client = create_code_interpreter_client(config)
    await client.connect()
    try:
        yield client
    finally:
        await client.close()


async def list_code_interpreter_tools(
    *,
    config: CodeInterpreterMCPConfig | None = None,
) -> Iterable[mcp.types.Tool]:
    """返回 MCP Server 暴露的工具清单。"""

    async with code_interpreter_client_session(config) as client:
        tools = await client.list_tools()
    return tools


async def discover_code_interpreter_tool_catalog(
    *,
    config: CodeInterpreterMCPConfig | None = None,
) -> list[str]:
    """以 ``<name>: <description>`` 形式返回人类可读的工具目录。"""

    tools = await list_code_interpreter_tools(config=config)

    catalog: list[str] = []
    for tool in tools:
        description = (tool.description or "").strip()
        catalog.append(f"{tool.name}: {description}" if description else tool.name)
    return catalog


@asynccontextmanager
async def code_interpreter_tool(
    tool_name: str,
    *,
    config: CodeInterpreterMCPConfig | None = None,
    wrap_tool_result: bool = True,
) -> AsyncIterator[MCPToolFunction]:
    """获取指定工具的 ``MCPToolFunction``，并在上下文退出时自动释放连接。"""

    async with code_interpreter_client_session(config) as client:
        tool = await client.get_callable_function(
            tool_name,
            wrap_tool_result=wrap_tool_result,
        )
        yield tool


async def get_code_interpreter_tool(
    tool_name: str,
    *,
    client: StdIOStatefulClient,
    wrap_tool_result: bool = True,
) -> MCPToolFunction:
    """在既有连接上获取指定工具函数。"""

    if not client.is_connected:
        raise RuntimeError(
            "StdIOStatefulClient 尚未连接，请先调用 connect()。",
        )

    return await client.get_callable_function(
        tool_name,
        wrap_tool_result=wrap_tool_result,
    )


__all__ = [
    "CodeInterpreterMCPConfig",
    "create_code_interpreter_client",
    "create_connected_code_interpreter_client",
    "code_interpreter_client_session",
    "discover_code_interpreter_tool_catalog",
    "list_code_interpreter_tools",
    "code_interpreter_tool",
    "get_code_interpreter_tool",
]


