"""Offline tests for the generic profile hooks the Long document mode relies on: per-document
sidecar data, a query filter with an unfiltered fallback, a canned pre-check reply, and a
profile-built context. Uses a throwaway store, fake embeddings and a fake chat model."""

from types import SimpleNamespace

import pytest

from app.chat_session import ChatSession
from app.profiles import Chunk, StandardProfile
from app.rag_engine import RagEngine
from app.vector_store import LocalVectorStore

A = [1.0, 0.0, 0.0]
B = [0.0, 1.0, 0.0]


# ---- sidecars live and die with their document ------------------------------------------------


def test_sidecars_are_stored_per_document_and_deleted_with_it(tmp_path):
    store = LocalVectorStore(tmp_path)
    doc = store.add_document("a.txt", ["alpha"], [A], "h1", sidecars={"parents": {"0": {"text": "full"}}, "vocab": [1, 2]})
    other = store.add_document("b.txt", ["beta"], [B], "h2", sidecars={"vocab": [3]})

    assert store.get_sidecar(doc["id"], "parents") == {"0": {"text": "full"}}
    assert store.get_sidecar(doc["id"], "missing") is None
    assert store.all_sidecars("vocab") == {doc["id"]: [1, 2], other["id"]: [3]}

    store.delete_document(doc["id"])

    assert store.get_sidecar(doc["id"], "parents") is None
    assert store.all_sidecars("vocab") == {other["id"]: [3]}
    assert not (tmp_path / "sidecars" / doc["id"]).exists()


def test_a_sidecar_that_cannot_be_saved_rolls_the_document_back(tmp_path):
    store = LocalVectorStore(tmp_path)

    with pytest.raises(RuntimeError, match="Failed to save document data"):
        store.add_document("a.txt", ["alpha"], [A], "h1", sidecars={"bad": {1, 2}})  # a set is not JSON

    assert store.count_chunks() == 0 and store.list_documents() == []


# ---- a profile with all the hooks switched on --------------------------------------------------


class HookedProfile(StandardProfile):
    id = "hooked"
    label = "Hooked"
    min_score = 0.25

    def __init__(self):
        super().__init__()
        self.filter = None
        self.canned = None
        self.seen_store = None

    def chunk(self, extracted):
        return [
            Chunk(text=t, metadata={"region": r, "page": n})
            for n, (r, t) in enumerate(extracted, 1)
        ]

    def sidecars(self, extracted):
        return {"info": {"count": len(extracted)}}

    def query_filter(self, question, store):
        self.seen_store = store
        return self.filter, (["filtered"] if self.filter else [])

    def precheck(self, question, store):
        return self.canned

    def build_context(self, hits, store):
        text = " || ".join(f"{h['metadata']['region']}:{h['text']}" for h in hits)
        return text, [{"text": "custom source", "score": 1.0, "source": "x", "page": 99}]


@pytest.fixture
def engine(tmp_path, fake_embedder):
    profile = HookedProfile()
    eng = RagEngine(profile, LocalVectorStore(tmp_path / "data"), fake_embedder)
    eng._index(
        [("asia", "growth outlook for asia is six percent"), ("africa", "growth outlook for africa is four percent")],
        "doc.pdf",
        "h",
    )
    return eng


def test_sidecars_are_written_at_index_time(engine):
    (doc,) = engine.list_documents()

    assert engine.store.get_sidecar(doc["id"], "info") == {"count": 2}


def test_a_profile_filter_narrows_the_search(engine):
    engine.profile.filter = {"region": "africa"}

    hits = engine.retrieve("growth outlook")

    assert [h["metadata"]["region"] for h in hits] == ["africa"]
    assert engine.last_filter_notes == ["filtered"]
    assert engine.profile.seen_store is engine.store


def test_a_filter_that_leaves_nothing_relevant_is_retried_unfiltered(engine):
    engine.profile.filter = {"region": "antarctica"}  # matches nothing

    hits = engine.retrieve("growth outlook for asia")

    assert hits and hits[0]["metadata"]["region"] == "asia"
    assert engine.last_filter_notes == ["filtered", "filter matched nothing relevant: retried unfiltered"]


def test_an_explicit_where_overrides_the_profile_filter(engine):
    engine.profile.filter = {"region": "africa"}

    hits = engine.retrieve("growth outlook", where={"region": "asia"})

    assert [h["metadata"]["region"] for h in hits] == ["asia"]


class RecordingLLM:
    def __init__(self):
        self.messages = []

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content="the answer")


def test_a_precheck_reply_skips_the_model_entirely(engine):
    engine.profile.canned = "The document has 4 chapters; there is no Chapter 7."
    chat = ChatSession(engine)
    chat._llm = RecordingLLM()

    result = chat.ask("What does Chapter 7 say?")

    assert result == {"reply": "The document has 4 chapters; there is no Chapter 7.", "sources": []}
    assert chat._llm.messages == []


def test_the_profile_builds_the_context_and_the_sources(engine):
    chat = ChatSession(engine)
    chat._llm = RecordingLLM()

    result = chat.ask("growth outlook for asia")

    system = chat._llm.messages[0].content
    assert "asia:growth outlook for asia is six percent" in system and " || " in system  # profile-built
    assert result["sources"] == [{"text": "custom source", "score": 1.0, "source": "x", "page": 99}]
    assert result["contextTokens"] > 0


def test_modes_without_these_hooks_behave_exactly_as_before(tmp_path, fake_embedder):
    profile = StandardProfile()
    profile.min_score = 0.25
    eng = RagEngine(profile, LocalVectorStore(tmp_path / "d"), fake_embedder)
    eng.load_document("Acme leave policy gives 18 days of paid vacation per year.", "p.txt")
    chat = ChatSession(eng)
    chat._llm = RecordingLLM()

    result = chat.ask("how many days of paid vacation")

    assert set(result["sources"][0]) == {"text", "score", "source"}
    assert eng.last_filter_notes == []
    assert eng.store.all_sidecars("anything") == {}
