"""Exercise Gateway tool contracts without AWS calls."""

import io
from types import SimpleNamespace

import pytest

from challenges import lambda_tools


def context(name):
    return SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "clay___" + name})
    )


def test_distance_tool_is_a_point_distance_and_rejects_bad_coordinates():
    result = lambda_tools.handler({"lat1": 0, "lon1": 0, "lat2": 0, "lon2": 1}, context("distance_km"))
    assert result["distance_km"] == pytest.approx(111.195, abs=0.01)
    assert "not protected-area boundary" in result["method"]
    with pytest.raises(ValueError):
        lambda_tools.handler({"lat1": 91, "lon1": 0, "lat2": 0, "lon2": 1}, context("distance_km"))


def test_kb_tool_keeps_retrieved_document_citations(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb")

    class KB:
        def retrieve(self, **args):
            assert args["knowledgeBaseId"] == "test-kb"
            assert args["retrievalQuery"] == {"text": "How can Clay change the rubric?"}
            return {
                "retrievalResults": [
                    {
                        "content": {"text": "Edit the YAML."},
                        "location": {"s3Location": {"uri": "s3://test/guide.md"}},
                        "score": 0.8,
                    }
                ]
            }

    monkeypatch.setattr(lambda_tools.boto3, "client", lambda *args, **kwargs: KB())
    result = lambda_tools.handler(
        {"query": "How can Clay change the rubric?"}, context("retrieve_clay_guidance")
    )
    assert result["sources"][0]["uri"] == "s3://test/guide.md"
    assert result["sources"][0]["text"] == "Edit the YAML."


def test_rubric_tool_reads_actual_s3_source(monkeypatch):
    monkeypatch.setenv("DOC_BUCKET", "test-docs")

    class S3:
        def get_object(self, **args):
            assert args == {"Bucket": "test-docs", "Key": "knowledge/clay-rubric.yaml.txt"}
            return {"Body": io.BytesIO(b"id: clay\nversion: 1\n")}

    monkeypatch.setattr(lambda_tools.boto3, "client", lambda *args, **kwargs: S3())
    result = lambda_tools.handler({}, context("rubric_reference"))
    assert result["source"] == "s3://test-docs/knowledge/clay-rubric.yaml.txt"
    assert result["rubric"].startswith("id: clay")
