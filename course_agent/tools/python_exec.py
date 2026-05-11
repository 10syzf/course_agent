"""Sandbox 化的 Python 代码执行工具.

四道安全闸（详见 task_008.md §4.1）：
  ① 输入校验（长度上限 + AST 黑名单）
  ② 隔离 subprocess（临时 cwd + 净化 env + 子进程 rlimit）
  ③ 超时熔断（asyncio.wait_for + kill）
  ④ 输出截断（stdout 8KB / stderr 4KB）

⚠️ 这是「半信任」沙箱：足够防住学生作业意外死循环 / 误删本地文件 / 误调真实 API，
   但**不能**用来抵御主动攻击。生产环境部署前请加 Docker / gVisor 强隔离。
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from course_agent.logger import get_logger
from course_agent.tools.registry import tool

_log = get_logger("python_exec")

_DEFAULT_TIMEOUT = 5
_MAX_TIMEOUT = 30
_MAX_CODE = 16 * 1024
_MAX_STDOUT = 8 * 1024
_MAX_STDERR = 4 * 1024
_MEM_LIMIT_BYTES = 256 * 1024 * 1024
_NOFILE_LIMIT = 64
_CPU_TIME_LIMIT = 5

# Task 009：受控的 extra_packages 白名单（数据科学 / 数学 / 网络题目最常用 6 个）
_ALLOWED_PACKAGES: set[str] = {
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "sympy",
    "requests",
}
_PIP_INSTALL_TIMEOUT = 120
_PKG_CACHE_DIR = Path("~/.cache/course-agent/pkgs").expanduser()

# 黑名单：模块层 import / from-import 出现这些就直接拒绝
# 注意：保留 socket（pypdf / trafilatura 都不需要它），不破坏现有工具
_FORBIDDEN_MODULES = {
    "subprocess",
    "ctypes",
    "socket",
    "shutil",  # 防 rmtree
    "pty",
    "fcntl",
    "multiprocessing",
}
# os 模块本身允许（join/path），但 os.system / os.popen / os.execv 等通过 attribute 访问黑名单拦
_FORBIDDEN_OS_ATTRS = {
    "system",
    "popen",
    "execv",
    "execvp",
    "execve",
    "execvpe",
    "execl",
    "execlp",
    "execle",
    "fork",
    "spawnl",
    "spawnv",
    "_exit",
}


class _SandboxAuditor(ast.NodeVisitor):
    """AST 静态扫描，找到第一处违规就抛 ValueError."""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _FORBIDDEN_MODULES:
                raise ValueError(f"被禁止的 import：{alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        top = (node.module or "").split(".")[0]
        if top in _FORBIDDEN_MODULES:
            raise ValueError(f"被禁止的 from-import：{node.module}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # 拦截 os.system / os.popen 等
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in _FORBIDDEN_OS_ATTRS
        ):
            raise ValueError(f"被禁止的属性访问：os.{node.attr}")
        self.generic_visit(node)


def _audit(code: str) -> str | None:
    """返回 None 表示通过，否则返回错误信息字符串."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"代码语法错误：{e.msg} (line {e.lineno})"
    try:
        _SandboxAuditor().visit(tree)
    except ValueError as e:
        return str(e)
    return None


def _set_subprocess_limits() -> None:
    """子进程入口前调用：设置 rlimit（仅 Unix）."""
    if sys.platform == "win32":
        return
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (_CPU_TIME_LIMIT, _CPU_TIME_LIMIT))
        resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (_NOFILE_LIMIT, _NOFILE_LIMIT))
    except Exception:  # noqa: BLE001
        # 部分平台 / 容器内不允许设置，安全降级
        pass


def _build_clean_env() -> dict[str, str]:
    """构造净化的环境变量：剥离所有 OPENAI_/AWS_/TAVILY_ 等敏感 key，禁网相关 proxy 也剥离."""
    keep_keys = {"PATH", "HOME", "LANG", "LC_ALL", "TZ"}
    env = {k: v for k, v in os.environ.items() if k in keep_keys}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # 禁网兜底：清空代理（rlimit + 应用层 socket 黑名单 + 这里三重保险）
    for k in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env.pop(k, None)
    return env


def _truncate(data: bytes, limit: int) -> tuple[str, bool]:
    if len(data) <= limit:
        return data.decode("utf-8", errors="replace"), False
    return data[:limit].decode("utf-8", errors="replace") + "\n...[truncated]", True


async def _arun_code(
    code: str,
    stdin: str,
    timeout: int,
    extra_pythonpath: str | None = None,
) -> dict[str, object]:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pyexec_") as tmpdir:
        script = Path(tmpdir) / "main.py"
        script.write_text(code, encoding="utf-8")

        env = _build_clean_env()
        if extra_pythonpath:
            # 注入白名单包目录；保留可能的现有 PYTHONPATH（理论上 _build_clean_env 已剥离）
            env["PYTHONPATH"] = extra_pythonpath

        kwargs: dict[str, object] = {
            "stdin": asyncio.subprocess.PIPE,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
            "cwd": tmpdir,
            "env": env,
        }
        if sys.platform != "win32":
            kwargs["preexec_fn"] = _set_subprocess_limits  # type: ignore[assignment]

        # extra_packages 模式下不能用 -I（会忽略 PYTHONPATH）；只用 -S 防 site-packages 用户目录
        py_flags = ["-S"] if extra_pythonpath else ["-I", "-S"]

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            *py_flags,
            str(script),
            **kwargs,  # type: ignore[arg-type]
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin.encode("utf-8") if stdin else None),
                timeout=timeout,
            )
        except TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=0.5)
            except TimeoutError:
                pass
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"[TIMEOUT] 执行超过 {timeout}s 被强制终止",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "truncated": False,
                "timed_out": True,
            }

        out_text, out_trunc = _truncate(stdout or b"", _MAX_STDOUT)
        err_text, err_trunc = _truncate(stderr or b"", _MAX_STDERR)
        return {
            "exit_code": proc.returncode if proc.returncode is not None else -1,
            "stdout": out_text,
            "stderr": err_text,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "truncated": out_trunc or err_trunc,
            "timed_out": False,
        }


def _run_code_sync(
    code: str,
    stdin: str,
    timeout: int,
    extra_pythonpath: str | None = None,
) -> dict[str, object]:
    """同步入口：在已有 event loop 时用线程池兜底."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(asyncio.run, _arun_code(code, stdin, timeout, extra_pythonpath))
            return fut.result()
    return asyncio.run(_arun_code(code, stdin, timeout, extra_pythonpath))


def _ensure_packages(packages: list[str]) -> tuple[str | None, str | None]:
    """白名单校验 + pip install --target 到缓存目录.

    Returns:
        (pythonpath, error)：成功返回 (cache_dir, None)；失败返回 (None, 错误信息)。
    """
    if not packages:
        return None, None

    # 1) 白名单校验
    not_allowed = sorted(set(packages) - _ALLOWED_PACKAGES)
    if not_allowed:
        return None, (
            f"以下包不在白名单：{not_allowed}；"
            f"当前允许：{sorted(_ALLOWED_PACKAGES)}"
        )

    # 2) 缓存目录（每个包一个子目录，方便复用）
    _PKG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = _PKG_CACHE_DIR / "shared"
    target.mkdir(parents=True, exist_ok=True)

    # 3) 检查每个包是否已就位（看 cache_dir 下是否有 <pkg> 顶层目录）
    missing = [p for p in packages if not (target / p).exists() and not (target / f"{p}.py").exists()]

    if missing:
        _log.info(f"python_exec: pip install --target={target} {missing}")
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    str(target),
                    "--disable-pip-version-check",
                    "--no-input",
                    "--quiet",
                    *missing,
                ],
                check=True,
                timeout=_PIP_INSTALL_TIMEOUT,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            return None, f"pip install 超过 {_PIP_INSTALL_TIMEOUT}s 超时（{missing}）"
        except subprocess.CalledProcessError as e:
            err = (e.stderr or b"").decode("utf-8", errors="replace")[:500]
            return None, f"pip install 失败（{missing}）：{err}"
        except Exception as e:  # noqa: BLE001
            return None, f"pip install 异常：{type(e).__name__}: {e}"

    return str(target), None


@tool(
    name="python_exec",
    description=(
        "在隔离的子进程里执行一段 Python 代码并返回 JSON: "
        "{exit_code, stdout, stderr, duration_ms, truncated, timed_out}。"
        "默认禁网 + 5s 超时 + 256MB 内存上限 + 输出截断。"
        "适合：算法验证、数据处理、自检测试用例、'写完代码立刻跑一下'。"
        "禁止 import：subprocess / ctypes / socket / shutil / multiprocessing，"
        "及 os.system/popen/exec*/fork。"
        "可选 extra_packages 白名单装包：numpy / pandas / matplotlib / scipy / sympy / requests。"
    ),
)
def python_exec(
    code: str,
    stdin: str = "",
    timeout: int = 5,
    extra_packages: list[str] | None = None,
) -> str:
    """在沙箱中执行 Python 代码.

    :param code: 要执行的 Python 源码字符串（≤16KB）.
    :param stdin: 喂给子进程的标准输入（可选）.
    :param timeout: 超时秒数（1~30，默认 5）.
    :param extra_packages: 可选白名单包列表，例如 ["numpy"]；
        装包到 ~/.cache/course-agent/pkgs/shared 并注入 PYTHONPATH，复用缓存。
        允许集合：numpy / pandas / matplotlib / scipy / sympy / requests。
    """
    if not isinstance(code, str) or not code.strip():
        return json.dumps({"error": "code 不能为空"}, ensure_ascii=False)
    if len(code.encode("utf-8")) > _MAX_CODE:
        return json.dumps(
            {"error": f"code 超过 {_MAX_CODE} 字节上限"}, ensure_ascii=False
        )
    if not isinstance(timeout, int) or timeout < 1 or timeout > _MAX_TIMEOUT:
        return json.dumps(
            {"error": f"timeout 必须是 1~{_MAX_TIMEOUT} 秒之间的整数"},
            ensure_ascii=False,
        )

    err = _audit(code)
    if err is not None:
        _log.warning(f"python_exec 拒绝执行：{err}")
        return json.dumps({"error": f"AST 校验失败：{err}"}, ensure_ascii=False)

    extra_pythonpath: str | None = None
    if extra_packages:
        if not isinstance(extra_packages, list) or not all(isinstance(p, str) for p in extra_packages):
            return json.dumps(
                {"error": "extra_packages 必须是字符串列表，例如 [\"numpy\"]"},
                ensure_ascii=False,
            )
        extra_pythonpath, pkg_err = _ensure_packages(extra_packages)
        if pkg_err:
            return json.dumps({"error": f"extra_packages 准备失败：{pkg_err}"}, ensure_ascii=False)

    result = _run_code_sync(code, stdin or "", timeout, extra_pythonpath)
    _log.info(
        f"python_exec done: exit={result['exit_code']}, "
        f"duration={result['duration_ms']}ms, timed_out={result['timed_out']}, "
        f"extra_packages={extra_packages or []}"
    )
    return json.dumps(result, ensure_ascii=False)
