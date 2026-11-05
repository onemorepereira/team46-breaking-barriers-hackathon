"""Opening a run reads each archive object once: tool results and finished span chunks are write-once,
so they are fetched in parallel and reused across opens (S3 GETs were serial and took 6-15 s a run)."""

from collections import Counter

from analysis import trace
from analysis.trace import Run
from core.store import FileStore
from tests.test_agent_local import only_run, run_harness


class Counting(FileStore):
    def __init__(self, uri):
        super().__init__(uri)
        self.reads = Counter()

    def read_text(self, key):
        self.reads[key] += 1
        return super().read_text(key)


def test_tool_results_and_spans_are_read_once_across_opens(tmp_path, monkeypatch):
    r = run_harness(tmp_path, "run", "--prompt", "prompts/tasks/dallas-dc.md", "--model", "scripted")
    assert r.returncode == 0, r.stdout + r.stderr
    plain = only_run(tmp_path)
    store = Counting(plain.store.uri)
    monkeypatch.setattr(trace, "_ARCHIVE_CACHE", trace._LRU(10_000_000))
    first = Run.load(store, plain.run_id)
    texts = [first.tool_result_text(s) for s in first.tool_results]
    assert texts == [plain.tool_result_text(s) for s in plain.tool_results] and all(texts)
    again = Run.load(store, plain.run_id)
    assert [again.tool_result_text(s) for s in again.tool_results] == texts
    assert again.all_spans == first.all_spans
    repeated = {k: n for k, n in store.reads.items() if n > 1 and ("tool_results/" in k or "/spans-" in k)}
    assert repeated == {}, repeated


def test_cache_is_bounded():
    cache = trace._LRU(10)
    cache.put(("s", "a"), "12345")
    cache.put(("s", "b"), "12345")
    cache.put(("s", "c"), "12")  # evicts the oldest
    assert cache.get(("s", "a")) is None and cache.get(("s", "c")) == "12"
    cache.put(("s", "big"), "x" * 9)  # over a quarter of the budget: not cached
    assert cache.get(("s", "big")) is None
