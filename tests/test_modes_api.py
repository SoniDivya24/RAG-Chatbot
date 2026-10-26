"""Offline tests for the mode-aware HTTP API: every route takes a `mode`
(default Standard), each mode has its own library, unknown/unavailable modes
fail clearly, and chunk metadata reaches the sources. Uses a throwaway data
folder, fake embeddings and a fake chat model - no network."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.modes import Modes
from app.profiles import Chunk, StandardProfile, UnavailableProfile, default_profiles

POLICY = (
    b"Acme Robotics leave policy. Full-time employees accrue 18 days of paid vacation "
    b"per year plus 10 paid sick days. Vacation requests need 5 business days notice."
)


class PagedTestProfile(StandardProfile):
    """A stand-in scenario mode: .txt only, chunks carry page/section/kind."""

    id = "paged"
    label = "Paged"
    description = "test mode"
    extensions = (".txt",)
    min_score = 0.25
    sample_file = "handbook.txt"
    sample_label = "Test handbook"

    def chunk(self, extracted):
        pages = [p.strip() for p in extracted.split("\f") if p.strip()]
        return [
            Chunk(
                text=text,
                metadata={"page": n, "section": f"Part {n}", "kind": "text", "ignored": None},
                embed_text=f"Part {n}\n\n{text}",
            )
            for n, text in enumerate(pages, 1)
        ]


class FakeLLM:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content="a fake reply")


@pytest.fixture
def api(tmp_path, fake_embedder, monkeypatch):
    import app.main as main

    profiles = default_profiles()
    profiles["standard"].min_score = 0.25  # floor suited to the fake embeddings
    profiles["paged"] = PagedTestProfile()
    profiles["planned"] = UnavailableProfile("planned", "Planned", "Not built yet.")
    test_modes = Modes(tmp_path / "data", fake_embedder, profiles)
    monkeypatch.setattr(main, "modes", test_modes)
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "handbook.txt").write_text("Intro page about the company mission.\fLeave policy: 18 days of paid vacation per year.")
    monkeypatch.setattr(main.config, "SAMPLES_DIR", samples)
    main.limiter.reset()  # the rate limiter is process-wide state; start each test fresh
    llm = FakeLLM()
    for mode in ("standard", "paged"):
        test_modes.chat(mode)._llm = llm
    client = TestClient(main.app)
    return SimpleNamespace(client=client, modes=test_modes, llm=llm, dir=tmp_path / "data")


def upload(client, name, content, mode=None):
    url = "/api/upload" + (f"?mode={mode}" if mode else "")
    return client.post(url, files={"documents": (name, content, "text/plain")})


def test_modes_endpoint_lists_all_four_with_availability(api):
    modes = api.client.get("/api/modes").json()["modes"]

    by_id = {m["id"]: m for m in modes}
    assert list(by_id) == ["standard", "report", "long", "visual", "paged", "planned"]
    assert by_id["standard"]["available"] is True and by_id["standard"]["documentCount"] == 0
    assert by_id["report"]["available"] is True and by_id["report"]["extensions"] == [".pdf"]
    assert by_id["visual"]["available"] is True and by_id["visual"]["extensions"] == [".pdf"]
    assert by_id["long"]["available"] is True and by_id["long"]["extensions"] == [".pdf"]
    assert by_id["planned"]["available"] is False and "documentCount" not in by_id["planned"]
    assert by_id["standard"]["extensions"] == [".txt", ".md", ".pdf"]


def test_default_mode_is_standard(api):
    upload(api.client, "policy.txt", POLICY)  # no mode given

    assert api.client.get("/api/documents?mode=standard").json()["documents"][0]["source_name"] == "policy.txt"
    assert api.client.get("/api/status").json()["mode"] == "standard"


def test_unknown_mode_is_a_400_on_every_route(api):
    assert api.client.get("/api/status?mode=nope").status_code == 400
    assert api.client.get("/api/documents?mode=nope").json() == {"error": 'Unknown mode "nope".'}
    assert upload(api.client, "a.txt", b"hello", "nope").status_code == 400
    assert api.client.post("/api/chat", json={"message": "hi", "mode": "nope"}).status_code == 400
    assert api.client.delete("/api/documents/x?mode=nope").status_code == 400


def test_unavailable_mode_is_a_501_and_never_calls_the_model(api):
    res = api.client.post("/api/chat", json={"message": "hi", "mode": "planned"})

    assert res.status_code == 501
    assert res.json() == {"error": "The Planned mode isn't available yet."}
    assert api.llm.messages == []
    assert upload(api.client, "a.txt", b"hello", "planned").status_code == 501
    assert api.client.get("/api/status?mode=planned").status_code == 501


def test_each_mode_has_its_own_library(api):
    upload(api.client, "policy.txt", POLICY, "standard")
    upload(api.client, "other.txt", b"Totally different content about canteen menus and soup.", "paged")

    std = api.client.get("/api/documents?mode=standard").json()["documents"]
    paged = api.client.get("/api/documents?mode=paged").json()["documents"]

    assert [d["source_name"] for d in std] == ["policy.txt"]
    assert [d["source_name"] for d in paged] == ["other.txt"]
    assert (api.dir / "modes" / "standard" / "documents.json").exists()
    assert (api.dir / "modes" / "paged" / "documents.json").exists()

    api.client.delete(f"/api/documents/{std[0]['id']}?mode=standard")
    assert api.client.get("/api/documents?mode=standard").json()["documents"] == []
    assert len(api.client.get("/api/documents?mode=paged").json()["documents"]) == 1


def test_same_file_in_two_modes_is_indexed_twice_not_deduplicated(api):
    a = upload(api.client, "policy.txt", POLICY, "standard").json()["documents"][0]
    b = upload(api.client, "policy.txt", POLICY, "paged").json()["documents"][0]

    assert a["duplicate"] is False and b["duplicate"] is False
    assert a["id"] != b["id"]


def test_upload_extension_rules_come_from_the_mode(api):
    std = upload(api.client, "notes.csv", b"a,b", "standard")
    paged = upload(api.client, "scan.pdf", b"%PDF", "paged")

    assert std.status_code == 400
    assert std.json()["errors"][0]["error"] == "Only .txt, .md, or .pdf files are supported"
    assert paged.status_code == 400
    assert paged.json()["errors"][0]["error"] == "Only .txt files are supported"


def test_standard_sources_keep_the_original_shape(api):
    upload(api.client, "policy.txt", POLICY, "standard")

    body = api.client.post(
        "/api/chat", json={"message": "how many vacation days do employees get", "mode": "standard"}
    ).json()

    assert body["reply"] == "a fake reply"
    assert body["sources"] and set(body["sources"][0]) == {"text", "score", "source"}
    system = api.llm.messages[0].content
    assert system.startswith("You are a helpful assistant answering questions about the uploaded")
    assert "CONTEXT:\nAcme Robotics" in system


def test_chunk_metadata_reaches_the_sources(api):
    pages = b"Intro page about the company mission.\fLeave policy: 18 days of paid vacation per year."
    upload(api.client, "handbook.txt", pages, "paged")

    body = api.client.post(
        "/api/chat", json={"message": "paid vacation days per year", "mode": "paged"}
    ).json()

    top = body["sources"][0]
    assert top["page"] == 2 and top["section"] == "Part 2" and top["kind"] == "text"
    assert top["source"] == "handbook.txt"
    assert "ignored" not in top


def test_status_counts_are_per_mode(api):
    upload(api.client, "policy.txt", POLICY, "standard")

    assert api.client.get("/api/status?mode=standard").json()["documentCount"] == 1
    assert api.client.get("/api/status?mode=paged").json()["documentCount"] == 0


def test_modes_endpoint_carries_ui_presentation_data(api):
    by_id = {m["id"]: m for m in api.client.get("/api/modes").json()["modes"]}

    assert by_id["standard"]["uploadHint"] and len(by_id["standard"]["exampleQuestions"]) == 3
    # The scenario modes ship the reference documents' sample questions.
    assert "South Asia" in by_id["long"]["exampleQuestions"][0]
    assert "ENERGY STAR" in by_id["visual"]["exampleQuestions"][0]
    assert "depository libraries" in by_id["report"]["exampleQuestions"][0]
    assert all(m["uploadHint"] for m in by_id.values() if m["id"] not in ("paged", "planned"))  # the real modes


# ---- built-in sample documents ---------------------------------------------------------------


def test_modes_say_which_have_a_sample_and_whether_its_file_is_there(api):
    by_id = {m["id"]: m for m in api.client.get("/api/modes").json()["modes"]}

    assert by_id["paged"]["sample"] == {"label": "Test handbook", "present": True}
    assert by_id["report"]["sample"] == {"label": "GPO 2018 Annual Report", "present": False}  # not in the temp folder
    assert "sample" not in by_id["standard"]


def test_loading_a_sample_indexes_it_into_that_mode_only(api):
    res = api.client.post("/api/sample?mode=paged")

    assert res.status_code == 200
    (doc,) = res.json()["documents"]
    assert doc["sourceName"] == "handbook.txt" and doc["chunkCount"] == 2 and doc["duplicate"] is False
    assert [d["source_name"] for d in api.client.get("/api/documents?mode=paged").json()["documents"]] == ["handbook.txt"]
    assert api.client.get("/api/documents?mode=standard").json()["documents"] == []


def test_loading_the_sample_twice_is_detected_as_a_duplicate(api):
    api.client.post("/api/sample?mode=paged")

    again = api.client.post("/api/sample?mode=paged").json()["documents"][0]

    assert again["duplicate"] is True
    assert len(api.client.get("/api/documents?mode=paged").json()["documents"]) == 1


def test_a_missing_sample_file_says_where_to_put_it(api):
    res = api.client.post("/api/sample?mode=report")  # the profile names a file that isn't in the temp samples folder

    assert res.status_code == 404
    assert "GPO-Anual-report.pdf" in res.json()["error"] and "samples/" in res.json()["error"]


def test_a_mode_without_a_sample_says_so(api):
    res = api.client.post("/api/sample?mode=standard")

    assert res.status_code == 404 and "no sample" in res.json()["error"]


def test_the_caller_cannot_choose_which_file_is_loaded(api, tmp_path):
    (tmp_path / "secret.txt").write_text("Do not index me.")

    res = api.client.post("/api/sample?mode=paged&name=../secret.txt&file=/etc/passwd")

    assert [d["sourceName"] for d in res.json()["documents"]] == ["handbook.txt"]  # the profile's file, always


def test_sample_loading_validates_the_mode_like_every_other_route(api):
    assert api.client.post("/api/sample?mode=nope").status_code == 400
    assert api.client.post("/api/sample?mode=planned").status_code == 501
