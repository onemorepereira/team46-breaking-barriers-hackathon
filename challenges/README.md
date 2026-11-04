# Team46 tiered technical challenges

Isolated branch: `challenges/tiered-aws`. Workshop copy: `/workshop/team46-challenges`. This does not replace Miguel's main app or the running evaluation prototype. All AWS operations are guarded to event account **952337755619**, WSParticipantRole, Oregon. No personal AWS account is used.

## Show the judge now

Open **https://d37rt8nwcs1lq3.cloudfront.net/proxy/8790/** in your signed-in workshop browser. Click **Run live proof for judge**. It makes fresh requests to the actual managed Runtime, rather than replaying a fixture.

| Challenge | What to show |
| --- | --- |
| Know Your Stuff | Ingestion COMPLETE, 3 documents indexed, 0 failed; live answer containing exact source-document S3 citations. Show the source excerpts below it. |
| Gateway Builder | Three deployed MCP tools: `clay___retrieve_clay_guidance`, `clay___rubric_reference`, `clay___distance_km`; successful tool call from the Runtime-hosted agent to `clay___retrieve_clay_guidance`. |
| Lock the Front Door | JWT authorizer on the Runtime using Cognito OAuth through AgentCore's inbound authentication; HTTP 401 without a token, HTTP 200 with a valid client-credentials bearer token. The token and client secret are never displayed. |

Ask the judge/organizer to record all three completions. Live verification is not a claim that points have been awarded or that a placing remains available. Deployment and observability were already completed by the team and are not re-claimed here.

## Verified live on November 4, 2026

The proof returned at **17:36:48 UTC (12:36:48 p.m. Eastern)** with all three checks true. Runtime: `team46_tiered-7RshNTD96q`; Knowledge Base: `BDEUWS8NP0`. The Gateway returned all three tools and the agent called the retrieval tool. Bedrock Kimi K2.5 generated an answer citing `s3://team46-tiered-docs-952337755619/knowledge/clay-rubric.md`. The three ingested documents are the Clay technical brief, the team's rubric customization guide, and the rubric source.

This is a small retrieval agent used for the challenge extension. Its workflow is retrieve via MCP Gateway, then generate a source-cited Bedrock answer. The fixed retrieval step is explicit; this does not claim that the model autonomously selected its tool.

AWS documentation: [Lambda Gateway targets](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-lambda.html), [AgentCore OAuth inbound authentication](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html), [Bedrock with S3 Vectors](https://aws.amazon.com/blogs/machine-learning/building-cost-effective-rag-applications-with-amazon-bedrock-knowledge-bases-and-amazon-s3-vectors/).

## Run again from the workshop terminal

```sh
cd /workshop/team46-challenges
/workshop/team46-adi-sandbox/.venv/bin/python -m challenges.proof
```

Start the private judge UI if needed:

```sh
/workshop/team46-adi-sandbox/.venv/bin/python -m challenges.judge_ui
```

Resource identifiers and sanitized proof are in ignored `out/challenges/resources.json` and `proof.json`. `oauth-client.private.json` contains the secret, mode 0600: do not print, commit or show it. No secrets are included in the Runtime package. The public browser endpoint still requires the existing workshop login; the managed Runtime independently requires a valid OAuth token.

## Provisioning and teardown

`python -m challenges.deploy kb`, then `auth`, `gateway`, `runtime` creates dedicated `team46-tiered*` resources. IAM execution policies are restricted to the specific Knowledge Base, source bucket prefix, Gateway/Lambda and model. The participant role is not edited. The dependency ZIP is reused from the previously verified, same-account Python/ARM64 deployment and extended with `challenge_main.py`.

After judging, remove only the resources listed in this copy's `resources.json`: the new Runtime, Gateway target/Gateway, Lambda, Knowledge Base/data source, S3 Vector index/bucket, Cognito domain/user pool and the four dedicated IAM roles. Preserve reports until judging is finished. The source bucket contains only challenge documents and its package. These are real AWS resources with usage charges in the event sandbox; this code does not create a billing hard cap.
