# Task 008：让 Course Agent 能「真正动手做作业」

> 本 Task 基于 Task 007（记忆系统 + 真实 Web 检索）完成后的项目现状，规划**下一阶段最值得开发的方向**，并挑选其中一组作为本期落地点。
>
> **核心命题**：Task 004 让 Agent 有了"嘴"（Web UI），Task 007 让它有了"脑子"（记忆）和"眼睛"（联网），而 **Task 008 要让它真正能"动手"** —— 能跑代码、能读 PDF 题目、能从图片里识题。

---

## 一、当前项目现状盘点

### 1.1 已具备的能力（Task 007 收尾后）

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | `run()` 同步 + `arun()` 异步 + 回调机制 |
| LLM 抽象层 | ✅ | `BaseLLM` / `MockLLM` / `OpenAILLM` |
| Tool Registry | ✅ | `@tool` + JSON Schema |
| 内置工具 | ✅ | calculator / file_read / file_write |
| Web 工具 | ✅ | web_search（Tavily/DDG）/ web_fetch（trafilatura） |
| Memory 子系统 | ✅ | ShortTerm（滑窗+LLM摘要）+ LongTerm（Chroma cosine HNSW） |
| Memory 工具化 | ✅ | `@tool recall` / `@tool remember` |
| Embedder 抽象 | ✅ | HashEmbedder（离线）/ OpenAIEmbedder（DashScope/OpenAI） |
| Chainlit 集成 | ✅ | per-session 持久化 + Settings 面板 + 记忆开关 + 场景按钮 |
| CLI | ✅ | `chat` / `tools` / `version` / `ui`（含 API Key 尾号诊断面板） |
| 配置稳定性 | ✅ | `.env` override OS env，避免 401 污染 |
| 测试与 Lint | ✅ | 54 passed + 5 skipped；ruff clean |

### 1.2 当前明显的缺口（"agent 仍然不会做事"）

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **`python_exec`** | ❌ 完全没有 | 编程作业 Agent 写完代码就"猜"它能跑，不能真正验证；用户被迫自己复制到 IDE 跑 |
| **作业 PDF 输入** | ❌ `file_read` 只能读 txt/py，PDF 二进制读出乱码 | 学生最常拿到的就是 PDF 题目，现在必须人肉抄题 |
| **图片 / 手写题** | ❌ 完全没有 | 教辅纸质题 / 板书 / 手写公式无法直接喂给 Agent |
| **课外可观测** | ⚠️ 只有 loguru 日志 | UI 看不到 token 消耗 / 单步时延 / Tool 失败率，调优无据 |
| **错误分类粒度** | ⚠️ 只区分 auth / api / 其它 | 401 / 限流 / 超时 / 模型不存在 都被混在 `[LLM 调用失败]` 里（Task 007 401 事故已吃过亏） |
| **多 Agent 协作** | ❌ `agent/` `orchestrator/` 仍是空包 | 单 Agent 在"先规划→再执行→自批改"这种链路上明显力不从心 |
| **会话级元信息** | ❌ Chainlit data layer 没开 | 关浏览器=丢历史；只有长期向量记忆能跨会话，原文消息找不回 |
| **流式输出** | ⚠️ `arun` 等 LLM 整个 response 才 yield | 长答案体验上还是"卡住几秒突然出现"，不是真 token-by-token |

### 1.3 Task 007 实战教训沉淀

| 教训 | 已修复部分 | 仍需做 |
|---|---|---|
| OS env 残留 key 污染 .env | ✅ `load_dotenv override=True`，启动面板显示 key 尾号 | ⚠️ 没有"启动自检" CLI；用户首次配错时只能在第一次发消息时才发现 |
| 「[LLM 认证失败]」错误把所有异常一锅端 | ✅ 已附带服务端原文 + 排查建议 | ⚠️ 限流 / 超时 / 上下文超限 等仍归到统一兜底，不分流 |
| Web UI 静态资源 task_004 事故 | ✅ 锁定 Python 3.13 + curl 验证 JS bundle | — |

---

## 二、候选开发方向（脑暴 + 打分）

我列了 **8 个候选**，按「价值 / 成本 / 与现有代码契合度」三个维度打分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **`python_exec` 沙箱执行**（subprocess + resource limit + 超时） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 编程作业杀手锏；Agent 自己跑测试用例验证答案 |
| **2** | **`pdf_read` 工具**（pypdf / pdfplumber 抽文本，可选 OCR fallback） | 🔥🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 学生最常见的题目形式；纯 Python 库即可 |
| **3** | **`image_ocr` 工具**（手写公式 / 拍照题目） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 用 GPT-4V / Qwen-VL 多模态 API；纸质题入口 |
| **4** | 多 Agent 编排（Planner / Executor / Grader） | 🔥🔥🔥🔥 | 高 | ⭐⭐⭐ | ⭐⭐⭐ | 架构升级，但依赖 #1 才能让 Executor 真正"做事"，先做工具再做编排 |
| **5** | 错误分类细化（限流 / 超时 / 上下文超限 / 模型不存在 各自专属提示） | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Task 007 401 教训直接驱动；改动小、收益高 |
| **6** | 启动自检 CLI（`course-agent doctor`：检查 key / 模型 / 网络 / 依赖） | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 用户首次跑通体验大幅改善 |
| **7** | 可观测性面板（token / 时延 / Tool 失败率，挂在 Chainlit Step 上） | 🔥🔥🔥 | 中 | ⭐⭐⭐ | ⭐⭐⭐ | 调优用，对学生用户感知不强 |
| **8** | 真流式 streaming（token-by-token 进 Chainlit Message） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | UX 优化；DashScope 已支持，OpenAI SDK 也支持 |

### 2.1 挑选逻辑

- **#1 + #2** 是当下最痛的"做不了事"问题——学生场景下 90% 的作业是「PDF 题目 + 跑代码验证」，现在两者都不行；它俩**相互正交、可独立交付**，作为本期主线。
- **#3 image_ocr** 价值高但依赖**多模态模型**接入（额外的 API、不同的消息结构），单独成 Task 009 更稳。
- **#4 多 Agent** 在 #1 落地前没有意义——Executor 没有 `python_exec` 就只能"嘴上跑代码"，所以推迟。
- **#5 + #6** 是 Task 007 401 教训的直接产物，改动小、价值高，**作为本期附赠的稳定性增强**一起带上。
- **#7 #8** 留到 Task 010 / Task 011。

→ **本期（Task 008）聚焦：#1 python_exec + #2 pdf_read（主线）+ #5 错误分类细化 + #6 doctor CLI（稳定性配菜）**

---

## 三、Task 008 目标（本期范围）

> **主题：从"会聊"到"会做"——让 Agent 真正动手跑代码、读 PDF**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ `python_exec`：subprocess + 临时目录 + 超时 + stdout/stderr 截断 | ❌ Docker/gVisor 强隔离（本期不引入容器依赖；按"半信任"模型，超时+wall-clock+输出截断三道闸） |
| ✅ 限制 CPU 时间、内存（rlimit on Unix）、禁网（隔离环境变量） | ❌ Windows 下完整资源限制（rlimit Linux/macOS only，Win 退化为仅超时） |
| ✅ 支持单文件 / 内联 source / 自带 stdin | ❌ 多文件项目 / pip install 任意包（仅预装白名单） |
| ✅ `pdf_read(path, page_range, max_chars)`：pypdf 提取文本 | ❌ 复杂版式还原 / LaTeX 公式精准识别（OCR 走 Task 009） |
| ✅ 自动判别扫描型 PDF 并给出友好提示（"该 PDF 看起来是扫描件，请等待 Task 009 OCR 支持"） | ❌ 真实 OCR |
| ✅ `course-agent doctor` CLI：体检 key / 网络 / 模型 / Embedder / 工具注册 | ❌ 自动修复（仅诊断 + 给出修复建议） |
| ✅ 错误分类细化：401 / 429 / 408 / 404 / 上下文超限 各自独立文案 | ❌ 自动重试已存在（Task 003），本期不动重试逻辑 |

### 3.2 成功指标

1. [x] Agent 收到「写一个二分查找并验证 [3,5,7] 中找 5 的位置」→ **自动调用 `python_exec` 跑代码、把 stdout 拿回来、再回答用户**
2. [x] `python_exec` 对 `while True: pass` 死循环能在 5 秒内强制超时返回，**不卡死主进程**
3. [x] `python_exec` 对 `import socket; socket.socket().connect(...)` 默认**禁网**返回 `OSError: Network is unreachable`
4. [x] `pdf_read("homework.pdf", page_range="1-3")` 返回前 3 页纯文本（≤ `max_chars` 字符）
5. [x] 扫描型 PDF（无可抽取文本）返回明确提示，**而不是空字符串**
6. [x] `course-agent doctor` 输出至少 6 项检查结果（含 ❌ 时给出**精确修复命令**）
7. [x] 误配置 401 / 限流 429 / 模型不存在 404 时，UI 上能看到**三种不同的错误文案**
8. [x] 所有新代码有单元测试，`pytest` 和 `ruff` 全绿
9. [x] 完全向后兼容：旧 CLI / Mock / Memory / Web 工具不受影响

---

## 四、技术方案

### 4.1 `python_exec` 工具：四道安全闸

```
┌─────────────────────  python_exec(code, stdin?, timeout?)  ───────────────────┐
│                                                                                │
│  闸 ① 输入校验                                                                  │
│      ├─ code 长度 ≤ 16 KB                                                      │
│      └─ 拒绝明显恶意 import：os.system / subprocess / ctypes（白名单 AST 静态检查）│
│                                                                                │
│  闸 ② 隔离 subprocess                                                          │
│      ├─ tempfile.TemporaryDirectory() 作为 cwd                                 │
│      ├─ env = {"PATH": ..., "PYTHONIOENCODING": "utf-8"}（剥离 OPENAI_*/AWS_*）│
│      ├─ 关闭网络：preexec_fn 设 setrlimit(RLIMIT_NOFILE) 限制 fd 数量            │
│      └─ Linux/macOS 加 RLIMIT_AS（地址空间）+ RLIMIT_CPU（CPU 时间）           │
│                                                                                │
│  闸 ③ 超时熔断                                                                 │
│      ├─ asyncio.wait_for(..., timeout=5)                                       │
│      └─ 超时后 process.kill() + 等待 0.5s 再 SIGKILL                            │
│                                                                                │
│  闸 ④ 输出截断                                                                 │
│      ├─ stdout 截至 8 KB，stderr 截至 4 KB                                      │
│      └─ 返回结构化 JSON: {exit_code, stdout, stderr, duration_ms, truncated}   │
└────────────────────────────────────────────────────────────────────────────────┘
```

**实现位置**：[`course_agent/tools/python_exec.py`](../course_agent/tools/python_exec.py)（新文件）

**关键代码骨架**：
```python
import asyncio
import json
import os
import resource
import sys
import tempfile
from pathlib import Path

from course_agent.tools.registry import tool

_FORBIDDEN_NAMES = {"os.system", "subprocess.", "ctypes.", "socket."}
_DEFAULT_TIMEOUT = 5
_MAX_CODE = 16 * 1024
_MAX_STDOUT = 8 * 1024
_MAX_STDERR = 4 * 1024


def _set_limits():
    if sys.platform != "win32":
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


@tool(name="python_exec",
      description="在隔离的子进程里执行一段 Python 代码并返回 stdout/stderr/exit_code。"
                  "禁网、有超时、内存限制。适合跑算法验证 / 数据处理 / 写完代码立刻验证。")
def python_exec(code: str, stdin: str = "", timeout: int = 5) -> str:
    if len(code) > _MAX_CODE:
        return json.dumps({"error": f"code too long (>{_MAX_CODE} bytes)"})
    # ...AST 校验、subprocess、wait_for、截断、JSON 序列化...
```

### 4.2 `pdf_read` 工具：纯文本快速路径

```
pdf_read(path, page_range="1-", max_chars=8000)
   │
   ├─→ pypdf.PdfReader(path) 打开
   ├─→ 解析 page_range （"1-3" / "1,3,5" / "1-"）
   ├─→ 逐页 .extract_text()
   ├─→ 累计字符截断 至 max_chars
   ├─→ 若总抽出文本 < 50 字符 → 判定扫描件，返回提示
   └─→ 返回纯文本 + 分页标记
```

**实现位置**：[`course_agent/tools/pdf_tools.py`](../course_agent/tools/pdf_tools.py)（新文件）

**返回格式**：
```
[Page 1]
本次作业：实现冒泡排序，并分析最坏时间复杂度。
要求：1) 用 Python ……

[Page 2]
2.1 提示：可使用以下伪代码……
```

**依赖**：`pypdf>=4.0`（轻量、纯 Python，无 C 编译）

### 4.3 `course-agent doctor` 启动自检

```
$ course-agent doctor
🔍 Course Agent 健康检查

[1/7] Python 版本               ✅ 3.13.12
[2/7] 关键依赖                  ✅ chainlit / openai / chromadb / pypdf 全部就位
[3/7] .env 文件                 ✅ 存在 (424 bytes)
[4/7] OPENAI_API_KEY            ✅ 来源=.env，尾号=...93e8f6 (len=35)
                                ⚠️  shell OS env 也设置了 OPENAI_API_KEY，但已被 .env override
[5/7] LLM 连通性 (chat)         ✅ qwen-plus 200 OK (424ms)
[6/7] LLM 连通性 (embedding)    ✅ text-embedding-v3 200 OK (305ms)
[7/7] 工具注册                  ✅ 9 个：calculator, file_read, file_write,
                                   web_search, web_fetch, recall, remember,
                                   python_exec, pdf_read

总结：7/7 通过 ✨ 可以开始使用
```

**实现位置**：[`course_agent/cli.py`](../course_agent/cli.py)（新增 `@app.command() def doctor()`）

### 4.4 错误分类细化

把 [`openai_like.py:_handle_error`](../course_agent/llm/openai_like.py) 的 `is_auth / is_api` 二分扩展为：

| openai 异常 | 文案前缀 | 排查建议 |
|---|---|---|
| `AuthenticationError` (401) | `[LLM 认证失败]` | 检查 key + base_url 配对（已有） |
| `RateLimitError` (429) | `[LLM 限流]` | 提示等待 N 秒 + 切换模型 |
| `APITimeoutError` / `APIConnectionError` | `[LLM 网络异常]` | 检查代理 / 切 base_url |
| `BadRequestError` 含 `context_length_exceeded` | `[LLM 上下文超限]` | 提示开启记忆压缩 / 减少历史 |
| `NotFoundError` (404 model) | `[LLM 模型不存在]` | 列出该 base_url 常见可用 model |
| 其它 | `[LLM 调用失败]` | 透传原文 |

### 4.5 与现有架构的拼合

```
       ┌─────────────────────────────────────────────────┐
       │            AgentLoop (ReAct, 已有)              │
       │                                                  │
       │   思考 → LLM.chat(tools=...) → tool_call?       │
       │            │                          │          │
       │            │                          ▼          │
       │            │       ┌─────────────────────────┐   │
       │            │       │  Tool Registry          │   │
       │            │       │                          │   │
       │            │       │  calculator ✅ (旧)      │   │
       │            │       │  file_read ✅ (旧)       │   │
       │            │       │  file_write ✅ (旧)      │   │
       │            │       │  web_search ✅ (Task007) │   │
       │            │       │  web_fetch ✅ (Task007)  │   │
       │            │       │  recall ✅ (Task007)     │   │
       │            │       │  remember ✅ (Task007)   │   │
       │            │       │  python_exec 🆕 (本期)   │   │
       │            │       │  pdf_read 🆕 (本期)      │   │
       │            │       └─────────────────────────┘   │
       │            ▼                                      │
       │      最终答案，回传 UI                            │
       └─────────────────────────────────────────────────┘
```

**完全不动 AgentLoop / Memory / Chainlit 集成层**——只新增工具 + 改进错误分类 + 新增 doctor 子命令。

---

## 五、实施步骤

### Step 1：依赖与骨架（0.5 天）
- [x] `pyproject.toml` 新增 `pypdf>=4.0`（pdf_read 必需）
- [x] 新建 [`course_agent/tools/python_exec.py`](../course_agent/tools/python_exec.py) 与 [`course_agent/tools/pdf_tools.py`](../course_agent/tools/pdf_tools.py) 骨架文件
- [x] [`tools/__init__.py`](../course_agent/tools/__init__.py) 加上对应 import 触发 @tool 注册

### Step 2：`python_exec` 实现（1.5 天）
- [x] AST 静态检查 + 关键 import 黑名单
- [x] `asyncio.create_subprocess_exec` + `preexec_fn=_set_limits`
- [x] `asyncio.wait_for(..., timeout)` + 强制 kill
- [x] stdout/stderr 字节级截断 + 结构化 JSON 返回
- [x] 单测：正常返回 / 超时 / 内存超限 / 禁网 / 输出截断 / 黑名单 import

### Step 3：`pdf_read` 实现（0.5 天）
- [x] page_range 解析（`"1-3"` / `"1,3,5"` / `"1-"` / `"-3"`）
- [x] pypdf 逐页 extract_text + 累计截断
- [x] 扫描件检测分支（max-per-page < 10 char 时返回友好提示）
- [x] 单测：单页 / 多页 / 范围 / 字符截断 / 文件不存在 / 扫描件提示

### Step 4：错误分类细化（0.5 天）
- [x] [`openai_like.py:_handle_error`](../course_agent/llm/openai_like.py) 拆分 5 类异常
- [x] 单测：每种异常类型对应唯一前缀
- [x] 不破坏 Task 007 已有的 401 详情 + shell key 提示

### Step 5：`doctor` CLI（0.5 天）
- [x] [`cli.py`](../course_agent/cli.py) 新增 `@app.command() def doctor()`
- [x] 7 项检查 + rich 表格输出 + 退出码（全过 0，否则 1）
- [x] 单测：mock 各种失败场景

### Step 6：测试 + 文档（0.5 天）
- [x] 全量 `uv run pytest -q` 与 `uv run ruff check .` 全绿（96 passed + 6 skipped）
- [x] [README.md](../README.md) 新增「🔬 沙箱执行 python_exec」「📄 PDF 阅读」「🩺 启动自检 doctor」三个小节
- [x] [task/task_008.md](task_008.md) 全部交付物打钩

**合计预估：4 天**（比 Task 007 的 6 天小一档，因为不再涉及 Embedder / Chainlit 改造，只是新增工具）

---

## 六、风险与应对

| 风险 | 应对 |
|---|---|
| `python_exec` 沙箱被绕过执行恶意代码 | ① AST 黑名单 ② 子进程 rlimit ③ 禁网 env ④ 不开放给非本机用户使用；README 强提示"半信任" |
| Windows 下 `resource` 模块不可用 | 平台分支：Win 仅做超时 + 输出截断；README 注明"完整资源限制需 Linux/macOS" |
| pypdf 抽不出文本（扫描件 / 复杂版式） | 友好提示 + 引导 Task 009 OCR；不抛异常 |
| `python_exec` 子进程与父进程同 Python 版本依赖（如 `numpy` 没装） | 默认只用纯 stdlib；用户要扩展走 `[exec-extra]` 可选 extra |
| 错误分类改动破坏旧测试 | 新错误前缀均保留 `[LLM ` 前缀，旧的 startswith 断言不破坏 |
| `doctor` 体检步骤之一失败导致后续步骤跳过 | 每步独立 try / except，全部跑完再汇总 |

---

## 七、交付物清单

- [x] [`course_agent/tools/python_exec.py`](../course_agent/tools/python_exec.py)
- [x] [`course_agent/tools/pdf_tools.py`](../course_agent/tools/pdf_tools.py)
- [x] [`course_agent/tools/__init__.py`](../course_agent/tools/__init__.py)（注册新工具）
- [x] [`course_agent/llm/openai_like.py`](../course_agent/llm/openai_like.py) `_handle_error` 拆分
- [x] [`course_agent/cli.py`](../course_agent/cli.py) 新增 `doctor` 子命令
- [x] `tests/test_python_exec.py`（14 项：正常 / stdin / 超时 / 内存(linux) / 禁网 / 截断 / 黑名单 + audit 单测）
- [x] `tests/test_pdf_tools.py`（13 项：单页 / 多页 / 范围 / 截断 / 扫描件 / 错误路径 / range 解析单测）
- [x] `tests/test_error_classification.py`（8 项：6 类异常 + 兜底 + 错路径回退）
- [x] `tests/test_doctor.py`（8 项：CLI 烟雾测试 + 各 _check_* 单测）
- [x] `pyproject.toml` 新增 `pypdf>=4.0`
- [x] `.env.example` 无变化（无新环境变量）
- [x] [`README.md`](../README.md) 新增 3 节 + 工具表 / Milestone / 项目结构同步

---

## 八、后续可衔接的 Task

- **Task 009**：`image_ocr` + 多模态视觉（Qwen-VL / GPT-4V 接入）—— 把扫描件 PDF / 手写题 / 板书拍照纳入输入
- **Task 010**：多 Agent 编排（Planner → Executor[python_exec] → Grader）—— 在 Task 008 沙箱基础上做"自批改"闭环
- **Task 011**：可观测性面板（token / 时延 / Tool 失败率，挂 Chainlit Step）
- **Task 012**：真流式 streaming（token-by-token 进 Chainlit Message）
- **Task 013**：生产化部署（Dockerfile + docker-compose + HTTPS）

---

## 九、完成后项目能力对比

| 能力 | Task 008 前 | Task 008 后 |
|---|---|---|
| 编程作业能跑代码验证 | ❌ 只能"嘴上"写代码 | ✅ Agent 自跑 `python_exec` 拿真实 stdout |
| PDF 题目输入 | ❌ `file_read` PDF 乱码 | ✅ `pdf_read` 抽文本 + 扫描件提示 |
| 死循环 / 资源耗尽风险 | — | ✅ 5s 超时 + 内存上限 + 禁网三道闸 |
| 工具数量 | 7 | **9**（+ python_exec / pdf_read） |
| 首次配错的体感 | ❌ 第一次发消息才报 401 | ✅ `course-agent doctor` 一秒看清 7 项状态 |
| 错误诊断粒度 | 3 类（auth / api / 其它） | 6 类（auth / 限流 / 网络 / 上下文超限 / 模型不存在 / 其它） |
| 与普通 AI Chat 差距 | 已明显（有记忆 + 联网） | **断层式**：跑代码 + 读 PDF 是普通 Chat 完全做不到的 |

---

> **一句话总结**：Task 008 做完，Course Agent 就从「会聊会查会记的助教」升级为「真正能动手帮你做完作业、还能自己验证答案的实习生」。配上 Task 007 的记忆，下次你打开浏览器它甚至会说："上次你那个二分查找的边界 bug，要不要我现在 `python_exec` 跑一下回归用例看看修好了没？"
