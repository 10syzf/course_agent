# Task 009：让 Agent「看得见」+「自己批改」—— 多模态视觉 + 编程作业自批改闭环

> 本 Task 基于 Task 008（python_exec 沙箱 + pdf_read + doctor + 6 类错误分类）完成后的项目现状，规划下一阶段最值得开发的方向。
>
> **核心命题**：Task 008 让 Agent 有了"手"（能跑代码）和"会读 PDF"，但**对扫描件、手写题、板书拍照仍然瞎**；同时 `python_exec` 虽然能跑代码，**却没有形成"写 → 跑 → 失败就改 → 再跑"的自批改闭环**。Task 009 要补这两块。

---

## 一、当前项目现状盘点（Task 008 收尾后）

### 1.1 已具备的能力

| 模块 | 状态 | 说明 |
|---|---|---|
| ReAct Agent Loop | ✅ | 同步 + 异步 + 回调 |
| LLM 抽象层 | ✅ | OpenAI 兼容（DashScope / DeepSeek / 火山豆包） |
| Tool Registry | ✅ | `@tool` + JSON Schema |
| **9 个工具** | ✅ | calculator / file_read / file_write / web_search / web_fetch / recall / remember / **python_exec** / **pdf_read** |
| Memory 子系统 | ✅ | 短期滑窗 + LLM 摘要 + Chroma 长期向量库 |
| Web 检索 | ✅ | Tavily / DuckDuckGo + trafilatura 抽正文 |
| Chainlit Web UI | ✅ | per-session + Settings + 场景按钮 + 记忆开关 |
| CLI | ✅ | `chat` / `tools` / `version` / `ui` / **`doctor`** |
| 错误分类 | ✅ | 6 类：认证 / 限流 / 网络 / 上下文超限 / 模型不存在 / 兜底 |
| 测试 + Lint | ✅ | 96 passed + 6 skipped；ruff clean |

### 1.2 当前明显的缺口

| 缺口 | 当前状态 | 痛点 |
|---|---|---|
| **看不见图片 / 手写 / 板书** | ❌ 完全不支持 | Task 008 扫描件 PDF 已经提示"等 Task 009"；学生拍照题目 / 黑板板书 / 手写公式现在零路径 |
| **`python_exec` 缺少自反思闭环** | ⚠️ 跑出来 stderr 后 LLM 可能直接放弃 | 写 → 跑 → 失败 → "好的我重新写" → 再跑这种循环目前**靠 LLM 自觉**，没有显式编排 |
| **多 Agent 编排** | ❌ `agent/` `orchestrator/` 仍是空包 | 单 Agent 角色混乱，"出题人 / 解题人 / 批改人"挤在一个 system prompt 里 |
| **流式输出** | ⚠️ `arun` 等 LLM 整个 response 才 yield | 长答案体验上"卡住几秒突然出现"，不是真 token-by-token |
| **可观测性** | ⚠️ 只有 loguru | UI 看不到 token 消耗 / 单步时延 / 工具失败率 |
| **会话历史持久化** | ❌ Chainlit data layer 没开 | 关浏览器 = 丢消息原文（向量记忆能跨会话，但拿不回原始对话） |
| **生产化部署** | ❌ 没有 Dockerfile | 同事想试用必须复制整个仓库 + 装 uv |

### 1.3 Task 008 实战教训沉淀

| 教训 | 已修复部分 | 仍需做 |
|---|---|---|
| `RLIMIT_AS` 在 macOS 不严格 | ✅ 测试改 `skipif != linux`；README 注明 | ⚠️ macOS 用户实际上**没有内存上限**，长跑可能触雷 |
| 扫描件阈值第一版误判短 PDF | ✅ 改成 max-per-page < 10 | ⚠️ 提示信息只说"等 Task 009"，但 Task 009 真该把 OCR 路径打通 |
| `python_exec` 默认 `python -I -S`，无法 `import numpy` | ⚠️ 没暴露用户控制 | 应增加 `extra_imports` 白名单或 `--allow-pip` 选项 |

---

## 二、候选开发方向（脑暴 + 打分）

8 个候选，按「价值 / 成本 / 与现有代码契合度」打分：

| # | 方向 | 价值 | 成本 | 契合度 | 综合 | 说明 |
|---|---|---|---|---|---|---|
| **1** | **`image_ocr` + 多模态视觉**（Qwen-VL / GPT-4V 接入） | 🔥🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Task 008 扫描件提示已经在等它；手写 / 板书 / 拍照题入口；接通 90% 纸质场景 |
| **2** | **`python_exec` 自批改闭环**（写→跑→失败→改→再跑，最多 N 轮） | 🔥🔥🔥🔥🔥 | 低 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Task 008 沙箱的"用法升级"，本质是给 AgentLoop 加一层 retry-with-feedback |
| **3** | 真流式 streaming（token-by-token 进 Chainlit） | 🔥🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | UX 立竿见影；OpenAI / DashScope SDK 都已支持 stream=True |
| **4** | 多 Agent 编排（Planner → Solver[python_exec] → Grader[image_ocr]） | 🔥🔥🔥🔥 | 高 | ⭐⭐⭐ | ⭐⭐⭐ | 架构升级；但依赖 #1 + #2 才能让角色真正分工有意义，先把基础打牢 |
| **5** | 可观测面板（token / 时延 / 工具失败率，挂 Chainlit Step） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 调优用，对学生用户感知不强 |
| **6** | Chainlit data layer（SQLite 持久化历史消息） | 🔥🔥🔥 | 低 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 关浏览器不丢历史，体验加分 |
| **7** | `python_exec` 包白名单 / 可选 venv（让用户能跑 numpy / pandas） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 只用 stdlib 对数据科学题目限制大；但加了 venv 复杂度上升 |
| **8** | Dockerfile + docker-compose（一键部署） | 🔥🔥🔥 | 中 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 推广必备，但当前个人用户场景还撑得住 `uv sync` |

### 2.1 挑选逻辑

- **#1 image_ocr** 是 Task 008 显式承诺过的事——「该 PDF 看起来是扫描件，请等待 Task 009 的 image_ocr」是已经写在用户面前的。**承诺要兑现**。
- **#2 自批改闭环** 是 Task 008 沙箱的「用法升级」，几乎不动核心代码，只是在 AgentLoop 上加一个`max_self_critique_rounds`。**ROI 极高**。
- **#3 真流式** 是 UX 杀手锏，但和 Memory + Tool-Calling 的整合较复杂（流式 + tool_call 的拼装需要小心），单独成 Task 010 更稳。
- **#4 多 Agent** 还是要等 #1 + #2 落地后角色分工才有素材；推迟。
- **#5 ~ #8** 价值递减或可独立后置。

→ **本期（Task 009）聚焦：#1 image_ocr + #2 自批改闭环（主线）+ #7 `python_exec` 可选 venv（小增强）**

---

## 三、Task 009 目标（本期范围）

> **主题：从「能动手」到「能看见 + 会反思」—— Agent 闭环升级**

### 3.1 明确范围

| 做 | 不做 |
|---|---|
| ✅ `image_ocr(path_or_url)` 工具：调用多模态 LLM 抽文字（含手写） | ❌ 本地部署 OCR 模型（PaddleOCR / Tesseract）；走 API 即可 |
| ✅ Qwen-VL / GPT-4V / Claude Vision 三家 base_url 兼容 | ❌ 同时混用多家做投票；选一家就行 |
| ✅ `pdf_read` 检测到扫描件时**自动建议** Agent 调用 `image_ocr`（页面 → 临时 PNG → ocr） | ❌ PDF 内嵌图片自动整页 OCR（先做最朴素的"用户喂截图"路径） |
| ✅ AgentLoop 增加 `self_critique` 回合：当 `python_exec` 返回 `exit_code != 0` 或断言失败，自动反馈给 LLM 让它修代码 | ❌ 任意工具的失败重试；**只对 python_exec 这一对 (代码, 结果) 做** |
| ✅ 自批改最多 `max_critique_rounds=3` 轮，每轮把 stderr / 失败用例喂回去 | ❌ 无限循环；硬上限 3 |
| ✅ `python_exec` 增加可选 `extra_packages` 列表（白名单：numpy / pandas / matplotlib），按需 `pip install --target` 到临时目录 | ❌ 任意 pip install；只允许白名单内 5~10 个包 |
| ✅ doctor 新增第 8 项：多模态 LLM 连通性检查（如配置了 VL 模型） | ❌ 自动配置 VL 模型 |
| ✅ Chainlit UI 支持上传图片 → 自动塞进对话 | ❌ 任意文件类型上传；先支持图片 |

### 3.2 成功指标

1. [x] 用户在 Chainlit 上传一张手写数学题截图 → Agent 自动调 `image_ocr` → 抽出题目 → 解题
2. [x] `pdf_read` 检测到扫描件时，回复里**直接附上**"已尝试 OCR 第一页：xxxxx"（而不是只说"请等待"）
3. [x] 给 Agent 一道题：「写一个判断回文数的函数，用 `assert is_palindrome(121) == True; assert is_palindrome(123) == False` 验证」→ 第一次写错时 Agent **自动修正再跑**，最终 `exit_code == 0`
4. [x] 自批改回合数有上限：故意给一个无解的需求（"写一个永远返回 True 的函数让 `assert f(0) == False`"），3 轮后给出"我尝试了 3 次仍不通过"的诚实回复，**不无限循环**
5. [x] `python_exec(code, extra_packages=["numpy"])` 能成功 `import numpy as np; print(np.zeros(3))`
6. [x] `course-agent doctor` 第 8 项显示多模态 LLM 状态（未配置时 ⚠️ 跳过，配了就真发一次 ping）
7. [x] 所有新代码有单元测试，`pytest` 与 `ruff` 全绿
8. [x] 完全向后兼容：Task 008 的 `python_exec` 不传 `extra_packages` 时行为完全不变

---

## 四、技术方案

### 4.1 `image_ocr` 工具：调多模态 LLM

```
image_ocr(path_or_url, prompt="请抽取图片中的全部文字，保留换行和公式格式")
   │
   ├─→ 判别 path 还是 url
   │    ├─ url：httpx 下载到临时文件
   │    └─ path：直接读
   ├─→ 转 base64 / data URL（OpenAI 多模态消息格式）
   ├─→ 调 multimodal LLM（base_url + model 走 .env 配置）
   │    └─ 兼容 OpenAI/DashScope 的 vision 消息：
   │         {"role":"user","content":[
   │            {"type":"text","text":prompt},
   │            {"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}
   │         ]}
   ├─→ 失败时降级：只返回 "[image_ocr] 模型未配置或调用失败：..."
   └─→ 返回纯文本（≤ 16 KB）
```

**实现位置**：[`course_agent/tools/image_ocr.py`](../course_agent/tools/image_ocr.py)（新文件）

**新增 .env**：
```env
# 多模态视觉模型（可选；默认未配置时 image_ocr 工具返回友好降级提示）
VL_MODEL=qwen-vl-plus
VL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VL_API_KEY=sk-xxx          # 不填则复用 OPENAI_API_KEY
```

### 4.2 `python_exec` 自批改闭环

不改 `python_exec` 本身，**在 AgentLoop 外面套一层 helper**，或更优雅地做成一个**新工具** `code_solve(task, tests, max_rounds=3)`：

```
code_solve(task: str, tests: str, max_rounds: int = 3)
   │
   for round in range(max_rounds):
       │
       ├─→ ① 让 LLM 写代码（system prompt: "你是 Python 程序员，根据需求写代码"）
       │     输入：task + tests + (上轮 stderr if any)
       │
       ├─→ ② 拼接 code + "\n# === auto tests ===\n" + tests
       │
       ├─→ ③ 调 python_exec(code, timeout=10)
       │
       ├─→ ④ 解析返回 JSON：
       │     ├─ exit_code == 0 → 成功，返回 {success: True, code, rounds}
       │     └─ != 0 → 把 stderr 截前 1KB，进入下一轮
       │
       └─→ 跳出循环（达到 max_rounds）→ 返回 {success: False, last_error, all_attempts}
```

**实现位置**：[`course_agent/tools/code_solve.py`](../course_agent/tools/code_solve.py)（新文件）

**关键设计**：
- 这是一个**用 LLM 的工具**——意味着工具内部要拿到 `LLM` 句柄（通过 `course_agent.llm.factory.get_default_llm()` 单例）
- 自批改的 system prompt 要明确告诉 LLM「你拿到的是上一轮的失败信息，请只返回**完整的新代码**，不要解释」，避免 LLM 又开始絮叨
- `max_rounds` 硬上限 5，防止用户手贱传 100

### 4.3 `python_exec` 增加 `extra_packages` 可选参数

```python
@tool(...)
def python_exec(
    code: str,
    stdin: str = "",
    timeout: int = 5,
    extra_packages: list[str] | None = None,  # 新增
) -> str:
    if extra_packages:
        # 白名单校验
        not_allowed = set(extra_packages) - _ALLOWED_PACKAGES
        if not_allowed:
            return json.dumps({"error": f"以下包不在白名单：{not_allowed}"})
        # pip install --target=tmpdir/_pkgs --no-deps numpy pandas ...
        # 子进程 PYTHONPATH 注入 tmpdir/_pkgs
        ...
```

**白名单**：`numpy / pandas / matplotlib / scipy / sympy / requests`（数据科学 / 数学 / 网络题目最常用 6 个）

**注意**：装包很慢，第一次 ~10s。可以缓存到 `~/.cache/course-agent/pkgs/<pkg>-<version>/` 复用。

### 4.4 `pdf_read` 扫描件 → 自动 OCR 兜底

```
pdf_read(path, page_range)
   │
   ├─→ pypdf 抽文本（Task 008 已有）
   ├─→ if max_page_chars < 10:   # 检测到扫描件
   │     ├─→ 尝试 import pypdfium2 把第一页渲染成 PNG
   │     ├─→ 调 image_ocr(png_path)
   │     └─→ 返回 "[pdf_read] 扫描件 PDF；已用 image_ocr 抽取第 1 页：\n<ocr_text>"
   └─→ 否则按原逻辑返回
```

**注意**：`pypdfium2` 是新依赖（无 C 编译，纯 wheel），如果用户没装就跳过 OCR 兜底，仍走 Task 008 的友好提示。

### 4.5 Chainlit UI 支持图片上传

Chainlit 自带 `cl.AskFileMessage` 和 `cl.Message(elements=[cl.Image(...)])`，但要让用户**拖拽图片到对话框**需要打开 `features.spontaneous_file_upload` 配置。

```toml
# .chainlit/config.toml
[features.spontaneous_file_upload]
enabled = true
accept = ["image/*"]
max_files = 3
max_size_mb = 10
```

收到 `cl.Message.elements` 中的 `cl.Image` 时，把它落地到临时文件，然后**自动给 Agent 注入一段提示**："用户上传了图片：/tmp/xxx.png，请先调用 image_ocr 抽取文字。"

### 4.6 与现有架构的拼合

```
       ┌────────────────────────────────────────────────────────┐
       │             AgentLoop（保持不动）                       │
       │                                                          │
       │   思考 → LLM.chat(tools=...) → tool_call?               │
       │            │                          │                  │
       │            │                          ▼                  │
       │            │     ┌──────────────────────────────┐        │
       │            │     │  Tool Registry               │        │
       │            │     │   (旧 9 个) + 🆕 image_ocr    │        │
       │            │     │            + 🆕 code_solve   │        │
       │            │     └──────────────────────────────┘        │
       │            ▼                                              │
       │      最终答案，回传 UI                                    │
       └────────────────────────────────────────────────────────┘
              ↑                                ↑
              │                                │
       Chainlit 上传图片                pdf_read 扫描件→OCR 兜底
```

**完全不动 Memory / 错误分类 / doctor 主体**——只新增工具 + 新增图片上传通道 + doctor 加 1 项检查。

---

## 五、实施步骤

### Step 1：依赖与骨架（0.5 天）
- [x] `pyproject.toml` 新增 `pypdfium2>=4.0`（PDF 渲染为图片）
- [x] 新建 [`course_agent/tools/image_ocr.py`](../course_agent/tools/image_ocr.py) 与 [`course_agent/tools/code_solve.py`](../course_agent/tools/code_solve.py)
- [x] [`tools/__init__.py`](../course_agent/tools/__init__.py) 注册新工具
- [x] `.env.example` 新增 `VL_MODEL` / `VL_BASE_URL` / `VL_API_KEY` 三行（带注释）

### Step 2：`image_ocr` 实现（1 天）
- [x] 路径 / URL 自动判别 + 下载
- [x] base64 编码 + OpenAI 多模态消息格式
- [x] 调 LLM + 错误降级（未配置 VL 时返回友好提示）
- [x] 单测：mock httpx + mock LLM；真实集成测试 `RUN_LIVE_VL=1` 才跑

### Step 3：`code_solve` 自批改闭环（1 天）
- [x] LLM 单例获取（factory 加 `get_default_llm()`）
- [x] system prompt 设计："你是 Python 程序员，根据需求和失败信息写完整代码"
- [x] 循环：写 → 跑 → 解析 → 反馈 → 再写
- [x] 单测：mock LLM + 真实 python_exec；验证「正确题第 1 轮通过」「错误题用 3 轮后失败诚实返回」

### Step 4：`python_exec` extra_packages（0.5 天）
- [x] 白名单常量 `_ALLOWED_PACKAGES`
- [x] `pip install --target` 到 `~/.cache/course-agent/pkgs/`
- [x] 子进程 `PYTHONPATH` 注入
- [x] 单测：mock pip install；真实 `RUN_LIVE_PIP=1` 才装 numpy 验证

### Step 5：`pdf_read` 扫描件 → OCR 兜底（0.5 天）
- [x] 检测到扫描件时，try import pypdfium2
- [x] 渲染第一页 → 临时 PNG → 调 `image_ocr`
- [x] 单测：mock image_ocr，验证返回拼接正确

### Step 6：Chainlit 图片上传（0.5 天）
- [x] `.chainlit/config.toml` 打开 `spontaneous_file_upload`
- [x] `chainlit_app.py` 处理 `message.elements` 中的 `cl.Image`
- [x] 落地临时文件 + 自动给 LLM 加提示
- [x] 手动验证：拖一张题目截图进对话框，看 Agent 是否自动调 OCR

### Step 7：doctor 第 8 项 + 测试 + 文档（0.5 天）
- [x] [`cli.py:doctor`](../course_agent/cli.py) 新增「多模态 LLM 连通性」检查
- [x] 全量 `uv run pytest -q` 与 `uv run ruff check .` 全绿
- [x] [README.md](../README.md) 新增「🖼️ 图片识别 image_ocr」「🔁 自批改闭环 code_solve」「📦 沙箱白名单包」三节
- [x] [task/task_009.md](task_009.md) 全部交付物打钩

**合计预估：4.5 天**

---

## 六、风险与应对

| 风险 | 应对 |
|---|---|
| 多模态 LLM 调用失败 / 不可用 | `image_ocr` 默认走 try/except，未配置 VL 时直接返回友好提示，不抛 |
| 自批改闭环把上下文越写越长 | 每轮只把上一轮的 stderr 截前 1KB 喂回去；不携带历史多轮 |
| 自批改导致死循环 | 硬上限 `max_rounds=5`，默认 3 |
| `pip install --target` 网络问题 / 版本冲突 | 缓存到磁盘 + 失败回退到「用 stdlib 重写」提示 |
| `pypdfium2` 在某些 ARM 平台缺 wheel | try import 失败时跳过 OCR 兜底，仍走 Task 008 的友好提示 |
| Chainlit 上传图片体积过大 | `max_size_mb=10` 限死 |
| `image_ocr` 把 base64 整张图传给 LLM 烧 token | 提示用户压缩图片；后续 Task 011 加图片预处理（resize） |

---

## 七、交付物清单

- [x] [`course_agent/tools/image_ocr.py`](../course_agent/tools/image_ocr.py)
- [x] [`course_agent/tools/code_solve.py`](../course_agent/tools/code_solve.py)
- [x] [`course_agent/tools/python_exec.py`](../course_agent/tools/python_exec.py)（新增 `extra_packages` 参数）
- [x] [`course_agent/tools/pdf_tools.py`](../course_agent/tools/pdf_tools.py)（扫描件 → OCR 兜底）
- [x] [`course_agent/tools/__init__.py`](../course_agent/tools/__init__.py)（注册新工具）
- [x] [`course_agent/llm/factory.py`](../course_agent/llm/factory.py) 新增 `get_default_llm()` 单例
- [x] [`course_agent/cli.py`](../course_agent/cli.py) doctor 第 8 项
- [x] [`course_agent/ui/chainlit_app.py`](../course_agent/ui/chainlit_app.py) 图片上传
- [x] [`.chainlit/config.toml`](../.chainlit/config.toml) `spontaneous_file_upload` 开关
- [x] `tests/test_image_ocr.py`（≥ 5 项：路径 / URL / 未配置降级 / mock 多模态调用 / 错误处理）
- [x] `tests/test_code_solve.py`（≥ 4 项：第 1 轮通过 / 多轮通过 / 达上限失败 / mock LLM 写出语法错误）
- [x] `tests/test_python_exec_packages.py`（≥ 3 项：白名单拒绝 / 无 extra_packages 兼容 / mock pip install）
- [x] `tests/test_pdf_ocr_fallback.py`（≥ 2 项：mock image_ocr 拼接 / 无 pypdfium2 时降级）
- [x] `pyproject.toml` 新增 `pypdfium2>=4.0`
- [x] `.env.example` 新增 VL 三行
- [x] [`README.md`](../README.md) 新增 3 节 + 工具表 / Milestone / 项目结构同步

---

## 八、后续可衔接的 Task

- **Task 010**：真流式 streaming（token-by-token 进 Chainlit Message + 与 tool_call 兼容）
- **Task 011**：多 Agent 编排（Planner → Solver[code_solve + python_exec] → Grader[image_ocr 看用户答案截图打分]）
- **Task 012**：可观测性面板（token / 时延 / 工具失败率 + 自批改成功率统计）
- **Task 013**：Chainlit data layer（SQLite 持久化历史消息）
- **Task 014**：生产化部署（Dockerfile + docker-compose + HTTPS）

---

## 九、完成后项目能力对比

| 能力 | Task 008 后 | Task 009 后 |
|---|---|---|
| 工具数量 | 9 | **11**（+ image_ocr / code_solve） |
| 手写题 / 板书 / 拍照题 | ❌ 完全瞎 | ✅ 拖图片到对话框，Agent 自动 OCR |
| 扫描件 PDF | ⚠️ 只提示"请等 Task 009" | ✅ 自动渲染首页 → OCR → 返回文字 |
| 编程题写错时 | ❌ 全靠 LLM 自觉 | ✅ `code_solve` 自动「写→跑→改→再跑」最多 3 轮 |
| 数据科学题（numpy/pandas） | ❌ 仅 stdlib | ✅ `extra_packages` 白名单 6 个常用包 |
| doctor 检查项 | 7 | **8**（+ 多模态连通性） |
| 与普通 AI Chat 差距 | 跑代码 + 读 PDF | **再加：看图、自反思、装包** —— 已经是「能独立完成完整作业」的助理 |

---

> **一句话总结**：Task 008 让 Agent 能「动手」，Task 009 让 Agent 能「看见」+「反思」。做完之后你拍一张老师手写的板书丢进去，Agent 不仅能识别题目，还能自己写代码、自己跑、跑错了自己改——你只需要负责拍照。

