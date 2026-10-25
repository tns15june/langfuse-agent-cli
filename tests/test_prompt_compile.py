from langfuse_cli.commands.prompt import compile_mustache, compile_prompt


def test_compile_mustache_string():
    tmpl = "Hello {{ name }}, your order reference is {{ ref }}!"
    vars_dict = {"name": "Alice", "ref": "ORD-123"}
    out = compile_mustache(tmpl, vars_dict)
    assert out == "Hello Alice, your order reference is ORD-123!"


def test_compile_prompt_chat():
    chat_prompt = [
        {"role": "system", "content": "You are assisting {{ role }}."},
        {"role": "user", "content": "Help me with {{ task }}."},
    ]
    vars_dict = {"role": "an analyst", "task": "a report"}
    compiled = compile_prompt(chat_prompt, vars_dict)
    assert compiled[0]["content"] == "You are assisting an analyst."
    assert compiled[1]["content"] == "Help me with a report."


def test_compile_mustache_inserts_values_literally():
    # Values are not regex replacement templates: backslashes (Windows paths, "\n", "\1") stay as given.
    assert compile_mustache("Open {{path}}", {"path": "C:\\Users\\new"}) == "Open C:\\Users\\new"
    assert compile_mustache("Open {{path}}", {"path": "a\\nb"}) == "Open a\\nb"
