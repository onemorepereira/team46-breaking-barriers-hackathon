"""AC5: spans serialized at on_end, flushed every 50 and on force_flush, to file:// and (faked) S3."""

import json

import boto3
from moto import mock_aws
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider

from agent import runctx
from agent.archive import ArchiveProcessor, ArchiveWriter
from core.store import FileStore, S3Store


class Mutator(SpanProcessor):
    """A later processor that rewrites attributes (like a translation step would)."""

    def on_end(self, span):
        span._attributes = {"mutated": True}  # noqa: SLF001 - simulate in-place rewriting


def provider_with(store):
    writer = ArchiveWriter(store, backoff=(0, 0, 0))
    proc = ArchiveProcessor(writer)
    p = TracerProvider()
    p.add_span_processor(proc)
    p.add_span_processor(Mutator())
    return p, proc, writer


def lines(text):
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def test_serializes_before_later_processors_and_flushes_at_50(tmp_path):
    runctx.set_context({"run_id": "r1"})
    store = FileStore(f"file://{tmp_path}")
    p, proc, writer = provider_with(store)
    tracer = p.get_tracer("harness")
    for i in range(55):
        with tracer.start_as_current_span(f"s{i}", attributes={"i": i}):
            pass
    assert writer.wait(5)
    part1 = lines(store.read_text("runs/r1/spans-0001.jsonl"))
    assert len(part1) == 50 and part1[0]["attributes"] == {"i": 0} and part1[0]["scope"] == "harness"
    assert store.read_text("runs/r1/spans-0002.jsonl") is None
    assert proc.force_flush()
    assert len(lines(store.read_text("runs/r1/spans-0002.jsonl"))) == 5


def test_writes_to_s3():
    runctx.set_context({"run_id": "r2"})
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-west-2")
        s3.create_bucket(Bucket="arch", CreateBucketConfiguration={"LocationConstraint": "us-west-2"})
        store = S3Store("s3://arch", client=s3)
        p, proc, _ = provider_with(store)
        with p.get_tracer("harness").start_as_current_span("x"):
            pass
        assert proc.force_flush()
        assert lines(store.read_text("runs/r2/spans-0001.jsonl"))[0]["name"] == "x"
        assert store.list("runs/r2") == ["runs/r2/spans-0001.jsonl"]


def test_write_failures_are_counted_not_raised(tmp_path):
    class Broken:
        uri = "broken://"

        def write_text(self, key, text):
            raise OSError("disk full")

    runctx.set_context({"run_id": "r3"})
    writer = ArchiveWriter(Broken(), backoff=(0, 0, 0))
    writer.put("runs/r3/x", "y")
    assert writer.wait(5) and writer.errors == 1
