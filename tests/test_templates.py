"""Tests for prompt template save and list."""

import tempfile
from pathlib import Path

from ctxray.core.templates import generate_template_name, save_template
from ctxray.storage.db import PromptDB


def _make_db():
    tmp = tempfile.mktemp(suffix=".db")
    return PromptDB(Path(tmp))


def test_save_template_returns_info():
    db = _make_db()
    result = save_template(db, text="debug auth — login returns 401")
    assert "name" in result
    assert "category" in result
    assert result["category"] == "debug"


def test_save_template_with_custom_name():
    db = _make_db()
    result = save_template(db, text="fix the bug", name="my-fix")
    assert result["name"] == "my-fix"


def test_save_template_with_custom_category():
    db = _make_db()
    result = save_template(db, text="some prompt", category="test")
    assert result["category"] == "test"


def test_list_templates_empty():
    db = _make_db()
    items = db.list_templates()
    assert items == []


def test_list_templates_after_save():
    db = _make_db()
    save_template(db, text="debug auth bug")
    save_template(db, text="add unit tests for user service")
    items = db.list_templates()
    assert len(items) == 2


def test_list_templates_filter_category():
    db = _make_db()
    save_template(db, text="debug auth bug", category="debug")
    save_template(db, text="add unit tests", category="test")
    debug_items = db.list_templates(category="debug")
    assert len(debug_items) == 1
    assert debug_items[0]["category"] == "debug"


def test_generate_template_name_unique():
    db = _make_db()
    name1 = generate_template_name("fix the auth bug", db)
    db.save_template(name=name1, text="fix the auth bug", category="debug")
    name2 = generate_template_name("fix the auth bug", db)
    assert name1 != name2
    assert name2.endswith("-2")


def test_get_template_by_name():
    db = _make_db()
    save_template(db, text="debug auth", name="auth-debug")
    t = db.get_template("auth-debug")
    assert t is not None
    assert t["text"] == "debug auth"


def test_get_template_not_found():
    db = _make_db()
    t = db.get_template("nonexistent")
    assert t is None


def test_render_templates_output():
    from ctxray.output.terminal import render_templates

    items = [
        {
            "name": "auth-debug",
            "text": "debug auth — login returns 401",
            "category": "debug",
            "usage_count": 3,
        },
        {
            "name": "add-tests",
            "text": "add unit tests for user service",
            "category": "test",
            "usage_count": 0,
        },
    ]
    output = render_templates(items)
    assert "auth-debug" in output
    assert "debug" in output
    assert "saved" in output
    assert "2" in output


def test_render_templates_empty():
    from ctxray.output.terminal import render_templates

    output = render_templates([])
    assert "No templates" in output


def test_render_template_basic():
    from ctxray.core.templates import render_template

    text = "Fix the {error_type} in {file_path}"
    result = render_template(text, {"error_type": "TypeError", "file_path": "auth/login.py"})
    assert result == "Fix the TypeError in auth/login.py"


def test_render_template_no_vars():
    from ctxray.core.templates import render_template

    text = "Fix the bug in the login flow"
    result = render_template(text, {})
    assert result == "Fix the bug in the login flow"


def test_render_template_missing_var():
    from ctxray.core.templates import render_template

    text = "Fix {error} in {file}"
    result = render_template(text, {"error": "TypeError"})
    # Missing variables should be left as-is
    assert result == "Fix TypeError in {file}"


def test_render_template_extra_vars():
    from ctxray.core.templates import render_template

    text = "Fix {error} in code"
    result = render_template(text, {"error": "Bug", "unused": "value"})
    assert result == "Fix Bug in code"


def test_extract_variables():
    from ctxray.core.templates import extract_variables

    text = "Fix {error_type} in {file_path} for {project}"
    vars = extract_variables(text)
    assert vars == ["error_type", "file_path", "project"]


def test_extract_variables_none():
    from ctxray.core.templates import extract_variables

    text = "Fix the bug in login"
    vars = extract_variables(text)
    assert vars == []
