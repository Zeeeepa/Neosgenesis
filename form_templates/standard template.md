*/

## 使用说明 / Usage Notes

- Each stage agent must update its own section immediately after completing the reasoning for that phase.
- Keep all fields precise, traceable, and cross-verifiable; reference external notes or appendices whenever additional context is required.
- Document every tool invocation’s key inputs, outputs, and mounting paths so that the form becomes the single source of truth for the task.
- Execution or coordinating agents must verify the index and ensure every prior phase is marked “completed and confirmed” before proceeding.
- If any field is currently unknown, write `TBD` and explain why the information is missing plus the expected time of completion.

---

## 索引 / Index

| No. | Phase / Node | Responsible Agent | Context | Status | Jump Link |
| --- | ------------ | ----------------- | ------- | ------ | --------- |
| 1 | 全局任务元数据 / Global Task Metadata | Central Agent / System | - | | [全局任务元数据](#全局任务元数据) |
| 2 | 阶段一 / Phase 1 | `Metacognitive_Analysis_agent` | See section around lines 30-43 and `ability_library/core_capabilities.md` | | [阶段一](#阶段一元能力分析metacognitive_analysis_agent) |
| 3 | 阶段二-A / Phase 2-A | `Candidate_Selection_agent` | `STAGE1_ANALYSIS` anchor, `strategy_library/strategy.md`, line 35 | | [阶段二-A](#阶段二-a候选策略产出candidate_selection_agent) |
| 4 | 阶段二-B / Phase 2-B | `Strategy_Selection_agent` | `STAGE1_ANALYSIS` + `STAGE2A_ANALYSIS`, `strategy_library/strategy.md` | | [阶段二-B](#阶段二-b策略遴选strategy_selection_agent) |
| 5 | 阶段二-C / Phase 2-C | `Stage2_Capability_Upgrade_agent` | `STAGE1_ANALYSIS` + `STAGE2B_ANALYSIS` | | [阶段二-C](#阶段二-c能力升级评估stage2_capability_upgrade_agent) |
| 6 | 阶段三 / Phase 3 | `Step_agent` | `STAGE1_ANALYSIS` + `STAGE2B_ANALYSIS`, `MCP/tool.md` | | [阶段三](#阶段三执行步骤规划step_agent) |
| 7 | 执行阶段 / Executor Phase | Execution Agent | `STAGE1_ANALYSIS` + `STAGE2B_ANALYSIS`, refer to lines 36-39 | | [执行阶段](#执行阶段任务落实executor) |
| 8 | 附录与补充材料 / Appendices | Any Contributor | - | | [附录与补充材料](#附录与补充材料) |

> **Tip**: When updating a status, annotate the timestamp next to the entry (e.g., `Completed @ 2025-11-14 02:05`).

---

## 全局任务元数据

- **Task Name**: `Fill in here`
- **Creation Time**: `YYYY-MM-DD HH:MM`
- **Coordinating Agent**: `Agent or system responsible for oversight`
- **Objective Summary**: `Describe the overarching goal in one sentence`
- **Success Criteria**:
  1. `Criterion 1`
  2. `Criterion 2`
  3. …
- **External Constraints / Assumptions**:
  - `Constraint or assumption`
- **Resource Index**: `List all inputs this task depends on (e.g., briefs, capability references, logs)`
- **Notes for All Agents**: `Any additional context every agent should know`

---

## 阶段一：元能力分析（Metacognitive_Analysis_agent）
> Phase 1: Metacognitive Capability Analysis

- **Lead**: `Metacognitive_Analysis_agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Describe the intended deliverable in 1-2 sentences`
- **Executive Summary for Other Agents**: `Distill 3-5 sentences summarizing core reasoning and conclusions`

### 阶段原文记录（阶段一）
> Please keep this anchor intact. Fill complete reasoning here between `<!-- STAGE1_ANALYSIS_START -->` and `<!-- STAGE1_ANALYSIS_END -->`.

<!-- STAGE1_ANALYSIS_START -->
`TBD`
<!-- STAGE1_ANALYSIS_END -->

### 1. Context Understanding

| Field | Content |
| ----- | ------- |
| Core question restated | |
| Key context points | |
| Constraints & assumptions | |
| Known unknowns (knowledge gaps) | |

### 2. Capability Inventory

| Capability / Resource | Source (library/module/agent) | Fit (`High/Medium/Low`) | Notes |
| --------------------- | -------------------------------- | ----------------------- | ----- |
| e.g., capability name | e.g., `ability_library/core_capabilities.md` | High | |
|  |  |  | |

### 3. Risks and Mitigations

- **Identified risks**:
  1. `Risk description` — `Initial mitigation idea`
- **Notes for downstream agents**:
  - `Item 1`

### 4. Phase Conclusion

- **Recommended direction**: `Summarize action guidance`
- **Phase completion status**: `Completed / Needs follow-up` (if the latter, explain why and when it will be resolved)

---

## 阶段二-A：候选策略产出（Candidate_Selection_agent）
> Phase 2-A: Candidate Strategy Generation

- **Lead**: `Candidate_Selection_agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Generate a diverse set of candidate strategies`
- **Executive Summary for Other Agents**: `Condense 3-5 sentences capturing the reasoning and outcome`

### 阶段原文记录（阶段二-A）
> Keep the anchor intact; fill the full reasoning between `<!-- STAGE2A_ANALYSIS_START -->` and `<!-- STAGE2A_ANALYSIS_END -->`.

<!-- STAGE2A_ANALYSIS_START -->
`TBD`
<!-- STAGE2A_ANALYSIS_END -->

### 1. Upstream Checkpoints

| Checkpoint | Covered (`Yes/No`) | Details |
| ---------- | ------------------ | ------- |
| Risk mitigation requirements |  | |
| Capability alignment guidance |  | |
| Other notes |  | |

### 2. Candidate Strategy Catalog

| ID | Strategy Title | Summary | Benefits | Main Costs / Risks | Dependencies |
| -- | -------------- | ------- | -------- | ------------------ | ------------ |
| S-1 | | | | | |
| S-2 | | | | | |
| S-3 | | | | | |

### 3. Prioritization Criteria

- **Sorting rule**: `e.g., maximize impact / minimize risk / favor speed`
- **Additional notes**: `List any specific evaluation metrics`

### 4. Delivery Status (Phase 2-A)

- **Status**: `Completed / In progress / Pending`
- **Outstanding items**: `List follow-ups if any`

---

## 阶段二-B：策略遴选（Strategy_Selection_agent）
> Phase 2-B: Strategy Selection

- **Lead**: `Strategy_Selection_agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Select and refine the optimal strategy from the candidates`
- **Executive Summary for Other Agents**: `Summarize the rationale in 3-5 sentences`

### 阶段原文记录（阶段二-B）
> Keep the anchor intact; fill reasoning between `<!-- STAGE2B_ANALYSIS_START -->` and `<!-- STAGE2B_ANALYSIS_END -->`.

<!-- STAGE2B_ANALYSIS_START -->
`TBD`
<!-- STAGE2B_ANALYSIS_END -->

### 1. Candidate Evaluation

| Strategy | Evaluation Criteria | Score / Judgment | Key Rationale |
| -------- | ------------------- | ---------------- | ------------- |
| S-1 | | | |
| S-2 | | | |
| S-3 | | | |

> **Tip**: Add sub-tables below if you need extra metrics.

### 2. Final Strategy Choice

- **Selected strategy**: `Strategy ID`
- **Core justification**:
  1. `Key argument 1`
  2. `Key argument 2`
- **Risk mitigation plan**: `How you plan to handle potential issues`
- **Fallback strategy**: `If available, specify trigger conditions`

### 3. Common Failure Points (易错点)

| Pitfall ID | Description | Trigger Signal | Linked Stage 1 Risk | Mitigation / Monitoring |
| ---------- | ----------- | -------------- | ------------------- | ----------------------- |
| P-1 | | | | |
| P-2 | | | | |

### 4. Delivery to Next Phase

- **Phase 2-B status**: `Completed / In progress / Pending`
- **Key handoff points**:
  - `Execution flow highlights`
  - `Required resources & preparation`

---

## 阶段二-C：能力升级评估（Stage2_Capability_Upgrade_agent）
> Phase 2-C: Capability Upgrade Assessment

- **Lead**: `Stage2_Capability_Upgrade_agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Determine if new capabilities or external aides are required`
- **Executive Summary for Other Agents**: `Summarize in 3-5 sentences`

### 阶段原文记录（阶段二-C）
> Keep the anchor intact; fill reasoning between `<!-- STAGE2C_ANALYSIS_START -->` and `<!-- STAGE2C_ANALYSIS_END -->`.

<!-- STAGE2C_ANALYSIS_START -->
`TBD`
<!-- STAGE2C_ANALYSIS_END -->

### 1. Capability Gap Diagnosis

| Gap | Impact | Severity (`High/Medium/Low`) | Notes |
| --- | ------ | --------------------------- | ----- |
|  |  |  | |

### 2. Upgrade Proposals

| Proposal ID | Upgrade Content | Expected Benefit | Cost / Risk | Preconditions | Window |
| ----------- | -------------- | ---------------- | ---------- | ------------- | ------ |
| U-1 | | | | | |
| U-2 | | | | | |

### 3. Decision & Actions

- **Recommended proposal**: `U-x`
- **Responsible party**: `Agent or external resource`
- **Timeline**: `Target completion`
- **Verification plan**: `How success will be measured`

### 4. Delivery Status (Phase 2-C)

- **Status**: `Completed / In progress / Pending`
- **Interface notes for other stages**: `List downstream dependencies`

---

## 阶段三：执行步骤规划（Step_agent）
> Phase 3: Execution Planning

- **Lead**: `Step_agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Break down executable steps`
- **Executive Summary for Other Agents**: `Summarize reasoning and outcome`

### 阶段原文记录（阶段三）
> Keep the anchor; fill plan between `<!-- STAGE3_PLAN_START -->` and `<!-- STAGE3_PLAN_END -->`.

<!-- STAGE3_PLAN_START -->
`TBD`
<!-- STAGE3_PLAN_END -->

### 1. Execution Overview

- **Strategy ID**: `S-x`
- **Prerequisites**:
  - Condition 1: `Fulfilled / Not fulfilled (explain)`
  - Condition 2: `Fulfilled / Not fulfilled (explain)`

### 2. Tool Pipeline Log

| Tool Step | Description | Inputs | Dependencies | Output Summary | Result Link |
| --------- | ----------- | ------ | ------------ | -------------- | ----------- |
| T-1 | | | | | |
| T-2 | | | | | |
| T-3 | | | | | |

### 3. Step-by-Step Checklist

| Step ID | Action Description | Owner | Expected Output | Dependencies | Acceptance |
| ------- | ------------------ | ----- | --------------- | ------------ | ---------- |
| Step-1 | | | | | |
| Step-2 | | | | | |
| Step-3 | | | | | |

### 4. Risk Monitoring

- **Key metrics**:
  1. `Monitor metric + trigger threshold`
- **Fallback strategy**: `Rollback procedure if execution fails`

### 5. Delivery Status (Phase 3)

- **Status**: `Completed / In progress / Pending`
- **Handoff notes**: `Special reminders for the executor`

---

## 执行阶段：任务落实（Executor）
> Execution Phase: Task Realization

- **Lead**: `Executor / Actual performing agent`
- **Last Updated**: `YYYY-MM-DD HH:MM`
- **Phase Goal Summary**: `Carry out the plan and record outcomes`
- **Executive Summary for Other Agents**: `Summarize in 3-5 sentences`

### 阶段原文记录（执行阶段）
> Keep the anchor; fill execution logs between `<!-- STAGE4_EXECUTION_START -->` and `<!-- STAGE4_EXECUTION_END -->`.

<!-- STAGE4_EXECUTION_START -->
`TBD`
<!-- STAGE4_EXECUTION_END -->

### 1. Readiness Check

| Checklist Item | Pass (`Yes/No`) | Notes |
| -------------- | --------------- | ----- |
| Required resources ready | | |
| Mitigation measures prepared | | |
| Communication mechanisms established | | |

### 2. Execution Record

| Step ID | Actual Duration | Outcome | Variance | Next Action |
| ------- | --------------- | ------- | -------- | ----------- |
| Step-1 | | | | |
| Step-2 | | | | |
| Step-3 | | | | |

### 3. Summary & Feedback

- **Goal achievement**: `Achieved / Partially achieved / Not achieved (reason)`
- **Lessons learned**:
  - `Success 1`
  - `Lesson 2`
- **Feedback for upstream agents or libraries**: `Suggestions for improvement`

---

## 附录与补充材料 / Appendices & Supplements

### External Document Links

- `List any additional notes or screenshots with sticky references`

### Data / Log Index

- `Reference the locations of data sources or logs`

### Glossary

| Term | Definition | Notes |
| ---- | ---------- | ----- |
| Example | Example | |

### Version History

| Version | Date | Key Updates | Updated By |
| ------- | ---- | ----------- | ---------- |
| v0.1 | YYYY-MM-DD | Initial draft | `Agent` |
|  |  |  |  |

> **Completion Reminder**: After the task is finished, the execution agent should update the status column in the index to `Completed @ timestamp` and ensure every section has a clear conclusion or follow-up owner.
