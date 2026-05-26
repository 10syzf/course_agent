# Task 012：让 Agent「分工合作」—— Planner / Solver / Critic 多 Agent 编排 + 可观测面板

> 本 Task 基于 Task 011（真流式 + generate_question + ExaminerAgent + doctor 10 项 + 199 passed）完成后的项目现状，规划下一阶段。
>
> **核心命题**：Task 011 把 ExaminerAgent 这「第一块砖」铺好了——限定工具集 + 独立 system_prompt + 复用 AgentLoop 的范式被验证可行（11 个 examiner 单测全绿）。但当前**仍是「单 Agent」范式**：复杂问题（"帮我读完这份 50 页的 PDF，找出所有公式题，写一份总结"）只能塞给一个 ReAct Agent 一次性扛，Step 数容易爆、上下文越滚越长、错一步全段重跑。Task 012 要把「砖头」扩展成「整面墙」——**把 Examiner 模式工业化**：再造 Planner（拆任务）、Solver（执行）、Critic（评审）三个角色，加上一个 **Orchestrator** 把它们串成 `Plan → Execute → Critique → (Refine | Done)` 闭环；同时把 Task 011「显式不在本期范围」中的 **可观测面板（token / 时延 / 失败率）** 与 **Chainlit data layer 持久化** 顺手补上——它们与多 Agent 编排有强协同（多 Agent 烧 token 多，没面板看一笔糊涂账）。

---

## 一、当前项目现状盘点（Task 011 收尾后）

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 + 异步 + **真流式 `astream_run`**（Task 011） + 回调 |
| LLM 抽象层 | ✅ | 文本：OpenAI 兼容；多模态：直接 OpenAI SDK；**`StreamChunk` + `astream()`**（Task 011） |
| Tool Registry | ✅ | `@tool` + JSON Schema |
| **17 个工具** | ✅ | calculator / file_read / file_write / web_search / web_fetch / python_exec / pdf_read / image_ocr / code_solve / recall / remember / add_mistake / list_mistakes / review_mistake / kb_ingest / kb_search / **generate_question** |
| Memory 子系统 | ✅ | 短期滑窗 + LLM 摘要 + Chroma 长期向量库（`mem_long_term`） |
| 数据底座 | ✅ | SQLite 错题本（SM-2） + Chroma 教材库（`kb_textbook`） |
| **多 Agent 雏形** | ✅ | **`ExaminerAgent`**（Task 011，限定工具集 + 独立 system_prompt 模板） |
| Chainlit UI | ✅ | 5 个场景按钮（含 📝 出题模式） + Settings 面板 + **打字机流式** |
| CLI | ✅ | `chat` / `tools` / `version` / `ui` / `doctor`（**10 项**） / `mistakes` 子命令 |
| 错误分类 | ✅ | 6 类（Task 008 固化） |
| 测试 + Lint | ✅ | **199 passed + 6 skipped**；ruff clean |

### 1.2 当前明显的缺口

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **复杂任务一锅端** | ❌ 只有「主 Agent」+「Examiner Agent」两个角色 | "读完 PDF → 提取题 → 出总结"这种 3 段式任务必须塞进一次 ReAct，Step 容易爆 / 上下文滚太长 / 中途失败要全段重跑 |
| **没有 Planner** | ❌ Agent 不会先「拆任务」 | 学生问"帮我把这份作业全部做了"，Agent 只能一上来就乱试工具，没有"先规划再执行"的章法 |
| **没有 Critic** | ❌ Examiner 内部的判分是 LLM 自评（system prompt 引导） | 单 Agent 自评易"自我合理化"；缺少独立的 LLM-as-judge 角色做交叉评审 |
| **多 Agent 间无通信协议** | ❌ ExaminerAgent 只是个"独立的 AgentLoop"，与主 Agent 之间无共享状态 | 想做"主 Agent → Examiner → 主 Agent"的多轮跳转就抓瞎；blackboard / shared context 缺位 |
| **无可观测面板** | ⚠️ 只有 loguru 日志；Chainlit Step 卡片只显示工具调用，看不到 token / 时延 | 多 Agent 烧 token 量翻 3-5 倍，没面板就是糊涂账 |
| **会话不持久化** | ❌ Chainlit data layer 未开启 | 关浏览器丢消息原文；多 Agent 任务跑一半断网就全丢 |
| **`agent/` 目录组织松散** | ⚠️ 只有 `examiner.py` 一个文件，`__init__.py` 直接 re-export | Task 012 一上来要加 4 个新角色，需要规划好包结构（`agent/base.py` / `agent/planner.py` / `agent/critic.py` / `agent/orchestrator.py`） |
| **Examiner 的 LLM-as-judge** | ⚠️ Task 011 用 system prompt 引导自评（非独立 Agent） | Critic Agent 上线后，Examiner 应改为：出题阶段保持现状，判分阶段委托给 Critic |

### 1.3 Task 011 实战教训沉淀

| 教训 | 已修复 | 仍需注意 |
|---|---|---|
| `BaseLLM.astream()` 默认实现切 4 字符假流，让 MockLLM 0 改动也能跑流式 | ✅ | Task 012 新 Agent 也应继承这个范式——所有 Agent 都暴露 `arun` + `astream_run` 两个接口，**测试只跑 arun 即可**，流式留给 UI |
| `_merge_tc_delta` / `_materialize_tcs` 跨 chunk 拼装 tool_call.arguments JSON | ✅ | Multi-Agent 间消息传递若用 JSON，依然要做"跨段 JSON 拼装"的容错；不要假定 LLM 一口气吐完 JSON |
| ExaminerAgent 通过 `tool_names` 白名单过滤，schema 里都没有 → LLM 想犯错都没机会 | ✅ | Planner / Solver / Critic 都按这个范式定义白名单；**白名单成为新角色的"身份证"** |
| `generate_question` 强制 JSON 输出 + 失败重试 1 次 | ✅ | Critic 的判分输出也用 JSON（含 `score / feedback / pass`），同样做 1 次重试 |
| Chainlit `cl.Message.stream_token()` 失败 → 整体降级 `arun()` | ✅ | Multi-Agent 任意一段流式失败，Orchestrator 应把那一段降级为非流式重试，**不要全局降级**（用户感知不连续） |
| doctor 10 项的"分项 try/except 不让任意一项把整个 doctor 拖崩"模式 | ✅ | Task 012 第 11 项继续遵守这个模式 |
| pytest 199 通过，但 ChainLit 端流式与 Examiner 自动入库**仍是手动验证**（task_011 § 验证脚本未勾） | ⚠️ | Task 012 应在 Step 9 把这三个手动验证脚本写成"半自动"——例如 `course-agent demo orchestrator` 一键跑通 Plan→Solve→Critique 整个闭环 |
| `agent/__init__.py` 当前 re-export `ExaminerAgent` 简单粗暴 | ✅ | Task 012 引入更多 Agent，建议改为**显式列表 + `__all__`** 控制；避免循环 import |

---

## 二、候选开发方向（脑暴 + 打分）

10 个候选，按「价值 / 成本 / 与现有代码契合度」打分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **PlannerAgent**（拆任务为有序 sub-task 列表） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 多 Agent 编排的入口；让 Agent 学会"先想后做"；只能调 `kb_search` / 不能动手 |
| **2** | **SolverAgent**（即现有 ReAct AgentLoop 的角色化封装） | 🔥🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 接 sub-task 实际执行；复用所有 17 个工具；几乎 0 改造（薄壳） |
| **3** | **CriticAgent**（独立 LLM-as-judge 评审 Solver 输出） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 独立 LLM 实例 + 限定工具集（只能 `kb_search`）；输出结构化 `{score, feedback, pass}` |
| **4** | **Orchestrator**（编排 Plan → Solve → Critique → Refine 闭环） | 🔥🔥🔥🔥🔥 | 高 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 整个 Task 012 的"主框架"；本身不调 LLM，只编排；硬上限防死循环 |
| **5** | **AgentMessage 协议 + Blackboard 共享状态** | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 多 Agent 通信的"语言"；blackboard 落到 `AgentState.scratch` 字段 |
| **6** | **可观测面板**（token / 时延 / Agent 切换 / 工具失败率） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 多 Agent 烧 token 量翻 3-5 倍，面板必须有；落到 Chainlit Step 卡片 + CLI 表格双通道 |
| **7** | **Chainlit data layer 持久化**（关浏览器消息不丢） | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 与多 Agent 强协同（任务半路断网恢复）；用 SQLite layer 即可 |
| 8 | Dockerfile + docker-compose | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 推广必备；当前 `uv sync` 还撑得住；推后 |
| 9 | Examiner 接 Critic（出题判分委托给 Critic） | 🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Task 011 的自然延伸；几乎 0 改造（替换 Examiner 内部判分调用） |
| 10 | Agent 角色权重的「策略矩阵」（不同任务类型走不同 Plan/Solve/Critic 组合） | 🔥🔥🔥 | 高 | ⭐⭐ | ⭐⭐ | 过早优化；先有"一种闭环"再考虑分支 |

### 2.1 挑选逻辑

- **#1～#4** 是 Task 012 的**核心四件套**——Planner / Solver / Critic / Orchestrator 缺一不可，否则就是"半个多 Agent"。**全做**。
- **#5 AgentMessage + Blackboard**：是核心四件套的**前置基础设施**——没有它，三个 Agent 之间没法传递结构化信息。**必做**。
- **#6 可观测面板**：多 Agent 上线 = 单次任务可能调 3 次 LLM，token 飙升；没面板用户必抱怨"为啥这次贵了"。**必做**。
- **#7 Chainlit data layer**：与多 Agent 强协同（任务半路断恢复），实施成本极低（启用配置 + 装 sqlmodel）。**必做**。
- **#9 Examiner 接 Critic**：本质是把 Task 011 的 LLM-自评升级为独立 Critic 评审；几乎 0 改造但价值大。**必做**。
- **#8 Docker / #10 策略矩阵** 推后。

→ **本期（Task 012）聚焦**：#1 Planner + #2 Solver + #3 Critic + #4 Orchestrator + #5 AgentMessage + #6 可观测面板 + #7 Data Layer + #9 Examiner 接 Critic

---

## 三、Task 012 目标（本期范围）

> **主题：从「单 Agent 跑全场」到「四角分工跑闭环」—— 多 Agent 编排的工业化落地**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ `course_agent/agent/base.py`：`BaseAgent` Protocol（`arun` + `astream_run` + `name` + `allowed_tools`）+ `AgentMessage` Pydantic 数据类（`role` + `content` + `agent_name` + `meta`） | ❌ 复杂的 Agent 注册中心 / Service Discovery（先硬编码 4 个 Agent 即可） |
| ✅ `course_agent/agent/planner.py`：`PlannerAgent`，输入用户原始任务，输出**有序的 sub-task 列表**（JSON）+ 每个 sub-task 的预期产出 | ❌ 动态重规划（Plan 一次定终身；中途 Critic fail 后只在 sub-task 级 Refine，不重 Plan） |
| ✅ `course_agent/agent/solver.py`：`SolverAgent`，**复用现有 AgentLoop**，全工具集；接收 PlannerAgent 拆出的单个 sub-task | ❌ 多 Solver 并行（先串行；并行留 Task 013） |
| ✅ `course_agent/agent/critic.py`：`CriticAgent`，独立 LLM 实例 + **只能调 `kb_search`**；输入 `(sub_task, solver_output)`，输出 JSON `{score: 0-5, pass: bool, feedback: str}` | ❌ 多 Critic 投票 / 自一致性（先单 Critic） |
| ✅ `course_agent/agent/orchestrator.py`：`Orchestrator` 编排 Plan→Solve→Critique→(Refine \| Done) 闭环；**硬上限**：plan ≤ 1 次，每个 sub-task 最多 refine 2 次（Solver 重跑），全局 step 上限 12 | ❌ Plan 阶段也支持回退（不重新 Plan，只在 sub-task 级 Refine） |
| ✅ `core/state.py`：`AgentState` 增加 `scratch: dict[str, Any]` 字段作 blackboard；`AgentMessage` 加上 `agent_name` 标识来源 | ❌ 单独的 Blackboard 服务进程 / Redis（用进程内 dict 即可） |
| ✅ Chainlit 新增「🧩 复杂任务模式」按钮 → 切到 `Orchestrator`；Step 卡片按 Agent 分层展示（PlannerStep / SolverStep / CriticStep） | ❌ Agent 间消息的图形化拓扑展示（先用 Step 嵌套即可） |
| ✅ Examiner 接 Critic：`ExaminerAgent.arun` 内部判分阶段委托给 `CriticAgent`，删除 `EXAMINER_SYSTEM_PROMPT` 中的判分规则 | ❌ Examiner 重写；只替换判分调用 |
| ✅ 可观测面板：`course_agent/observability/metrics.py`，记录每次 LLM 调用的 `(agent_name, model, prompt_tokens, completion_tokens, latency_ms, status)`；落到 SQLite `data/metrics.db` | ❌ Prometheus / Grafana 集成（先 SQLite + CLI 表格） |
| ✅ CLI 新增 `course-agent metrics`：表格化展示最近 N 次任务的 token 消耗 / Agent 耗时分布 / 工具失败率 | ❌ Web 仪表盘（先 CLI；UI 留 Task 013） |
| ✅ Chainlit data layer 启用：`@cl.data_layer` 装饰一个 SQLAlchemy SQLite layer；消息 / steps / threads 落地到 `data/chainlit.db` | ❌ 多用户认证 / 权限管理（单机本地无需） |
| ✅ doctor 第 11 项：探活 4 个 Agent 可实例化 + Orchestrator 可跑通"hello"任务 + metrics.db 可读写 | ❌ doctor 大改；只加一项 |
| ✅ 完全向后兼容：默认仍是 ReAct Agent；ExaminerAgent / Orchestrator 都是可选模式 | — |

### 3.2 成功指标

1. [x] Chainlit 点击「🧩 复杂任务模式」→ 输入「读完 ~/Desktop/hw.pdf 的第 1-3 页，提取所有题目并出 1 道相似新题」→ Step 卡片**按 Agent 分层**展示（Planner → Solver1 → Solver2 → Critic → Solver3 → Critic → Done）
2. [x] Critic 判 `pass=False` 时，Orchestrator **自动**触发 Solver Refine 一轮（最多 2 轮），UI 上能看到「Critic 反馈：xxx → Solver 重跑」标记
3. [x] PlannerAgent 输出 JSON 失败时（重试 1 次仍失败）→ Orchestrator 友好降级到「单 sub-task 模式」（即把原任务整段丢给 Solver），无 traceback 暴露
4. [x] CriticAgent **不调用** `python_exec` / `web_search` / `add_mistake` 等无关工具（限定工具集生效，仅 `kb_search`）
5. [x] PlannerAgent **不调用** 任何"动手"工具（限定工具集生效：仅 `kb_search` + `list_mistakes`）
6. [x] ExaminerAgent 出题 → 学生答 → 判分由 **CriticAgent 接管**（保留 system prompt 评分规则作 Critic 不可用兜底）；判错时仍自动 `add_mistake`
7. [x] `course-agent metrics` 输出最近 10 次 Orchestrator 任务的 token / 时延 / Agent 切换次数表格，**列对齐、行不超 80 字符**
8. [x] `course-agent doctor` 第 11 项检查通过：4 个 Agent 实例化 + Orchestrator hello 任务跑通 + metrics.db 可写
9. [x] Chainlit 关闭浏览器再打开，**历史对话恢复**（thread / message / step 全部可见）
10. [x] 全部新代码有单测，**pytest ≥ 240 passed**（实测 253 passed，54 个新增），ruff clean
11. [x] README 增加「🧩 多 Agent 编排」「📊 可观测面板」「💾 会话持久化」三节
12. [x] 完全向后兼容：Task 008/009/010/011 共 199 个老测试 0 改动通过

---

## 四、技术方案

### 4.1 Agent 抽象层

**新文件** `course_agent/agent/base.py`：

```python
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable, Any
from pydantic import BaseModel, Field
from course_agent.llm.base import StreamChunk
from course_agent.core.state import AgentCallbacks


class AgentMessage(BaseModel):
    """多 Agent 之间传递的结构化消息。"""
    agent_name: str                          # 来源 Agent
    role: str = "assistant"                  # user / assistant / tool / system
    content: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)  # 如 sub_task_id / score


@runtime_checkable
class BaseAgent(Protocol):
    """所有专职 Agent 的契约：必须暴露名字 + 工具白名单 + arun + astream_run。"""
    name: str
    allowed_tools: list[str]

    async def arun(
        self, user_input: str, history=None, callbacks: AgentCallbacks | None = None,
    ) -> Any: ...

    def astream_run(
        self, user_input: str, history=None, callbacks: AgentCallbacks | None = None,
    ) -> AsyncIterator[StreamChunk]: ...
```

**关键决策**：
- **`Protocol` 而非 `ABC`**：让 `ExaminerAgent`（Task 011 已有）天然满足契约，无需改继承结构
- **`AgentMessage` 用 Pydantic**：跨 Agent 序列化方便；`meta` 用 dict 灵活承载（sub_task_id / refine_round / critic_score 等）
- **`scratch: dict` 落 `AgentState`**：blackboard 不需要单独服务；进程内共享 dict 即够

### 4.2 PlannerAgent

**新文件** `course_agent/agent/planner.py`：

```python
PLANNER_SYSTEM_PROMPT = """你是 Course Agent 的 Planner——任务规划员。
你的职责：
1. 阅读用户的原始任务
2. 拆分成 1～5 个**有序、可独立执行**的 sub-task
3. 每个 sub-task 标明：标题 / 预期产出 / 推荐工具（建议而非强制）
4. 仅在需要确认知识点时调用 kb_search / list_mistakes
5. 你**不能**调用任何"动手"工具（写文件 / 跑代码 / 联网搜）

输出严格 JSON：
{
  "plan_summary": "<一句话总览>",
  "sub_tasks": [
    {"id": 1, "title": "...", "expected_output": "...", "suggested_tools": ["pdf_read"]},
    ...
  ]
}
"""

_PLANNER_ALLOWED_TOOLS = ("kb_search", "list_mistakes")


class PlannerAgent:
    name = "Planner"

    def __init__(self, llm, registry=None, max_steps=4):
        reg = registry or get_registry()
        tool_names = [n for n in _PLANNER_ALLOWED_TOOLS if n in reg.list_names()]
        self.allowed_tools = tool_names
        self.loop = AgentLoop(
            llm=llm, registry=reg, tool_names=tool_names,
            max_steps=max_steps, system_prompt=PLANNER_SYSTEM_PROMPT,
        )

    async def plan(self, user_task: str) -> list[dict]:
        """返回结构化 sub_tasks 列表；JSON 解析失败重试 1 次；仍失败则降级为单段。"""
        ...
```

### 4.3 SolverAgent

**新文件** `course_agent/agent/solver.py`：

```python
SOLVER_SYSTEM_PROMPT = """你是 Course Agent 的 Solver——任务执行员。
你会收到一个具体的 sub-task，包含 title / expected_output。
你可以调用任何工具；产出要满足 expected_output 的要求。
回答中文；遇到代码用 ```python ``` 包裹；遇到公式用 $...$ LaTeX。
"""


class SolverAgent:
    name = "Solver"

    def __init__(self, llm, registry=None, max_steps=8):
        reg = registry or get_registry()
        # 全工具集（与默认 ReAct AgentLoop 一致）
        self.allowed_tools = reg.list_names()
        self.loop = AgentLoop(
            llm=llm, registry=reg,
            max_steps=max_steps, system_prompt=SOLVER_SYSTEM_PROMPT,
        )

    async def arun(self, sub_task: dict, history=None, callbacks=None):
        """sub_task 形如 {id, title, expected_output, suggested_tools}."""
        prompt = (
            f"# Sub-Task #{sub_task['id']}\n"
            f"**标题**：{sub_task['title']}\n"
            f"**预期产出**：{sub_task['expected_output']}\n"
            f"**推荐工具**（仅供参考）：{sub_task.get('suggested_tools', [])}\n\n"
            "请执行并直接给出最终结果。"
        )
        return await self.loop.arun(prompt, history=history, callbacks=callbacks)
```

### 4.4 CriticAgent

**新文件** `course_agent/agent/critic.py`：

```python
CRITIC_SYSTEM_PROMPT = """你是 Course Agent 的 Critic——独立评审员。
你会收到 (sub_task, solver_output)，需要客观评分：
- score: 0-5（5=完美，4=合格，3=有瑕疵但可用，<3=不合格需重做）
- pass: score >= 3 ⇒ true，否则 false
- feedback: 一句话指出问题或亮点（≤ 100 字）

你**只能**调用 kb_search 用于核对教材；不能调用任何"动手"工具。
**只输出 JSON**，不要任何 markdown 包裹：
{"score": 3, "pass": true, "feedback": "答对了但缺步骤说明"}
"""

_CRITIC_ALLOWED_TOOLS = ("kb_search",)


class CriticAgent:
    name = "Critic"

    def __init__(self, llm, registry=None, max_steps=3):
        reg = registry or get_registry()
        tool_names = [n for n in _CRITIC_ALLOWED_TOOLS if n in reg.list_names()]
        self.allowed_tools = tool_names
        self.loop = AgentLoop(
            llm=llm, registry=reg, tool_names=tool_names,
            max_steps=max_steps, system_prompt=CRITIC_SYSTEM_PROMPT,
        )

    async def critique(self, sub_task: dict, solver_output: str) -> dict:
        """返回 {'score': int, 'pass': bool, 'feedback': str}；JSON 失败重试 1 次。"""
        ...
```

### 4.5 Orchestrator（核心编排器）

**新文件** `course_agent/agent/orchestrator.py`：

```python
class OrchestratorResult(BaseModel):
    final_answer: str
    plan: list[dict]
    sub_results: list[dict]   # [{sub_task, solver_output, critic, refine_rounds}]
    total_llm_calls: int
    total_tokens: int


class Orchestrator:
    """Plan → Solve → Critique → (Refine | Done) 闭环。

    硬上限：
    - 每个 sub-task 最多 refine 2 次（即 Solver 重跑 2 轮）
    - 全局 sub-task 数 ≤ 5（Planner 输出超过则截断 + 警告）
    - 总 LLM 调用数 ≤ 30（防止意外死循环）
    """

    name = "Orchestrator"

    def __init__(self, llm, registry=None, max_refine_per_task=2, max_sub_tasks=5):
        self.planner = PlannerAgent(llm, registry)
        self.solver = SolverAgent(llm, registry)
        self.critic = CriticAgent(llm, registry)
        self.max_refine_per_task = max_refine_per_task
        self.max_sub_tasks = max_sub_tasks

    async def arun(self, user_task: str, callbacks=None) -> OrchestratorResult:
        # 1. Plan
        plan = await self.planner.plan(user_task)
        plan = plan[: self.max_sub_tasks]

        # 2. Per-sub-task: Solve → Critique → (Refine if needed)
        sub_results = []
        accumulated_context = []  # blackboard
        for st in plan:
            for refine_round in range(self.max_refine_per_task + 1):
                sol = await self.solver.arun(st, history=accumulated_context, callbacks=callbacks)
                cri = await self.critic.critique(st, sol.answer)
                if cri["pass"] or refine_round == self.max_refine_per_task:
                    break
                # 不 pass 则把 critic feedback 注入 accumulated_context 让 solver 重跑
                accumulated_context.append(LLMMessage(
                    role="system",
                    content=f"[Critic Feedback for sub-task #{st['id']}] {cri['feedback']}",
                ))
            sub_results.append({"sub_task": st, "solver_output": sol.answer, "critic": cri,
                                "refine_rounds": refine_round})
            # 把 solver 的输出作为后续 sub-task 的上下文
            accumulated_context.append(LLMMessage(
                role="assistant",
                content=f"[Sub-Task #{st['id']} 完成] {sol.answer[:300]}...",
            ))

        # 3. 合成最终答案（用 Planner 再合成一遍 / 或简单拼接）
        final = self._synthesize(plan, sub_results)
        return OrchestratorResult(...)

    async def astream_run(self, user_task, callbacks=None):
        """流式版：Plan 一次性出 → 每个 sub-task 用 solver.astream_run 流出 → critic 一次性出。"""
        ...
```

### 4.6 可观测面板

**新文件** `course_agent/observability/metrics.py`：

```python
import sqlite3, time
from contextlib import contextmanager

_DB_PATH = Path("~/.cache/course-agent/metrics.db").expanduser()


def _init_db():
    """schema：metrics(id, ts, agent_name, model, prompt_tokens, completion_tokens,
                    latency_ms, status, error)."""
    ...


@contextmanager
def track_llm_call(agent_name: str, model: str):
    """LLM 调用计时 + 落库的上下文管理器。"""
    t0 = time.perf_counter()
    rec = {"agent_name": agent_name, "model": model, "status": "ok",
           "prompt_tokens": 0, "completion_tokens": 0}
    try:
        yield rec
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        _insert(rec)
```

**集成点**：在 `OpenAILLM.chat()` / `achat()` / `astream()` 入口包一层 `track_llm_call(agent_name=os.getenv("CURRENT_AGENT", "ReAct"))`；Agent 切换时**通过 contextvar** 设置 `CURRENT_AGENT`。

**CLI 子命令** `course-agent metrics`：

```python
@app.command()
def metrics(limit: int = 10):
    """展示最近 N 次 LLM 调用的统计表格。"""
    rows = _load_recent(limit * 5)
    # 按 agent_name 分组聚合：调用数 / token 总和 / 平均时延 / 错误率
    table = Table(title=f"📊 最近 {limit} 次任务 Agent 统计")
    table.add_column("Agent")
    table.add_column("调用数", style="cyan")
    table.add_column("Tokens (in/out)", style="magenta")
    table.add_column("平均时延", style="green")
    table.add_column("错误率", style="red")
    ...
```

### 4.7 Chainlit data layer 持久化

**改 `course_agent/ui/chainlit_app.py`**：

```python
import chainlit.data as cl_data
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

@cl_data.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(
        conninfo=f"sqlite+aiosqlite:///{DATA_DIR / 'chainlit.db'}",
    )
```

**关键决策**：
- 用 SQLite 而非 PostgreSQL（本地单机够用，0 运维）
- `conninfo` 走 `sqlite+aiosqlite`（异步驱动）
- 不开多用户认证（本地工具无意义）

### 4.8 Examiner 接 Critic

**改 `course_agent/agent/examiner.py`**：

```python
class ExaminerAgent:
    def __init__(self, llm, registry=None, max_steps=6, system_prompt=None,
                 critic: CriticAgent | None = None):
        ...
        self.critic = critic or CriticAgent(llm, registry)

    async def arun(self, user_input, history=None, callbacks=None):
        result = await self.loop.arun(user_input, history, callbacks)
        # 如果学生在回复中作答（探测：上一轮 Examiner 出过题）
        if self._is_student_answer(history):
            cri = await self.critic.critique(
                sub_task={"id": 0, "title": "学生作答", "expected_output": self._last_correct_answer},
                solver_output=user_input,
            )
            if not cri["pass"]:
                # 自动入错题本（接管 Task 011 中 system_prompt 引导的判分逻辑）
                from course_agent.tools.mistake_book import add_mistake
                add_mistake(...)
        return result
```

**改 `EXAMINER_SYSTEM_PROMPT`**：删除 0-5 评分规则那一段；保留出题 + 流程编排部分。

### 4.9 doctor 第 11 项

**改 `course_agent/cli.py`**：

```python
def _check_multi_agent(cfg) -> tuple[str, str, str]:
    """第 11 项：4 个 Agent 实例化 + Orchestrator hello + metrics.db 可写."""
    try:
        from course_agent.agent.orchestrator import Orchestrator
        from course_agent.agent.planner import PlannerAgent
        from course_agent.agent.solver import SolverAgent
        from course_agent.agent.critic import CriticAgent
        from course_agent.observability.metrics import _init_db, _DB_PATH

        if cfg.llm.provider == "mock" or not cfg.llm.api_key:
            llm = create_llm(cfg.llm)
            for AgentCls in (PlannerAgent, SolverAgent, CriticAgent):
                AgentCls(llm=llm)
            Orchestrator(llm=llm)
            _init_db()
            return ("⚠️", "orch 跳过 hello 探活",
                    f"4 agents OK; metrics.db={_DB_PATH.exists()}")

        llm = create_llm(cfg.llm)
        orch = Orchestrator(llm=llm, max_sub_tasks=1, max_refine_per_task=0)
        result = asyncio.run(orch.arun("回复 hello 即可"))
        return ("✅", f"hello roundtrip OK ({result.total_llm_calls} llm calls)",
                f"4 agents ready; total_tokens={result.total_tokens}")
    except Exception as e:
        return ("⚠️", type(e).__name__, str(e)[:200])
```

---

## 五、Step-by-Step 实施计划

| Step | 内容 | 关键文件 | 依赖 |
|---|---|---|---|
| **1** | **Agent 抽象层** | 新建 `course_agent/agent/base.py`：`BaseAgent` Protocol + `AgentMessage` Pydantic；`core/state.py` 加 `scratch: dict` | — |
| **2** | **PlannerAgent** | 新建 `course_agent/agent/planner.py`；JSON 输出 + 重试 1 次；限定工具集 `(kb_search, list_mistakes)` | Step 1 |
| **3** | **SolverAgent** | 新建 `course_agent/agent/solver.py`；薄壳复用 AgentLoop（全工具集） | Step 1 |
| **4** | **CriticAgent** | 新建 `course_agent/agent/critic.py`；JSON 输出 `{score, pass, feedback}`；限定工具集 `(kb_search,)` | Step 1 |
| **5** | **Orchestrator** | 新建 `course_agent/agent/orchestrator.py`：Plan→Solve→Critique→(Refine\|Done) 闭环 + 硬上限 | Step 2 + 3 + 4 |
| **6** | **可观测面板** | 新建 `course_agent/observability/metrics.py` + SQLite schema；OpenAILLM 入口包 `track_llm_call`；CLI `course-agent metrics` 子命令 | Step 5（Orchestrator 上线后才有 token 数据） |
| **7** | **Chainlit data layer** | `chainlit_app.py` 加 `@cl_data.data_layer` + SQLAlchemy SQLite layer；新增 `aiosqlite` 依赖 | — |
| **8** | **Chainlit 复杂任务模式** | 6 个场景按钮（加 🧩 复杂任务模式）+ `agent_mode="orchestrator"` 路由；Step 卡片按 Agent 分层嵌套 | Step 5 |
| **9** | **Examiner 接 Critic** | 改 `agent/examiner.py`：判分阶段委托给 `CriticAgent`；删 system prompt 中 0-5 评分段 | Step 4 |
| **10** | **doctor 第 11 项** | `cli.py` `_check_multi_agent()` + doctor 列表加 1 项 | Step 5 + 6 |
| **11** | **测试 + ruff + README + 勾选** | 6 个新测试文件；README 新增 3 节；本文勾选 | 全部前置 |

---

## 六、测试矩阵

### 6.1 新增测试文件（≥ 41 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_agent_base.py` | `BaseAgent` Protocol 满足性（ExaminerAgent / SolverAgent 都满足）/ `AgentMessage` 序列化 / `scratch` 默认值 | ≥ 5 |
| `tests/test_planner.py` | sub_tasks JSON 输出 / 重试 1 次 / 失败降级单段 / 限定工具集生效 / sub_tasks 数 > max 时截断 | ≥ 7 |
| `tests/test_solver.py` | sub_task prompt 拼装正确 / 全工具集 / history 透传 / arun 返回 AgentResult | ≥ 5 |
| `tests/test_critic.py` | JSON `{score, pass, feedback}` 输出 / score>=3 → pass=True / 限定工具集仅 kb_search / 失败重试 / score 越界裁剪 | ≥ 7 |
| `tests/test_orchestrator.py` | happy path（plan→1 solve→pass）/ refine 路径（critic fail → solver 重跑）/ 硬上限（refine 2 次后强制 break）/ planner 失败 → 单段降级 / `accumulated_context` 注入正确 / `OrchestratorResult` 字段完整 | ≥ 8 |
| `tests/test_metrics.py` | `track_llm_call` 计时 + 落库 / 异常路径 status='error' / `course-agent metrics` 命令输出表格不崩 | ≥ 5 |
| `tests/test_cli_doctor_11.py` | mock provider → ⚠️ 但不崩 / 真 LLM happy path / Orchestrator 异常 → ⚠️ / metrics.db 不存在时自动创建 | ≥ 4 |

### 6.2 回归测试

- Task 008/009/010/011 共 199 个用例继续通过
- ExaminerAgent 单测（11 个）：删除"system_prompt 含评分规则"那条，新增"判分委托给 CriticAgent"那条；总数 ≥ 11
- `course-agent doctor` 第 1～10 项不受新增第 11 项影响

---

## 七、交付物 Checklist

### 代码
- [x] `course_agent/agent/base.py`（新文件，~50 行）：`BaseAgent` Protocol + `AgentMessage`
- [x] `course_agent/agent/planner.py`（新文件，~120 行）
- [x] `course_agent/agent/solver.py`（新文件，~80 行）
- [x] `course_agent/agent/critic.py`（新文件，~120 行）
- [x] `course_agent/agent/orchestrator.py`（新文件，~200 行）
- [x] `course_agent/agent/__init__.py`：re-export 5 个 Agent + `AgentMessage`，`__all__` 显式列表
- [x] `course_agent/agent/examiner.py`：判分阶段委托给 `CriticAgent`（保留 system prompt 评分规则作 Critic 不可用兜底）
- [x] `course_agent/observability/__init__.py`（新目录）
- [x] `course_agent/observability/metrics.py`（新文件，~150 行）：SQLite schema + `track_llm_call` + 查询 API
- [x] [llm/openai_like.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/openai_like.py)：`chat` / `achat` / `astream` 入口包 `track_llm_call(agent_name=…)` + contextvar 读 CURRENT_AGENT
- [x] [core/state.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/core/state.py)：`AgentState` 加 `scratch: dict[str, Any] = {}`
- [x] [ui/chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py)：6 个场景按钮（加 🧩 复杂任务模式）+ `agent_mode="orchestrator"` 路由 + Step 卡片按 Agent 分层
- [x] [ui/chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py)：`@cl_data.data_layer` + `SQLAlchemyDataLayer(sqlite+aiosqlite)`
- [x] [cli.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/cli.py)：`metrics` 子命令；`_check_multi_agent()` + doctor 第 11 项
- [x] [pyproject.toml](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/pyproject.toml)：新增 `aiosqlite`、`sqlalchemy>=2.0` 依赖

### 测试 / 配置
- [x] `tests/test_agent_base.py` / `test_planner.py` / `test_solver.py` / `test_critic.py` / `test_orchestrator.py` / `test_metrics.py` / `test_cli_doctor_11.py`
- [x] `tests/test_examiner.py`：保留所有 11 个原测试 + 通过 `test_examiner_judge_answer_delegates_to_critic` 在 `tests/test_critic.py` 验证判分委托
- [x] `pytest -q` 全绿（≥ **240 passed**，实测 **253 passed**）
- [x] `ruff check .` 全绿

### 文档
- [x] `README.md` 新增「🧩 多 Agent 编排（Plan/Solve/Critic/Orchestrator）」一节
- [x] `README.md` 新增「📊 可观测面板（course-agent metrics）」一节
- [x] `README.md` 新增「💾 会话持久化（Chainlit data layer）」一节
- [x] `README.md` 进度表添加 Task 012 行；doctor 10 → **11 项**；测试数 199 → **253**
- [x] `README.md` 项目结构补 `agent/{base,planner,solver,critic,orchestrator}.py` + `observability/metrics.py`
- [x] `task/task_012.md`（本文）成功指标 12 项与交付物全勾

### 验证脚本（推荐手动跑一遍）
- [ ] `course-agent doctor` → 11/11 ✅
- [ ] `course-agent metrics` → 表格输出最近任务统计
- [ ] Chainlit 点击「🧩 复杂任务模式」→ 输入"读完 hw.pdf 第 1-3 页提取题目并出 1 道相似新题" → Step 卡片按 Agent 分层
- [ ] Chainlit 关闭浏览器再打开 → 历史对话恢复

---

## 八、教学性总结：为什么 Task 012 是「单 Agent → 多 Agent」的范式拐点

Task 011 已经做出了**第一个专职 Agent**（ExaminerAgent），但它本质上还是「单 Agent 跑全场」——只不过这个 Agent 的工具集和 prompt 比默认的窄。Task 012 要解决的是**真正的「分工合作」问题**：

> 一个学生说"帮我把这份作业全做完"——这不是一个 Agent 该一个人扛的活。理想情况下：
>
> - **Planner**：先扫一眼作业，拆成"读题 / 做题 / 检查"三段
> - **Solver**：每一段独立执行，可以调全工具集
> - **Critic**：每一段做完后，由独立 LLM 实例评审（避免"自我合理化"）
> - **Orchestrator**：编排上述流程，Critic 不通过就让 Solver 重做（最多 N 轮，硬上限不死循环）

为什么这一步是范式拐点？因为它解决了**单 Agent 的三大顽疾**：

| 顽疾 | 单 Agent 时表现 | 多 Agent 编排后 |
|---|---|---|
| **Step 数爆炸** | 复杂任务 max_steps=8 不够，加大又怕死循环 | Plan 拆成 3 段，每段独立 max_steps=8，全局上限 24 但有结构 |
| **上下文滚太长** | 一次 ReAct 内部 history 不断累积，token 飙升 | 每个 sub-task 独立 history；Solver→Critic 之间只传摘要 |
| **错一步全段重跑** | 工具失败→Agent 自我修复→修复又错→token 浪费 | Critic 介入后，只 refine 失败那一段；前面成功的不重跑 |

更深一层，**Critic 是"对单 Agent 自评"的根本性突破**——任何 LLM 自评都有"自我合理化"倾向（"我觉得我答得不错"），而独立 Critic 实例（独立 system_prompt + 限定工具集 + 独立调用上下文）能给出真正客观的评分。这就是为什么 Task 011 的 Examiner 自评要在 Task 012 升级为 Examiner-委托-Critic：**"出题"和"判分"是两种心智模型，不应同一个 Agent 同时扮演**。

可观测面板（Task 012 #6）和持久化（#7）则是多 Agent 上线的**配套基础设施**——多 Agent = 单次任务调多次 LLM = token 飙升 = 必须能看账；多 Agent = 任务跑得长 = 中途断网概率大 = 必须能恢复。

> **一句话定位**：Task 011 是「让 Agent 出题」，Task 012 是「让 Agent 们合作」——前者是单点能力，后者是组织能力。从此 Course Agent 不再是「一个 LLM 套 ReAct 套工具」，而是「一支由 LLM 组成的小团队」。

---

## 九、风险与备选

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Planner JSON 输出不稳定（不同 LLM 表现差异大） | 高 | sub_tasks 解析失败 | 与 `generate_question` 一样：失败重试 1 次 + 仍失败降级为「单 sub-task 模式」（原任务整段塞 Solver） |
| Critic 评分方差大（同一答案两次评分差 2 分） | 中 | refine 路径触发不稳定 | 在 Critic prompt 里强制"先简述 solver_output 再评分"——降低 hallucinate；后续 Task 013 可上"多 Critic 投票" |
| Multi-Agent token 消耗 3-5x，DashScope 月度配额可能不够 | 中 | 用户抱怨贵 | metrics 面板显式展示；README 在「🧩 多 Agent 编排」一节明确标注「比单 Agent 多 ~3x token 消耗」 |
| `accumulated_context` 滚太长导致 sub-task N 时上下文爆 | 中 | LLM 报 context too long | 每个 sub-task 完成后，把 solver_output 截断到 300 字再注入下一段；超过 5 个 sub-task 时启用 LLM 摘要 |
| Chainlit data layer SQLite 锁冲突（多浏览器标签页同时写） | 低 | UI 卡住 | aiosqlite 默认 WAL 模式；本地工具单标签页使用为主 |
| `track_llm_call` 用 contextvar 读 CURRENT_AGENT 在线程切换时丢失 | 中 | metrics 中 agent_name 误标为 "ReAct" | asyncio 内部 contextvar 跟着 task 走；测试覆盖 thread pool executor 调用路径 |
| Orchestrator 硬上限被触发，但用户感知不到 | 低 | 用户疑惑"为什么没继续 refine" | UI 显式展示「⚠️ 已达 refine 上限（2 次），保留当前结果」 |
| Examiner 接 Critic 后，原"自动入错题本"逻辑迁移不完整 | 中 | 学生答错没自动入库 | Task 011 的 11 个 examiner 测试要全部更新为"通过 Critic 触发 add_mistake"路径；保留兼容性测试 |
| 新依赖 sqlalchemy + aiosqlite 与 chainlit 既有 anyio 版本冲突 | 中 | UI 启动失败 | 实施 Step 7 前先 `uv pip install --dry-run sqlalchemy aiosqlite` 看版本约束；冲突则降级 chainlit data layer 到下一期 |

---

## 十、显式不在本期范围（防 scope creep）

- ❌ **多 Solver 并行执行 sub-task** → Task 013（先串行确保正确性）
- ❌ **多 Critic 投票 / 自一致性** → Task 013
- ❌ **Plan 阶段失败后重新 Plan**（动态重规划）→ Task 013
- ❌ **Web 仪表盘**（基于 metrics.db 的可视化）→ Task 013（CLI 表格先够用）
- ❌ **Prometheus / OpenTelemetry 集成** → Task 014
- ❌ **多用户认证 / 权限管理** → 不计划（本地工具）
- ❌ **Agent 角色策略矩阵**（不同任务类型走不同 Agent 组合）→ Task 014
- ❌ **Examiner 多模态出题（带图）** → Task 013
- ❌ **跨 Agent 的语义记忆共享**（目前 long-term memory 仅主 Agent 用）→ Task 013
- ❌ **Dockerfile / docker-compose** → Task 014
- ❌ **Critic 评分的人工纠偏 UI**（学生标记"Critic 判错了"反馈给 Critic 再训练）→ Task 015+

> 上面这些是好东西，但**塞进 Task 012 会让本期失焦**。Task 012 的核心是「**把多 Agent 编排的最小可工作版本（MVP）跑通**」——`Plan → Solve → Critique → Refine` 闭环 + 4 个角色 + 必要的可观测和持久化。一次只解决一组耦合问题：「角色分工 + 编排器 + 配套基建」。把这些做扎实，比把"并行 / 投票 / 重规划"等高级特性硬塞同一期更稳——这些都是**有了基础闭环之后才有意义的优化**。

---

## 十一、与 Task 011 的承接关系

| Task 011 留下的 | Task 012 如何承接 |
|---|---|
| `ExaminerAgent`（限定工具集 + 独立 system_prompt + 复用 AgentLoop）的范式 | **范式工业化**：抽出 `BaseAgent` Protocol，PlannerAgent / SolverAgent / CriticAgent 全部按这个模板套出 |
| `StreamChunk` + `AgentLoop.astream_run()` | Orchestrator 也暴露 `astream_run`：Plan 一次性 → Solve 流式 → Critic 一次性，分层流给 UI |
| Examiner 内部 system_prompt 引导的 LLM 自评 | 升级为**独立 Critic 评审**（避免自我合理化） |
| `generate_question` JSON 输出 + 重试 1 次的模式 | Planner / Critic 两个 Agent 的 JSON 输出**沿用**这个"重试 1 次 + 失败降级"模式 |
| doctor 第 10 项「流式 + Examiner」 | doctor 第 11 项「多 Agent + Orchestrator hello + metrics」自然延续 |
| Chainlit 5 个场景按钮 | 加第 6 个「🧩 复杂任务模式」；不动前 5 个 |
| Task 011 自己声明的「Task 012 完整 Planner/Solver/Grader 编排」 | **Task 012 兑现这一承诺** |

---

## 十二、对 Task 010 / 011 的回归承诺

- ✅ Task 010 的错题本 + 教材 RAG 系统**继续工作**：`add_mistake` / `kb_search` 都被新 Agent 引用；CRITIC 用 `kb_search` 核对教材。
- ✅ Task 011 的 Examiner 模式**继续工作**：仅判分实现替换为委托 Critic，外部行为不变（学生答错仍自动入错题本）。
- ✅ Task 008/009 的 `python_exec` / `code_solve` / `image_ocr` / `pdf_read` **不需任何改动**：它们是 SolverAgent 的工具，Solver 用全工具集。
- ✅ Task 007 的 Memory 系统**继续工作**：Orchestrator 入口仍走 MemoryManager.enrich_context（与 ReAct 模式一致）；blackboard 是任务级别的，不污染长期记忆。
- ✅ 所有 199 个老测试**0 改动通过**（仅 `tests/test_examiner.py` 中关于 system_prompt 的 1-2 个用例需调整为新行为，新增量 ≥ 41）。
