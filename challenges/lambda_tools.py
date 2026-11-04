"""Three real Gateway tools; invoked only through the scoped Gateway role."""

import math
import os

import boto3


def handler(event, context):
    custom = getattr(getattr(context, "client_context", None), "custom", None) or {}
    name = custom.get("bedrockAgentCoreToolName", "").split("___")[-1]
    if name == "retrieve_clay_guidance":
        r = boto3.client("bedrock-agent-runtime", region_name="us-west-2").retrieve(
            knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
            retrievalQuery={"text": event["query"]},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 4}},
        )
        return {
            "knowledge_base_id": os.environ["KNOWLEDGE_BASE_ID"],
            "sources": [
                {
                    "text": x["content"].get("text", ""),
                    "uri": x.get("location", {}).get("s3Location", {}).get("uri"),
                    "score": x.get("score"),
                }
                for x in r["retrievalResults"]
            ],
        }
    if name == "rubric_reference":
        data = (
            boto3.client("s3")
            .get_object(Bucket=os.environ["DOC_BUCKET"], Key="knowledge/clay-rubric.yaml.txt")["Body"]
            .read()
            .decode()
        )
        return {"source": f"s3://{os.environ['DOC_BUCKET']}/knowledge/clay-rubric.yaml.txt", "rubric": data}
    if name == "distance_km":
        a, b, c, d = [float(event[k]) for k in ["lat1", "lon1", "lat2", "lon2"]]
        if not (-90 <= a <= 90 and -90 <= c <= 90 and -180 <= b <= 180 and -180 <= d <= 180):
            raise ValueError("Invalid coordinates")
        x, y = math.radians(c - a), math.radians(d - b)
        h = (
            math.sin(x / 2) ** 2
            + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(y / 2) ** 2
        )
        return {
            "distance_km": 6371.0088 * 2 * math.asin(min(1, math.sqrt(h))),
            "method": "Haversine between points; not protected-area boundary distance",
        }
    raise ValueError("Unknown Gateway tool: " + name)
