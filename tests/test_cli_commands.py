import json

import pytest
from helpers import load_fixture

from langfuse_cli.cli import main
from langfuse_cli.commands import doctor
from langfuse_cli.config import ConfigManager

FLAGS = ["--host", "http://lf.test", "--public-key", "pk", "--secret-key", "sk"]
OBS = "/api/public/v2/observations"


def run(capsys, *argv):
    code = main([*argv, *FLAGS])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_prompt_list_text_shows_latest_version(fake_api, capsys):
    fake_api.route("GET", "/api/public/v2/prompts", json=load_fixture("prompts_list"))

    _, out, _ = run(capsys, "prompt", "list", "-o", "text")

    assert "  - support/greeter (v1) [labels: latest, production, staging] - type: chat" in out.splitlines()
    assert "  - welcome-bot (v2) [labels: latest, production, staging] - type: text" in out.splitlines()


def test_prompt_push_json_stdout_is_one_document(fake_api, capsys):
    fake_api.route("POST", "/api/public/v2/prompts", json=load_fixture("prompt_create"), status=201)

    code, out, _ = run(capsys, "prompt", "push", "greeter-test", "--text", "Hi {{user_name}}", "--labels", "staging")

    assert code == 0
    assert json.loads(out)["version"] == 1
    assert fake_api.bodies[-1] == {
        "name": "greeter-test", "type": "text", "prompt": "Hi {{user_name}}", "labels": ["staging"]}


def test_score_create_json_stdout_is_one_document(fake_api, capsys):
    fake_api.route("POST", "/api/public/scores", json=load_fixture("score_create"))

    code, out, _ = run(capsys, "score", "create", "--trace-id", "t1", "--name", "accuracy", "--value", "1")

    assert code == 0
    assert json.loads(out) == {"id": "9fcdf61e-ef47-4193-aa21-ce4054c7eca6"}
    assert fake_api.bodies[-1] == {"traceId": "t1", "name": "accuracy", "value": 1.0}


def test_dataset_list_reads_v2(fake_api, capsys):
    fake_api.route("GET", "/api/public/v2/datasets", json=load_fixture("datasets_list"))

    _, out, _ = run(capsys, "dataset", "list")

    assert [d["name"] for d in json.loads(out)] == ["intent-classification-evals"]


def test_dataset_get_merges_items(fake_api, capsys):
    fake_api.route("GET", "/api/public/v2/datasets/intent-classification-evals", json=load_fixture("dataset_get"))
    fake_api.route("GET", "/api/public/dataset-items", json=load_fixture("dataset_items"))

    code, out, _ = run(capsys, "dataset", "get", "intent-classification-evals")

    data = json.loads(out)
    assert code == 0
    assert data["name"] == "intent-classification-evals"
    assert sorted(i["expectedOutput"]["intent"] for i in data["items"]) == ["account", "billing", "bug"]
    assert fake_api.calls[-1][2]["datasetName"] == "intent-classification-evals"


def test_dataset_run_is_gone():
    with pytest.raises(SystemExit) as exc:
        main(["dataset", "run", "--dataset", "d", "--run-name", "r"])
    assert exc.value.code == 2


@pytest.fixture
def no_skill_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(doctor, "KNOWN_SKILL_TARGETS", [("Claude Code", tmp_path / "skills")])


def route_doctor(fake_api, projects_status=200, observations_status=200):
    fake_api.route("GET", "/api/public/health", json=load_fixture("health"))
    projects = load_fixture("projects") if projects_status == 200 else {"message": "Invalid credentials"}
    fake_api.route("GET", "/api/public/projects", json=projects, status=projects_status)
    observations = load_fixture("obs_empty") if observations_status == 200 else None
    fake_api.route("GET", OBS, json=observations, status=observations_status,
                   text=None if observations_status == 200 else "<html>404</html>",
                   content_type="application/json" if observations_status == 200 else "text/html")


def test_doctor_valid_keys(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)

    code, out, _ = run(capsys, "doctor")

    assert code == 0
    assert "Source: flags" in out
    assert "langfuse-agent-cli" in out  # project name from /api/public/projects
    assert "4.70.0" in out


def test_doctor_bad_keys(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api, projects_status=401)

    code, out, _ = run(capsys, "doctor")

    assert code == 1
    assert "401" in out


def test_doctor_old_server_without_v2_observations(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api, observations_status=404)

    code, out, _ = run(capsys, "doctor")

    assert code == 1
    assert "API Authorization: Valid" in out  # the keys are fine; the server is too old
    assert "trace commands need Langfuse v4" in out
    assert "Observations API v2: HTTP 404" not in out  # the generic branch names the same path


def test_auth_status_rejects_bad_keys(fake_api, capsys):
    fake_api.route("GET", "/api/public/projects", json={"message": "Invalid credentials"}, status=401)

    code, out, _ = run(capsys, "auth", "status")

    assert code == 1
    assert "Invalid credentials" in out


def test_doctor_fails_when_the_host_answers_with_a_web_page(fake_api, capsys, no_skill_dirs):
    for path in ("/api/public/health", "/api/public/projects", OBS):
        fake_api.route("GET", path, text="<html>Sign in</html>", content_type="text/html")

    code, out, _ = run(capsys, "doctor")

    assert code == 1
    assert "API Authorization: Valid" not in out


FOLDER_PROMPT = "/api/public/v2/prompts/support%2Fgreeter"


def test_prompt_get_compiles_vars(fake_api, capsys):
    fake_api.route("GET", FOLDER_PROMPT, json=load_fixture("prompt_get_folder"))

    _, out, _ = run(capsys, "prompt", "get", "support/greeter", "--vars", '{"user_name": "Ana", "question": "Why?"}')

    assert [m["content"] for m in json.loads(out)["compiled_prompt"]] == ["You help Ana with their account.", "Why?"]


@pytest.mark.parametrize("bad_vars", ["{bad", "[1, 2]"])
def test_prompt_get_bad_vars_fails_before_any_request(fake_api, capsys, bad_vars):
    code, out, err = run(capsys, "prompt", "get", "support/greeter", "--vars", bad_vars)

    assert (code, out, fake_api.calls) == (1, "", [])
    assert err.startswith("Error: --vars")


@pytest.mark.parametrize("content,prompt_type,sent", [
    ('[{"role": "user", "content": "Hi {{name}}"}]', "chat", [{"role": "user", "content": "Hi {{name}}"}]),
    ("Hi {{name}}", "text", "Hi {{name}}"),
    ('{"answer_format": "json"}', "text", '{"answer_format": "json"}'),  # a text prompt stays text
])
def test_prompt_push_from_file(fake_api, capsys, tmp_path, content, prompt_type, sent):
    path = tmp_path / "prompt.txt"
    path.write_text(content)
    fake_api.route("POST", "/api/public/v2/prompts", json=load_fixture("prompt_create"), status=201)

    code, _, _ = run(capsys, "prompt", "push", "p", "--file", str(path), "--type", prompt_type)

    assert code == 0
    assert fake_api.bodies[-1]["prompt"] == sent


def test_prompt_push_chat_file_must_be_json(fake_api, capsys, tmp_path):
    path = tmp_path / "chat.json"
    path.write_text("Hi {{name}}")

    code, out, err = run(capsys, "prompt", "push", "p", "--file", str(path), "--type", "chat")

    assert (code, out, fake_api.calls) == (1, "", [])
    assert err.startswith("Error: ")


def test_doctor_finds_a_project_level_skill(fake_api, capsys, no_skill_dirs, tmp_path):
    # `npx skills add` installs into the current project by default (tmp_path is the cwd, see conftest).
    (tmp_path / ".claude" / "skills" / "langfuse-agent-cli").mkdir(parents=True)
    route_doctor(fake_api)

    code, out, _ = run(capsys, "doctor")

    assert code == 0
    assert "All checks passed." in out


SECRET = "sk-lf-0123456789abcdef"


def test_status_commands_never_print_the_secret_key(fake_api, capsys, no_skill_dirs):
    route_doctor(fake_api)
    ConfigManager().save_profile("default", "http://lf.test", "pk-lf-0123456789", SECRET)

    for argv in (["doctor"], ["auth", "status"], ["auth", "list"]):
        assert main(argv) == 0, argv
        captured = capsys.readouterr()
        assert SECRET[6:-4] not in captured.out + captured.err, argv  # the part the mask never shows
