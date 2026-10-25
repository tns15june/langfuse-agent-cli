import pytest
from helpers import load_fixture

from langfuse_cli.client import LangfuseClient
from langfuse_cli.config import ProfileConfig

OBS = "/api/public/v2/observations"


@pytest.fixture
def client():
    return LangfuseClient(ProfileConfig("t", "http://lf.test", "pk", "sk", "profile"))


def rows(*ids):
    """Real recorded observation rows, renamed so paging order is easy to read."""
    base = load_fixture("obs_roots")["data"][0]
    return [{**base, "id": i} for i in ids]


def test_get_prompt_encodes_folder_name(fake_api, client):
    fake_api.route("GET", "/api/public/v2/prompts/support%2Fgreeter", json=load_fixture("prompt_get_folder"))

    assert client.get_prompt("support/greeter")["name"] == "support/greeter"
    assert fake_api.calls[-1][1] == "/api/public/v2/prompts/support%2Fgreeter"


def test_list_observations_sends_bool_and_drops_none(fake_api, client):
    fake_api.route("GET", OBS, json=load_fixture("obs_roots"))

    client.list_observations(isRootObservation=True, sessionId=None, fields="core,basic")

    assert fake_api.calls[-1][2] == {"isRootObservation": "true", "fields": "core,basic"}


def test_iter_observations_follows_cursor(fake_api, client):
    fake_api.route("GET", OBS, json={"data": rows("a", "b"), "meta": {"cursor": "c2"}})
    fake_api.route("GET", OBS, json={"data": rows("c"), "meta": {}})

    assert [o["id"] for o in client.iter_observations({"traceId": "t"})] == ["a", "b", "c"]
    assert "cursor" not in fake_api.calls[0][2]
    assert fake_api.calls[1][2]["cursor"] == "c2"
    assert fake_api.calls[1][2]["traceId"] == "t"


def test_iter_observations_stops_at_max_items(fake_api, client):
    fake_api.route("GET", OBS, json={"data": rows("a", "b"), "meta": {"cursor": "c2"}})

    assert [o["id"] for o in client.iter_observations({}, max_items=2)] == ["a", "b"]
    assert len(fake_api.calls) == 1  # budget spent: the second page is never requested
    assert fake_api.calls[0][2]["limit"] == "2"


def test_iter_observations_zero_budget_makes_no_request(fake_api, client):
    assert list(client.iter_observations({}, max_items=0)) == []
    assert fake_api.calls == []


def test_iter_observations_never_exceeds_budget_when_server_returns_more(fake_api, client):
    fake_api.route("GET", OBS, json={"data": rows("a", "b", "c"), "meta": {}})

    assert [o["id"] for o in client.iter_observations({}, max_items=2)] == ["a", "b"]


def test_datasets_use_v2_paths(fake_api, client):
    fake_api.route("GET", "/api/public/v2/datasets", json={"data": [load_fixture("dataset_get")], "meta": {}})
    fake_api.route("GET", "/api/public/v2/datasets/intent-classification-evals", json=load_fixture("dataset_get"))
    fake_api.route("GET", "/api/public/dataset-items", json=load_fixture("dataset_items"))

    assert client.list_datasets()["data"][0]["name"] == "intent-classification-evals"
    assert client.get_dataset("intent-classification-evals")["name"] == "intent-classification-evals"
    assert len(client.list_dataset_items("intent-classification-evals")["data"]) == 3
    assert fake_api.calls[-1][2]["datasetName"] == "intent-classification-evals"


def test_get_dataset_encodes_folder_name(fake_api, client):
    fake_api.route("GET", "/api/public/v2/datasets/evals%2Fintent", json=load_fixture("dataset_get"))

    client.get_dataset("evals/intent")

    assert fake_api.calls[-1][1] == "/api/public/v2/datasets/evals%2Fintent"
