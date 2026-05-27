# Task 018：把 Course Agent 从“Prompt-native Agent Platform”推进到“Context-governed Agent Platform”

> 本 Task 基于 Task 017 完成后的项目状态继续推进。
>
> 截止目前，项目已经具备：
>
> - ReAct `AgentLoop` 与 graph-native `ReactGraphRuntime`
> - Planner / Solver / Critic / Examiner / Orchestrator 多 Agent 编排
> - 短期记忆 + 长期记忆 + `MemoryManager`
> - Session / Resume / Human-in-the-loop / Replay
> - `PromptEnvelope` / Prompt Compiler / `static_prefix` / `dynamic_tail`
> - `COURSE_AGENT.md` 项目级说明文件
> - `prompt inspect / latest / profile`
> - **467 passed + 6 skipped**
>
> 这说明项目已经完成了从：
>
> - Agent MVP
> - Graph-native Runtime
> - Stateful Runtime
> - Prompt-native Runtime
>
> 的四轮关键升级。
>
> 但是，如果继续把项目往“真正成熟的 Agent 平台”推进，现在还存在一个下一阶段会迅速放大的核心问题：
>
> > **虽然 prompt 已经架构化了，但“上下文”仍然没有被统一治理。**
>
> 也就是说：
>
> - prompt 这一层已经有了 `static_prefix` / `dynamic_tail`
> - 但真正喂给模型的 **history / memory / sub-task handoff / critic feedback / session state / retrieved context**
>   仍然是分散拼装、缺少预算意识、缺少压缩策略、缺少角色视图的
>
> 这会在四个方向上逐渐成为瓶颈：
>
> 1. **AgentLoop 的上下文仍偏“朴素追加”**
>    现在 `AgentLoop` 已经能统一编译 prompt，
>    但对于真正进入模型的 history，仍然缺少：
>
>    - 统一上下文预算
>    - 分层选择策略
>    - 超预算裁剪 / 压缩
>    - “哪些必须保留、哪些可以摘要、哪些应丢弃”的显式规则
>
> 2. **多 Agent 之间的上下文传递还比较粗糙**
>    当前 Orchestrator 的上下文流转基本是：
>
>    - Planner 产出 sub-task
>    - Solver 执行
>    - Critic 返回 feedback
>    - 把一段 feedback 或截断后的 solver 输出塞回 history
>
>    这足够跑通闭环，但还不是成熟的 context handoff 设计。
>
>    它缺少：
>
>    - 面向角色的上下文视图
>    - 面向子任务的 briefing
>    - 面向评审的 evidence packet
>    - 面向最终合成的 compact digest
>
> 3. **记忆系统已经有了，但还没有被上下文治理层真正接住**
>    现在已经有：
>
>    - `ShortTermMemory`：滑动窗口 + LLM 摘要压缩
>    - `LongTermMemory`：向量检索
>    - `MemoryManager`：统一 enrich
>
>    但它仍然更像“有记忆模块”，而不是“有记忆策略”。
>
>    还缺：
>
>    - 什么内容值得写入长期记忆
>    - 什么内容应只保留在 session
>    - 什么内容应升格为 pinned facts
>    - recall 回来的内容怎样变成 context packet，而不是一段大文本
>
> 4. **上下文压缩还只是一个局部能力，不是平台能力**
>    当前压缩基本只存在于 `ShortTermMemory._compress()`，
>    也就是：
>
>    - 对早期对话做一次 200 字摘要
>
>    这是一种“能用”的起点，
>    但还不是：
>
>    - budget-aware compression
>    - role-aware compression
>    - task-aware compression
>    - multi-stage compression
>    - inspectable compression artifact
>
> 换句话说，Task 017 解决的是：
>
> - “怎么把 prompt 组织好”
>
> 而 Task 018 需要解决的是：
>
> > **怎么把上下文真正变成一等平台资产：可选择、可裁剪、可压缩、可传递、可解释。**
>
> 这意味着项目要从：
>
> - Prompt-native Agent Platform
>
> 继续演进为：
>
> - Context-governed Agent Platform
>
> 也就是说，Task 018 的核心重点会转向：
>
> > **Context Envelope / Context Budget / Context Handoff / Memory Policy / Compression Pipeline**

---

## 一、当前项目现状盘点（Task 017 收尾后）

### 1.1 已有能力

| 模块 | 状态 | 说明 |
|---|---|---|
| `AgentLoop` | ✅ | 单 Agent ReAct 主循环 |
| `ReactGraphRuntime` | ✅ | graph-native 单 Agent runtime |
| Planner / Solver / Critic / Orchestrator | ✅ | 多 Agent 编排闭环 |
| `ShortTermMemory` | ✅ | 滑动窗口 + 简单摘要压缩 |
| `LongTermMemory` | ✅ | 向量检索型长期记忆 |
| `MemoryManager` | ✅ | 短期 + 长期 enrich 入口 |
| Session / Resume / HITL | ✅ | 有状态任务执行 |
| Prompt Compiler | ✅ | `static_prefix` / `dynamic_tail` |
| Prompt Profiling | ✅ | prompt 结构可 inspect / profile |
| 测试质量 | ✅ | **467 passed + 6 skipped** |

### 1.2 当前上下文层面的剩余短板

| 方向 | 当前状态 | 问题 |
|---|---|---|
| **AgentLoop 上下文预算** | ❌ 缺失 | 没有统一 token / char budget 概念 |
| **上下文选择策略** | ⚠️ 分散 | history / memory / feedback 各自拼接 |
| **多 Agent 上下文交接** | ⚠️ 粗粒度 | 主要靠截断字符串 + system feedback |
| **记忆策略** | ⚠️ 初步可用 | 有模块，但没有“写入 / 召回 / pin / 过期 / 压缩”统一政策 |
| **上下文压缩管线** | ❌ 缺失 | 只有短期记忆局部摘要，没有平台级 compression pipeline |
| **上下文可观测性** | ❌ 缺失 | 无法直接回答“本轮上下文为什么是这些” |
| **角色视图** | ❌ 缺失 | Planner / Solver / Critic 没有独立 context view |
| **压缩工件** | ❌ 缺失 | 没有 context artifact / compression trace |

### 1.3 为什么 Task 018 很关键

Task 017 让你可以讲：

- “我们已经有 prompt architecture”
- “我们可以 inspect prompt”

但 Task 018 会让你开始讲更深入的一层：

- “我们如何治理模型输入上下文”
- “我们如何在多 Agent 间做上下文交接”
- “我们如何用记忆系统服务上下文，而不是让记忆孤立存在”
- “我们如何在不丢关键信息的前提下压缩 token”

这会让项目从“prompt 已经成体系”，进一步走向“context 已经成体系”。

---

## 二、Task 018 的核心目标

> **主题：把 Course Agent 升级为一个真正支持上下文预算、上下文选择、上下文压缩、记忆策略和多 Agent 上下文交接的 Context-governed Agent Platform。**

本期不再只关心：

- prompt 怎么拼

而更关心：

- history 该如何进入模型
- memory 该如何进入模型
- 多 Agent 之间该如何交接上下文
- 超预算时该如何压缩
- 压缩后如何保证关键信息不丢
- 如何让每个角色只看到“它该看到的上下文”

### 2.1 本期聚焦

本期聚焦五件事：

1. **Context Envelope / Context Sections**
   建立统一的上下文结构化表示，而不是继续在各处直接拼接消息。

2. **Context Budget / Selection**
   为单 Agent 与多 Agent 引入预算意识和上下文选择规则。

3. **Memory Policy**
   让短期记忆、长期记忆、pinned facts、session notes 进入统一上下文治理层。

4. **Compression Pipeline**
   让上下文压缩从“短期记忆里的一个函数”，升级为可复用、可观察的平台能力。

5. **Multi-Agent Context Handoff**
   设计 Planner / Solver / Critic / Orchestrator 之间更清晰的上下文交接格式。

### 2.2 本期不做什么

| 做 | 不做 |
|---|---|
| ✅ 建立统一 Context Infrastructure | ❌ 一期内做复杂的 tokenizer 成本计费平台 |
| ✅ 建立 context budget / selection 规则 | ❌ 一期内接入完整 reranker / cross-encoder |
| ✅ 建立 compression pipeline | ❌ 一期内做 tree-of-thought / graph-of-thought 全自动压缩 |
| ✅ 改进 multi-agent context handoff | ❌ 一期内做跨 session 全局知识图谱 |
| ✅ 补齐 inspect / profile / artifact | ❌ 一期内做分布式 memory service |

---

## 三、为什么 Task 018 值得做

### 3.1 Prompt 已经结构化了，下一步一定是 Context 结构化

Prompt 决定“模型被怎样约束”；
Context 决定“模型到底看到哪些信息”。

如果上下文仍然是临时拼接的，那么 prompt 再精致，模型输入仍然可能：

- 冗余
- 失焦
- 角色污染
- token 爆炸
- 关键信息被埋

### 3.2 AgentLoop 的上限，往往不是 tool，而是 context

单 Agent 跑短任务时问题不明显；
一旦任务复杂、轮次拉长、history / memory / tool result / session notes 同时进入上下文，`AgentLoop` 的瓶颈就不再是“有没有工具”，而变成：

- 模型能不能在有限上下文里看到真正重要的信息
- 系统能不能持续控制上下文质量

### 3.3 多 Agent 的核心，不只是分工，而是“交接”

多 Agent 不是把一个大问题拆开就结束了。
真正困难的是：

- Planner 如何把任务交给 Solver
- Solver 如何把结果交给 Critic
- Critic 如何把 feedback 交回 Solver
- Orchestrator 如何汇总多轮中间结果

如果交接只是“塞一段字符串过去”，随着复杂度提升，系统会越来越不稳定。

### 3.4 记忆系统只有接入上下文治理，才真正有平台价值

现在已经有：

- 短期记忆
- 长期记忆
- recall / remember

但下一阶段真正要解决的问题是：

- 哪类信息是短期上下文
- 哪类信息是长期偏好
- 哪类信息要在本轮强制 pin 住
- 哪类信息该被摘要后继续传递

这意味着“记忆”必须被放进“上下文策略”里，而不是只当作一个外挂模块。

---

## 四、Task 018 目标（本期范围）

### 4.1 统一 Context 模型

建议引入统一概念：

```python
class ContextSection(BaseModel):
    name: str
    content: str
    source: str
    priority: int
    char_count: int
    compressible: bool = True
    pinned: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextEnvelope(BaseModel):
    role: str
    sections: list[ContextSection]
    total_chars: int
    selected_chars: int
    dropped_sections: list[str] = Field(default_factory=list)
    compression_trace: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

核心原则：

- 上下文不再只是 `list[LLMMessage]`
- 在进入消息层之前，先有一层可分析、可裁剪、可压缩的结构化 envelope

### 4.2 Context Budget

建议引入预算概念：

- `max_context_chars`
- `reserve_for_response`
- `role_budget_overrides`
- `compression_trigger_ratio`

预算不必一期内严格做到 tokenizer 级；
先做字符数近似 + 可扩展结构即可。

要求至少支持：

- 单 Agent budget
- 多 Agent role budget
- 超预算时优先压缩而不是直接硬裁

### 4.3 Context Selection Policy

建议把上下文来源拆成几类：

- `prompt_tail_context`
- `recent_history`
- `short_memory_summary`
- `recalled_long_memory`
- `session_state`
- `subtask_brief`
- `critic_feedback`
- `tool_result_digest`
- `pinned_facts`

并为每一类定义：

- 优先级
- 默认是否压缩
- 是否可丢弃
- 面向哪些角色可见

### 4.4 Memory Policy

建议升级记忆系统的角色：

1. **Short-term session memory**
   - 面向最近交互
   - 支持渐进压缩

2. **Long-term semantic memory**
   - 面向偏好 / 历史事实 / 高价值知识
   - recall 后不直接原样塞进消息，而先转成 context sections

3. **Pinned facts**
   - 本轮或本 session 必须保留的信息
   - 例如：
     - 用户指定的硬约束
     - 当前作业目标
     - 当前分支 / 路径 / 关键文件

4. **Ephemeral working notes**
   - 中间推导、临时计划、sub-task evidence
   - 可以被压缩、汇总、回收

### 4.5 Compression Pipeline

建议新增统一压缩管线：

```python
compress_context(
    sections: list[ContextSection],
    budget: ContextBudget,
    strategy: str = "hybrid",
) -> CompressionResult
```

建议至少支持三种策略：

1. **truncate**
   - 超预算时的保底策略

2. **extractive**
   - 保留标题、关键 bullet、关键事实

3. **summary**
   - 借助 LLM 做压缩摘要

一期可先做：

- heuristic + LLM summary 的 hybrid 版本

### 4.6 AgentLoop Context Middleware

建议把 `AgentLoop` 升级为：

- 不是直接接收 history
- 而是通过统一 context builder / broker 先构建本轮上下文

例如：

```python
build_runtime_context(
    role="react",
    user_input="...",
    history=...,
    memory_manager=...,
    session=...,
    task_notes=...,
) -> ContextEnvelope
```

然后再把 `ContextEnvelope` 转成消息层，进入 LLM。

### 4.7 Multi-Agent Context Handoff

建议为多 Agent 设计更清晰的交接对象：

```python
class SubTaskBrief(BaseModel):
    sub_task: dict[str, Any]
    constraints: list[str]
    accepted_context: list[str]
    pinned_facts: list[str]
    recent_findings: list[str]


class CriticDigest(BaseModel):
    score: int
    pass_: bool
    must_fix: list[str]
    optional_suggestions: list[str]
    evidence: list[str]
```

目标：

- Planner 不再只吐原始 JSON sub-task
- Solver 不再只吃杂糅 history
- Critic feedback 不再只是一段 system string
- Orchestrator 可基于结构化 digest 决定下一轮上下文

### 4.8 Context Inspect / Profile

建议新增 CLI：

```bash
course-agent context inspect
course-agent context inspect --role solver --query "..."
course-agent context latest
course-agent context profile
```

至少支持：

- 查看本轮上下文 section 列表
- 查看哪些 section 被保留 / 压缩 / 丢弃
- 查看总长度、压缩前后长度、各来源占比
- 查看 compression trace

### 4.9 Context Artifact

建议新增：

- `data/contexts/`

每次关键运行可落地：

- `context_envelope.json`
- `context_envelope.md`

至少包含：

- role
- input
- selected sections
- dropped sections
- compression trace
- size profile

---

## 五、成功指标（本期验收标准）

1. [ ] 系统引入统一 `ContextSection` / `ContextEnvelope` / `ContextBudget` 抽象
2. [ ] `AgentLoop` 至少接入统一 context build / select / compress 流程
3. [ ] Planner / Solver / Critic / Orchestrator 至少有一条多 Agent 路径接入 context handoff
4. [ ] 记忆系统从“直接 enrich 文本”升级为“产出 context sections”
5. [ ] 支持最小可用的上下文压缩管线（truncate / extractive / summary 至少 2 种）
6. [ ] CLI 可 inspect / latest / profile 当前 context
7. [ ] context artifact 可落盘并可回看压缩轨迹
8. [ ] README 补充 Task 018 的 context governance 说明
9. [ ] 单测新增后，`pytest` 总数 ≥ **505 passed**
10. [ ] `ruff check .` 全绿

---

## 六、技术方案

### 6.1 顶层新增结构

建议新增：

```text
course_agent/
├── context/
│   ├── models.py
│   ├── budget.py
│   ├── compiler.py
│   ├── selectors.py
│   ├── compressor.py
│   ├── handoff.py
│   ├── artifacts.py
│   └── profiling.py
docs/
└── tech_share_task018/
    ├── context_governance.md
    ├── agentloop_context_flow.md
    ├── multi_agent_handoff.md
    └── compression_demo.md
```

### 6.2 Context 模型

建议最小字段：

- `ContextSection`
  - `name`
  - `content`
  - `source`
  - `priority`
  - `compressible`
  - `pinned`
  - `metadata`

- `ContextEnvelope`
  - `role`
  - `sections`
  - `total_chars`
  - `selected_chars`
  - `dropped_sections`
  - `compression_trace`
  - `metadata`

- `ContextBudget`
  - `max_chars`
  - `reserve_chars`
  - `compression_trigger_ratio`
  - `hard_drop_allowed`

### 6.3 Context Compiler

建议建立统一入口：

```python
compile_context(
    *,
    role: str,
    user_input: str,
    history: list[LLMMessage] | None = None,
    memory_manager: MemoryManager | None = None,
    session_notes: dict[str, Any] | None = None,
    task_notes: dict[str, Any] | None = None,
    role_budget: ContextBudget | None = None,
) -> ContextEnvelope
```

职责：

- 收集候选上下文 section
- 评估预算
- 触发选择 / 压缩
- 生成 inspect / artifact 可用结构

### 6.4 Compression 策略

建议压缩顺序：

1. 先保留 pinned / critical sections
2. 再优先保留最近轮次 history
3. 对低优先级长文本做 extractive 压缩
4. 仍超预算时再做 summary 压缩
5. 最后才进行 hard drop

### 6.5 AgentLoop 接入点

建议改造：

- `_build_prompt_envelope(...)`
- `_build_prompt_messages(...)`

之外，再新增：

- `_build_context_envelope(...)`
- `_build_context_messages(...)`

最终组装顺序建议为：

1. `static_prefix`
2. `dynamic_tail`
3. selected context messages
4. current user input

### 6.6 MemoryManager 升级

建议把 `MemoryManager.enrich_context()` 升级为两层：

1. `collect_context_sections(...)`
   - 返回结构化 sections

2. `render_context_messages(...)`
   - 仅在最后一步把 sections 渲染成 `LLMMessage`

这样做的价值：

- 记忆系统不再直接拼字符串
- 上下文治理层可以决定保留 / 压缩 / 丢弃哪些部分

### 6.7 Multi-Agent Handoff

建议：

- Planner 输出 `SubTaskBrief`
- Solver 输出 `SubTaskResultDigest`
- Critic 输出 `CriticDigest`
- Orchestrator 维护 `TaskContextLedger`

这样后续各角色只接收：

- 自己需要的摘要
- 必要的 pinned facts
- 必须修复的 critic issues

而不是共享一个不断膨胀的 history。

### 6.8 CLI / Artifact

建议新增 `context` 子命令，功能对齐 `prompt`：

- `inspect`
- `latest`
- `profile`

同时支持把 context artifact 落到：

- `data/contexts/`

### 6.9 与 Prompt Infrastructure 的关系

Task 017 和 Task 018 的边界建议明确：

- **Task 017** 负责“模型约束层”：prompt contract
- **Task 018** 负责“模型信息层”：context governance

两者关系可以理解为：

```text
Prompt Compiler
    + Context Compiler
    = Final LLM Input
```

---

## 七、迁移步骤（建议顺序）

### Step 1：Context 基础模型
- `ContextSection`
- `ContextEnvelope`
- `ContextBudget`

### Step 2：Compression Pipeline
- `truncate`
- `extractive`
- `summary`

### Step 3：MemoryManager 升级
- collect sections
- recall → context packet
- pinned facts

### Step 4：AgentLoop 接入
- build context
- select / compress
- 转消息层

### Step 5：多 Agent Context Handoff
- Planner brief
- Critic digest
- Orchestrator ledger

### Step 6：CLI / Artifact / Profile
- `context inspect`
- `context latest`
- `context profile`

### Step 7：README / 分享素材 / 回填
- README
- docs/tech_share_task018
- task_018.md 勾选

---

## 八、测试矩阵

### 8.1 新增测试文件（建议 ≥ 38 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_context_models.py` | `ContextSection` / `ContextEnvelope` / `ContextBudget` | ≥ 5 |
| `tests/test_context_selector.py` | budget / priority / pin / drop | ≥ 6 |
| `tests/test_context_compressor.py` | truncate / extractive / summary | ≥ 6 |
| `tests/test_context_compiler.py` | history / memory / session / task 编译 | ≥ 6 |
| `tests/test_context_cli.py` | `context inspect / latest / profile` | ≥ 5 |
| `tests/test_context_artifact.py` | artifact 落盘 / latest / markdown | ≥ 4 |
| `tests/test_memory_context_policy.py` | memory → context sections / pinned facts | ≥ 4 |
| `tests/test_multi_agent_context_handoff.py` | Planner / Solver / Critic / Orchestrator 交接 | ≥ 4 |

### 8.2 回归测试

必须继续通过：

- Task 008~017 的所有测试
- 特别是：
  - `test_agent_loop.py`
  - `test_prompt_integration.py`
  - `test_react_graph_runtime.py`
  - `test_cli_session.py`
  - `test_langgraph_orchestrator.py`

### 8.3 验收门槛

- `pytest -q` ≥ **505 passed**
- `ruff check .` 全绿

---

## 九、交付物 Checklist

### 代码
- [ ] `course_agent/context/models.py`
- [ ] `course_agent/context/budget.py`
- [ ] `course_agent/context/compiler.py`
- [ ] `course_agent/context/selectors.py`
- [ ] `course_agent/context/compressor.py`
- [ ] `course_agent/context/handoff.py`
- [ ] `course_agent/context/artifacts.py`
- [ ] `course_agent/context/profiling.py`
- [ ] `course_agent/core/agent_loop.py`：接入统一 context compiler
- [ ] `course_agent/memory/manager.py`：升级为 section-based memory policy
- [ ] `course_agent/memory/short_term.py`：接入统一 compression pipeline
- [ ] `course_agent/agent/planner.py`：接入 `SubTaskBrief`
- [ ] `course_agent/agent/solver.py`：接入 context-aware solver input
- [ ] `course_agent/agent/critic.py`：接入 `CriticDigest`
- [ ] `course_agent/agent/orchestrator.py`：接入 `TaskContextLedger`
- [ ] `course_agent/cli.py`：新增 `context` 子命令

### 测试 / 配置
- [ ] `tests/test_context_models.py`
- [ ] `tests/test_context_selector.py`
- [ ] `tests/test_context_compressor.py`
- [ ] `tests/test_context_compiler.py`
- [ ] `tests/test_context_cli.py`
- [ ] `tests/test_context_artifact.py`
- [ ] `tests/test_memory_context_policy.py`
- [ ] `tests/test_multi_agent_context_handoff.py`
- [ ] `pytest -q` ≥ **505 passed**
- [ ] `ruff check .` 全绿

### 文档 / 分享素材
- [ ] `README.md` 新增「🧠 Context Governance」一节
- [ ] `README.md` 新增「🗜️ Context Compression」一节
- [ ] `README.md` 更新 Task 018 进度行
- [ ] `docs/tech_share_task018/context_governance.md`
- [ ] `docs/tech_share_task018/agentloop_context_flow.md`
- [ ] `docs/tech_share_task018/multi_agent_handoff.md`
- [ ] `docs/tech_share_task018/compression_demo.md`
- [ ] `task/task_018.md`（本文）成功指标与交付物回填

### 验证脚本（推荐手动跑）
- [ ] `course-agent context inspect`
- [ ] `course-agent context inspect --role solver --query "..."`
- [ ] `course-agent context latest`
- [ ] `course-agent context profile`
- [ ] 运行一次 chat / multi-agent 流程后查看 context artifact

---

## 十、Task 018 的教学 / 分享价值

如果说：

- Task 017 讲的是“如何把 prompt 做成基础设施”

那么 Task 018 讲的就是：

> **当 prompt 已经成体系之后，如何进一步把模型输入中的“上下文”做成一套可治理、可压缩、可交接的工程系统。**

这一期很适合做更深入的技术分享，因为它天然能讲：

### 10.1 架构层
- 为什么 prompt 之后一定是 context
- 为什么 AgentLoop 的下一阶段瓶颈是上下文治理
- 为什么多 Agent 的核心不是“多”，而是“交接”

### 10.2 工程层
- 如何设计 `ContextEnvelope`
- 如何设计 budget / selection / compression pipeline
- 如何让 memory system 与上下文治理层对接

### 10.3 演示层
- inspect 一次 context envelope
- 展示哪些 section 被保留、压缩、丢弃
- 展示 Planner / Solver / Critic 的不同 context view
- 展示一次 compression trace

### 10.4 方法论层
- 从“拼 history”转向“治理上下文”
- 从“有记忆模块”转向“有记忆策略”
- 从“能压缩一点”转向“可持续控制上下文质量”

---

## 十一、Task 018 完成后的预期效果

当 Task 018 完成后，Course Agent 应该不只是：

- 一个有 prompt architecture 的 Agent 平台
- 一个有 replay / session / HITL 的 Agent 平台

而应该成为：

> **一个支持 Context Budget、Memory Policy、Compression Pipeline 和 Multi-Agent Context Handoff 的 Context-governed Agent Platform 样板。**

届时你在技术分享里可以进一步讲清楚：

1. 为什么 Agent 的下一阶段关键问题不是“多加工具”，而是“治理上下文”
2. 为什么记忆系统必须和上下文治理打通
3. 为什么多 Agent 的质量很大程度上取决于 handoff 质量
4. 为什么上下文压缩应该从局部技巧升级为平台能力

---
