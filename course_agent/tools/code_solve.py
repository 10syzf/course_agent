"""自批改闭环工具：写代码 → 跑 → 失败就改 → 再跑（最多 N 轮）.

实现要点：
  ① 拿到默认 LLM 句柄（factory.get_default_llm() 单例，复用 .env 配置）
  ② for round in range(max_rounds):
       a. 让 LLM 写代码（system: 你是 Python 程序员，根据需求写代码 / 拿到上轮失败信息时只返回完整新代码）
       b. 抽取 ```python ... ``` 代码块（防止 LLM 顺手写个解释）
       c. 拼接 code + "\n# === auto tests ===\n" + tests
       d. 调 python_exec(code, timeout=10) 拿 JSON 结果
       e. exit_code == 0 → 成功；否则把 stderr 截 1KB 喂回去
  ③ 返回 {success, rounds, code, last_error, attempts}
  ④ 硬上限 max_rounds=5；默认 3
"""

from __future__ import annotations

import json
import re

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("code_solve")

_DEFAULT_MAX_ROUNDS = 3
_HARD_MAX_ROUNDS = 5
_PYTHON_EXEC_TIMEOUT = 10
_STDERR_FEEDBACK_LIMIT = 1024  # 喂回 LLM 的 stderr 截断
_TESTS_SEPARATOR = "\n\n# === auto tests (auto-injected by code_solve) ===\n"

_SYSTEM_PROMPT_FIRST = (
    "你是一名严格、简洁的 Python 程序员。"
    "用户会给你一段中文需求和一段断言测试，请只返回**完整、可独立运行**的 Python 代码。"
    "要求：\n"
    "1) 只用 Python 标准库（除非用户显式允许其它包）；\n"
    "2) 不要写解释、不要写注释之外的自然语言；\n"
    "3) 用 ```python ... ``` 三引号代码块包裹整段代码。"
)

_SYSTEM_PROMPT_RETRY = (
    "你刚才写的 Python 代码运行失败了。"
    "请仔细阅读 stderr，**只返回修正后完整可运行的代码**（仍用 ```python ... ``` 包裹），"
    "不要解释、不要道歉、不要保留旧的错误代码。"
)

_CODE_BLOCK_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def _extract_code(text: str) -> str:
    """从 LLM 输出里抽取 Python 代码块；找不到就把整段当代码."""
    m = _CODE_BLOCK_RE.search(text or "")
    if m:
        return m.group(1).strip()
    return (text or "").strip()


def _ask_llm_for_code(
    llm,  # noqa: ANN001  避免引入 BaseLLM 的循环依赖
    task: str,
    tests: str,
    last_stderr: str | None,
) -> str:
    """让 LLM 写代码，返回抽取后的纯 Python 字符串."""
    from course_agent.llm.base import LLMMessage

    if last_stderr is None:
        system = _SYSTEM_PROMPT_FIRST
        user = (
            f"【需求】\n{task.strip()}\n\n"
            f"【自动测试代码（你的代码后会被自动追加这一段）】\n```python\n{tests.strip() or '# (无)'}\n```"
        )
    else:
        system = _SYSTEM_PROMPT_RETRY
        user = (
            f"【需求】\n{task.strip()}\n\n"
            f"【自动测试代码】\n```python\n{tests.strip() or '# (无)'}\n```\n\n"
            f"【上一轮 stderr (最多 1KB)】\n```\n{last_stderr[:_STDERR_FEEDBACK_LIMIT]}\n```"
        )

    resp = llm.chat(
        [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ],
        tools=None,
    )
    return _extract_code(resp.content or "")


@tool(
    name="code_solve",
    description=(
        "自批改编程闭环：根据自然语言需求和断言测试，自动写 Python 代码、运行、"
        "失败时根据 stderr 自我修正、再运行，最多 N 轮。"
        "适合：学生让 Agent 帮写一个函数并要求自动验证。"
    ),
)
def code_solve(task: str, tests: str = "", max_rounds: int = 3) -> str:
    """自批改闭环工具.

    Args:
        task: 自然语言需求，如「写一个判断回文数的函数 is_palindrome(n)」。
        tests: 断言测试代码，会被追加到 LLM 写的代码末尾，如
            `assert is_palindrome(121) == True\\nassert is_palindrome(123) == False`。
        max_rounds: 最大自批改轮数，硬上限 5；默认 3。

    Returns:
        JSON 字符串：{success, rounds, code, last_error, attempts}。
    """
    rounds_cap = max(1, min(int(max_rounds or _DEFAULT_MAX_ROUNDS), _HARD_MAX_ROUNDS))

    if not task or not task.strip():
        return json.dumps(
            {
                "success": False,
                "rounds": 0,
                "code": "",
                "last_error": "[code_solve] 入参 task 为空，请提供自然语言需求。",
                "attempts": [],
            },
            ensure_ascii=False,
        )

    # 延迟 import：避免在 module-load 期触发 LLM 创建（影响测试）
    try:
        from course_agent.llm.factory import get_default_llm
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {
                "success": False,
                "rounds": 0,
                "code": "",
                "last_error": f"[code_solve] 获取 LLM 失败：{e}",
                "attempts": [],
            },
            ensure_ascii=False,
        )

    try:
        llm = get_default_llm()
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {
                "success": False,
                "rounds": 0,
                "code": "",
                "last_error": f"[code_solve] 初始化 LLM 失败（请检查 .env）：{e}",
                "attempts": [],
            },
            ensure_ascii=False,
        )

    # 延迟 import python_exec：拿到底层 _run_code_sync 直接调，不走 @tool 包装层
    from course_agent.tools.python_exec import _run_code_sync

    attempts: list[dict] = []
    last_stderr: str | None = None
    last_code = ""

    for r in range(1, rounds_cap + 1):
        try:
            code = _ask_llm_for_code(llm, task, tests, last_stderr)
        except Exception as e:  # noqa: BLE001
            last_stderr = f"[LLM 调用失败] {type(e).__name__}: {e}"
            attempts.append({"round": r, "code": "", "stage": "llm", "error": last_stderr})
            _log.warning(f"code_solve round={r} LLM 调用失败：{e}")
            continue

        if not code.strip():
            last_stderr = "[code_solve] LLM 返回空代码"
            attempts.append({"round": r, "code": "", "stage": "llm", "error": last_stderr})
            continue

        full_code = code + (_TESTS_SEPARATOR + tests if tests.strip() else "")
        last_code = full_code

        result = _run_code_sync(full_code, "", _PYTHON_EXEC_TIMEOUT)
        exit_code = int(result.get("exit_code", -1))
        stdout = str(result.get("stdout", ""))
        stderr = str(result.get("stderr", ""))
        timed_out = bool(result.get("timed_out", False))

        attempts.append(
            {
                "round": r,
                "code": code,  # 只存 LLM 写的部分，测试代码不用重复存
                "exit_code": exit_code,
                "stdout": stdout[:512],
                "stderr": stderr[:512],
                "timed_out": timed_out,
            }
        )

        if exit_code == 0:
            _log.info(f"code_solve 在第 {r} 轮通过 ✅")
            return json.dumps(
                {
                    "success": True,
                    "rounds": r,
                    "code": full_code,
                    "stdout": stdout,
                    "last_error": "",
                    "attempts": attempts,
                },
                ensure_ascii=False,
            )

        last_stderr = stderr or f"exit_code={exit_code}"
        _log.info(
            f"code_solve round={r}/{rounds_cap} 失败 (exit={exit_code}, timed_out={timed_out})"
        )

    return json.dumps(
        {
            "success": False,
            "rounds": rounds_cap,
            "code": last_code,
            "last_error": (
                f"[code_solve] 已尝试 {rounds_cap} 轮仍未通过；"
                f"最后一次 stderr (截断)：{(last_stderr or '')[:_STDERR_FEEDBACK_LIMIT]}"
            ),
            "attempts": attempts,
        },
        ensure_ascii=False,
    )
