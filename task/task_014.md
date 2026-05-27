# Task 014：把 Course Agent 渐进迁移到 LangGraph 框架 —— LangGraph First，LangChain Compatible

> 本 Task 基于 Task 013 完成后的项目状态继续推进。
>
> 截止目前，项目已经具备：
>
> - ReAct Agent Loop
> - Tool Registry
> - Planner / Solver / Critic / Orchestrator 多 Agent 编排
> - Capability Layer（internal_tool / skill / mcp）
> - CLI / Chainlit UI / metrics / doctor / SQLite / Chroma
> - **307 passed + 6 skipped**
>
> 这说明项目已经从“一个能跑的 Agent Demo”成长为“具备多角色编排、能力扩展、可观测性、数据持久化”的完整 Agent 系统。
>
> 但与此同时，新的问题也已经开始出现：
>
> 1. **流程控制越来越重**
>    `AgentLoop`、`PlannerAgent`、`Orchestrator`、`ChainlitCallbacks`、`metrics`、`CapabilityRouter` 等模块之间已经形成了明显的工作流依赖关系；
>    这些关系目前主要靠手写 Python 控制流维护。
>
> 2. **状态流转越来越复杂**
>    现在系统里已经存在多类状态：
>    - 对话历史
>    - AgentState
>    - Orchestrator 的 sub-task / critic / refine 状态
>    - MemoryManager 的上下文增强
>    - Capability metrics / LLM metrics
>    - Chainlit session state
>
> 3. **“渐进扩展”开始遇到上限**
>    Task 013 已经引入了 Skill 和 MCP，下一步很自然会继续出现：
>    - 更复杂的 Planner → Solver → Critic → Router → Skill / MCP 路径
>    - 人工干预（HITL）
>    - 中断恢复（checkpoint）
>    - 并行子任务
>    - 可回放 trace tree
>
> 如果继续沿用“全手写编排 + 手写状态流转”的方式，项目还可以继续做，但维护成本会快速上升：
>
> - 想做 checkpoint，要自己保存状态
> - 想做 graph 可视化，要自己画流程
> - 想做人工中断，要自己处理节点暂停与恢复
> - 想做并行 fan-out，要自己管理 async task 和归并
> - 想做 trace，要自己额外埋点
>
> 所以 Task 014 的核心命题不是“把项目换个库重写一遍”，而是：
>
> > **把当前 Course Agent 的核心运行时从“手写控制流”升级为“图式编排运行时”。**
>
> 本 Task 的结论很明确：
>
> > **优先迁移到 LangGraph**
> > → **LangChain 作为模型 / Tool / Callback / Message 抽象层**
> > → **保留现有工程接口，采用双运行时并存 + 渐进替换**
>
> 也就是说：
>
> - **LangGraph 是目标运行时**
> - **LangChain 是配套基础设施**
> - **现有手写 AgentLoop / Orchestrator 不是立刻删除，而是逐步退居兼容层**
>
> 这是一个“架构升级 Task”，不是“功能堆叠 Task”。

---

## 一、当前项目现状盘点（Task 013 收尾后）

### 1.1 已有能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 / 异步 / 流式 / tool_call |
| 多 Agent | ✅ | Planner / Solver / Critic / Orchestrator |
| Capability Layer | ✅ | internal_tool / skill / mcp |
| Skill Runtime | ✅ | 本地 Skill 可注册、可调用 |
| MCP Adapter | ✅ | mock-first，可选开启 |
| Chainlit UI | ✅ | 场景切换 / Step 展示 / settings / memory |
| 记忆系统 | ✅ | 短期摘要 + 长期 Chroma |
| 可观测性 | ✅ | LLM metrics + capability metrics |
| CLI | ✅ | doctor / metrics / capabilities / skills / mcp |
| 测试质量 | ✅ | **307 passed + 6 skipped** |

### 1.2 当前最明显的架构瓶颈

| 瓶颈 | 当前状态 | 问题 |
|---|---|---|
| **流程编排全手写** | ❌ `AgentLoop` + `Orchestrator` + 各 Agent 内部控制流手写 | 越复杂越难扩展 |
| **没有图式运行时** | ❌ 无统一 graph runtime | 流程结构不可视、不可检查 |
| **没有 checkpoint / resume** | ❌ 进程中断即丢 | 长任务、人工介入、回放困难 |
| **没有节点级中断恢复** | ❌ 无 HITL 原语 | 很难做审批、人工修正 |
| **并行能力缺位** | ❌ 当前串行 | sub-task / capability fan-out 难做 |
| **消息抽象不统一** | ⚠️ 自定义 `LLMMessage` / `AgentMessage` | 与 LangChain / LangGraph 生态脱节 |
| **Tool / Capability 适配层重复** | ⚠️ 自己维护 schema、注册、调用 | 可复用现成生态但还没接 |
| **Chainlit 与 runtime 绑定较深** | ⚠️ 回调是自定义接口 | 如果要接 Graph events，需要再适配 |
| **trace 结构不统一** | ⚠️ LLM metrics 与 capability metrics 各有一套 | 没有 graph execution 级 trace |

### 1.3 为什么现在是迁移的合适时机

如果在 Task 008 时迁移，太早；
如果等到 Task 017 再迁移，太晚。

Task 014 是一个很好的窗口期，因为：

1. **核心角色已经稳定**
   Planner / Solver / Critic / Orchestrator 的职责边界已经清楚，适合映射成 graph nodes。

2. **能力层已经抽象出来**
   Tool / Skill / MCP 已经被统一为 capability，这非常适合挂到 LangChain Tool / Runnable / Node 上。

3. **可观测基础已经存在**
   metrics / doctor / Chainlit Step 都有了，迁移后只要改“数据来源”，不必从零做 UI 和运维工具。

4. **测试基线已经足够强**
   307 个通过用例意味着我们可以做“渐进迁移 + 行为对比”，而不是靠拍脑袋重构。

---

## 二、为什么是 LangGraph，而不是只上 LangChain

### 2.1 LangChain 解决什么问题

LangChain 更适合解决这些问题：

- 统一模型适配层
- 统一工具抽象
- 统一消息抽象
- 统一 callback / tracing
- LCEL / Runnable 组合
- 生态接入（retriever / tool / chat model / output parser）

### 2.2 LangGraph 解决什么问题

LangGraph 更适合解决这些问题：

- 多节点状态机
- 条件边
- 循环边（例如 Critic fail → 回 Solver）
- checkpoint / resume
- human-in-the-loop
- graph 可视化
- 并行 fan-out / map-reduce
- 可回放的运行图状态历史

### 2.3 为什么本项目“优先 LangGraph”

因为当前项目真正最痛的不是“缺一个 Tool 抽象”，而是：

> **编排复杂度已经开始超过“手写 for / while + if/else”所适合的范围。**

也就是说：

- 如果只是接一个模型，LangChain 足够
- 如果只是接几个工具，LangChain 足够
- 但现在我们已经有：
  - 多 Agent
  - capability routing
  - refine loop
  - skill / mcp
  - memory
  - streaming
  - UI callbacks
  - metrics
- 这已经明显是 **LangGraph 场景**

### 2.4 最终选择

| 方案 | 结论 |
|---|---|
| 只迁移到 LangChain，不上 LangGraph | ❌ 不够，解决不了编排复杂度核心问题 |
| 直接全面 All in LangGraph，删除旧 runtime | ❌ 风险太高，回归成本太大 |
| **LangGraph First + LangChain Compatible + 双运行时并存** | ✅ 本 Task 推荐方案 |

---

## 三、候选迁移方向（脑暴 + 打分）

| # | 方向 | 价值 | 成本 | 风险 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **消息模型迁移到 LangChain messages** | 🔥🔥🔥🔥 | 中 | 中 | ⭐⭐⭐⭐ | 是后续 graph 化的基础 |
| **2** | **Tool / Capability 迁移到 LangChain Tool 接口** | 🔥🔥🔥🔥 | 中 | 中 | ⭐⭐⭐⭐ | 能减少自维护 schema / 调用桥接 |
| **3** | **新增 LangGraph Runtime，不删旧 runtime** | 🔥🔥🔥🔥🔥 | 中 | 低 | ⭐⭐⭐⭐⭐ | 最稳妥主方案 |
| **4** | **把 Orchestrator 改成 StateGraph** | 🔥🔥🔥🔥🔥 | 中 | 低 | ⭐⭐⭐⭐⭐ | 当前最适合 graph 化的模块 |
| **5** | **把 AgentLoop 改造成 Graph ReAct Runtime** | 🔥🔥🔥🔥 | 高 | 中 | ⭐⭐⭐⭐ | 值得做，但不要一口气替换 |
| **6** | **把 memory / capability / metrics 挂到 graph events** | 🔥🔥🔥🔥 | 中 | 中 | ⭐⭐⭐⭐ | 是真正完成迁移的关键 |
| **7** | **Chainlit 直接消费 graph events** | 🔥🔥🔥 | 中 | 中 | ⭐⭐⭐ | 用户体验会更统一 |
| 8 | 一次性删除旧实现 | 🔥🔥🔥 | 高 | 高 | ⭐ | 不建议 |

### 3.1 本期聚焦

> **先把“运行时”迁过去，而不是先把所有代码风格都换掉。**

所以本期聚焦：

- LangChain 作为消息 / 工具 / 模型适配层
- LangGraph 作为图式运行时
- 优先迁移 **Orchestrator**
- 保留旧 `AgentLoop` 作为兼容 fallback
- 以“**双运行时共存**”为主，不做激进删库式重构

---

## 四、Task 014 目标（本期范围）

> **主题：把 Course Agent 的核心运行时升级为 LangGraph 图式编排运行时，LangChain 作为统一抽象层。**

### 4.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ 新增 `course_agent/runtime/langgraph_runtime.py` | ❌ 一上来删除旧 `AgentLoop` |
| ✅ 新增 `course_agent/runtime/langchain_adapters.py`：把现有 BaseLLM / Tool / Capability 适配到 LangChain 接口 | ❌ 立即全面改写所有 `tool` 装饰器和底层工具函数 |
| ✅ 新增 LangGraph 版 Orchestrator | ❌ 一次性把所有 Agent 都改成 Graph agent |
| ✅ 保留旧 `Orchestrator` 与旧 `AgentLoop`，通过配置切换 | ❌ 强制所有用户立刻迁到新 runtime |
| ✅ 优先迁移消息模型与 Tool/Capability 桥接层 | ❌ 一期内把所有 metrics / Chainlit / memory 全部重写完 |
| ✅ 配置增加 `runtime.backend = "legacy" | "langgraph"` | ❌ 删除旧 CLI / 旧 doctor / 旧 tests |
| ✅ doctor 新增第 13 项：LangGraph runtime 探活 | ❌ 把 doctor 旧项打碎重做 |
| ✅ CLI / Chainlit 能切 runtime | ❌ 强行改掉原有用户交互习惯 |
| ✅ LangGraph 版 Orchestrator 支持 checkpoint（至少 memory/sqlite saver 二选一） | ❌ 一期内直接上分布式存储 |
| ✅ 输出 graph 可视化（至少 Mermaid） | ❌ 一期内做复杂前端图谱编辑器 |

### 4.2 渐进迁移原则

#### Phase A：先“接适配层”，不改业务语义

- 现有 `BaseLLM` 保留
- 现有 Tool / Capability 保留
- 新增适配器把它们包装成 LangChain / LangGraph 可消费对象

#### Phase B：先迁 Orchestrator，不先迁一切

- `Planner → Solver → Critic → Refine` 天然是图结构
- 先把这条主链迁到 LangGraph
- 其他部分暂时照旧

#### Phase C：双运行时并存

- `legacy`：当前手写运行时
- `langgraph`：新图运行时
- 默认先保守用 `legacy`，逐步切换

#### Phase D：后续 Task 再逐步扩大

- Graph 化 ReAct AgentLoop
- Graph events 接 Chainlit
- HITL / parallel fan-out / replay / checkpoint UI

---

## 五、成功指标（本期验收标准）

1. [ ] 新增 LangGraph runtime，不破坏现有 `legacy` runtime
2. [ ] `runtime.backend=langgraph` 时，能跑通 Planner → Solver → Critic → Refine 最小闭环
3. [ ] LangGraph 版 Orchestrator 在 mock LLM 下可离线测试
4. [ ] LangGraph 版 Orchestrator 与 legacy 版行为在核心场景保持等价
5. [ ] Tool / Skill / MCP 至少能通过 LangChain Tool 适配层暴露给 LangGraph runtime
6. [ ] doctor 新增第 13 项 `LangGraph Runtime` 检查
7. [ ] CLI 可查看当前 runtime backend，且能切换或指定 backend
8. [ ] Chainlit 至少能在 orchestrator 模式下切到 LangGraph backend
9. [ ] metrics 至少能区分 `legacy` / `langgraph` backend
10. [ ] graph 可导出 Mermaid 或等价文本可视化
11. [ ] 单测新增后，`pytest` 总数 ≥ **350 passed**
12. [ ] `ruff check .` 全绿，README 补充 LangGraph 迁移说明

---

## 六、技术方案

### 6.1 顶层目标结构

建议新增：

```text
course_agent/
├── runtime/
│   ├── __init__.py
│   ├── backend.py
│   ├── langchain_adapters.py
│   ├── langgraph_runtime.py
│   ├── legacy_runtime.py
│   └── state.py
├── graph/
│   ├── __init__.py
│   ├── orchestrator_graph.py
│   ├── nodes.py
│   ├── edges.py
│   └── prompts.py
```

说明：

- `runtime/`：统一运行时入口
- `graph/`：LangGraph 节点定义与状态图逻辑
- 旧 `agent/`、`tools/`、`capabilities/` 暂不删除

### 6.2 关键设计：双运行时并存

#### 6.2.1 Backend 选择

新增配置：

```yaml
runtime:
  backend: legacy     # legacy | langgraph
  checkpoint: memory  # none | memory | sqlite
  draw_graph: true
```

或环境变量：

```bash
RUNTIME_BACKEND=langgraph
```

#### 6.2.2 统一入口

```python
class RuntimeBackend(str, Enum):
    LEGACY = "legacy"
    LANGGRAPH = "langgraph"


def create_runtime(cfg: AppConfig):
    if cfg.runtime.backend == "langgraph":
        return LangGraphRuntime(cfg)
    return LegacyRuntime(cfg)
```

这样 CLI / Chainlit / doctor 只依赖统一入口，不直接依赖具体实现。

---

### 6.3 LangChain 适配层

### 6.3.1 为什么要先有 adapters

现有工程已经有：

- `BaseLLM`
- `LLMMessage`
- `ToolRegistry`
- `CapabilityRegistry`

如果粗暴重写，会把 Task 008~013 的稳定性打掉。

所以要先做桥接层：

- `BaseLLM` -> LangChain ChatModel 适配
- `ToolRegistry` / `CapabilityRegistry` -> LangChain Tool 列表
- `LLMMessage` / `AgentMessage` -> LangChain messages

### 6.3.2 适配方向

**消息适配**
- `LLMMessage` <-> `HumanMessage / AIMessage / ToolMessage / SystemMessage`

**工具适配**
- `Tool` / `CapabilitySpec` -> `StructuredTool`

**模型适配**
- 若能直接接 LangChain 官方 `ChatOpenAI`，尽量直接接
- 若必须保留现有 `OpenAILLM` 特性，则做 `BaseChatModel` 包装器

### 6.3.3 原则

> 能直接复用 LangChain 官方组件就复用，  
> 不能直接复用再写 adapter，  
> 但**不允许为了“纯正”而牺牲现有稳定功能**。

---

### 6.4 LangGraph 版 Orchestrator

这是 Task 014 的核心。

#### 6.4.1 当前手写 Orchestrator 的天然图结构

当前逻辑其实已经是一个 graph：

```text
START
  ↓
PlannerNode
  ↓
ForEachSubTask
  ↓
SolverNode
  ↓
CriticNode
  ├─ pass=True  → NextSubTask / END
  └─ pass=False → RefineDecision
                    ├─ 未超上限 → SolverNode
                    └─ 超上限   → NextSubTask / END
```

#### 6.4.2 Graph State 设计

建议新建 `course_agent/runtime/state.py`：

```python
class GraphRuntimeState(TypedDict):
    user_task: str
    plan: list[dict[str, Any]]
    current_index: int
    current_sub_task: dict[str, Any] | None
    solver_output: str
    critic_result: dict[str, Any]
    sub_results: list[dict[str, Any]]
    refine_round: int
    total_llm_calls: int
    backend: str
    trace: list[dict[str, Any]]
```

#### 6.4.3 节点划分

- `planner_node`
- `pick_next_subtask_node`
- `solver_node`
- `critic_node`
- `refine_decision_node`
- `append_result_node`
- `finalize_node`

#### 6.4.4 条件边

- `planner_node -> pick_next_subtask_node`
- `pick_next_subtask_node -> solver_node / finalize_node`
- `solver_node -> critic_node`
- `critic_node -> refine_decision_node`
- `refine_decision_node -> solver_node / append_result_node`
- `append_result_node -> pick_next_subtask_node`

这样当前手写逻辑可以几乎 1:1 映射过去。

---

### 6.5 Checkpoint / Resume

这是 LangGraph 迁移的第一批关键收益之一。

#### 6.5.1 本期最小实现

支持：

- `InMemorySaver`（开发 / 测试）
- `SqliteSaver`（本地持久化）

#### 6.5.2 作用

- 用户页面刷新后能接着跑
- 人工中断后能恢复
- 出错后能回放状态

#### 6.5.3 原则

checkpoint 是 **runtime 层能力**，  
不是每个 Agent 自己负责存状态。

---

### 6.6 Tool / Capability 迁移策略

### 6.6.1 不推翻现有 Tool Registry

Task 014 不会删除现有：

- [tools/registry.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/tools/registry.py)
- [capabilities/registry.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/capabilities/registry.py)

而是新增 LangChain Tool 桥接：

```python
def to_langchain_tool(spec: CapabilitySpec, runtime_call: Callable[..., str]) -> BaseTool:
    ...
```

### 6.6.2 三类能力统一映射

| 原始能力 | LangChain / LangGraph 视角 |
|---|---|
| internal_tool | Tool |
| skill | Tool 或 Runnable |
| mcp | Tool |

### 6.6.3 为什么不直接把 Skill 改成 Chain

因为 Skill 当前已经是项目自己的高层能力单元，贸然改写成 LangChain Chain 会扩大迁移面。  
本期先把 Skill 视为“可调用能力节点”，不强迫其内部实现也立刻 LangChain 化。

---

### 6.7 Memory 与 Graph 的关系

当前 MemoryManager 在 `on_message` 入口前做上下文增强。  
LangGraph 化后，需要决定 Memory 放在哪一层。

### 6.7.1 本期建议

**继续保留现有 MemoryManager 作为 graph 入口前置增强层。**

也就是说：

```text
user_input
  ↓
MemoryManager.enrich_context()
  ↓
LangGraph runtime
```

原因：

- 风险最小
- 不打散现有记忆逻辑
- 先把编排 runtime 迁过去

### 6.7.2 后续再考虑

- 把 recall / remember 也变成 graph 节点
- 把压缩摘要变成 graph 后处理

---

### 6.8 Metrics 与 Tracing

### 6.8.1 本期最小目标

现有 `metrics.py` 至少新增一列或一个维度：

- `runtime_backend`: `legacy` / `langgraph`

这样可回答：

- LangGraph 是否更慢？
- LangGraph 是否 token 更高？
- LangGraph 的错误率如何？

### 6.8.2 后续潜力

如果后续接 LangSmith，可以把：

- 节点输入输出
- 条件边决策
- graph state history

统一接入 tracing 系统。

但本期不强依赖 LangSmith。

---

### 6.9 Chainlit 迁移策略

### 6.9.1 本期目标

Chainlit 不直接感知“所有图细节”，只做最小适配：

- 根据 runtime backend 选择 `legacy` 或 `langgraph`
- orchestrator 模式下支持 LangGraph runtime
- 至少能展示关键节点执行信息

### 6.9.2 不做的事

- 不在本期开发完整 graph 可视化前端
- 不要求 Chainlit 直接展示整个状态图

---

### 6.10 CLI / doctor 迁移策略

### 6.10.1 CLI

新增或扩展：

```bash
course-agent runtime
course-agent runtime --backend langgraph
course-agent graph
```

功能建议：

- `runtime`：显示当前 backend、checkpoint 模式
- `graph`：输出 orchestrator graph 的 Mermaid 文本

### 6.10.2 doctor 第 13 项

新增：

- LangGraph 依赖是否可导入
- LangGraph runtime 是否能实例化
- mock 路径下是否能跑最小 graph roundtrip
- checkpoint saver 是否可用（至少 memory / sqlite 一种）

---

## 七、迁移步骤（建议顺序）

### Step 1：配置与依赖
- `pyproject.toml` 新增 `langchain` / `langgraph`
- `config.py` + `config/default.yaml` 增加 `runtime` 配置

### Step 2：LangChain 适配层
- `langchain_adapters.py`
- message / tool / capability / llm 桥接

### Step 3：LangGraph State + Nodes
- `state.py`
- `nodes.py`
- `edges.py`

### Step 4：LangGraph 版 Orchestrator
- 先完成 Planner → Solver → Critic → Refine 闭环
- 先不碰记忆、Chainlit 深度集成

### Step 5：双运行时入口
- `legacy_runtime.py`
- `langgraph_runtime.py`
- `backend.py`

### Step 6：CLI + doctor + metrics
- runtime 切换
- graph 导出
- doctor 第 13 项
- metrics 增加 backend 维度

### Step 7：Chainlit 集成
- orchestrator 模式支持切 LangGraph backend
- 最小事件展示

### Step 8：测试 + README + 勾选
- 行为等价测试
- mock graph 测试
- 回归测试
- 文档更新

---

## 八、与 Task 013 的关系

### 8.1 Task 013 不会被推翻

Task 013 引入的这些成果会被保留：

- Capability Layer
- Skill Runtime
- MCP Adapter
- capability metrics
- CLI capabilities / skills / mcp

Task 014 不是替代它们，而是把它们放到新的运行时之下。

### 8.2 Capability Layer 会变得更重要

因为 LangGraph 节点并不关心底层来源是 Tool / Skill / MCP，  
它只关心：

- 节点要调用什么能力
- 输入输出是什么
- 结果如何写回状态

Task 013 的能力抽象，正好是 Task 014 迁移的关键前置条件。

---

## 九、渐进式路线图（Task 014 之后）

### 9.1 Task 014（本期）
- LangGraph Runtime
- LangChain Adapter
- Graph 版 Orchestrator
- 双运行时并存

### 9.2 Task 015（建议后续）
> **Graph-native AgentLoop：把单 Agent ReAct 也迁到 LangGraph**

- 让 `chat` 模式也走 graph runtime
- 把 tool_call loop graph 化
- 统一 legacy / graph 行为语义

### 9.3 Task 016（建议后续）
> **Checkpoint / HITL / Replay**

- 人工中断恢复
- 审批节点
- graph 状态回放
- 历史执行树调试

### 9.4 Task 017（建议后续）
> **并行 Graph + 更深的 LangSmith / tracing 集成**

- parallel sub-tasks
- capability fan-out
- graph execution tracing
- backend 性能画像

---

## 十、测试矩阵

### 10.1 新增测试文件（建议 ≥ 45 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_langchain_adapters.py` | message/tool/capability/llm 适配 | ≥ 8 |
| `tests/test_langgraph_state.py` | graph state 初始化 / 更新 | ≥ 5 |
| `tests/test_langgraph_orchestrator.py` | graph 版最小闭环 / refine / 上限控制 | ≥ 10 |
| `tests/test_runtime_backend.py` | backend 切换 / 默认值 / 配置读取 | ≥ 5 |
| `tests/test_cli_runtime.py` | runtime / graph CLI | ≥ 5 |
| `tests/test_cli_doctor_13.py` | doctor 第 13 项 | ≥ 4 |
| `tests/test_metrics_runtime_backend.py` | metrics 区分 legacy/langgraph | ≥ 4 |
| `tests/test_chainlit_runtime_switch.py` | Chainlit orchestrator backend 切换 | ≥ 4 |

### 10.2 回归测试

必须继续通过：

- Task 008~013 的现有 307 个通过用例
- 尤其是：
  - `test_orchestrator.py`
  - `test_orchestrator_capabilities.py`
  - `test_solver.py`
  - `test_planner.py`
  - `test_cli_doctor_11.py`
  - `test_cli_doctor_12.py`

### 10.3 验收门槛

- `pytest -q` ≥ **350 passed**
- `ruff check .` 全绿

---

## 十一、交付物 Checklist

### 代码
- [ ] `course_agent/runtime/__init__.py`
- [ ] `course_agent/runtime/backend.py`
- [ ] `course_agent/runtime/langchain_adapters.py`
- [ ] `course_agent/runtime/langgraph_runtime.py`
- [ ] `course_agent/runtime/legacy_runtime.py`
- [ ] `course_agent/runtime/state.py`
- [ ] `course_agent/graph/__init__.py`
- [ ] `course_agent/graph/orchestrator_graph.py`
- [ ] `course_agent/graph/nodes.py`
- [ ] `course_agent/graph/edges.py`
- [ ] `course_agent/graph/prompts.py`
- [ ] [config.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/config.py)：新增 runtime 配置
- [ ] [cli.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/cli.py)：新增 runtime / graph / doctor 第 13 项
- [ ] [ui/chainlit_app.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/ui/chainlit_app.py)：orchestrator 模式支持 runtime backend 切换
- [ ] [observability/metrics.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/observability/metrics.py)：增加 `runtime_backend` 维度
- [ ] [agent/orchestrator.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/agent/orchestrator.py)：作为 legacy 保留或桥接导出

### 测试 / 配置
- [ ] `tests/test_langchain_adapters.py`
- [ ] `tests/test_langgraph_state.py`
- [ ] `tests/test_langgraph_orchestrator.py`
- [ ] `tests/test_runtime_backend.py`
- [ ] `tests/test_cli_runtime.py`
- [ ] `tests/test_cli_doctor_13.py`
- [ ] `tests/test_metrics_runtime_backend.py`
- [ ] `tests/test_chainlit_runtime_switch.py`
- [ ] `pytest -q` ≥ **350 passed**
- [ ] `ruff check .` 全绿

### 文档
- [ ] `README.md` 新增「🕸️ LangGraph Runtime」一节
- [ ] `README.md` 新增「🔗 LangChain Adapter Layer」一节
- [ ] `README.md` 新增「🔁 双运行时（legacy / langgraph）」一节
- [ ] `README.md` 进度表添加 Task 014 行；doctor 12 → **13 项**；测试数 307 → **≥ 350**
- [ ] `README.md` 项目结构补 `runtime/`、`graph/`
- [ ] `task/task_014.md`（本文）成功指标与交付物全勾

### 验证脚本（推荐手动跑）
- [ ] `course-agent runtime`
- [ ] `course-agent graph`
- [ ] `course-agent doctor` → 13/13
- [ ] Chainlit 切到 langgraph backend 后跑通复杂任务模式
- [ ] Mermaid graph 可导出并可读

---

## 十二、教学性总结：为什么 Task 014 是“Agent Demo → Agent Runtime”的拐点

Task 008~013 的连续迭代，让项目学会了：

1. 动手做事
2. 记忆与检索
3. 多 Agent 分工
4. 能力扩展（Skill / MCP）
5. 可观测性

但这些能力目前仍然跑在一个**手写控制流运行时**上。

Task 014 的价值，不在于“换一个流行库”，而在于：

> **把项目从“写了一堆 Agent 逻辑”升级为“拥有统一图式运行时的 Agent 系统”。**

这会带来三个层面的跃迁：

### 12.1 架构层
- 从函数式控制流升级为图式编排
- 从隐式状态流升级为显式状态图
- 从手写循环升级为可检查、可恢复、可回放的 runtime

### 12.2 工程层
- checkpoint / resume 更容易做
- HITL 更容易做
- parallel 更容易做
- graph trace 更容易做

### 12.3 教学层
Task 014 非常适合让学生理解：

- 什么是 LangChain，什么是 LangGraph
- 为什么简单 Agent 可以手写，复杂 Agent 更适合 graph runtime
- 为什么“能跑”与“可扩展、可维护、可恢复”是两回事

如果说：

- Task 012 是让 Agent 学会“分工合作”
- Task 013 是让 Agent 学会“借外脑”

那么 Task 014 的意义就是：

> **让这套 Agent 系统拥有一套真正能承载复杂工作流的运行时骨架。**