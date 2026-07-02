"""
PromptLoader 单元测试：覆盖加载、版本管理、渲染与异常分支。
"""

import pytest

from agent.prompt_loader import PromptLoader


@pytest.fixture
def loader():
    """使用仓库自带 prompts 目录的加载器。"""
    return PromptLoader()


def test_load_returns_prompt_text(loader):
    text = loader.load("daily_evaluation")
    assert "EmpValue-AI" in text or "员工" in text


def test_load_missing_raises(loader):
    with pytest.raises(FileNotFoundError):
        loader.load("not-a-real-prompt")


def test_version_extracted_from_header(loader):
    assert loader.version("daily_evaluation") == "v0.1"


def test_version_unknown_when_no_header(tmp_path):
    # 构造一个无版本头的临时 prompt 文件
    (tmp_path / "no_version.md").write_text("# 只有标题\n\n无版本信息。", encoding="utf-8")
    loader = PromptLoader(prompts_dir=tmp_path)
    assert loader.version("no_version") == "unknown"


def test_list_versions_returns_sorted(loader):
    # v0.2 新增后，versions/ 目录下含 v0.1 与 v0.2 两个快照
    assert loader.list_versions("daily_evaluation") == ["v0.1", "v0.2"]


def test_list_versions_empty_when_no_versions_dir(tmp_path):
    loader = PromptLoader(prompts_dir=tmp_path)
    assert loader.list_versions("daily_evaluation") == []


def test_list_versions_filters_by_name(tmp_path):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()
    (versions_dir / "daily_evaluation_v0.1.md").write_text("a", encoding="utf-8")
    (versions_dir / "daily_evaluation_v0.3.md").write_text("b", encoding="utf-8")
    (versions_dir / "other_v0.2.md").write_text("c", encoding="utf-8")
    loader = PromptLoader(prompts_dir=tmp_path)
    assert loader.list_versions("daily_evaluation") == ["v0.1", "v0.3"]
    assert loader.list_versions("other") == ["v0.2"]


def test_load_version_with_v_prefix(loader):
    text = loader.load_version("daily_evaluation", "v0.1")
    assert len(text) > 0


def test_load_version_without_v_prefix(loader):
    text = loader.load_version("daily_evaluation", "0.1")
    assert len(text) > 0


def test_load_version_missing_raises_with_available(loader):
    with pytest.raises(FileNotFoundError) as exc:
        loader.load_version("daily_evaluation", "v9.9")
    assert "v0.1" in str(exc.value)


def test_render_replaces_known_placeholders(loader):
    # daily_evaluation 模板使用 {raw_inputs}/{employee_history}/{company_kb}
    rendered = loader.render(
        "daily_evaluation",
        raw_inputs=[{"day": "周一", "content": "完成 A"}],
        employee_history=[{"period": "2026-W24", "score": 80}],
        company_kb=[{"rule": "执行力优先"}],
        employee_id="EMP001",
        period="2026-W25",
    )
    assert "完成 A" in rendered
    assert "执行力优先" in rendered
    assert "2026-W24" in rendered


def test_render_substitutes_employee_id_and_period():
    # 用合成模板验证 {employee_id}/{period} 占位符替换
    loader = PromptLoader()
    result = loader._render_template(
        "id={employee_id}, period={period}",
        raw_inputs=[],
        employee_id="EMP001",
        period="2026-W25",
    )
    assert result == "id=EMP001, period=2026-W25"


def test_render_preserves_unknown_braces(loader):
    # 模板里若含未知 {foo} 占位符，应原样保留
    template = "inputs={raw_inputs}, keep={foo}"
    result = loader._render_template(template, raw_inputs=[{"x": 1}])
    assert "{foo}" in result
    assert '"x": 1' in result


def test_render_defaults_empty_collections(loader):
    rendered = loader.render(
        "daily_evaluation",
        raw_inputs=[{"d": "周一"}],
        employee_history=None,
        company_kb=None,
    )
    assert "[]" in rendered  # None -> 空数组


def test_render_version_replaces_placeholders(loader):
    rendered = loader.render_version(
        "daily_evaluation",
        "v0.1",
        raw_inputs=[{"day": "周一", "task": "修复 bug"}],
        employee_id="EMP002",
        period="2026-W26",
    )
    assert "修复 bug" in rendered
