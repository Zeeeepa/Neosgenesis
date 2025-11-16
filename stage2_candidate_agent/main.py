# -*- coding: utf-8 -*-
"""CandidateSelectionAgent 命令行入口脚本。"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
from getpass import getpass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import sys as sys_module

PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys_module.path:
    sys_module.path.insert(0, PARENT_DIR)

from Document_Checking.template_generation import TemplateGenerationAgent, TemplateGenerationConfig

try:
    from .Candidate_Selection_agent import (
        CandidateSelectionAgent,
        CandidateSelectionAgentConfig,
    )
except ImportError:  # pragma: no cover
    import sys

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    if CURRENT_DIR not in sys.path:
        sys.path.insert(0, CURRENT_DIR)

    from Candidate_Selection_agent import CandidateSelectionAgent, CandidateSelectionAgentConfig  # type: ignore  # pylint: disable=import-error


EXIT_COMMANDS = {"exit", "quit", "q"}
MULTILINE_SENTINEL = "END"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class UserExit(RuntimeError):
    """用户主动退出交互循环。"""


def _save_result_to_template(
    template_agent: TemplateGenerationAgent,
    meta_analysis: str | None,
    objective: str | None,
    candidate_limit: int | None,
    result_text: str | None,
) -> None:
    """将候选策略结果写入最新的模板文档中对应区域。"""
    from datetime import datetime

    docs = sorted(template_agent.finish_form_dir.glob("*.md"), reverse=True)
    if not docs:
        print("⚠ 没有可用的模板文档")
        return

    latest_doc = docs[0]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _format_blockquote(text: str | None) -> str:
        if not text:
            return "> （未提供）"
        lines = text.strip().splitlines()
        if not lines:
            return "> （未提供）"
        return "\n".join(f"> {line}" if line else ">" for line in lines)

    body = (result_text or "（无内容）").strip()
    candidate_limit_text = str(candidate_limit) if candidate_limit is not None else "默认"
    formatted_result = (
        f"#### 自动生成候选策略（{timestamp}）\n\n"
        f"**上游分析摘要**：\n{_format_blockquote(meta_analysis)}\n\n"
        f"**目标**: {objective or '（未提供）'}\n\n"
        f"**候选数量上限**: {candidate_limit_text}\n\n"
        f"{body}\n"
    )

    current_content = latest_doc.read_text(encoding="utf-8")
    stage2_pattern = re.compile(
        r"(<!-- STAGE2A_ANALYSIS_START -->)(?P<content>.*?)(<!-- STAGE2A_ANALYSIS_END -->)",
        re.DOTALL,
    )
    match = stage2_pattern.search(current_content)
    if match:
        replacement = f"{match.group(1)}\n{formatted_result}{match.group(3)}"
        updated_content = (
            current_content[: match.start()]
            + replacement
            + current_content[match.end() :]
        )
    else:
        fallback_entry = (
            f"\n## 阶段二-A 候选策略结果 [{timestamp}]\n\n"
            f"**上游分析摘要**：\n{_format_blockquote(meta_analysis)}\n\n"
            f"**目标**: {objective or '（未提供）'}\n\n"
            f"**候选数量上限**: {candidate_limit_text}\n\n"
            f"**输出内容**:\n{body}\n\n---\n"
        )
        updated_content = current_content + fallback_entry

    latest_doc.write_text(updated_content, encoding="utf-8")
    relative_path = template_agent._to_relative_string(latest_doc)  # pylint: disable=protected-access
    print(f"✓ 结果已保存到: {relative_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="candidate-selection-agent",
        description="交互式运行候选策略筛选代理（DeepSeek 驱动）。",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="DeepSeek API Key，若不提供则尝试从环境变量 DEEPSEEK_API_KEY 读取。",
    )
    parser.add_argument(
        "--model",
        default="deepseek-chat",
        help="DeepSeek 模型名称（默认：deepseek-chat）。",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="启用流式输出（默认关闭）。",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.deepseek.com",
        help="DeepSeek API 基础地址（默认：https://api.deepseek.com）。",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="推理强度设置（默认：medium）。",
    )
    parser.add_argument(
        "--system-prompt",
        dest="system_prompt",
        help="自定义 system prompt，若不提供将使用 selector.md 及策略库生成的默认提示词。",
    )
    parser.add_argument(
        "--candidate-limit",
        dest="candidate_limit",
        type=int,
        help="设置候选策略数量上限（默认：3）。",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅执行一次分析后退出（默认进入持续交互模式）。",
    )
    return parser.parse_args()


def _ensure_api_key(cli_api_key: str | None) -> str:
    api_key = cli_api_key or os.getenv("DEEPSEEK_API_KEY")
    if api_key:
        return api_key

    while not api_key:
        api_key = getpass("请输入 DeepSeek API Key（回车确认）: ").strip()
    return api_key


def _print_banner() -> None:
    print("=" * 78)
    print("Strategy Candidate Selection Agent (DeepSeek)")
    print("输入 'exit' / 'quit' / 'q' 可在任意主提示下退出。")
    print(f"多行输入请以单独一行 '{MULTILINE_SENTINEL}' 结束。")
    print("=" * 78)


def _prompt_line(prompt: str, *, required: bool = False) -> str | None:
    while True:
        try:
            value = input(prompt).strip()
        except (EOFError, KeyboardInterrupt) as exc:  # pragma: no cover
            raise UserExit from exc

        if value.lower() in EXIT_COMMANDS:
            raise UserExit

        if value:
            return value

        if not required:
            return None

        print("该字段不能为空，请重新输入。")


def _prompt_multiline(prompt: str, *, required: bool = False) -> str | None:
    while True:
        print(prompt)
        print(f"(输入完成后请单独输入 '{MULTILINE_SENTINEL}' 结束)")
        lines: list[str] = []

        while True:
            try:
                line = input("> ")
            except (EOFError, KeyboardInterrupt) as exc:  # pragma: no cover
                raise UserExit from exc

            trimmed = line.strip()
            if not lines and trimmed.lower() in EXIT_COMMANDS:
                raise UserExit

            if trimmed == MULTILINE_SENTINEL:
                break
            lines.append(line)

        text = "\n".join(lines).strip()
        if text:
            return text

        if not required:
            return None

        print("该字段不能为空，请重新输入。")


async def _interactive_loop(
    agent: CandidateSelectionAgent,
    template_agent: TemplateGenerationAgent,
    *,
    single_run: bool,
) -> None:
    _print_banner()

    while True:
        try:
            meta_analysis = _prompt_multiline("Stage 1 META_ANALYSIS (必填) >", required=True)
            objective = _prompt_line("目标 Objective (可选)> ")
            candidate_limit_raw = _prompt_line("候选数量上限 (可选，示例 3)> ")
        except UserExit:
            print("已退出。")
            break

        candidate_limit = None
        if candidate_limit_raw:
            try:
                candidate_limit = max(2, int(candidate_limit_raw))
            except ValueError:
                print("候选数量上限需要是整数。\n")
                if single_run:
                    break
                continue

        print("\n生成候选策略中，请稍候...\n")
        try:
            result_text = await agent.analyze_text(
                meta_analysis=meta_analysis or "",
                objective=objective,
                candidate_limit=candidate_limit,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"发生错误: {exc}\n")
            if single_run:
                break
            continue

        separator = "-" * 78
        print(separator)
        print(result_text or "<无内容>")
        print(separator + "\n")
        try:
            _save_result_to_template(
                template_agent=template_agent,
                meta_analysis=meta_analysis,
                objective=objective,
                candidate_limit=candidate_limit,
                result_text=result_text,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(f"保存结果失败: {exc}\n")

        if single_run:
            break


async def _main_async(args: argparse.Namespace) -> None:
    config_kwargs: dict[str, Any] = {
        "api_key": _ensure_api_key(args.api_key),
        "model_name": args.model,
        "stream": args.stream,
        "base_url": args.base_url,
        "reasoning_effort": args.reasoning_effort,
        "system_prompt": args.system_prompt,
    }

    if args.candidate_limit is not None:
        config_kwargs["default_candidate_limit"] = args.candidate_limit

    config = CandidateSelectionAgentConfig(**config_kwargs)
    agent = CandidateSelectionAgent(config=config)

    template_config = TemplateGenerationConfig(
        threshold=8,
        finish_form_dir=PROJECT_ROOT / "finish_form",
        template_path=PROJECT_ROOT / "form_templates" / "standard template.md",
    )
    template_agent = TemplateGenerationAgent(config=template_config)

    if not any(template_agent.finish_form_dir.glob("*.md")):
        print("正在创建初始模板...")
        template_result = template_agent.run()
        if template_result.get("created"):
            print(f"✓ 已创建模板: {template_result['created']}")
        print(f"✓ 现有模板数: {len(template_result.get('documents', []))}\n")

    await _interactive_loop(agent, template_agent, single_run=args.once)


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_main_async(args))
    except UserExit:
        print("已退出。")
    except KeyboardInterrupt:
        print("\n已退出。")


if __name__ == "__main__":
    main()


