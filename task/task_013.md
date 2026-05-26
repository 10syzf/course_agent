# Task 013：让 Agent「会借外脑」—— Skill Runtime + MCP Adapter + 外部能力渐进式接入

> 本 Task 基于 Task 012（多 Agent 编排 + 可观测面板 + Chainlit data layer + 253 passed）完成后的项目现状，规划下一阶段。
>
> **核心命题**：Task 012 已经把项目从「单 Agent 跑全场」推进到了「Planner / Solver / Critic / Orchestrator 四角分工」。但这些 Agent 目前仍然只会使用**项目内部自带的 17 个工具**。这意味着能力边界完全由本仓库决定: 想接浏览器自动化、外部知识系统、远程沙箱、内部工作流、专门的长链 Prompt 技能，只有两条路:
>
> 1. 要么继续把所有能力都硬塞进 `tools/`，导致工具目录越来越臃肿；
> 2. 要么临时写特殊逻辑，让 Orchestrator/Agent 去调用某个外部系统，最终把架构拉回「if/else 到处飞」。
>
> Task 013 要解决的是这个**架构分水岭**：
>
> - 一方面，我们要让 Agent **会调用“项目外部”的能力**，而不只是调用仓库内的 Python 工具；
> - 另一方面，我们又不能一口气把项目改造成一个重依赖、难调试、学习门槛很高的“平台怪兽”。
>
> 所以本 Task 的策略不是“直接全面接入一切”，而是：
>
> > **先抽象统一能力层（Capability Layer）**
> > → **先接本地 Skill Runtime（低风险、低依赖、最好测）**
> > → **再兼容 MCP Adapter（可选开启、渐进引入）**
> > → **后续 Task 再逐步扩大 Skill / MCP 的真实使用场景**
>
> 这会让项目从“会用内部工具的 Agent”升级为“会借外脑的 Agent”。

---

## 一、当前项目现状盘点（Task 012 收尾后）

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 / 异步 / 真流式 |
| Tool Registry | ✅ | 17 个内部工具，JSON Schema 完整 |
| 多 Agent | ✅ | Planner / Solver / Critic / Orchestrator / Examiner |
| 可观测面板 | ✅ | LLM 调用 token / latency / error 落 SQLite |
| Chainlit data layer | ✅ | 会话 / message / step 可持久化 |
| CLI | ✅ | `chat` / `doctor` / `metrics` / `mistakes` 等 |
| 测试质量 | ✅ | **253 passed + 6 skipped** |

### 1.2 当前明显的缺口

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **只能用内部工具** | ❌ `tools/` 之外没有统一能力接入层 | 每接一个外部系统都要定制改造 Agent / Orchestrator |
| **没有 Skill 机制** | ❌ 没有“高层任务模板 / Prompt Skill / 工作流 Skill”的概念 | 复杂能力只能写成底层工具，复用粒度太粗 |
| **没有 MCP 兼容层** | ❌ 无法使用 MCP server 暴露的外部工具与资源 | 浏览器、文件系统、远程沙箱、组织内部系统没法标准化接入 |
| **Planner 不知道“外部能力”存在** | ❌ Planner 只能建议内部工具 | 无法做“先选能力，再执行”的更高层规划 |
| **Capability 观测缺位** | ⚠️ metrics 只记录 LLM 调用 | Skill / MCP 的耗时、失败率、命中率不可见 |
| **Doctor 无法探活外部能力层** | ❌ 只有 Tool / LLM / Agent 检查 | Skill runtime、MCP 连接、配置错误无法一眼定位 |
| **Chainlit 无能力来源展示** | ⚠️ 只能看到 Tool step | 用户看不出来这次是内部工具、Skill 还是 MCP 在工作 |

### 1.3 Task 012 留给 Task 013 的自然延伸

Task 012 已经为 Task 013 铺好了三块地基：

1. **Agent 抽象层**  
   `BaseAgent` + `AgentMessage` 已经把“角色化 Agent”规范化，后续 Capability Router 可以挂在 Planner / Solver / Orchestrator 上，而不需要推翻原有 Agent 设计。

2. **可观测基础**  
   `metrics.py` 已经有 SQLite + contextvar + CLI 表格，这意味着 Skill / MCP 不需要另起一套监控系统，只要把指标维度扩充到 capability 层即可。

3. **Chainlit 分层展示**  
   复杂任务模式已经支持按 Agent 分层展示 Step，后续只要把 Step 再细分为 `internal_tool / skill / mcp`，前端认知成本很低。

---

## 二、为什么这一步应该引入 Skill / MCP

### 2.1 如果继续只堆内部工具，会发生什么

如果沿着当前路线继续开发，未来你会不断把新能力塞进 `tools/`：

- 浏览器自动化 → `browser_open`, `browser_click`, `browser_snapshot`
- GitHub 工作流 → `github_search_issues`, `github_create_pr`
- 远程沙箱 → `sandbox_run`, `sandbox_upload`
- 报告生成 → `generate_report`
- 学习计划 → `make_study_plan`
- 某个特定长流程 → `analyze_pdf_and_make_quiz`

这样做的问题不是“不能用”，而是**系统会逐渐失去层次**：

- 低层工具和高层能力混在一起
- Planner 无法区分“这是一把螺丝刀”还是“这是一个现成工作流”
- Tool registry 变成“万能杂物柜”
- 新人越来越看不懂“哪些能力该写成 Tool，哪些该写成 Agent，哪些该写成 Workflow”

### 2.2 Skill 和 MCP 各自解决什么问题

| 机制 | 本质 | 适合解决的问题 |
|---|---|---|
| **Skill** | 高层能力封装，通常是“Prompt + 参数 + 执行器 + 输入输出约定” | 复用某个复杂任务模板、一个多步工作流、一个专门场景能力 |
| **MCP** | 标准化外部能力协议，让本项目能接外部 server 暴露的工具 / 资源 | 接浏览器、远程文件、组织内平台、沙箱、知识系统、跨进程能力 |

可以把它们理解成：

- **Tool**：螺丝刀 / 扳手 / 电钻
- **Skill**：装一张桌子的“施工卡片”
- **MCP**：从别的工具房借来一套专业设备，并且有统一插头

### 2.3 为什么要“先 Skill，后 MCP”

直接 All in MCP 虽然听起来很酷，但对当前项目并不是最稳妥的第一步，原因有三：

1. **依赖与环境复杂度更高**  
   MCP 天然涉及外部 server、连接、超时、协议握手、版本兼容、可选认证。对教学项目来说，初次引入就全量落地，容易让任务重心从“架构设计”跑偏到“环境排障”。

2. **测试成本更高**  
   本项目一直强调“先把 mock 路径和离线路径做扎实”。Skill 可以全部本地化、纯 Python、可完全离线测试；MCP 更适合作为第二层、可选层。

3. **当前项目最缺的是“高层能力复用”**  
   很多需求其实并不一定非得连外部系统才能解决，比如“读 PDF 并整理成学习提纲”、“基于错题本生成复习计划”、“给一段代码做讲解并生成练习”。这些都更像 Skill，而不是 MCP Tool。

→ 所以 Task 013 的结论是：

> **先把 Skill Runtime 做出来，让系统先学会“调用高层能力”**；  
> **再用同一套 Capability 抽象兼容 MCP**，让未来外部接入顺滑落地。

---

## 三、候选开发方向（脑暴 + 打分）

8 个候选方向，按「价值 / 成本 / 与现有项目契合度」评分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **Capability 抽象层**（统一 Tool / Skill / MCP） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Task 013 的总地基，不先做这个，后面全是硬编码 |
| **2** | **Local Skill Runtime** | 🔥🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 最低风险的第一步，可纯离线测试，可立即带来“高层能力复用” |
| **3** | **MCP Adapter（客户端）** | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 先做兼容层和 mock server，真实接入循序渐进 |
| **4** | **Capability Router**（Planner / Solver 选能力） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 让系统不仅知道“有什么能力”，还知道“什么时候该调用谁” |
| **5** | **Capability Metrics**（skill/mcp 耗时、失败率） | 🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 复用已有 observability 基础，性价比极高 |
| **6** | **CLI 能力探测**（`skills list` / `mcp list` / `capabilities`） | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 对调试、教学、排障非常重要 |
| **7** | **Chainlit 能力来源展示** | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 让用户理解“本次能力来自内部 / skill / mcp” |
| 8 | Skill 市场 / 动态安装 | 🔥🔥🔥🔥 | 高 | ⭐⭐ | ⭐⭐ | 很诱人，但太早，先不碰 |

### 3.1 挑选逻辑

- **#1 Capability 抽象层**：必做。它决定项目是不是“平台化”而不是“堆功能”。
- **#2 Local Skill Runtime**：必做。它是最低风险、最高收益的第一层落地。
- **#3 MCP Adapter**：必做，但本期只做到“兼容接入 + mock / demo”，不追求一口气接全所有真实 server。
- **#4 Capability Router**：必做。否则 Skill / MCP 只是孤立存在，Agent 不会真正用起来。
- **#5 Capability Metrics**：必做。Task 012 已经有 metrics，不接上就很可惜。
- **#6 CLI 能力探测**：必做。没有 CLI，能力层是黑盒。
- **#7 Chainlit 能力来源展示**：建议做，实施成本低，教学价值高。
- **#8 Skill 市场 / 动态安装**：推后。先把基础 runtime 做稳。

→ **本期（Task 013）聚焦**：

> **Capability Layer + Local Skill Runtime + MCP Adapter（实验性） + Capability Router + Metrics + CLI + Chainlit 展示**

---

## 四、Task 013 目标（本期范围）

> **主题：从“会用内部工具”到“会借外脑”—— 统一能力层 + Skill 优先 + MCP 兼容**

### 4.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ 新建 `course_agent/capabilities/base.py`：定义 `CapabilityKind` / `CapabilitySpec` / `CapabilityCallResult` / `BaseCapabilityProvider` | ❌ 一开始就把 Tool Registry 整体推翻重写 |
| ✅ 新建 `course_agent/capabilities/registry.py`：统一注册 `internal_tool / skill / mcp` 三类能力元信息 | ❌ 动态插件热加载 / 远程安装 |
| ✅ 新建 `course_agent/capabilities/router.py`：实现最小可用的 `CapabilityRouter`，支持 Planner / Solver 根据任务和白名单选能力 | ❌ 复杂策略学习 / 强化学习式能力选择 |
| ✅ 新建 `course_agent/skills/` 目录：实现 Local Skill Runtime（本地 Skill 清单 + 参数 schema + 执行器） | ❌ Skill 市场 / 第三方下载中心 |
| ✅ 至少落地 **2 个内建 Skill Demo**：如 `summarize_pdf_skill`、`study_plan_skill` 或 `quiz_from_notes_skill` | ❌ 一口气做十几个 Skill |
| ✅ 新建 `course_agent/mcp/client.py`：MCP 客户端适配层（配置、连接、列出工具、调用工具） | ❌ 上来就接多种认证、远端集群、复杂资源订阅 |
| ✅ 新建 `course_agent/mcp/mock_server.py` 或测试夹具：提供离线可测的 mock MCP server | ❌ 强依赖用户本机必须装真实 MCP server 才能开发 |
| ✅ CLI 新增：`course-agent capabilities` / `course-agent skills list` / `course-agent mcp list` | ❌ 丰富到像 package manager 一样的完整 CLI |
| ✅ Chainlit 在复杂任务模式里展示能力来源：`内部工具 / Skill / MCP` | ❌ 复杂可视化拓扑图 |
| ✅ `observability/metrics.py` 扩展：记录 capability 调用统计（kind / name / status / latency） | ❌ Prometheus / Grafana / 外部 APM |
| ✅ doctor 第 12 项：Skill runtime 可用 + MCP mock 探活 + capability registry 可读 | ❌ doctor 大改；只加一项 |
| ✅ 与 Task 012 完全兼容：旧的 ToolRegistry 与 AgentLoop 继续可用 | ❌ 让旧工具调用路径失效 |

### 4.2 本期“渐进式引入”策略

这是 Task 013 最重要的设计原则：**不要一上来就强迫全系统依赖 Skill/MCP**。

#### Phase A：统一抽象先落地（本期必做）

- 有 `CapabilitySpec`
- 有 `CapabilityRegistry`
- 有 `CapabilityRouter`
- 但默认仍可只走内部 Tool

#### Phase B：先让 Solver 会用 Local Skill（本期必做）

- Skill 是本地能力，零网络、零外部依赖、最好测
- 先只让 Solver / Orchestrator 知道 Skill
- Planner 先只在 `suggested_capabilities` 里能提到 Skill

#### Phase C：MCP 作为“可选增强”（本期必做，但只做实验性）

- 若环境里配置了 MCP server，则可被 Capability Registry 发现
- 若未配置，则系统正常运行，不报错、不崩
- 测试路径主要基于 mock MCP server

#### Phase D：后续 Task 再扩大使用面（本期明确留钩子）

- Planner 学会主动选择 Skill / MCP
- Chainlit 可以直接切到“外部能力模式”
- Doctor 加真实 MCP server 连接检查
- 引入并行 capability 执行、HITL 审批、外部权限控制

---

## 五、成功指标（本期验收标准）

1. [x] `course-agent capabilities` 能列出三类能力：`internal_tool / skill / mcp`，并带 schema / 描述 / 来源
2. [x] Local Skill Runtime 至少有 **2 个内建 Skill**，能被 Solver 发现并调用
3. [x] 未配置任何 MCP server 时，系统**正常工作**，CLI / doctor / Chainlit 都不崩
4. [x] 配置 mock MCP server 后，`course-agent mcp list` 能列出可调用工具
5. [x] Solver 在复杂任务中可调用 Skill，且 Chainlit Step 上能看到 `Skill: xxx`
6. [x] Solver 在复杂任务中可调用 MCP tool，且 Chainlit Step 上能看到 `MCP: server/tool`
7. [x] Capability Router 能根据能力类型和白名单做最小决策，不会把禁用能力暴露给 Agent
8. [x] `course-agent metrics` 能看到 capability 统计项（kind / name / latency / error_rate）
9. [x] doctor 第 12 项通过：Skill runtime OK + capability registry OK + MCP mock OK / skip
10. [x] 旧的 17 个内部工具和 Task 012 的多 Agent 流程保持可用，无回归
11. [x] 单测新增后，`pytest` 总数 ≥ **300 passed**
12. [x] `ruff check .` 全绿，README 补充 Task 013 的三节说明

---

## 六、技术方案

### 6.1 顶层设计：统一 Capability Layer

**新目录**：

```text
course_agent/
├── capabilities/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── router.py
│   └── adapters.py
├── skills/
│   ├── __init__.py
│   ├── runtime.py
│   ├── registry.py
│   ├── builtin.py
│   └── manifests/
├── mcp/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   └── mock_server.py
```

**核心思想**：

- 内部 Tool 不废弃，而是被包装成 `CapabilityKind.INTERNAL_TOOL`
- Local Skill 是 `CapabilityKind.SKILL`
- MCP server 暴露的 tool 是 `CapabilityKind.MCP`

上层 Agent / Router 不再关心“这是 tools 目录里的函数，还是外部 server 的 tool”，只关心：

- 它叫什么
- 它做什么
- 它的参数 schema 是什么
- 它当前是否可用
- 它是不是在我的白名单里

### 6.2 基础数据结构

**新文件** `course_agent/capabilities/base.py`：

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field


class CapabilityKind(str, Enum):
    INTERNAL_TOOL = "internal_tool"
    SKILL = "skill"
    MCP = "mcp"


class CapabilitySpec(BaseModel):
    name: str
    kind: CapabilityKind
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    source: str = ""                 # tool_registry / skills / mcp:server_name
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class CapabilityCallResult(BaseModel):
    capability_name: str
    kind: CapabilityKind
    ok: bool = True
    output: str = ""
    error: str | None = None
    latency_ms: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)


class BaseCapabilityProvider(Protocol):
    provider_name: str

    def list_capabilities(self) -> list[CapabilitySpec]:
        ...

    async def call(self, name: str, arguments: dict[str, Any]) -> CapabilityCallResult:
        ...
```

### 6.3 Capability Registry

**新文件** `course_agent/capabilities/registry.py`：

职责：

1. 汇总三类 provider 的能力清单
2. 提供按 kind / tag / enabled / source 过滤
3. 对外给 CLI / Planner / Solver / Chainlit 统一使用

关键 API：

```python
class CapabilityRegistry:
    def __init__(self) -> None:
        self._providers: list[BaseCapabilityProvider] = []

    def register_provider(self, provider: BaseCapabilityProvider) -> None: ...
    def list_all(self) -> list[CapabilitySpec]: ...
    def list_by_kind(self, kind: CapabilityKind) -> list[CapabilitySpec]: ...
    def get(self, name: str) -> CapabilitySpec | None: ...
```

**关键决策**：

- 不替换现有 `ToolRegistry`，而是**包装它**
- 保证老路径继续可用
- 让新能力层可以平滑压在旧架构之上

### 6.4 Local Skill Runtime

#### 6.4.1 Skill 的定义方式

Skill 不是低层工具，而是“高层任务模板 / 场景能力”。

建议每个 Skill 由四部分组成：

1. `name`
2. `description`
3. `parameters schema`
4. `executor`

可以先不用做复杂 DSL，直接做最稳妥的 Python 注册模式：

```python
class SkillSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
    tags: list[str] = []


@skill(
    name="study_plan_skill",
    description="基于错题本和教材范围生成 7 天复习计划",
    parameters={...},
    tags=["study", "planner"],
)
async def study_plan_skill(ctx: SkillContext, topic: str, days: int = 7) -> str:
    ...
```

#### 6.4.2 为什么 Skill 不直接等于 Tool

因为 Skill 的粒度比 Tool 大，它可以：

- 组合多个内部工具
- 带自己的 prompt 模板
- 带自己的执行策略
- 约束输出格式

示例：

- `summarize_pdf_skill`
  - 内部可调 `pdf_read`
  - 再调 LLM 生成结构化摘要

- `quiz_from_notes_skill`
  - 内部可调 `kb_search` / `generate_question`
  - 输出统一的练习题 markdown

这类能力如果写成 Tool，会让 Tool 与 Workflow 混在一起；写成 Skill 更清晰。

#### 6.4.3 本期建议落地的 2 个 Skill Demo

| Skill | 价值 | 可能复用的内部工具 |
|---|---|---|
| `study_plan_skill` | 基于错题本和教材范围生成复习计划 | `list_mistakes`, `kb_search` |
| `quiz_from_notes_skill` | 根据笔记 / 文本生成练习题 | `generate_question`, `kb_search` |

二者都不强依赖外部系统，适合先跑通 Skill Runtime。

### 6.5 MCP Adapter（实验性接入）

#### 6.5.1 本期只做“兼容层 + mock”

Task 013 不追求上来就稳定接浏览器、GitHub、沙箱等所有真实 MCP server。本期只做三件事：

1. 有 `MCPClientProvider`
2. 能从配置里读取 server 列表
3. 能在 mock server 下完成 `list_tools` + `call_tool`

#### 6.5.2 配置草案

可在 `config/default.yaml` 增加：

```yaml
mcp:
  enabled: false
  servers:
    - name: demo
      transport: stdio
      command: "python"
      args: ["-m", "course_agent.mcp.mock_server"]
      timeout_s: 15
```

#### 6.5.3 Provider 形态

```python
class MCPClientProvider:
    provider_name = "mcp"

    def __init__(self, cfg: MCPConfig) -> None:
        ...

    def list_capabilities(self) -> list[CapabilitySpec]:
        # 把每个 server 的 tool 转成 CapabilitySpec(kind=MCP)
        ...

    async def call(self, name: str, arguments: dict[str, Any]) -> CapabilityCallResult:
        ...
```

#### 6.5.4 为什么要做 mock MCP server

因为本项目的测试哲学一直是：

- 默认离线可跑
- 真环境测试可选
- mock 路径足够覆盖主逻辑

MCP 若不做 mock，Task 013 的单测体系会立刻变脆。

### 6.6 Capability Router

#### 6.6.1 角色定位

Router 不负责“思考任务本身”，而负责“把可用能力筛干净并选择候选集合”。

它的输入：

- 当前 Agent（Planner / Solver / Critic / Examiner）
- 用户任务或 sub-task
- 当前白名单
- 当前可用 capability 清单

它的输出：

- 允许暴露给 LLM 的能力子集
- 或直接在某些场景下走“路由直达”

#### 6.6.2 最小路由规则（本期）

**Planner**：

- 默认只看 `internal_tool` 中的 `kb_search`, `list_mistakes`
- 可额外看到 Skill 的“名字 + 描述”，但**不能直接执行**
- 目的是让 Planner 知道未来 Solver 可调用哪些高层能力

**Solver**：

- 可看到内部工具 + enabled skill + enabled mcp
- 但必须受白名单控制

**Critic**：

- 继续严格收口，只允许 `kb_search`
- 本期不让 Critic 用 Skill / MCP，避免评审面失控

### 6.7 Metrics 扩展

Task 012 的 metrics 只记录 LLM 调用；Task 013 需要再补一类：

```sql
CREATE TABLE capability_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    capability_name TEXT NOT NULL,
    capability_kind TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ok',
    error TEXT
);
```

CLI `course-agent metrics --raw` 可扩展为两块：

1. LLM metrics
2. Capability metrics

### 6.8 Chainlit 展示

Task 012 已经有按 Agent 分层的 Step；Task 013 再加一层“能力来源标识”即可：

- `Tool: pdf_read`
- `Skill: study_plan_skill`
- `MCP: demo/search_notes`

这样用户能立刻理解：

> 这次不是“系统内部工具”在干活，而是借了一个 Skill 或 MCP 能力。

### 6.9 CLI 设计

建议新增三个命令：

```bash
course-agent capabilities
course-agent skills list
course-agent mcp list
```

#### 6.9.1 `course-agent capabilities`

统一表格输出三类能力：

| Name | Kind | Source | Enabled | Description |

#### 6.9.2 `course-agent skills list`

只列 Local Skill，便于调试 Skill runtime。

#### 6.9.3 `course-agent mcp list`

只列 MCP server 与其暴露工具；未配置时给出友好提示，不报错。

### 6.10 doctor 第 12 项

新增 `_check_capabilities_and_mcp()`：

检查内容：

1. Capability Registry 可实例化
2. 至少能列出内部 Tool + Local Skill
3. 若 MCP 未开启，则返回 `⚠️ skip` 但不算失败
4. 若 MCP 开启，则尝试 mock / demo 探活

目标输出：

```text
12  外部能力层（Skill + MCP）   ✅ / ⚠️
```

---

## 七、与 Task 012 的接口关系

### 7.1 不推翻 Tool Registry

Task 013 不会推翻 `ToolRegistry`，而是把它包成 Capability Provider。

原因：

- 否则 Task 008/009/010/011/012 的大量代码都得重写
- 不符合“渐进式引入”的原则

### 7.2 不强迫所有 Agent 立即使用 Skill / MCP

本期只要求：

- Solver 支持 Skill / MCP
- Planner 知道它们存在
- Critic 暂不放开

这是一种**安全收口**：

- 先让“执行者”学会借外脑
- 不让“评审者”也变成黑盒

### 7.3 Orchestrator 暂不做并行 capability

虽然 Task 013 已经引入了更丰富的能力来源，但本期**仍不做并行执行**：

- Skill 与 MCP 的超时 / 失败语义还没完全打磨
- 并发一上来会让排障复杂度暴增

并行能力建议留给后续 Task。

---

## 八、渐进式路线图（Task 013 之后怎么继续）

这是本 Task 最关键的一部分：**Task 013 不是终点，而是 Capability Platform 的起点**。

### 8.1 Task 013（本期）

目标：

- 统一 Capability Layer
- Local Skill Runtime
- MCP Adapter（实验性）
- CLI / doctor / metrics / Chainlit 打通

特点：

- Skill 优先
- MCP 可选
- 完整离线可测

### 8.2 Task 014（建议后续）

主题建议：

> **让 Planner 真正会“选能力”—— Capability-aware Planning + Prompt Skill 编排**

建议内容：

- Planner 输出 `suggested_capabilities`
- 路由规则升级成 capability-aware planning
- 引入 3~5 个高价值 Skill
- Chainlit 新增“能力推荐”展示

### 8.3 Task 015（建议后续）

主题建议：

> **让外部能力接入进入生产可用态—— Real MCP Servers + 权限控制 + 超时治理**

建议内容：

- 接真实 MCP server（浏览器 / 沙箱 / 文件系统）
- 能力白名单与权限控制
- 长耗时 capability 的 timeout / retry / cancel
- doctor 对真实 server 做分级探活

### 8.4 Task 016（建议后续）

主题建议：

> **让外部能力成为“工作流节点”—— 并行 Capability + HITL 审批 + 可回放编排**

建议内容：

- 并行 Skill / MCP fan-out
- Human-in-the-loop 审批
- 外部能力调用的回放、审计、trace tree

→ 也就是说：

> **Task 013 先把“插座标准”定下来；Task 014+ 再不断往上插更多设备。**

---

## 九、实施步骤（建议顺序）

### Step 1：Capability 基础抽象

- `capabilities/base.py`
- `capabilities/registry.py`
- `capabilities/__init__.py`

### Step 2：包装现有 ToolRegistry

- 写 `InternalToolProvider`
- 把现有 17 个内部工具暴露为 `CapabilitySpec(kind=INTERNAL_TOOL)`

### Step 3：Local Skill Runtime

- `skills/runtime.py`
- `skills/registry.py`
- `skills/builtin.py`
- 先落 2 个 Skill demo

### Step 4：Capability Router

- 给 Planner / Solver 挂路由能力
- 保持 Critic 收口

### Step 5：MCP Adapter（mock first）

- `mcp/client.py`
- `mcp/config.py`
- `mcp/mock_server.py`

### Step 6：CLI + doctor + metrics

- `course-agent capabilities`
- `course-agent skills list`
- `course-agent mcp list`
- doctor 第 12 项
- capability metrics 表

### Step 7：Chainlit 展示

- Step 上标出 Tool / Skill / MCP 来源
- 复杂任务模式下能看到调用来源

### Step 8：测试 + README + 验收

- 新增测试矩阵
- README 补 Task 013
- 目标总测试数 ≥ 300

---

## 十、测试矩阵

### 10.1 新增测试文件（建议 ≥ 48 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_capability_base.py` | `CapabilitySpec` / `CapabilityKind` / `CapabilityCallResult` / provider duck typing | ≥ 6 |
| `tests/test_capability_registry.py` | 注册 / 去重 / 按 kind 过滤 / enabled 过滤 | ≥ 6 |
| `tests/test_skill_runtime.py` | Skill 注册 / schema / 调用 / 异常处理 | ≥ 8 |
| `tests/test_skill_builtin.py` | 2 个 demo skill 的 happy path / 参数边界 | ≥ 6 |
| `tests/test_mcp_adapter.py` | mock server 探活 / list_tools / call_tool / timeout / 未配置降级 | ≥ 8 |
| `tests/test_capability_router.py` | Planner / Solver / Critic 的能力收口 | ≥ 6 |
| `tests/test_cli_capabilities.py` | `capabilities` / `skills list` / `mcp list` 输出不崩 | ≥ 5 |
| `tests/test_cli_doctor_12.py` | doctor 第 12 项 mock path / skip path / error path | ≥ 4 |
| `tests/test_orchestrator_capabilities.py` | Solver 在多 Agent 流程中调用 skill / mcp 的链路 | ≥ 5 |

### 10.2 回归测试

- Task 012 的 253 个通过用例继续通过
- 老的 17 个内部工具测试零回归
- Planner / Solver / Critic / Orchestrator 原能力不受破坏

### 10.3 验收门槛

- `pytest -q` ≥ **300 passed**
- `ruff check .` 全绿
- `course-agent doctor` 第 1～12 项不崩

---

## 十一、交付物 Checklist

### 代码

- [x] `course_agent/capabilities/base.py`
- [x] `course_agent/capabilities/registry.py`
- [x] `course_agent/capabilities/router.py`
- [x] `course_agent/capabilities/__init__.py`
- [x] `course_agent/skills/runtime.py`
- [x] `course_agent/skills/registry.py`
- [x] `course_agent/skills/builtin.py`
- [x] `course_agent/skills/__init__.py`
- [x] `course_agent/mcp/client.py`
- [x] `course_agent/mcp/config.py`
- [x] `course_agent/mcp/mock_server.py`
- [x] `course_agent/mcp/__init__.py`
- [x] [cli.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/cli.py)：新增 `capabilities` / `skills list` / `mcp list` / doctor 第 12 项
- [x] [observability/metrics.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/observability/metrics.py)：扩 capability metrics
- [x] [ui/chainlit_app.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/ui/chainlit_app.py)：展示能力来源（Tool / Skill / MCP）
- [x] [agent/solver.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/agent/solver.py)：接 Capability Router
- [x] [agent/planner.py](file:///Users/bytedance/Desktop/syzf项目/cousre_agent/course_agent/agent/planner.py)：能感知 Skill / MCP 名称与描述

### 测试 / 配置

- [x] `tests/test_capability_base.py`
- [x] `tests/test_capability_registry.py`
- [x] `tests/test_skill_runtime.py`
- [x] `tests/test_skill_builtin.py`
- [x] `tests/test_mcp_adapter.py`
- [x] `tests/test_capability_router.py`
- [x] `tests/test_cli_capabilities.py`
- [x] `tests/test_cli_doctor_12.py`
- [x] `tests/test_orchestrator_capabilities.py`
- [x] `pytest -q` ≥ **300 passed**
- [x] `ruff check .` 全绿

### 文档

- [x] `README.md` 新增「🧠 Skill Runtime」一节
- [x] `README.md` 新增「🔌 MCP Adapter（实验性）」一节
- [x] `README.md` 新增「🧰 统一 Capability Layer」一节
- [x] `README.md` 进度表添加 Task 013 行；doctor 11 → **12 项**；测试数 253 → **≥ 300**
- [x] `README.md` 项目结构补 `capabilities/`、`skills/`、`mcp/`
- [x] `task/task_013.md`（本文）成功指标与交付物全勾

### 验证脚本（推荐手动跑）

- [x] `course-agent capabilities`
- [x] `course-agent skills list`
- [x] `course-agent mcp list`
- [ ] `course-agent doctor` → 12/12
- [ ] Chainlit 复杂任务模式下出现 `Skill:` / `MCP:` 来源标记

---

## 十二、教学性总结：为什么 Task 013 是“工具系统 → 能力平台”的拐点

Task 008/009/010/011/012 的连续演进，本质上是在做三件事：

1. 让 Agent **能行动**（Tool）
2. 让 Agent **会分工**（Multi-Agent）
3. 让系统 **可观测、可持久化、可调试**

但到 Task 012 为止，能力边界仍然被仓库本身锁死。Task 013 的意义在于：

> **把“能力”从“项目源码里的函数”提升为“可注册、可路由、可观测、可渐进扩展的统一对象”。**

这带来三个长期收益：

### 12.1 架构层

以后再接新能力，不必再纠结“它该塞到 tools 还是 agent 还是别的地方”，而是先问：

> 它是低层工具、场景 Skill，还是外部 MCP 能力？

这会让整个项目的抽象层次开始清晰。

### 12.2 工程层

Skill 可以本地演化、快速试错；MCP 可以标准化接外部系统。两者共享同一套 Capability Layer，意味着未来不会出现两套平行体系各玩各的。

### 12.3 教学层

Task 013 很适合让学生理解：

- 什么是低层工具
- 什么是高层技能
- 什么是外部协议
- 为什么“抽象先行”比“功能堆叠”更重要

如果 Task 012 是“让 Agent 学会分工”，那 Task 013 就是：

> **让这群 Agent 不只会用自己手里的工具，还会去借别人的工具箱。**
