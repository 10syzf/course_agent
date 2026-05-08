"""测试内置工具."""

from __future__ import annotations

from pathlib import Path

from course_agent.tools import get_registry
from course_agent.tools.builtin import calculator, file_read, file_write, web_search


def test_registry_contains_builtin_tools():
    names = get_registry().list_names()
    for n in ("calculator", "file_read", "file_write", "web_search"):
        assert n in names


def test_calculator_basic():
    assert "8" in calculator("(3+5)")
    assert "16" in calculator("(3+5)*2")
    assert "计算失败" in calculator("import os")


def test_file_read_write(tmp_path: Path):
    p = tmp_path / "hello.txt"
    msg = file_write(str(p), "你好, Agent")
    assert "已写入" in msg
    assert file_read(str(p)).strip() == "你好, Agent"


def test_file_read_missing(tmp_path: Path):
    assert "不存在" in file_read(str(tmp_path / "nope.txt"))


def test_web_search_mock():
    out = web_search("深度学习", top_k=2)
    assert "深度学习" in out
    assert out.count("https://example.com") == 2


def test_schema_generation():
    reg = get_registry()
    schemas = reg.to_openai_schemas(["calculator"])
    assert schemas[0]["function"]["name"] == "calculator"
    assert "expression" in schemas[0]["function"]["parameters"]["properties"]
