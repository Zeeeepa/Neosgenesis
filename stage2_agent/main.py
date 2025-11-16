"""Stage 2 pipeline orchestrator that chains candidate selection, strategy refinement,
and capability upgrade agents end-to-end."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from Document_Checking.template_generation import (  # noqa: E402
    TemplateGenerationAgent,
    TemplateGenerationConfig,
)
from stage2_candidate_agent.Candidate_Selection_agent import (  # noqa: E402
    CandidateSelectionAgent,
    CandidateSelectionAgentConfig,
)
from stage2_capability_upgrade_agent.stage2_capability_upgrade_agent import (  # noqa: E402
    Stage2CapabilityUpgradeAgent,
    Stage2CapabilityUpgradeConfig,
)
from .Strategy_Selection_agent import (  # noqa: E402  # type: ignore[attr-defined]
    StrategySelectionAgent,
    StrategySelectionAgentConfig,
)

FINISH_FORM_DIR = PROJECT_ROOT / "finish_form"
TEMPLATE_PATH = PROJECT_ROOT / "form_templates" / "standard template.md"

STAGE1_MARKERS = ("<!-- STAGE1_ANALYSIS_START -->", "<!-- STAGE1_ANALYSIS_END -->")
STAGE2A_MARKERS = ("<!-- STAGE2A_ANALYSIS_START -->", "<!-- STAGE2A_ANALYSIS_END -->")
STAGE2B_MARKERS = ("<!-- STAGE2B_ANALYSIS_START -->", "<!-- STAGE2B_ANALYSIS_END -->")
STAGE2C_MARKERS = ("<!-- STAGE2C_ANALYSIS_START -->", "<!-- STAGE2C_ANALYSIS_END -->")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stage2-agent-pipeline",
        description="Run the full Stage 2 pipeline: candidate selection → strategy refinement → capability upgrade.",
    )
    parser.add_argument(
        "--finish-form",
        type=str,
        help="Path to the finish form markdown. Defaults to the latest file in finish_form/.",
    )
    parser.add_argument(
        "--finish-dir",
        type=str,
        help="Override finish_form directory when auto-discovering documents.",
    )
    parser.add_argument(
        "--objective",
        type=str,
        help="Override objective text. Falls back to the value parsed from the finish form.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Override candidate limit passed to the candidate selection agent (default: agent config value).",
    )
    parser.add_argument(
        "--suspected",
        type=str,
        help="Suspected new capabilities for the upgrade agent, separated by '|'.",
    )
    parser.add_argument(
        "--pending",
        type=str,
        help="Pending strategy updates (pipe-delimited) for the upgrade agent.",
    )
    parser.add_argument(
        "--maintainer-notes",
        type=str,
        help="Maintainer notes forwarded to the upgrade agent.",
    )
    parser.add_argument(
        "--additional-context",
        type=str,
        help="Additional context forwarded to the upgrade agent.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="DeepSeek API key. Defaults to environment variable DEEPSEEK_API_KEY.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-chat",
        help="DeepSeek model name (default: deepseek-chat).",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses for all agents.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://api.deepseek.com",
        help="DeepSeek API base URL.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default="medium",
        help="Reasoning effort passed to all agents (default: medium).",
    )
    parser.add_argument(
        "--max-library-chars",
        type=int,
        help="Maximum characters to load from strategy library snapshot for the upgrade agent.",
    )
    parser.add_argument(
        "--no-auto-apply",
        action="store_true",
        help="Disable auto-applying capability patches to the strategy library.",
    )
    parser.add_argument(
        "--library-file",
        type=str,
        help="Custom strategy library file path for the capability upgrade agent.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Disable backup creation when writing capability patches or updating the finish form.",
    )
    parser.add_argument(
        "--skip-capability-upgrade",
        action="store_true",
        help="Skip invoking the capability upgrade agent (still updates Stage 2A/2B sections).",
    )
    return parser.parse_args()


def _load_finish_form(path: Path | None, finish_dir: Path) -> Path:
    if path:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"指定的 finish_form 文件不存在：{resolved}")
        return resolved

    candidates = sorted(
        finish_dir.glob("*.md"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]

    template_agent = TemplateGenerationAgent(
        TemplateGenerationConfig(
            threshold=0,
            finish_form_dir=finish_dir,
            template_path=TEMPLATE_PATH,
        )
    )
    summary = template_agent.run()
    created = summary.get("created")
    if not created:
        raise RuntimeError("未能在 finish_form 目录中创建新的模板文档。")
    created_path = PROJECT_ROOT / created
    return created_path.expanduser().resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str, *, backup: bool) -> None:
    if backup and path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_suffix(path.suffix + f".bak-{timestamp}")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(content, encoding="utf-8")


def _extract_between_markers(content: str, markers: tuple[str, str]) -> str:
    start_marker, end_marker = markers
    try:
        start_idx = content.index(start_marker) + len(start_marker)
        end_idx = content.index(end_marker, start_idx)
    except ValueError as exc:
        raise ValueError(f"缺少标记 {markers[0]} 或 {markers[1]}") from exc

    segment = content[start_idx:end_idx]
    cleaned = segment.strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned[1:-1].strip()
    return cleaned.strip()


def _replace_between_markers(content: str, markers: tuple[str, str], body: str) -> str:
    start_marker, end_marker = markers
    try:
        start_idx = content.index(start_marker) + len(start_marker)
        end_idx = content.index(end_marker, start_idx)
    except ValueError as exc:
        raise ValueError(f"缺少标记 {start_marker} 或 {end_marker}") from exc

    body_text = body.strip() or "`待填写`"
    replacement = f"\n{body_text}\n"
    return content[:start_idx] + replacement + content[end_idx:]


def _ensure_stage2c_markers(content: str) -> str:
    """Inject Stage 2C analysis markers when missing."""

    if STAGE2C_MARKERS[0] in content and STAGE2C_MARKERS[1] in content:
        return content

    header_pattern = re.compile(
        r"(## 阶段二-C：能力升级评估（Stage2_Capability_Upgrade_agent）.*?\n)(.*?)"
        r"(### 1\. 能力缺口诊断)",
        re.DOTALL,
    )
    match = header_pattern.search(content)
    if not match:
        return content

    insertion_block = (
        f"{match.group(1)}{match.group(2)}"
        "### 阶段原文记录（阶段二-C）\n\n"
        f"{STAGE2C_MARKERS[0]}\n`待填写`\n{STAGE2C_MARKERS[1]}\n\n"
        f"{match.group(3)}"
    )
    updated = content[: match.start()] + insertion_block + content[match.end() :]
    return updated


def _parse_objective(content: str) -> str | None:
    pattern = re.compile(r"- \*\*目标概述\*\*：(?P<value>.*)")
    match = pattern.search(content)
    if not match:
        return None
    value = match.group("value").strip()
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value or None


def _split_pipe(text: str | None) -> list[str] | None:
    if not text:
        return None
    parts = [part.strip() for part in text.split("|")]
    clean = [part for part in parts if part]
    return clean or None


def _validate_stage1(stage1_text: str) -> str:
    cleaned = stage1_text.strip()
    if not cleaned or cleaned == "待填写":
        raise ValueError("阶段一内容为空，请先完成 Stage 1 再运行本脚本。")
    return cleaned


def _build_capability_input(stage1_text: str, stage2b_text: str) -> str:
    return (
        "### Stage 1（Metacognitive Analysis）\n"
        f"{stage1_text.strip()}\n\n"
        "### Stage 2-B（Strategy Selection）\n"
        f"{stage2b_text.strip()}"
    ).strip()


async def _run_pipeline(args: argparse.Namespace) -> None:
    finish_dir = Path(args.finish_dir).expanduser().resolve() if args.finish_dir else FINISH_FORM_DIR
    finish_dir.mkdir(parents=True, exist_ok=True)

    finish_form_path = _load_finish_form(Path(args.finish_form).expanduser() if args.finish_form else None, finish_dir)
    finish_content = _read_text(finish_form_path)
    finish_content = _ensure_stage2c_markers(finish_content)
    if STAGE2C_MARKERS[0] not in finish_content or STAGE2C_MARKERS[1] not in finish_content:
        raise ValueError("无法在 finish_form 文档中找到或插入阶段二-C 的标记，请检查模板。")

    stage1_text = _validate_stage1(_extract_between_markers(finish_content, STAGE1_MARKERS))
    objective = args.objective or _parse_objective(finish_content)

    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未提供 DeepSeek API Key，请通过 --api-key 或环境变量 DEEPSEEK_API_KEY 提供。")

    print(f"使用 finish_form: {finish_form_path}")
    if objective:
        print(f"检测到任务目标：{objective}")
    else:
        print("未在文档中找到任务目标，如需可通过 --objective 指定。")

    candidate_config = CandidateSelectionAgentConfig(
        api_key=api_key,
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
    )
    candidate_agent = CandidateSelectionAgent(config=candidate_config)
    candidate_limit = args.candidate_limit

    print("\n[阶段二-A] 生成候选策略中...")
    stage2a_output = await candidate_agent.analyze_text(
        meta_analysis=stage1_text,
        objective=objective,
        candidate_limit=candidate_limit,
    )
    print("[阶段二-A] 完成。")

    finish_content = _replace_between_markers(finish_content, STAGE2A_MARKERS, stage2a_output)

    strategy_config = StrategySelectionAgentConfig(
        api_key=api_key,
        model_name=args.model,
        stream=args.stream,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
    )
    strategy_agent = StrategySelectionAgent(config=strategy_config)

    print("\n[阶段二-B] 进行策略遴选中...")
    stage2b_text = await strategy_agent.analyze_text(
        meta_analysis=stage1_text,
        candidate_sheet=stage2a_output,
        objective=objective,
        finish_form_path=str(finish_form_path),
    )
    print("[阶段二-B] 完成。")

    finish_content = _replace_between_markers(finish_content, STAGE2B_MARKERS, stage2b_text)

    capability_result_text = ""
    applied_patch_path: Path | None = None
    patch_markdown: str | None = None

    if not args.skip_capability_upgrade:
        upgrade_config = Stage2CapabilityUpgradeConfig(
            api_key=api_key,
            model_name=args.model,
            stream=args.stream,
            base_url=args.base_url,
            reasoning_effort=args.reasoning_effort,
            max_library_chars=args.max_library_chars,
            auto_apply_patch=not args.no_auto_apply,
            backup_before_write=not args.no_backup,
            library_file=args.library_file,
        )
        upgrade_agent = Stage2CapabilityUpgradeAgent(config=upgrade_config)

        print("\n[阶段二-C] 评估能力升级需求...")
        capability_input = _build_capability_input(stage1_text, stage2b_text)
        capability_result_text = await upgrade_agent.evaluate_text(
            metacognitive_report=capability_input,
            suspected_new_capabilities=_split_pipe(args.suspected),
            pending_updates=_split_pipe(args.pending),
            maintainer_notes=args.maintainer_notes,
            additional_context=args.additional_context,
        )
        applied_patch_path = upgrade_agent.last_applied_path
        patch_markdown = upgrade_agent.last_patch_markdown
        print("[阶段二-C] 完成。")

        finish_content = _replace_between_markers(finish_content, STAGE2C_MARKERS, capability_result_text)

    _write_text(finish_form_path, finish_content, backup=not args.no_backup)

    print("\n===== 阶段二流水线完成 =====")
    print(f"- Stage2A 内容已写入：{finish_form_path}")
    print(f"- Stage2B 内容已写入：{finish_form_path}")
    if not args.skip_capability_upgrade:
        if capability_result_text.strip():
            print("- Stage2C 评估结果已写入 finish_form。")
        else:
            print("- Stage2C 未输出补丁（空结果）。")
        if applied_patch_path:
            print(f"- 策略库已更新：{applied_patch_path}")
        elif patch_markdown:
            print("- 生成了策略补丁，但未自动写入。")
        else:
            print("- 未检测到策略补丁输出。")
    else:
        print("- 已跳过能力升级评估。")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    args = _parse_args()
    try:
        asyncio.run(_run_pipeline(args))
    except KeyboardInterrupt:
        print("\n已中断。")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n❌ 出现错误：{exc}")


if __name__ == "__main__":
    main()


