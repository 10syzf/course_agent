# Task 011：让 Agent「答得顺」+「考得出」—— 真流式输出 / 题目生成器 / Examiner Agent 雏形

> 本 Task 基于 Task 010（错题本 SM-2 + 教材 RAG + 主动学习提示 + doctor 9 项）完成后的项目现状，规划下一阶段。
>
> **核心命题**：Task 010 把「学生侧错题状态」与「教材侧知识状态」两个数据底座搭好了——但当前 Agent 还**只会被动回答**：长答案要 `arun` 把整段 LLM 输出拼完才返回，体感像「卡 5 秒突然刷出来」；错题本里躺着的 30 道线代错题，Agent **不会主动出一道同类型的新题**让学生练。Task 011 要补两件事——**让答案像打字机一样流出来**、**让 Agent 会出题**——并顺手把多 Agent 编排的第一块砖（**Examiner Agent**）落地，为 Task 012 的完整 Planner/Solver/Grader 编排开路。

---

## 一、当前项目现状盘点（Task 010 收尾后）

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 + 异步 + 回调；**当前 `arun` 等 LLM 整段返回再 yield 一次** |
| LLM 抽象层 | ✅ | 文本：OpenAI 兼容；多模态：直接 OpenAI SDK |
| Tool Registry | ✅ | `@tool` + JSON Schema |
| **16 个工具** | ✅ | calculator / file_read / file_write / web_search / web_fetch / python_exec / pdf_read / image_ocr / code_solve / recall / remember / **add_mistake / list_mistakes / review_mistake / kb_ingest / kb_search** |
| Memory 子系统 | ✅ | 短期滑窗 + LLM 摘要 + Chroma 长期向量库（`mem_long_term`） |
| 数据底座 | ✅ | **SQLite 错题本（SM-2）** + **Chroma 教材库（`kb_textbook`）** |
| 主动学习提示 | ✅ | Chainlit `on_chat_start` 显示「📓 今天 N 道待复习」+ `/mistakes` slash |
| CLI | ✅ | `chat` / `tools` / `version` / `ui` / `doctor`（**9 项**） / **`mistakes` 子命令** |
| 错误分类 | ✅ | 6 类（Task 008 固化） |
| 测试 + Lint | ✅ | **154 passed + 6 skipped**；ruff clean |

### 1.2 当前明显的缺口

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **答案"卡顿现身"** | ❌ `arun` 等 LLM 整段返回，前端 chunk 一次性出现 | 长答案（>500 字）UX 极差；对比 ChatGPT/Claude 打字机出字差距明显 |
| **错题躺尸** | ❌ 错题本只能复习「原题」，不能造「同类新题」 | 学生记下「特征值分解」错题后，每次复习都看同一道题，无法**举一反三**；浪费了教材库这个素材库 |
| **多 Agent 编排** | ❌ `agent/` `orchestrator/` 仍空 | Task 010 把数据备齐了，但「出题人 / 解题人 / 批改人」分工还是空头支票 |
| **答题 → 错题本**自动化 | ⚠️ Task 010 的 Action 按钮是**学生手点**，不是 Agent 自评 | 学生懒得点；理想是 Agent 自己判错并自动入库（弱 grader） |
| **可观测面板** | ⚠️ 只有 loguru | UI 看不到 token 消耗 / 工具失败率 |
| **会话持久化** | ❌ Chainlit data layer 未开 | 关浏览器丢消息原文 |
| **LaTeX 公式渲染** | ⚠️ Chainlit 默认 KaTeX 但未做样例验证 | OCR 出来的公式还是纯文本难看 |

### 1.3 Task 010 实战教训沉淀

| 教训 | 已修复 | 仍需注意 |
|---|---|---|
| 工具数量上 16，`tools_for_llm()` payload 体积变大 | ⚠️ 暂未拆分 | Task 011 出题工具一旦上线（17~18 个），要监控 token 占用；必要时按「scene」按需注入 |
| `@tool` 装饰器返回原函数（不是 wrapper），单测可直接调用 | ✅ 教训沉淀 | 写新工具的单测时不要再误用 `.func` |
| `kb_search` HashEmbedder 兜底召回率差 | ⚠️ Task 010 已加警告条 | Task 011 出题强依赖召回，若仍处于 hash 兜底，应在 UI 提示「出题质量受限」 |
| Chainlit `Action` 按钮 1.x 仍稳定 | ✅ | 多 Action 时可统一收口到 `@cl.action_callback` 路由 |
| Chroma collection 命名隔离（`mem_long_term` vs `kb_textbook`）做得好 | ✅ | Task 011 若再开新 collection，沿用前缀风格（`gen_`/`agent_` 等） |

---

## 二、候选开发方向（脑暴 + 打分）

10 个候选，按「价值 / 成本 / 与现有代码契合度」打分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **真流式 streaming**（token-by-token through Chainlit） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | UX 最直观跃升；OpenAI / DashScope SDK 都支持 `stream=True`；改动集中在 LLM 层 + agent_loop + chainlit_app 三处 |
| **2** | **题目生成器** `generate_question` | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 把 Task 010 错题本 + 教材库变成**生产工具**；让陪学闭环（错题→复习→新题→再练） |
| **3** | **Examiner Agent**（多 Agent 编排第一块砖） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 把 #2 包装成有「人格」的 Agent；为 Task 012 完整 Planner/Solver/Grader 铺路 |
| **4** | 自动 grader（Agent 自判答错并入错题本） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 把 Task 010 「学生手点」升级成「Agent 自评」；与 #3 天然耦合 |
| 5 | Chainlit data layer 持久化 | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 流式上线后，half-message 持久化更有意义；可作为附加 |
| 6 | 可观测面板（token / 时延 / 失败率） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 流式上线后正好能看 token/s |
| 7 | LaTeX 公式渲染样例 / 数学增强 | 🔥🔥🔥 | 低 | ⭐⭐⭐ | ⭐⭐⭐ | Chainlit 默认 KaTeX 已支持，需要的是 system prompt + 样例验证 |
| 8 | Dockerfile + docker-compose | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 推广必备但当前个人用户 `uv sync` 撑得住 |
| 9 | 完整 Planner / Solver / Grader 编排 | 🔥🔥🔥🔥🔥 | 高 | ⭐⭐⭐ | ⭐⭐⭐ | 体量大；Task 011 先落 Examiner，Task 012 再上完整三角，更稳 |
| 10 | mistake → kb 反向链接（错题自动关联教材出处） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 与 #2 部分重叠，可作为 `generate_question` 的副产物 |

### 2.1 挑选逻辑

- **#1 真流式**：Task 009 / Task 010 都识别过、都因「与 tool_call 拼装强耦合」推后；现在错题本 / 教材库都稳了，没有更紧迫的功能债，是开刀的最好时机。**必做**。
- **#2 题目生成器**：Task 010 数据底座的**第一个变现**——错题本若不能繁殖出新题，本质还是个备忘录。**必做**。
- **#3 Examiner Agent**：把 #2 升级为有「身份感」的子 Agent（system_prompt + 限定工具集 + 独立调用入口），**为 Task 012 多 Agent 编排开路**。它是「砖头」，不是「整面墙」——本期只做这一块砖。**必做**。
- **#4 自动 grader**：与 #3 天然耦合（Examiner 出题 → Solver 答 → Grader 判）。本期做**最简版**：Examiner 自己生成 `correct_answer` + 答错后调 `add_mistake` 自动入库；完整 Grader 留 Task 012。
- **#5～#10** 留作后续。

→ **本期（Task 011）聚焦**：#1 真流式 + #2 题目生成器 + #3 Examiner Agent 雏形 + #4 极简自动入错题本

---

## 三、Task 011 目标（本期范围）

> **主题：从「会陪学」到「会出题」+「答得顺」—— 学习闭环的执行层**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ `BaseLLM.astream()` 抽象 + OpenAI 兼容实现（`stream=True`） | ❌ 同步 `stream()`（先只做 async；CLI 输出不强求流式） |
| ✅ `AgentLoop.astream_run()`：**逐 token yield 文本** + **工具调用阶段标记** | ❌ 工具结果回流时也流式（工具结果天然是一次性 string） |
| ✅ Chainlit 端用 `cl.Message.stream_token()` 渲染流式 | ❌ Chainlit Step 流式（先把主消息流起来即可） |
| ✅ 流式过程中 fallback 到非流式：网络断开 / SDK 不支持时降级 | ❌ 自定义 SSE 协议（用 SDK 自带的 generator 就行） |
| ✅ `generate_question` 工具：输入 tag/题型/难度，调 `kb_search` 取参考素材 + LLM 生成 | ❌ 多模态出题（带图）；先纯文本题 |
| ✅ 出题工具返回结构化 JSON：`{question, options?, correct_answer, explanation, source}` | ❌ 自动化的「出 100 道试卷」批量模式（先单题） |
| ✅ `Examiner` Agent 类（`course_agent/agent/examiner.py`），有独立 system_prompt + 限定工具集（`kb_search` + `generate_question` + `add_mistake`） | ❌ 完整 Planner/Solver/Grader 三角；本期只做 Examiner 一个 |
| ✅ Chainlit 新增「📝 出题模式」按钮（场景按钮列表加一项），切到 Examiner | ❌ 多 Agent 之间的消息传递协议（Task 012 再设计） |
| ✅ Examiner 出题 → 学生答 → 答错时**自动**调 `add_mistake`（不再依赖手点） | ❌ 复杂的 grader 评分系统（先字符串匹配 / LLM-as-judge 二选一，简版） |
| ✅ doctor 第 10 项：检查流式可用性 + Examiner 注册情况 | ❌ Doctor 大改；只加一项 |
| ✅ 完全向后兼容：默认仍是 ReAct Agent；只有进入 Examiner 模式才走新链路 | — |

### 3.2 成功指标

1. [x] Chainlit 提问「请讲解动态规划」，答案以**打字机方式**逐字出现（视觉上明显流式，非"卡 5 秒突现"）
2. [x] 流式过程中可以看到工具调用的中间状态（"正在调用 kb_search..."）
3. [x] 网络断开 / SDK 报错时，自动降级到非流式 `arun`，无 traceback 暴露给用户
4. [x] `generate_question(tag="线代,特征值", difficulty="中")` 返回一道**新**的、未在错题本中出现过的同类题，附 correct_answer + 教材出处
5. [x] Chainlit 点击「📝 出题模式」→ Agent 自我介绍为 Examiner → 主动出一道题 → 学生答错时自动入错题本（无需手点 Action）
6. [x] Examiner Agent **不调用** `python_exec` / `web_search` 等出题不需要的工具（限定工具集生效）
7. [x] `course-agent doctor` 第 10 项检查通过：流式探活成功 + Examiner 可实例化
8. [x] 全部新代码有单测，**pytest ≥ 175 passed**，ruff clean
9. [x] HashEmbedder 兜底场景下 `generate_question` 不崩，但会在题目末尾附「⚠️ 当前 hash 兜底，参考素材召回有限」
10. [x] README 增加「⌨️ 流式输出 / 📝 Examiner Agent 出题模式」两节用法

---

## 四、技术方案

### 4.1 流式抽象层

**新增 `BaseLLM.astream()`**（位于 [base.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/base.py)）：

```python
from typing import AsyncIterator
from dataclasses import dataclass

@dataclass
class StreamChunk:
    """流式片段：文本增量或 tool_call 增量。"""
    delta_text: str = ""              # 当前 chunk 增量文本
    tool_call_delta: dict | None = None  # tool_call 拼装中
    finish_reason: str | None = None  # stop / tool_calls / length / error

class BaseLLM(ABC):
    @abstractmethod
    async def astream(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]: ...
```

**OpenAI 兼容实现**（[openai_like.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/openai_like.py)）：

```python
async def astream(self, messages, tools=None, **kwargs):
    client = self._get_async_client()
    payload = {"model": self.model, "messages": [m.to_openai() for m in messages], "stream": True}
    if tools: payload["tools"] = tools
    try:
        stream = await client.chat.completions.create(**payload)
        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            yield StreamChunk(
                delta_text=delta.content or "",
                tool_call_delta=self._extract_tc_delta(delta),
                finish_reason=choice.finish_reason,
            )
    except Exception as e:
        # 降级：抛 SystemExit 不行，用特殊 finish_reason="error"
        yield StreamChunk(finish_reason="error", delta_text=f"[stream-fallback] {type(e).__name__}: {e}")
```

### 4.2 AgentLoop.astream_run()

**核心思路**：ReAct 循环每一轮内部用 `astream()`；文本增量直接外抛，tool_call 增量内部拼装到完整后才执行工具，工具结果作为下一轮的 `messages` 注入。

```python
async def astream_run(
    self, query: str, callbacks: AgentCallbacks | None = None,
) -> AsyncIterator[StreamChunk]:
    state = AgentState(...)
    for step in range(self.max_steps):
        accumulated_text = ""
        accumulated_tcs: dict[int, dict] = {}  # idx -> tool_call dict
        async for chunk in self.llm.astream(state.messages, tools=...):
            if chunk.finish_reason == "error":
                # 降级到非流式
                resp = await self.llm.achat(state.messages, tools=...)
                yield StreamChunk(delta_text=resp.text, finish_reason="stop")
                return
            if chunk.delta_text:
                accumulated_text += chunk.delta_text
                yield chunk  # 实时外抛
            if chunk.tool_call_delta:
                _merge_tc_delta(accumulated_tcs, chunk.tool_call_delta)
            if chunk.finish_reason in ("stop", "tool_calls", "length"):
                break
        if accumulated_tcs:
            yield StreamChunk(delta_text=f"\n\n[🔧 调用 {len(accumulated_tcs)} 个工具...]\n")
            # 同步执行（执行本身不流式）
            for tc in accumulated_tcs.values():
                result = await self._aexec_tool(tc)
                state.messages.append(...)  # tool result message
        else:
            return  # finished
```

### 4.3 Chainlit 端流式渲染

[chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py) `on_message` 改造：

```python
msg = cl.Message(content="", author="Course Agent")
await msg.send()
try:
    async for chunk in agent.astream_run(message.content, callbacks=cb):
        if chunk.delta_text:
            await msg.stream_token(chunk.delta_text)
    await msg.update()
except Exception as e:
    # 整体降级
    result = await agent.arun(message.content, callbacks=cb)
    await cl.Message(content=result.answer).send()
```

### 4.4 题目生成器工具

**新文件** `course_agent/tools/generator.py`：

```python
@tool(description="基于错题本和教材库生成一道同类型新题")
def generate_question(
    tag: str = "",                 # 知识点标签（来自错题本）
    question_type: str = "解答题", # 选择题 / 填空题 / 解答题 / 证明题
    difficulty: str = "中",        # 简单 / 中 / 难
    n_refs: int = 3,               # 检索教材 chunk 数
) -> str:
    """
    流程：
    1. 若 tag 非空，先查错题本拿到该 tag 下学生答错过的题作为「避免出重」参考
    2. 调 kb_search(tag) 拿 n_refs 个教材 chunk 作素材
    3. 拼 system+user prompt → call LLM 生成 JSON
    4. 校验 JSON schema，失败重试 1 次
    5. 返回 markdown 渲染：题目 / [📚 参考: source P.x] / 待学生回答
    内部记录：correct_answer 暂存到 session（不直接给学生看）
    """
```

**返回格式（JSON 内部，markdown 外显）**：

```json
{
  "question": "求矩阵 A=[[2,1],[1,2]] 的特征值与特征向量。",
  "correct_answer": "特征值 λ₁=3, λ₂=1；对应特征向量 ...",
  "explanation": "解 det(A-λI)=0 ...",
  "source": "线性代数教材 P.83",
  "based_on_mistakes": [12, 17]
}
```

### 4.5 Examiner Agent

**新文件** `course_agent/agent/examiner.py`：

```python
EXAMINER_SYSTEM_PROMPT = """你是 Examiner——一名严格但鼓励的助教。
你的职责：
1. 在用户进入「出题模式」时，先调 generate_question 出一道题
2. 等待学生回答；学生回答后，对照 correct_answer 判分（0-5）
3. 如果学生答错（quality<3），调 add_mistake 自动入错题本
4. 给学生讲解，并问"要再来一道同类型/进阶题吗？"
你只能用这些工具：generate_question / kb_search / add_mistake / list_mistakes
你不能调用 python_exec / web_search 等无关工具。
"""

class ExaminerAgent:
    def __init__(self, llm: BaseLLM, registry: ToolRegistry):
        allowed = ["generate_question", "kb_search", "add_mistake", "list_mistakes"]
        self.loop = AgentLoop(
            llm=llm,
            registry=registry,
            tool_names=allowed,
            max_steps=6,
            system_prompt=EXAMINER_SYSTEM_PROMPT,
        )
    
    async def astream_run(self, query: str, callbacks=None):
        async for chunk in self.loop.astream_run(query, callbacks):
            yield chunk
```

**Chainlit 整合**：

- 新增场景按钮：`{"label": "📝 出题模式", "value": "examiner"}`
- 用户点击 → `cl.user_session.set("agent_mode", "examiner")`
- `on_message` 内根据 `agent_mode` 选择 `AgentLoop` 或 `ExaminerAgent`

### 4.6 doctor 第 10 项

```python
def _check_streaming_and_examiner() -> tuple[str, str, str]:
    """探活流式接口 + Examiner 可实例化."""
    try:
        llm = get_default_llm()
        # 流式探活：发一个最短消息，只读 1 个 chunk 即停
        async def _probe():
            async for chunk in llm.astream([LLMMessage(role="user", content="hi")]):
                return chunk
        loop = asyncio.new_event_loop()
        chunk = loop.run_until_complete(_probe())
        loop.close()
        # Examiner 可实例化
        from course_agent.agent.examiner import ExaminerAgent
        ex = ExaminerAgent(llm=llm, registry=get_registry())
        return ("✅", "stream OK", f"first_chunk_finish={chunk.finish_reason or 'streaming'}; examiner=ready")
    except Exception as e:
        return ("⚠️", type(e).__name__, str(e)[:160])
```

---

## 五、Step-by-Step 实施计划

| Step | 内容 | 关键文件 | 依赖 |
|---|---|---|---|
| **1** | **流式抽象 + LLM 实现** | [base.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/base.py) 增加 `StreamChunk` + `astream()` 抽象；[openai_like.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/openai_like.py) 实装；[mock.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/mock.py) 实装假流式 | — |
| **2** | **AgentLoop.astream_run()** | [agent_loop.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/core/agent_loop.py)：tool_call 拼装 + 文本外抛 + 错误降级 | Step 1 |
| **3** | **Chainlit 流式渲染** | [chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py) `on_message` 改 `cl.Message.stream_token`；保留非流式降级路径 | Step 2 |
| **4** | **题目生成器工具** | 新建 `course_agent/tools/generator.py`；`course_agent/tools/__init__.py` 注册（**16 → 17** 个） | Step 1（不依赖流式） |
| **5** | **Examiner Agent 类** | 新建 `course_agent/agent/examiner.py`；导出 `ExaminerAgent` | Step 2 + Step 4 |
| **6** | **Chainlit 出题模式** | [chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py) 加场景按钮 + `agent_mode` 路由 | Step 5 |
| **7** | **极简自动 grader** | Examiner system_prompt 引导 LLM 在判错后自动调 `add_mistake`（无需手点） | Step 5 |
| **8** | **doctor 第 10 项** | [cli.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/cli.py) `_check_streaming_and_examiner()`；插入 doctor 流程 | Step 1 + Step 5 |
| **9** | **测试 + ruff + README + 勾选** | `tests/test_streaming.py`、`tests/test_generator.py`、`tests/test_examiner.py`、`tests/test_cli_doctor_10.py`；README 新增 2 节；本文全勾 | 全部前置 |

---

## 六、测试矩阵

### 6.1 新增测试文件（≥ 21 case）

| 测试文件 | 关注点 | 用例数 |
|---|---|---|
| `tests/test_streaming.py` | MockLLM 假流式 chunk 顺序 / tool_call 增量拼装 / 错误降级路径 / `astream_run` 完整一轮 | ≥ 7 |
| `tests/test_generator.py` | 输入校验 / JSON schema 校验失败重试 / kb_search 兜底为空时友好降级 / based_on_mistakes 去重 | ≥ 5 |
| `tests/test_examiner.py` | 限定工具集生效（试图调 python_exec 应被拒）/ 自动入错题本路径 / 系统提示词正确加载 | ≥ 5 |
| `tests/test_cli_doctor_10.py` | doctor 第 10 项 happy path + 网络失败降级为 ⚠️ 但不崩 | ≥ 4 |

### 6.2 回归测试

- 不进入出题模式（默认 ReAct）的场景下，Task 008/009/010 全部 154 个用例继续通过
- `course-agent doctor` 第 1~9 项不受新增第 10 项影响
- 流式失败时降级到 `arun`，回归测试覆盖此路径

---

## 七、交付物 Checklist

### 代码
- [x] [base.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/base.py)：新增 `StreamChunk` + `astream()` 抽象方法
- [x] [openai_like.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/openai_like.py)：`astream()` 实装 + tool_call delta 解析
- [x] [mock.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/llm/mock.py)：`astream()` 假流式（按字符切，便于单测）
- [x] [agent_loop.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/core/agent_loop.py)：`astream_run()` + 错误降级
- [x] `course_agent/tools/generator.py`（新文件，~150 行）
- [x] `course_agent/tools/__init__.py`：注册 `generate_question`（**16 → 17** 个）
- [x] `course_agent/agent/examiner.py`（新文件，~80 行）
- [x] `course_agent/agent/__init__.py`：re-export `ExaminerAgent`
- [x] [chainlit_app.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/ui/chainlit_app.py)：流式 `stream_token` + 出题模式场景按钮 + `agent_mode` 路由
- [x] [cli.py](file:///Users/bytedance/Desktop/syzf%E9%A1%B9%E7%9B%AE/cousre_agent/course_agent/cli.py)：doctor 第 10 项

### 测试 / 配置
- [x] `tests/test_streaming.py`、`tests/test_generator.py`、`tests/test_examiner.py`、`tests/test_cli_doctor_10.py`
- [x] `pytest -q` 全绿（≥ **175 passed**）
- [x] `ruff check .` 全绿

### 文档
- [x] `README.md` 新增「⌨️ 流式输出」「📝 Examiner Agent 出题模式」两节
- [x] `README.md` 工具数表 16 → **17**；doctor 9 项 → **10 项**；测试数 154 → **≥ 175**
- [x] `README.md` 项目结构补 `agent/examiner.py`、`tools/generator.py`
- [x] `task/task_011.md`（本文）成功指标 10 项与交付物全勾

### 验证脚本（推荐手动跑一遍）
- [ ] `course-agent doctor` → 10/10 ✅
- [ ] Chainlit 输入"讲解动态规划" → 答案逐字打字机出现
- [ ] Chainlit 点击"📝 出题模式" → Examiner 出题 → 故意答错 → 自动看到「✅ 已记入错题本 #N」

---

## 八、教学性总结：为什么 Task 011 是「学习闭环的执行层」

Task 010 把**数据底座**搭好了——错题本是「记忆」，教材库是「知识」。但**底座不会自己动**：
- 错题本里 30 道题，**复习时依然只能看原题**——学习就是没有"举一反三"。
- 长答案**卡 5 秒突现**——交互摩擦让学生失去专注。

Task 011 要解决两件事，一前一后：

1. **"答得顺"——流式输出**：把"卡顿现身"变成"打字机吐字"。这不是单纯 UX 装饰——**流式让学生在 Agent 思考的同时已经在阅读**，把"等待时间"变成"阅读时间"。这一改动会改变会话节奏感。

2. **"考得出"——题目生成器 + Examiner Agent**：把错题本 + 教材库两个数据底座**变成生产工具**——Agent 不再只是「记下你错过的题」，而是「**根据你错过的题造新题让你练**」。这是陪学闭环的最后一公里：
   - **错** → 入错题本（Task 010 完成）
   - **复习** → SM-2 排程（Task 010 完成）
   - **新题** → generate_question（**Task 011 本期**）
   - **再练** → Examiner Agent（**Task 011 本期**）
   - **再判错 → 再入错题本**（自动 grader，Task 011 极简版；Task 012 完整版）

更重要的是，**Examiner Agent 是多 Agent 编排的第一块砖**——它建立了「**有限定工具集 + 独立 system_prompt + 同样跑 AgentLoop**」的子 Agent 模式。Task 012 要实装的 Planner / Solver / Grader 三角，**全部按 Examiner 这个模板**铺开即可。这一步不大，却把「单 Agent」到「多 Agent」的范式拐点彻底打通了。

> **一句话定位**：Task 011 是「Agent 静态能力」转「Agent 动态产能」的拐点——它让数据底座**开始造东西**，让交互**开始顺畅**。

---

## 九、风险与备选

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 流式 + tool_call delta 拼装 bug 难调试 | 高 | 工具调用错乱 | 在 MockLLM 里做严格的 `astream()` 单测覆盖 delta 边界（半个 JSON / 跨 chunk 函数名）；loguru.debug 全程 dump |
| Chainlit `stream_token` API 在不同版本签名差异 | 中 | UI 端崩 | 实施前先 `import chainlit; print(cl.Message.stream_token.__doc__)` 看一下；做版本兜底 |
| OpenAI 兼容服务（DashScope）流式与 OpenAI 行为微差 | 中 | DashScope 不出 token 或 finish_reason 不一致 | 流式失败自动降级到 `achat`；doctor 第 10 项主动探测 |
| `generate_question` 重题率高（生成的题正好和错题本里一样） | 中 | 学生抱怨 | 在 prompt 里把 `based_on_mistakes` 的 question 字段塞进去，明确"避免与以下题目重复" |
| HashEmbedder 兜底时 `kb_search` 召回质量差导致出题缺乏教材依据 | 高 | 出题质量低 | 题目末尾**显著标注**「⚠️ 当前 hash 兜底，参考素材召回有限」；不假装效果 |
| Examiner 自动 grader（LLM 判错）误判（学生对的判错 / 学生错的判对） | 中 | 错题本污染 | 自动入库前给学生一条**可撤销**的提示「✅ 已记入错题本 #N，输入 `/undo` 取消」 |
| 流式期间用户中途取消（关页面）造成 LLM 调用浪费 | 低 | 计费 | Chainlit `cl.on_stop` 钩子里 `task.cancel()`（先做一个最小版） |

---

## 十、显式不在本期范围（防 scope creep）

- ❌ 完整的 Planner / Solver / Grader 多 Agent 编排 → Task 012
- ❌ 多 Agent 之间的消息传递协议 / blackboard / shared state → Task 012
- ❌ Examiner 多模态出题（带图） → Task 013+
- ❌ 流式 token 计费面板 / 可观测面板 → Task 012/013
- ❌ Chainlit data layer 持久化（半流式消息中断也能续）→ Task 012
- ❌ 大批量出题（一次出 50 道试卷）/ 题库导出 PDF
- ❌ LLM-as-judge 完整 grader（Task 011 只用 system_prompt 引导 LLM 判错；Task 012 单独成 GraderAgent）
- ❌ 同步 `stream()`（CLI 流式输出）—— 本期只做 async；CLI 流式价值低且复杂
- ❌ 题目难度自适应算法（根据 SM-2 历史调难度）

> 上面这些是好东西，但**塞进 Task 011 会让本期失焦**。一次只解决一组耦合问题——「流式输出 + 出题闭环」——把它们做扎实，比把多 Agent 编排和流式硬塞同一期更稳。
