# Task 016：把 Course Agent 从“可演示的 Graph-native Agent 平台”推进到“可恢复、可中断、可人工介入的 Stateful Agent Platform”

> 本 Task 基于 Task 015 完成后的项目状态继续推进。
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
> - Chainlit 中的最小 graph runtime 摘要展示
> - 技术分享素材目录
> - **396 passed + 6 skipped**
>
> 这说明项目已经完成了从“普通 Agent 工程”到“Graph-native Agent 平台”的第一轮升级。
>
> 但如果继续往真正的平台能力推进，现在还有一个更本质的短板：
>
> > **系统已经可回放、可比较、可演示，但还不是真正“可持续执行”的 Stateful Agent Platform。**
>
> 换句话说，Task 015 解决了这些问题：
>
> - graph runtime 跑起来了
> - 单 Agent / 多 Agent 都有图式表达
> - 可以导出 replay
> - 可以做 runtime compare
> - 可以拿来做技术分享
>
> 但以下这些在更真实的 Agent 平台里非常关键的能力，还没有真正补齐：
>
> 1. **没有“中断后恢复”的上层产品化路径**
>    当前虽然底层有 checkpoint / replay / thread_id 概念，但还没有形成：
>    - inspect
>    - resume
>    - continue
>    - 从某一步恢复执行
>
> 2. **没有“人工介入（HITL）”的明确停靠点**
>    现在 graph 是自动执行完的，缺少：
>    - 等待确认
>    - 等待补充输入
>    - 等待审批
>    - 人工纠错再继续
>
> 3. **没有“长任务 / 多轮任务”的状态生命周期管理**
>    现在 replay 更像一次性 artifact，而不是一个活的 execution session。
>
> 4. **还没有“任务中心 / session 中心”的抽象**
>    目前用户还是：
>    - 发一个 query
>    - Agent 给一个 answer
>
>    但真实平台更像：
>
>    - 创建一个任务
>    - 任务进入执行态
>    - 过程中暂停、恢复、人工修改、继续运行
>    - 最后任务归档并可复盘
>
> 5. **Chainlit 目前还不是“状态化任务界面”**
>    它已经能展示 graph summary，但还不能真正承载：
>    - paused task
>    - pending approval
>    - waiting for human input
>    - resume latest task
>
> 所以 Task 016 的核心命题，不再是：
>
> - “怎么把 Agent 跑在图上”
> - “怎么把运行过程导出来”
>
> 而是：
>
> > **怎么把一次 graph 执行，升级成一个可持久化、可恢复、可人工介入的状态化任务。**
>
> 这意味着项目要从：
>
> - Graph-native Agent Platform
>
> 继续演进为：
>
> - Stateful Agent Platform
>
> 也就是说，Task 016 的核心重点会转向：
>
> > **Session / Resume / Human-in-the-loop / Task Lifecycle**

---

## 一、当前项目现状盘点（Task 015 收尾后）

### 1.1 已有能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 单 Agent legacy loop | ✅ | `AgentLoop` |
| 单 Agent graph-native loop | ✅ | `ReactGraphRuntime` |
| 多 Agent graph runtime | ✅ | `LangGraphRuntime` |
| Capability Layer | ✅ | internal_tool / skill / mcp |
| Replay / Trace Export | ✅ | 单 Agent graph replay 已可导出 |
| Benchmark / Compare | ✅ | legacy vs langgraph chat runtime |
| Chainlit graph 摘要 | ✅ | 最小 graph runtime Step 展示 |
| 技术分享素材 | ✅ | docs/tech_share_task015 |
| 测试质量 | ✅ | **396 passed + 6 skipped** |

### 1.2 当前剩余短板

| 方向 | 当前状态 | 问题 |
|---|---|---|
| **Resume / Continue** | ⚠️ 底层有 checkpoint | 上层没有可操作入口 |
| **HITL** | ❌ 缺失 | 没有等待人工确认节点 |
| **Task Lifecycle** | ❌ 缺失 | 没有任务状态机 |
| **Session 管理** | ⚠️ 零散存在 | 缺少统一 session store |
| **UI 任务中心** | ❌ 缺失 | Chainlit 仍是普通问答视角 |
| **Task-level metrics** | ⚠️ 只有 LLM / capability 调用级 metrics | 缺少任务级统计 |
| **Pause / Resume 演示路径** | ❌ 缺失 | 技术分享无法展示“有状态运行” |

### 1.3 为什么 Task 016 很关键

Task 015 让你可以讲：

- “我们已经 graph-native”
- “我们能 replay”
- “我们能 benchmark”

但 Task 016 会让你开始讲更高级的话题：

- “我们已经有状态化执行”
- “任务可以暂停、恢复、等待人工确认”
- “Agent 不是一次性回答器，而是一个可持续推进的任务执行器”

这会让项目从“可讲的图式平台”进一步变成“更像真实 Agent 产品后端”的系统。

---

## 二、Task 016 的核心目标

> **主题：把 Course Agent 升级为一个真正支持 Session、Resume、Human-in-the-loop 的 Stateful Agent Platform。**

本期不再只关心“怎么跑”，
而更关心：

- 任务是否有生命周期
- graph 是否可以暂停和恢复
- 人工是否可以进入执行环路
- UI / CLI 是否能把任务当成一个持续对象来操作

### 2.1 本期聚焦

本期聚焦四件事：

1. **Task Session & Lifecycle**
   引入统一任务对象：创建、运行中、等待输入、等待审批、完成、失败、取消。

2. **Resume / Continue**
   基于 Task 015 的 replay / checkpoint 能力，新增 inspect / resume / continue CLI。

3. **Human-in-the-loop**
   在 graph 中加入明确的人工确认节点与人工补充输入节点。

4. **Stateful UI / Demo**
   在 Chainlit 里展示“任务态”而不仅仅是“回答态”。

### 2.2 本期不做什么

| 做 | 不做 |
|---|---|
| ✅ 任务生命周期状态机 | ❌ 一期内做复杂工作流编排后台 |
| ✅ CLI resume / inspect | ❌ 一期内做完整 Web 管理控制台 |
| ✅ 最小 HITL 节点 | ❌ 一期内做权限系统 / 审批组织树 |
| ✅ Chainlit 任务态展示 | ❌ 重写整个 UI 成任务管理平台 |
| ✅ session 持久化 | ❌ 上来就做分布式任务调度系统 |

---

## 三、为什么 Task 016 值得做

### 3.1 Graph-native 的下一步，天然就是 Stateful

当一个系统开始有：

- graph
- checkpoint
- replay
- trace

它下一个自然问题一定是：

> “那我能不能从中间继续？”

所以 Task 016 不是额外发散，而是 Task 015 的自然延伸。

### 3.2 真正复杂的 Agent，一定不是“一问一答”

真实复杂任务往往会经历：

- 先规划
- 中途发现上下文不够
- 询问用户补充资料
- 等待确认是否继续
- 某一步失败后重新继续

这说明 Agent 平台需要的是：

- 任务对象
- 状态流转
- 中间态持久化

而不是仅仅一次性生成一个 final answer。

### 3.3 这会显著提升技术分享层次

Task 015 的技术分享可以讲：

- graph-native
- replay
- benchmark

Task 016 的技术分享则能讲：

- Stateful Agent
- HITL
- task lifecycle
- pause / resume
- session orchestration

这会让你的分享从“架构升级”走向“产品级运行时设计”。

---

## 四、Task 016 目标（本期范围）

### 4.1 Task Session 抽象

建议新增统一任务模型：

```python
class TaskSession(BaseModel):
    session_id: str
    title: str
    runtime_kind: str
    backend: str
    status: str
    input: str
    latest_answer: str | None
    latest_replay_path: str | None
    created_at: str
    updated_at: str
```

建议状态：

- `created`
- `running`
- `waiting_human_input`
- `waiting_approval`
- `completed`
- `failed`
- `cancelled`

### 4.2 Resume / Continue CLI

新增 CLI：

```bash
course-agent session list
course-agent session show <id>
course-agent session resume <id>
course-agent session continue <id> --input "..."
course-agent session cancel <id>
```

要求支持：

- 最近任务列表
- 任务详情查看
- 恢复执行
- 补充人工输入后继续

### 4.3 Human-in-the-loop 节点

在 graph 中增加两类最小停靠点：

1. `wait_human_input`
   - 当任务缺关键上下文时暂停

2. `wait_approval`
   - 当任务进入关键步骤前暂停，等待确认

最小可行原则：

- mock-first
- 可在 CLI / Chainlit 中触发和继续
- 不需要一期内做复杂权限系统

### 4.4 Session Store

建议新增：

- 本地 SQLite 或 JSON 文件 session store
- 保存：
  - session 元数据
  - status
  - last replay path
  - last checkpoint info
  - latest human input

### 4.5 Chainlit 任务态展示

本期目标不是重写 UI，而是最小做到：

- 当前消息属于哪个 session
- session 当前状态是什么
- 若等待人工输入 / 审批，要给出明确提示
- 支持“继续这个任务”而不是只能重新提问

---

## 五、成功指标（本期验收标准）

1. [x] 系统引入统一 `TaskSession` / `SessionStore` 抽象
2. [x] CLI 可列出、查看、恢复、继续、取消 session
3. [x] graph 中支持至少 1 类人工输入等待节点
4. [x] graph 中支持至少 1 类人工审批等待节点
5. [x] 单 Agent 或 Orchestrator 至少有一条路径能进入 paused / waiting 状态
6. [x] replay / session / checkpoint 三者能形成可恢复闭环
7. [x] Chainlit 至少能展示 session id 与等待状态摘要
8. [x] README 补充 Task 016 的状态化执行说明
9. [x] 单测新增后，`pytest` 总数 ≥ **430 passed**
10. [x] `ruff check .` 全绿

---

## 六、技术方案

### 6.1 顶层新增结构

建议新增：

```text
course_agent/
├── session/
│   ├── models.py
│   ├── store.py
│   └── manager.py
├── runtime/
│   ├── session_runtime.py
│   └── resume.py
├── graph/
│   ├── human_nodes.py
│   └── session_edges.py
docs/
└── tech_share_task016/
    ├── stateful_agent_overview.md
    ├── hitl_demo.md
    ├── session_lifecycle.md
    └── resume_demo.md
```

### 6.2 Session 模型

建议最小字段：

- `session_id`
- `status`
- `runtime_kind`
- `backend`
- `input`
- `latest_answer`
- `latest_replay_path`
- `checkpoint_ref`
- `waiting_reason`
- `created_at`
- `updated_at`

### 6.3 Session Store

建议第一期使用本地 SQLite：

- 简单
- 可测试
- 易于 CLI 查询
- 与当前项目风格一致

### 6.4 HITL 节点设计

建议 graph 中加入：

- `decision_node`
- `wait_human_input_node`
- `wait_approval_node`

决策例子：

- query 中出现“需要你确认后再继续”
- 或 planner 发现缺少关键输入
- 或 benchmark / demo 场景下显式注入 pause

### 6.5 Resume 流程

推荐流程：

1. session 进入 `waiting_*`
2. session store 写入状态
3. checkpoint / replay 同步落盘
4. 用户通过 CLI / UI 提供继续信号
5. runtime 读取 session 并从对应状态恢复

---

## 七、迁移步骤（建议顺序）

### Step 1：TaskSession 与 SessionStore
- 定义模型
- 定义状态机
- 定义存储接口

### Step 2：CLI session 命令
- `list`
- `show`
- `resume`
- `continue`
- `cancel`

### Step 3：graph 中的等待节点
- `wait_human_input`
- `wait_approval`

### Step 4：单 Agent / Orchestrator 接入
- 至少一条 runtime 路径支持 paused / resumed

### Step 5：Chainlit 任务态展示
- 展示 session id
- 展示 waiting 状态
- 提示如何继续

### Step 6：文档 / 分享素材 / 回填
- README
- docs/tech_share_task016
- task_016.md 勾选

---

## 八、测试矩阵

### 8.1 新增测试文件（建议 ≥ 34 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_session_models.py` | session 状态模型 | ≥ 4 |
| `tests/test_session_store.py` | session store 持久化 | ≥ 5 |
| `tests/test_cli_session.py` | session CLI | ≥ 6 |
| `tests/test_human_nodes.py` | human-in-the-loop 节点 | ≥ 5 |
| `tests/test_resume_runtime.py` | resume / continue | ≥ 5 |
| `tests/test_chainlit_session_view.py` | Chainlit 任务态展示 | ≥ 4 |
| `tests/test_session_lifecycle.py` | created→running→waiting→completed 流程 | ≥ 5 |

### 8.2 回归测试

必须继续通过：

- Task 008~015 的所有测试
- 特别是：
  - `test_react_graph_runtime.py`
  - `test_cli_replay.py`
  - `test_cli_benchmark.py`
  - `test_chainlit_graph_events.py`
  - `test_langgraph_orchestrator.py`

### 8.3 验收门槛

- `pytest -q` ≥ **430 passed**
- `ruff check .` 全绿

---

## 九、交付物 Checklist

### 代码
- [x] `course_agent/session/models.py`
- [x] `course_agent/session/store.py`
- [x] `course_agent/session/manager.py`
- [x] `course_agent/runtime/session_runtime.py`
- [x] `course_agent/runtime/resume.py`
- [x] `course_agent/graph/human_nodes.py`
- [x] `course_agent/graph/session_edges.py`
- [x] `course_agent/cli.py`：新增 `session` 子命令
- [x] `course_agent/ui/chainlit_app.py`：新增 session 状态展示与继续提示
- [x] `course_agent/config.py`：新增 Task 016 所需 session / hitl 配置

### 测试 / 配置
- [x] `tests/test_session_models.py`
- [x] `tests/test_session_store.py`
- [x] `tests/test_cli_session.py`
- [x] `tests/test_human_nodes.py`
- [x] `tests/test_resume_runtime.py`
- [x] `tests/test_chainlit_session_view.py`
- [x] `tests/test_session_lifecycle.py`
- [x] `pytest -q` ≥ **430 passed**（当前 `430 passed, 6 skipped`）
- [x] `ruff check .` 全绿

### 文档 / 分享素材
- [x] `README.md` 新增「⏯️ Session / Resume」一节
- [x] `README.md` 新增「🧑 Human-in-the-loop」一节
- [x] `README.md` 更新 Task 016 进度行
- [x] `docs/tech_share_task016/stateful_agent_overview.md`
- [x] `docs/tech_share_task016/hitl_demo.md`
- [x] `docs/tech_share_task016/session_lifecycle.md`
- [x] `docs/tech_share_task016/resume_demo.md`
- [x] `task/task_016.md`（本文）成功指标与交付物回填

### 验证脚本（推荐手动跑）
- [x] `course-agent session list`
- [x] `course-agent session show <id>`
- [x] `course-agent session resume <id>`
- [x] `course-agent session continue <id> --input "..."`
- [x] Chainlit 中展示 waiting 状态并提示如何继续

---

## 十、Task 016 的教学 / 分享价值

如果说：

- Task 014 讲的是“让 Agent 跑在图上”
- Task 015 讲的是“让 graph 执行可回放、可比较、可演示”

那么 Task 016 讲的就是：

> **当 Agent 已经 graph-native 之后，如何把它进一步升级成一个真正有状态、可恢复、可人工介入的任务执行平台。**

这一期很适合做更高级的技术分享，因为它天然能讲：

### 10.1 架构层
- graph-native 为什么自然演进到 stateful runtime
- 为什么 session / lifecycle 是 Agent 产品化的核心

### 10.2 工程层
- 如何设计统一 session store
- 如何让 replay / checkpoint / resume 协同工作
- 如何把 HITL 节点设计成平台能力而不是业务硬编码

### 10.3 演示层
- 创建任务
- 进入 waiting 状态
- 人工补充输入
- 恢复执行
- 最终完成并回放

### 10.4 方法论层
- 从“能跑一次”转向“能持续推进”
- 从“回答系统”转向“状态化任务系统”

---

## 十一、Task 016 完成后的预期效果

当 Task 016 完成后，Course Agent 应该不只是：

- 一个 graph-native Agent 平台
- 一个可以 replay / benchmark 的 Agent 平台

而应该成为：

> **一个支持 Session、Resume、Human-in-the-loop、Task Lifecycle 的 Stateful Agent Platform 样板。**

届时你在技术分享里可以进一步讲清楚：

1. 为什么 graph-native 的下一步就是 stateful
2. 为什么 replay 之后必须做 resume
3. 为什么真正复杂任务离不开人工介入
4. 为什么 Agent 平台的关键不是“回答一次”，而是“持续推进一个任务”

---

## 十二、Task 016 完成小结

本次执行完成了：

1. ✅ **Session 抽象**：新增 `TaskSession`、`SessionStatus`、`SessionStore`、`SessionManager`；
2. ✅ **Stateful Runtime**：新增 `SessionRuntime`，把 `ReactGraphRuntime` 升级成可创建 / 恢复 / 继续 / 取消的有状态执行器；
3. ✅ **HITL 节点**：新增 `wait_human_input` 与 `wait_approval` 两类 graph 停靠点；
4. ✅ **CLI session 子命令**：支持 `start / list / show / resume / continue / cancel`；
5. ✅ **Chainlit 任务态展示**：react graph 模式下可显示 `session_id / status / waiting_reason / replay path`；
6. ✅ **Session + Replay 闭环**：session 会记录 `latest_replay_path` 与 `checkpoint_ref`，形成最小恢复链路；
7. ✅ **技术分享素材**：新增 `docs/tech_share_task016/`，沉淀 stateful agent / HITL / resume 演示资料；
8. ✅ **新增测试 34 个**：覆盖 session model/store、HITL node、resume runtime、session CLI、Chainlit session view、session lifecycle；
9. ✅ **最终验证通过**：`uv run pytest -q` → `430 passed, 6 skipped`，`uv run ruff check .` 全绿；
10. ✅ **README 收口**：新增 Session / Resume、Human-in-the-loop 两节，并回填 Task 016 进度。

当前结果已经满足 Task 016 的“Stateful Agent Platform”目标：

- 不再只是 graph-native
- 还能暂停、等待人、继续执行
- 能以 session 视角操作任务
- 能把一次任务执行讲成一个完整生命周期
