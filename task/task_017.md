# Task 017：把 Course Agent 从“Stateful Agent Platform”推进到“Prompt-native Agent Platform”

> 本 Task 基于 Task 016 完成后的项目状态继续推进。
>
> 截止目前，项目已经具备：
>
> - ReAct Agent Loop 与 graph-native `ReactGraphRuntime`
> - Planner / Solver / Critic / Orchestrator 多 Agent 编排
> - Capability Layer（internal_tool / skill / mcp）
> - LangGraph Runtime（单 Agent / 多 Agent 都已接入）
> - LangChain Adapter Layer
> - Replay / Trace Export
> - Benchmark / Compare CLI
> - Session / Resume / Human-in-the-loop / Task Lifecycle
> - Chainlit 中的 graph runtime 与 session 状态摘要展示
> - 技术分享素材目录
> - **430 passed + 6 skipped**
>
> 这说明项目已经完成了从：
>
> - Agent MVP
> - Graph-native Runtime
> - Stateful Runtime
>
> 的三轮核心升级。
>
> 但是，如果继续往真正成熟的 Agent Platform 推进，现在还有一个被低估、但实际上非常关键的短板：
>
> > **系统已经有了工具层、图运行时、session 生命周期，但“发给模型的 prompt”仍然是分散的、临时拼接的、缺少统一架构的。**
>
> 也就是说，现在项目虽然越来越像一个平台，
> 但 prompt 这一层仍然更像“代码里散落的字符串常量 + 各模块各自拼接”的状态。
>
> 这会带来几个明显问题：
>
> 1. **Prompt 缺少统一分层**
>    当前已经能看到多处独立 system prompt：
>    - `AgentLoop._DEFAULT_SYSTEM_PROMPT`
>    - `PLANNER_SYSTEM_PROMPT`
>    - `SOLVER_SYSTEM_PROMPT`
>    - `CRITIC_SYSTEM_PROMPT`
>    - `EXAMINER_SYSTEM_PROMPT`
>    - Chainlit scene prompts
>
>    这些 prompt 各自有效，但它们并没有被组织成一套统一的 prompt architecture。
>
> 2. **Prompt 没有清晰的“静态前缀 / 动态尾部”边界**
>    当前更多是：
>    - 先写一段 system prompt
>    - 再在不同地方手工把用户任务、上下文、记忆、工具信息拼进去
>
>    但这不利于：
>    - 缓存
>    - 复用
>    - 调优
>    - 可观测性
>    - 后续 prompt profiling
>
> 3. **缺少类似 Claude Code 的“全局统一前缀”**
>    参考 Claude Code 这类工程代理的一个重要思路：
>
>    - 前面是一段**跨用户共享、稳定、可缓存的静态前缀**
>    - 后面是**用户 / 项目 / 环境 / 记忆 / MCP / 当前任务**等动态尾部
>
>    这种设计的价值不只是“更像大厂 prompt”。
>    它本质上是在做：
>
>    - prompt 架构化
>    - token 利用率优化
>    - 行为一致性约束
>    - 上下文拼装标准化
>
> 4. **当前 prompt 拼接方式不利于长期演进**
>    现在要往 system prompt 里再加内容，经常会变成：
>
>    - 在某个 agent 文件里多补两行
>    - 在 UI 里再拼一段
>    - 在 runtime 里再塞一个 history / memory 提示
>
>    这会导致：
>
>    - prompt 逻辑分散
>    - 不同 agent 行为不一致
>    - 很难解释“最终到底给模型发了什么”
>    - 很难做统一的 prompt diff / prompt replay / prompt benchmarking
>
> 5. **Prompt 还没有成为一等平台资产**
>    当前项目里：
>
>    - runtime 是一等资产
>    - trace / replay 是一等资产
>    - session 是一等资产
>
>    但 prompt 还不是。
>
>    更成熟的平台应该能回答：
>
>    - 静态前缀是什么？
>    - 动态尾部包含什么？
>    - 本次请求最终 prompt 长什么样？
>    - 哪些是缓存友好的？
>    - 哪些是用户特定的？
>    - 哪些来自项目说明、记忆、MCP、UI 场景？
>
> 所以 Task 017 的核心命题不再是：
>
> - “怎么让 Agent 更会跑”
> - “怎么让任务更可恢复”
>
> 而是：
>
> > **怎么把系统发给模型的 prompt，从‘零散字符串’升级成一套可分层、可缓存、可解释、可观察的 Prompt Infrastructure。**
>
> 这意味着项目要从：
>
> - Stateful Agent Platform
>
> 继续演进为：
>
> - Prompt-native Agent Platform
>
> 也就是说，Task 017 的核心重点会转向：
>
> > **Static Prefix / Dynamic Tail / Prompt Compiler / Prompt Replay / Prompt Observability**

---

## 一、当前项目现状盘点（Task 016 收尾后）

### 1.1 已有能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 单 Agent legacy loop | ✅ | `AgentLoop` |
| 单 Agent graph-native loop | ✅ | `ReactGraphRuntime` |
| 多 Agent graph runtime | ✅ | `LangGraphRuntime` |
| Capability Layer | ✅ | internal_tool / skill / mcp |
| Replay / Trace Export | ✅ | graph replay 可导出 |
| Session / Resume / HITL | ✅ | Task 016 已完成 |
| Benchmark / Compare | ✅ | legacy vs langgraph chat runtime |
| Chainlit graph + session 摘要 | ✅ | 最小任务态展示 |
| 技术分享素材 | ✅ | docs/tech_share_task015 / 016 |
| 测试质量 | ✅ | **430 passed + 6 skipped** |

### 1.2 当前 prompt 层面的剩余短板

| 方向 | 当前状态 | 问题 |
|---|---|---|
| **Prompt 分层** | ❌ 缺失 | 静态前缀 / 动态尾部没有明确边界 |
| **Prompt 统一入口** | ❌ 缺失 | 各模块各自拼接 |
| **Prompt 可观测性** | ⚠️ 部分可推断 | 无法直接查看“最终 prompt” |
| **Prompt 缓存友好性** | ❌ 缺失 | 无 static prefix hash / cache segment |
| **项目级说明文件** | ⚠️ 没有正式 prompt contract | 缺少类似 `CLAUDE.md` 的约定入口 |
| **Prompt replay** | ❌ 缺失 | replay 有 trace，但没有 prompt artifact |
| **Prompt profiling** | ❌ 缺失 | 不知道静态前缀和动态尾部各占多少 token |

### 1.3 为什么 Task 017 很关键

Task 016 让你可以讲：

- “我们有 session”
- “我们能 resume”
- “我们支持 HITL”

但 Task 017 会让你开始讲更深一层的东西：

- “我们把 prompt 本身做成了平台基础设施”
- “我们有统一的静态前缀与动态尾部边界”
- “我们能解释本次请求到底给模型发了什么”
- “我们能为 prompt 做 replay / profiling / benchmark”

这会让项目从“运行时成熟”进一步走向“认知层成熟”。

---

## 二、Task 017 的核心目标

> **主题：把 Course Agent 升级为一个真正支持 Prompt 分层、Prompt 编译、Prompt Replay、Prompt Profiling 的 Prompt-native Agent Platform。**

本期不再只关心“怎么执行任务”，
而更关心：

- 最终 prompt 是如何组成的
- 哪些内容是稳定可缓存的
- 哪些内容是用户 / 项目 / 环境相关的
- 如何统一单 Agent、多 Agent、UI 场景与项目级说明的 prompt contract

### 2.1 本期聚焦

本期聚焦四件事：

1. **Static Prefix / Dynamic Tail**
   建立统一的 prompt 分层模型，明确缓存边界。

2. **Prompt Compiler**
   建立统一 prompt 编译入口，把：
   - 全局规则
   - agent 角色定义
   - 项目说明
   - 记忆摘要
   - MCP 指令
   - 环境信息
   - 当前任务
   编译成最终 prompt。

3. **Prompt Replay / Inspect**
   支持查看“本次请求实际发给模型的 prompt”。

4. **Prompt Profiling / Benchmark**
   支持估算 static / dynamic token 占比，并纳入后续 benchmark 与调优。

### 2.2 本期不做什么

| 做 | 不做 |
|---|---|
| ✅ 统一 Prompt Infrastructure | ❌ 一期内训练 / 微调模型 |
| ✅ static prefix / dynamic tail 边界 | ❌ 一期内做复杂自动压缩器 |
| ✅ prompt replay / inspect | ❌ 一期内做完整 prompt IDE |
| ✅ 项目级说明文件接入 | ❌ 强行兼容所有外部 prompt 标准 |
| ✅ prompt profiling | ❌ 一期内做真实 tokenizer 成本计费平台 |

---

## 三、为什么 Task 017 值得做

### 3.1 Prompt 是 Agent 的“认知接口”

工具、图、session 解决的是“怎么执行”；
prompt 解决的是“怎么理解任务、怎么做决策、怎么受约束”。

如果 prompt 仍然是零散的，那么平台再强，认知层也仍然是松散的。

### 3.2 Claude Code 类设计的关键，不只是提示词长，而是“分层”

参考 Claude Code 的一个重要点，并不是它 prompt 写得多，
而是它把 prompt 分成了两层：

1. **静态前缀**
   - 角色定义
   - 安全红线
   - 行为准则
   - 操作安全
   - 工具使用规则
   - Git 安全
   - 输出风格

2. **动态尾部**
   - 当前环境
   - 当前项目说明
   - 当前记忆
   - MCP 连接状态
   - 当前任务

这件事的价值在于：

- 静态部分可共享
- 动态部分可精确更新
- 边界清晰，便于 profiling 和缓存

### 3.3 这会显著提升技术分享与后续演进能力

Task 017 完成后，你不仅能讲：

- 我们有什么 runtime
- 我们有什么 session / replay

还可以讲：

- 我们如何设计 prompt architecture
- 我们如何把 prompt 变成可重放工件
- 我们如何控制 prompt 的稳定层与变化层
- 我们如何借鉴 Claude Code 但适配 Course Agent 场景

---

## 四、Task 017 目标（本期范围）

### 4.1 Prompt 分层模型

建议引入统一概念：

```python
class PromptEnvelope(BaseModel):
    static_prefix: str
    dynamic_tail: str
    full_prompt: str
    static_hash: str
    dynamic_hash: str
    sections: list[dict[str, Any]]
```

核心原则：

- `static_prefix`
  - 全局共享
  - 尽量稳定
  - 优先作为 cache-friendly segment

- `dynamic_tail`
  - 每次请求重算
  - 用户 / 项目 / runtime / 环境特定

### 4.2 静态前缀设计

静态前缀参考 Claude Code，但要适配本项目：

- 角色定义：你是 Course Agent / Planner / Solver / Critic / Examiner / Orchestrator
- 安全红线：拒绝破坏性攻击、供应链攻击、DoS 等
- 行为准则：先读后改、原子修改、验证后再报告
- 操作安全：危险操作需确认
- 工具使用：优先专用工具而非 bash
- Git 安全：不改 git config、不跳 hook、不 force push 主分支
- 输出风格：语言匹配用户、简洁、少废话

要求：

- 单 Agent / 多 Agent 的静态前缀应共享同一套全局主前缀
- 各 agent 只在其后追加少量角色专属前缀

### 4.3 动态尾部设计

动态尾部建议至少包含：

- 环境信息
  - 工作目录
  - 平台
  - shell
  - 日期
  - git 状态摘要

- 项目说明文件
  - 类似 `CLAUDE.md`
  - 建议本项目引入 `COURSE_AGENT.md` 或兼容 `CLAUDE.md`

- 记忆指令
  - 用户偏好
  - 项目偏好
  - 历史反馈

- MCP / Capability 指令
  - 当前可用 MCP
  - 当前 capability 摘要

- 当前任务
  - 用户 query
  - 当前 session 状态
  - 当前 scene / agent mode

### 4.4 Prompt Compiler

建议新增统一 prompt 编译器：

```python
compile_prompt(
    role="solver",
    user_input="...",
    context=...,
    project_instructions=...,
    memory_notes=...,
    mcp_notes=...,
    env_notes=...,
) -> PromptEnvelope
```

这个编译器应该负责：

- 按统一顺序拼装 prompt
- 标记分层边界
- 输出静态 hash / 动态 hash
- 生成 inspect / replay 可用结构

### 4.5 项目级说明文件

建议新增：

- `COURSE_AGENT.md`

定位类似 Claude Code 的 `CLAUDE.md`：

- 项目技术栈
- 代码风格
- 测试要求
- 关键约束
- 当前分享 / 架构目标

规则：

- 若项目根目录存在 `COURSE_AGENT.md`，则动态尾部自动引入
- 若不存在，则降级为空

### 4.6 Prompt Replay / Inspect

新增 CLI：

```bash
course-agent prompt inspect
course-agent prompt inspect --role solver --query "..."
course-agent prompt latest
course-agent prompt profile
```

要求至少支持：

- 查看当前完整 prompt
- 分别查看 `static_prefix` / `dynamic_tail`
- 查看 section 列表
- 查看 static hash / dynamic hash

### 4.7 Prompt Profiling

本期先做轻量版本，至少输出：

- static 长度
- dynamic 长度
- full 长度
- static 占比
- dynamic 占比

如有合适 tokenizer，可再支持 token 估算。

---

## 五、成功指标（本期验收标准）

1. [x] 系统引入统一 `PromptEnvelope` / Prompt Compiler 抽象
2. [x] 单 Agent、Planner、Solver、Critic、Examiner 至少接入统一 prompt 架构
3. [x] prompt 具备明确的 `static_prefix` / `dynamic_tail` 边界
4. [x] CLI 可 inspect 当前完整 prompt 与分层内容
5. [x] replay 或独立 artifact 中可落地 prompt 信息
6. [x] 支持项目级说明文件 `COURSE_AGENT.md` 接入
7. [x] 支持最小 prompt profiling / prompt benchmark
8. [x] README 补充 Task 017 的 prompt 架构说明
9. [x] 单测新增后，`pytest` 总数 ≥ **465 passed**
10. [x] `ruff check .` 全绿

---

## 六、技术方案

### 6.1 顶层新增结构

建议新增：

```text
course_agent/
├── prompt/
│   ├── models.py
│   ├── static_prefix.py
│   ├── dynamic_tail.py
│   ├── compiler.py
│   ├── project_instructions.py
│   └── profiling.py
docs/
└── tech_share_task017/
    ├── prompt_architecture.md
    ├── static_vs_dynamic.md
    ├── prompt_inspect_demo.md
    └── prompt_profiling_demo.md
COURSE_AGENT.md
```

### 6.2 Prompt 模型

建议最小字段：

- `role`
- `static_prefix`
- `dynamic_tail`
- `full_prompt`
- `static_hash`
- `dynamic_hash`
- `sections`
- `metadata`

### 6.3 Static Prefix 设计

建议由两层组成：

1. **Global Static Prefix**
   - 全角色共享
   - 对应 Claude Code 的“global cache”思想

2. **Role Static Prefix**
   - planner / solver / critic / examiner / react / orchestrator 各自追加少量角色约束

组合关系：

```text
global_static_prefix
+ role_static_prefix
= static_prefix
```

### 6.4 Dynamic Tail 设计

建议动态部分进一步分段：

- `env_section`
- `project_instruction_section`
- `memory_section`
- `mcp_section`
- `session_section`
- `task_section`

这样后续可以单独做：

- diff
- profiling
- selective inclusion

### 6.5 Project Instructions

建议规则：

- 先找项目根目录 `COURSE_AGENT.md`
- 可选兼容 `CLAUDE.md`
- 若两者都不存在则为空

读取内容后，进入 `project_instruction_section`。

### 6.6 Prompt Artifact / Replay

建议新增：

- `data/prompts/`

每次需要时可落地：

- `prompt_inspect.json`
- `prompt_inspect.md`

结构至少包含：

- role
- query
- static_prefix
- dynamic_tail
- full_prompt
- static_hash
- dynamic_hash
- section list

### 6.7 Prompt Profiling

建议输出：

```json
{
  "role": "solver",
  "static_chars": 18000,
  "dynamic_chars": 5200,
  "full_chars": 23200,
  "static_ratio": 0.77,
  "dynamic_ratio": 0.23
}
```

---

## 七、迁移步骤（建议顺序）

### Step 1：Prompt 基础模型
- `PromptEnvelope`
- `PromptSection`
- static / dynamic 边界定义

### Step 2：全局静态前缀
- 全局行为规则
- 工具 / Git / 输出风格约束

### Step 3：角色级静态前缀
- planner
- solver
- critic
- examiner
- react

### Step 4：动态尾部编译器
- env
- project instructions
- memory
- capability / mcp
- session
- task

### Step 5：接入现有 Agent / Runtime
- `AgentLoop`
- `ReactGraphRuntime`
- Planner / Solver / Critic / Examiner

### Step 6：Prompt CLI
- `inspect`
- `latest`
- `profile`

### Step 7：Prompt replay / docs / 回填
- README
- docs/tech_share_task017
- task_017.md 勾选

---

## 八、测试矩阵

### 8.1 新增测试文件（建议 ≥ 35 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_prompt_models.py` | PromptEnvelope / PromptSection | ≥ 4 |
| `tests/test_static_prefix.py` | 全局 / 角色静态前缀拼装 | ≥ 5 |
| `tests/test_dynamic_tail.py` | env / memory / project / session section | ≥ 6 |
| `tests/test_prompt_compiler.py` | 完整 prompt 编译 | ≥ 6 |
| `tests/test_project_instructions.py` | `COURSE_AGENT.md` / `CLAUDE.md` 读取 | ≥ 4 |
| `tests/test_cli_prompt.py` | prompt inspect / latest / profile | ≥ 5 |
| `tests/test_prompt_profiling.py` | static/dynamic profiling | ≥ 3 |
| `tests/test_prompt_integration.py` | AgentLoop / Solver / Planner 接入 | ≥ 4 |

### 8.2 回归测试

必须继续通过：

- Task 008~016 的所有测试
- 特别是：
  - `test_react_graph_runtime.py`
  - `test_cli_session.py`
  - `test_chainlit_session_view.py`
  - `test_langgraph_orchestrator.py`

### 8.3 验收门槛

- `pytest -q` ≥ **465 passed**
- `ruff check .` 全绿

---

## 九、交付物 Checklist

### 代码
- [x] `course_agent/prompt/models.py`
- [x] `course_agent/prompt/static_prefix.py`
- [x] `course_agent/prompt/dynamic_tail.py`
- [x] `course_agent/prompt/compiler.py`
- [x] `course_agent/prompt/project_instructions.py`
- [x] `course_agent/prompt/profiling.py`
- [x] `course_agent/cli.py`：新增 `prompt` 子命令
- [x] `course_agent/core/agent_loop.py`：接入统一 prompt compiler
- [x] `course_agent/agent/planner.py`：接入统一 prompt compiler
- [x] `course_agent/agent/solver.py`：接入统一 prompt compiler
- [x] `course_agent/agent/critic.py`：接入统一 prompt compiler
- [x] `course_agent/agent/examiner.py`：接入统一 prompt compiler
- [x] `course_agent/runtime/react_graph_runtime.py`：接入 prompt inspect / artifact
- [x] `COURSE_AGENT.md`

### 测试 / 配置
- [x] `tests/test_prompt_models.py`
- [x] `tests/test_static_prefix.py`
- [x] `tests/test_dynamic_tail.py`
- [x] `tests/test_prompt_compiler.py`
- [x] `tests/test_project_instructions.py`
- [x] `tests/test_cli_prompt.py`
- [x] `tests/test_prompt_profiling.py`
- [x] `tests/test_prompt_integration.py`
- [x] `pytest -q` ≥ **465 passed**（当前 `467 passed, 6 skipped`）
- [x] `ruff check .` 全绿

### 文档 / 分享素材
- [x] `README.md` 新增「🧱 Prompt Architecture」一节
- [x] `README.md` 新增「🪄 Static Prefix / Dynamic Tail」一节
- [x] `README.md` 更新 Task 017 进度行
- [x] `docs/tech_share_task017/prompt_architecture.md`
- [x] `docs/tech_share_task017/static_vs_dynamic.md`
- [x] `docs/tech_share_task017/prompt_inspect_demo.md`
- [x] `docs/tech_share_task017/prompt_profiling_demo.md`
- [x] `task/task_017.md`（本文）成功指标与交付物回填

### 验证脚本（推荐手动跑）
- [x] `course-agent prompt inspect`
- [x] `course-agent prompt inspect --role solver --query "..."`
- [x] `course-agent prompt latest`
- [x] `course-agent prompt profile`
- [x] 运行一次 chat / session 后查看 prompt artifact

---

## 十、Task 017 的教学 / 分享价值

如果说：

- Task 015 讲的是“让 graph 执行可回放、可比较、可演示”
- Task 016 讲的是“让任务有状态、可恢复、可人工介入”

那么 Task 017 讲的就是：

> **当运行时已经成熟之后，如何把模型侧的 prompt 从临时字符串升级成一套真正的平台级 Prompt Infrastructure。**

这一期很适合做更深一层的技术分享，因为它天然能讲：

### 10.1 架构层
- 为什么 prompt 需要像 runtime 一样被架构化
- 为什么 Claude Code 风格的静态 / 动态分层是有效的

### 10.2 工程层
- 如何设计 prompt compiler
- 如何统一多角色 prompt contract
- 如何把项目说明、记忆、MCP、session 都纳入动态尾部

### 10.3 演示层
- inspect 一个最终 prompt
- 展示 static prefix 与 dynamic tail
- 展示 prompt profiling
- 展示 prompt replay artifact

### 10.4 方法论层
- 从“写提示词”转向“设计 prompt system”
- 从“能回答”转向“能解释模型为什么这样回答”

---

## 十一、Task 017 完成后的预期效果

当 Task 017 完成后，Course Agent 应该不只是：

- 一个 graph-native / stateful Agent 平台
- 一个有 replay / session / HITL 的 Agent 平台

而应该成为：

> **一个支持统一 Prompt Compiler、Static Prefix / Dynamic Tail、Prompt Replay、Prompt Profiling 的 Prompt-native Agent Platform 样板。**

届时你在技术分享里可以进一步讲清楚：

1. 为什么 prompt 需要像 runtime 一样被基础设施化
2. 为什么静态前缀 / 动态尾部是高性能 Agent prompt 的关键结构
3. 为什么项目说明、记忆、MCP、session 都应该进入统一动态尾部
4. 为什么 prompt inspect / replay / profiling 会极大提升可解释性和调优效率

---

## 十二、Task 017 完成小结

本次执行完成了：

1. ✅ **Prompt 基础模型**：新增 `PromptSection`、`PromptEnvelope` 与统一哈希字段；
2. ✅ **静态前缀架构**：抽出 global static prefix 与 role static prefix，形成稳定共享层；
3. ✅ **动态尾部架构**：统一纳入环境、项目说明、memory、MCP、session、任务上下文；
4. ✅ **Prompt Compiler**：新增统一 `compile_prompt()` 入口，并支持 prompt artifact 落盘；
5. ✅ **运行时接入**：`AgentLoop`、Planner、Solver、Critic、Examiner、`ReactGraphRuntime` 全部接入统一 prompt 架构；
6. ✅ **Prompt CLI**：新增 `prompt inspect / latest / profile`，可查看完整 prompt、分层内容与 profiling 结果；
7. ✅ **项目级说明文件**：新增 `COURSE_AGENT.md`，并支持 `CLAUDE.md` fallback 读取；
8. ✅ **技术分享素材**：新增 `docs/tech_share_task017/`，沉淀 prompt architecture / inspect / profiling 演示资料；
9. ✅ **新增测试 37 个**：覆盖 prompt model、static prefix、dynamic tail、compiler、project instructions、CLI、profiling 与 integration；
10. ✅ **最终验证通过**：`uv run pytest -q` → `467 passed, 6 skipped`，`uv run ruff check .` 全绿，`prompt inspect/latest/profile` 全部可用。

当前结果已经满足 Task 017 的“Prompt-native Agent Platform”目标：

- prompt 不再是散落字符串
- static prefix 与 dynamic tail 已有明确边界
- prompt 已成为可 inspect、可复盘、可 profiling 的一等工程资产
