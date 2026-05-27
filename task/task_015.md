# Task 015：把 Course Agent 从“能跑的 LangGraph Runtime”推进到“可演示、可回放、可度量的 Graph-native Agent 平台”

> 本 Task 基于 Task 014 完成后的项目状态继续推进。
>
> 截止目前，项目已经具备：
>
> - ReAct Agent Loop
> - Planner / Solver / Critic / Orchestrator 多 Agent 编排
> - Capability Layer（internal_tool / skill / mcp）
> - LangGraph Runtime（Orchestrator 已 graph 化）
> - LangChain Adapter Layer
> - CLI / Chainlit UI / metrics / doctor / SQLite / Chroma
> - **357 passed + 6 skipped**
>
> 这意味着项目已经不再只是“一个带工具调用的聊天 Demo”，而是已经拥有：
>
> - 多角色协作能力
> - 图式运行时能力
> - 可观测性能力
> - 可扩展能力层
> - 一套可以持续演进的工程骨架
>
> 但是，如果接下来要做一次**技术分享**，或者要把项目往“更像一个真正的 Agent Platform”推进，现阶段还存在一个明显问题：
>
> > **Task 014 解决了“Orchestrator graph 化”，但还没有把整个项目提升到“Graph-native 平台”层面。**
>
> 换句话说，当前项目已经有了 LangGraph，但它还主要承担：
>
> - Orchestrator 这条主编排链
> - backend 切换入口
> - graph 导出与基础 checkpoint
>
> 而以下这些更适合拿来做**技术深度展示**、也更能体现“架构成熟度”的部分，仍然没有真正补齐：
>
> 1. **单 Agent 主链仍然主要停留在 legacy ReAct AgentLoop**
>    `chat` 模式、日常对话模式、本地工具调用模式，本质上还是旧的 loop 驱动。
>
> 2. **Graph events 还没有成为统一的前端事件源**
>    Chainlit 现在能切换 backend，但还不能把 graph 执行事件作为一等公民来展示。
>
> 3. **缺少 replay / trace export / benchmark**
>    现在能运行，但还不够“可讲”、“可分析”、“可比较”。
>    对技术分享来说，这三件事非常重要：
>    - 能回放
>    - 能对比
>    - 能量化
>
> 4. **checkpoint 只是“可用”，还不是“产品级可操作”**
>    有 memory / sqlite saver，但没有明确的 resume / inspect / replay 路径。
>
> 5. **Graph runtime 的工程价值还没被充分展示出来**
>    也就是说，现在我们能说“项目已经接入 LangGraph”，但还不够有说服力地展示：
>    - 为什么 graph-native 比 legacy 更适合复杂 Agent
>    - 为什么这套架构在工程上更强
>    - 为什么它对后续 HITL / replay / benchmark / 并行扩展更有利
>
> 所以 Task 015 的核心命题不是“再多堆几个功能”，而是：
>
> > **把当前的 Course Agent 从“已经接入 LangGraph”升级为“真正以 Graph 为核心运行范式的 Agent 平台”。**
>
> 本 Task 的结论也很明确：
>
> > **Task 015 的重点是：Graph-native AgentLoop + Graph Events + Replay / Benchmark / Demo Assets**
>
> 这不仅是对项目技术深度的继续完善，
> 也会直接生成一套适合做**技术分享、架构讲解、演示对比**的材料与能力。

---

## 一、当前项目现状盘点（Task 014 收尾后）

### 1.1 已有能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 / 异步 / 流式 / tool_call |
| 多 Agent 编排 | ✅ | Planner / Solver / Critic / Orchestrator |
| Capability Layer | ✅ | internal_tool / skill / mcp |
| LangGraph Runtime | ✅ | Orchestrator 已 graph 化 |
| LangChain Adapter Layer | ✅ | message / tool / capability / chat model 桥接 |
| CLI | ✅ | runtime / graph / doctor / metrics / capabilities / skills / mcp |
| Chainlit | ✅ | 场景切换 / orchestrator backend 切换 |
| metrics | ✅ | 支持 `runtime_backend` 维度 |
| graph 导出 | ✅ | Mermaid 可导出 |
| checkpoint | ✅ | memory / sqlite 基础能力 |
| 测试质量 | ✅ | **357 passed + 6 skipped** |

### 1.2 当前技术层面的剩余短板

| 方向 | 当前状态 | 问题 |
|---|---|---|
| **单 Agent 仍非 graph-native** | ⚠️ 主要还是 `AgentLoop` 驱动 | 架构叙事不统一 |
| **前端事件源不统一** | ⚠️ Chainlit 仍以 callbacks 为主 | Graph 价值展示不够直观 |
| **没有 replay CLI / trace export** | ❌ 缺失 | 无法复盘一次 graph 执行 |
| **没有 benchmark 套件** | ❌ 缺失 | 无法对比 legacy vs langgraph |
| **没有 demo assets** | ⚠️ 只有运行能力 | 技术分享时不够“成体系” |
| **checkpoint 缺少 inspect / resume 入口** | ⚠️ 底层可用 | 上层不可操作 |
| **Graph trace 未沉淀为结构化工件** | ⚠️ 只有轻量 trace/state | 难做分析与可视化 |

### 1.3 为什么 Task 015 很适合做“技术分享版升级”

因为 Task 014 已经把最危险的一步走完了：

- 运行时入口已经统一
- LangGraph 已经不再是“概念”
- 项目已有足够强的回归测试
- README / CLI / doctor / metrics 已经形成工程闭环

这意味着 Task 015 不必再解释“为什么要迁移”，
而可以开始解释更高级的问题：

1. **如何把 AgentLoop 也 graph-native 化**
2. **如何把 graph execution 变成真正可展示、可分析的资产**
3. **如何用 benchmark 证明架构升级的工程价值**
4. **如何把一次技术分享，做成“代码 + 演示 + 数据 + 图谱”四位一体**

---

## 二、Task 015 的核心目标

> **主题：把 Course Agent 升级为一个真正可演示、可回放、可比较、可复盘的 Graph-native Agent 平台。**

这一期不再只关心“功能有没有”，而更关心：

- 架构是否统一
- 运行时是否可解释
- 执行过程是否可回放
- 新旧架构是否可量化对比
- 是否能支撑一次像样的技术分享

### 2.1 本期聚焦

本期聚焦以下四件事：

1. **Graph-native AgentLoop**
   把当前单 Agent ReAct 主链迁成 LangGraph 版本，至少让 `chat` 模式可切到 graph runtime。

2. **Graph Events & Replay**
   把 graph 执行过程输出为结构化 trace / replay artifact，可在 CLI 或文件中查看。

3. **Benchmark & Compare**
   新增 legacy vs langgraph 的离线 benchmark / smoke compare，量化延迟、步骤数、调用数。

4. **Tech-share Assets**
   为后续技术分享准备：
   - Mermaid 图
   - 运行时对比表
   - 演示脚本
   - replay 样例
   - benchmark 输出样例

### 2.2 本期不做什么

| 做 | 不做 |
|---|---|
| ✅ Graph-native 单 Agent 主链 | ❌ 一次性删除旧 `AgentLoop` |
| ✅ replay / inspect / export | ❌ 上来就做复杂前端 trace 可视化系统 |
| ✅ benchmark / compare CLI | ❌ 做大规模性能压测平台 |
| ✅ Chainlit 最小 graph event 展示 | ❌ 重写整个 UI 交互框架 |
| ✅ 为技术分享沉淀 demo assets | ❌ 一期内做生产级 HITL 审批后台 |

---

## 三、为什么 Task 015 值得做

### 3.1 从“接入框架”到“掌控运行时”

Task 014 的重点是：

> “接入 LangGraph，并让 Orchestrator 跑在图上。”

Task 015 的重点则是：

> “让项目的核心运行范式真正围绕 Graph 展开，并让 Graph execution 变成工程资产。”

这两者的差别非常大：

- Task 014 偏“架构切换”
- Task 015 偏“平台成熟度”

### 3.2 对技术分享最有帮助的，不是多一个功能，而是多一组“证据”

技术分享时最怕的是：

- 只有架构图，没有真实运行结果
- 只有 demo，没有工程对比
- 只有功能，没有数据
- 只有代码，没有可复盘资产

Task 015 要补的就是这些“证据”：

- 一次 graph 的 replay 文件
- 一次 legacy vs langgraph 的 benchmark 对比
- 一份 graph-native AgentLoop 的 Mermaid 图
- 一组 CLI 命令，现场能直接跑出来

### 3.3 这会让项目从“好看”变成“有说服力”

因为你后面在讲这个项目时，就不只是说：

- “我们用了 LangGraph”

而是可以说：

- “我们把单 Agent 和多 Agent 都纳入统一 graph runtime”
- “我们能导出 execution graph 和 replay artifact”
- “我们能做 legacy / langgraph 行为和成本对比”
- “我们能在 CLI / UI / doctor / metrics / benchmark 里形成闭环”

这就不是“接了个框架”，而是“做了一套运行时工程升级”。

---

## 四、Task 015 目标（本期范围）

### 4.1 Graph-native AgentLoop

新增 graph 版单 Agent ReAct Runtime，目标是让当前 `chat` 模式也可以走 LangGraph。

建议路径：

- 保留旧 `AgentLoop`
- 新增 graph 版 `react_graph_runtime.py` 或等价模块
- 通过 `runtime.backend` 或更细粒度的 `runtime.agent_loop_backend` 切换

最小目标：

```text
START
  ↓
PrepareContext
  ↓
LLMNode
  ├─ 有 tool_calls → ToolNode → LLMNode
  └─ 无 tool_calls → Finalize
```

### 4.2 Graph Events / Trace / Replay

新增统一执行产物导出：

- `trace.json`
- `state_history.json`
- `replay.md` 或 `replay.json`

要求至少包含：

- thread_id
- backend
- 节点执行顺序
- 每步输入摘要
- 每步输出摘要
- 条件边决策
- 最终答案摘要

### 4.3 Benchmark / Compare

新增 CLI：

```bash
course-agent benchmark runtime
course-agent benchmark runtime --backend legacy
course-agent benchmark runtime --backend langgraph
course-agent benchmark compare
```

至少支持：

- mock LLM 下稳定离线跑
- 比较 legacy / langgraph
- 输出：
  - 总耗时
  - LLM 调用数
  - tool 调用数
  - graph 节点数 / step 数

### 4.4 Demo Assets

新增 `docs/tech_share_task015/` 或等价目录，沉淀：

- `architecture_overview.md`
- `graph_vs_legacy.md`
- `demo_queries.md`
- `benchmark_sample.md`
- `replay_sample.md`

这部分不是“附属品”，而是本 Task 的明确交付物。

---

## 五、成功指标（本期验收标准）

1. [x] 单 Agent `chat` 模式可切到 graph-native runtime
2. [x] graph-native AgentLoop 在 mock LLM 下可离线测试
3. [x] graph-native AgentLoop 与 legacy AgentLoop 在核心场景行为大体等价
4. [x] CLI 可导出 graph execution trace / replay artifact
5. [x] CLI 可运行 benchmark，并输出 legacy / langgraph 对比结果
6. [x] Chainlit 至少能展示关键 graph event 或 replay 摘要
7. [x] README 补充 Task 015 的技术亮点与分享视角说明
8. [x] 新增技术分享素材目录或等价文档集合
9. [x] 单测新增后，`pytest` 总数 ≥ **395 passed**
10. [x] `ruff check .` 全绿

---

## 六、技术方案

### 6.1 顶层新增结构

建议新增：

```text
course_agent/
├── runtime/
│   ├── react_graph_runtime.py
│   ├── replay.py
│   └── benchmark.py
├── graph/
│   ├── react_graph.py
│   ├── react_nodes.py
│   └── trace.py
docs/
└── tech_share_task015/
    ├── architecture_overview.md
    ├── graph_vs_legacy.md
    ├── demo_queries.md
    ├── benchmark_sample.md
    └── replay_sample.md
```

说明：

- `react_graph_runtime.py`：graph-native 单 Agent 运行时
- `replay.py`：trace / replay artifact 导出
- `benchmark.py`：运行时 benchmark 逻辑
- `react_graph.py`：单 Agent ReAct 图
- `trace.py`：graph 事件标准化与结构化导出

### 6.2 Graph-native ReAct Runtime

#### 6.2.1 当前单 Agent 的天然图结构

现在的 `AgentLoop` 本质上也是一个 graph：

```text
START
  ↓
BuildMessages
  ↓
LLM
  ├─ tool_calls → ExecuteTools → AppendToolMessages → LLM
  └─ final_answer → END
```

所以 Task 015 的一个核心动作，就是把这个隐式 loop 显式 graph 化。

#### 6.2.2 状态设计建议

建议新增 `ReactGraphState`：

```python
class ReactGraphState(TypedDict):
    user_input: str
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    final_answer: str
    steps: int
    max_steps: int
    backend: str
    trace: list[dict[str, Any]]
```

#### 6.2.3 节点划分

- `prepare_context_node`
- `llm_node`
- `tool_node`
- `finalize_node`

#### 6.2.4 条件边

- `prepare_context_node -> llm_node`
- `llm_node -> tool_node / finalize_node`
- `tool_node -> llm_node`

---

### 6.3 Trace / Replay 设计

### 6.3.1 目标

把“运行过一次”从瞬时行为，变成可沉淀资产。

建议统一导出结构：

```json
{
  "thread_id": "...",
  "backend": "langgraph",
  "runtime_kind": "react_graph",
  "input": "...",
  "steps": [
    {
      "node": "llm",
      "kind": "model_call",
      "summary": "...",
      "ts": 1234567890.0
    }
  ],
  "final_answer": "..."
}
```

### 6.3.2 CLI 形态

建议新增：

```bash
course-agent replay latest
course-agent replay show path/to/replay.json
course-agent replay export --format json
```

### 6.3.3 原则

- replay 是 runtime 层统一能力
- 不让每个 Agent 自己定义 replay 格式
- 不和 Chainlit UI 强绑定

---

### 6.4 Benchmark 设计

### 6.4.1 为什么必须做

因为一旦进入技术分享阶段，最容易被问的问题就是：

- LangGraph 到底比 legacy 好在哪？
- 会不会更慢？
- 会不会步骤更多？
- 工程复杂度值不值得？

如果没有 benchmark，这些回答就会变成“感觉上更好”。

### 6.4.2 Benchmark 的最小维度

至少比较：

- 总耗时
- LLM 调用数
- Tool 调用数
- 节点执行数
- 最终结果摘要

### 6.4.3 Benchmark 原则

- 优先 mock-first，确保 CI 可稳定跑
- 可以额外支持真实 LLM smoke benchmark，但不能成为默认门槛

---

### 6.5 Chainlit 集成策略

### 6.5.1 本期目标

Chainlit 不需要一下子完全 graph-native，但要做到：

- graph 模式下显示当前 backend
- 至少展示 graph 执行摘要
- 能附加 replay 链接 / trace 摘要 / 节点数信息

### 6.5.2 最小展示形式

例如在回答后追加一个可折叠 Step：

- backend: `langgraph`
- runtime: `react_graph`
- nodes: `prepare_context -> llm -> tool -> llm -> finalize`
- total steps: `4`

---

### 6.6 技术分享资产设计

这一部分是 Task 015 的特色。

它不是传统任务里“顺手写点文档”，而是明确为了技术分享服务。

建议沉淀为 5 份文档：

1. `architecture_overview.md`
   - 项目从 Task 012 → 013 → 014 → 015 的架构演进

2. `graph_vs_legacy.md`
   - 为什么 graph-native 更适合复杂 Agent

3. `demo_queries.md`
   - 演示时现场可直接输入的 query 清单

4. `benchmark_sample.md`
   - benchmark 输出样例与解释

5. `replay_sample.md`
   - 一次典型 graph execution 的 replay 样例

---

## 七、迁移步骤（建议顺序）

### Step 1：Graph-native 单 Agent 运行时设计
- 梳理 `AgentLoop` 当前主循环
- 设计 `ReactGraphState`
- 拆出 graph 节点与条件边

### Step 2：接入统一 runtime 入口
- 让 `chat` 模式可切 graph-native runtime
- 保留 legacy fallback

### Step 3：结构化 trace / replay
- 定义 replay artifact schema
- 增加 CLI 导出与查看命令

### Step 4：benchmark
- 增加 benchmark runtime / compare CLI
- 输出 legacy / langgraph 比较结果

### Step 5：Chainlit 最小展示
- 显示 graph backend
- 显示 graph 执行摘要

### Step 6：技术分享素材沉淀
- docs/tech_share_task015/
- demo queries
- benchmark sample
- replay sample

### Step 7：测试 + README + 勾选
- 行为等价测试
- replay / benchmark 测试
- 文档更新

---

## 八、测试矩阵

### 8.1 新增测试文件（建议 ≥ 38 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_react_graph_runtime.py` | graph-native chat 主链 | ≥ 8 |
| `tests/test_react_graph_nodes.py` | llm/tool/finalize 节点 | ≥ 6 |
| `tests/test_replay_export.py` | replay artifact 导出/读取 | ≥ 5 |
| `tests/test_cli_replay.py` | replay CLI | ≥ 4 |
| `tests/test_cli_benchmark.py` | benchmark / compare CLI | ≥ 5 |
| `tests/test_runtime_compare.py` | legacy vs langgraph 行为比较 | ≥ 4 |
| `tests/test_chainlit_graph_events.py` | Chainlit graph event 展示 | ≥ 3 |
| `tests/test_trace_schema.py` | trace schema / 序列化 | ≥ 3 |

### 8.2 回归测试

必须继续通过：

- Task 008~014 已有全部测试
- 尤其是：
  - `test_agent_loop.py`
  - `test_agent_loop_async.py`
  - `test_langgraph_orchestrator.py`
  - `test_runtime_backend.py`
  - `test_cli_runtime.py`
  - `test_cli_doctor_13.py`

### 8.3 验收门槛

- `pytest -q` ≥ **395 passed**
- `ruff check .` 全绿

---

## 九、交付物 Checklist

### 代码
- [x] `course_agent/runtime/react_graph_runtime.py`
- [x] `course_agent/runtime/replay.py`
- [x] `course_agent/runtime/benchmark.py`
- [x] `course_agent/graph/react_graph.py`
- [x] `course_agent/graph/react_nodes.py`
- [x] `course_agent/graph/trace.py`
- [x] `course_agent/cli.py`：新增 replay / benchmark 命令
- [x] `course_agent/ui/chainlit_app.py`：新增 graph event / replay 摘要展示
- [x] `course_agent/config.py`：新增 Task 015 所需 graph runtime 细粒度配置

### 测试 / 配置
- [x] `tests/test_react_graph_runtime.py`
- [x] `tests/test_react_graph_nodes.py`
- [x] `tests/test_replay_export.py`
- [x] `tests/test_cli_replay.py`
- [x] `tests/test_cli_benchmark.py`
- [x] `tests/test_runtime_compare.py`
- [x] `tests/test_chainlit_graph_events.py`
- [x] `tests/test_trace_schema.py`
- [x] `pytest -q` ≥ **395 passed**（当前 `396 passed, 6 skipped`）
- [x] `ruff check .` 全绿

### 文档 / 分享素材
- [x] `README.md` 新增「📈 Benchmark / Compare」一节
- [x] `README.md` 新增「🔁 Replay / Trace Export」一节
- [x] `README.md` 更新 Task 015 进度行与测试状态
- [x] `docs/tech_share_task015/architecture_overview.md`
- [x] `docs/tech_share_task015/graph_vs_legacy.md`
- [x] `docs/tech_share_task015/demo_queries.md`
- [x] `docs/tech_share_task015/benchmark_sample.md`
- [x] `docs/tech_share_task015/replay_sample.md`
- [x] `task/task_015.md`（本文）成功指标与交付物回填

### 验证脚本（推荐手动跑）
- [x] `course-agent chat "..." --backend langgraph`
- [x] `course-agent replay latest`
- [x] `course-agent benchmark runtime`
- [x] `course-agent benchmark compare`
- [x] Chainlit graph 模式下展示关键 event / replay 摘要

---

## 十、Task 015 的教学 / 分享价值

如果说：

- Task 012 讲的是“多 Agent 分工”
- Task 013 讲的是“能力扩展”
- Task 014 讲的是“图式运行时迁移”

那么 Task 015 讲的就是：

> **当一个 Agent 项目已经跑起来之后，如何把它进一步升级成一个“可解释、可比较、可演示”的工程化平台。**

这一期非常适合做技术分享，因为它天然能讲四层内容：

### 10.1 架构层
- 为什么 single-agent / multi-agent 都应该统一到 graph runtime
- 为什么 replay / trace / benchmark 是运行时成熟度的重要标志

### 10.2 工程层
- 如何设计统一 trace schema
- 如何做 legacy vs langgraph 的 benchmark compare
- 如何让 CLI / UI / docs 使用同一套 runtime 资产

### 10.3 演示层
- 现场跑一条 query
- 导出 graph
- 展示 replay
- 展示 benchmark compare

### 10.4 方法论层
- 从“功能迭代”转向“平台化建设”
- 从“能跑”转向“可解释、可复盘、可证明”

---

## 十一、Task 015 完成后的预期效果

当 Task 015 完成后，Course Agent 应该不只是：

- 一个能做题的 Agent
- 一个有多角色编排的 Agent
- 一个接入了 LangGraph 的 Agent

而应该成为：

> **一个具有 graph-native 单 / 多 Agent 运行时、支持 replay / benchmark / compare、并且可以直接拿来做技术分享的 Agent Platform 样板。**

届时你在技术分享里可以更完整地讲清楚：

1. 这个项目从哪一步开始不再是 Demo
2. 为什么 runtime 设计是 Agent 工程化的关键
3. 为什么 graph-native 比手写 loop 更适合复杂系统
4. 为什么 replay / benchmark / trace 能显著提升说服力

---

## 十二、Task 015 完成小结

本次执行完成了：

1. ✅ **Graph-native 单 Agent Runtime**：新增 `ReactGraphRuntime`，`chat` 模式支持 `--backend langgraph`；
2. ✅ **统一 chat runtime 入口**：新增 `create_chat_runtime(...)`，Chainlit 与 CLI 共享同一接入点；
3. ✅ **Replay / Trace Export**：新增 `replay.py` 与 `graph/trace.py`，每次 graph-native chat 会落地 replay artifact；
4. ✅ **Benchmark / Compare**：新增 `benchmark runtime` / `benchmark compare` CLI，可对比 `legacy` 与 `langgraph`；
5. ✅ **Chainlit 最小 graph 摘要展示**：react graph 模式下会渲染 `Graph Runtime` Step，显示 backend / runtime / nodes / replay path；
6. ✅ **技术分享素材**：新增 `docs/tech_share_task015/` 目录，沉淀架构演进、demo queries、benchmark 样例、replay 样例；
7. ✅ **新增测试 39 个**：覆盖 react graph runtime、节点、replay、benchmark、CLI、Chainlit graph events、trace schema；
8. ✅ **最终验证通过**：`uv run pytest -q` → `396 passed, 6 skipped`，`uv run ruff check .` 全绿；
9. ✅ **README 收口**：新增 Benchmark / Replay 章节，并同步更新测试状态和项目结构。

当前结果已经满足 Task 015 的“技术分享版升级”目标：

- 不仅能讲 LangGraph
- 还能讲 graph-native AgentLoop
- 能展示 replay artifact
- 能展示 benchmark compare
- 能把架构、运行、数据、演示材料串成一套完整故事
