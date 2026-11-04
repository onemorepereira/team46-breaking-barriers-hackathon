"""Deploy isolated tiered challenge resources in the explicitly authorized event account."""

from __future__ import annotations

import argparse
import io
import json
import os
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ACCOUNT = "952337755619"
REGION = "us-west-2"
PREFIX = "team46-tiered"
ROOT = Path("out/challenges")
ROOT.mkdir(parents=True, exist_ok=True)
STATE = ROOT / "resources.json"
session = boto3.Session(region_name=REGION)
identity = session.client("sts").get_caller_identity()
if (
    os.environ.get("AWS_PROFILE")
    or identity["Account"] != ACCOUNT
    or ":assumed-role/WSParticipantRole/" not in identity["Arn"]
):
    raise SystemExit("Refusing access outside the authorized event workshop role.")
state = json.loads(STATE.read_text()) if STATE.exists() else {"account": ACCOUNT, "region": REGION}


def save():
    STATE.write_text(json.dumps(state, indent=2, default=str))
    STATE.chmod(0o600)


def note(text):
    print(text, flush=True)


def role(name, service, statements):
    iam = session.client("iam")
    arn = f"arn:aws:iam::{ACCOUNT}:role/{name}"
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": service},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"aws:SourceAccount": ACCOUNT}},
            }
        ],
    }
    if service == "lambda.amazonaws.com":
        trust["Statement"][0].pop("Condition")
    try:
        iam.get_role(RoleName=name)
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(
            RoleName=name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Team46 event technical challenge role",
        )
    iam.put_role_policy(
        RoleName=name,
        PolicyName="event-scoped",
        PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": statements}),
    )
    return arn


def allow(actions, resources):
    return {"Effect": "Allow", "Action": actions, "Resource": resources}


def retry(fn, seconds=60):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return fn()
        except ClientError as e:
            msg = str(e).lower()
            if time.monotonic() > deadline or not any(
                w in msg
                for w in ["assume", "propagat", "not found", "not exist", "validation", "being created"]
            ):
                raise
            note("Waiting for service/role propagation: " + e.response["Error"]["Code"])
            time.sleep(5)


def kb():
    s3 = session.client("s3")
    sv = session.client("s3vectors")
    br = session.client("bedrock-agent")
    bucket = f"{PREFIX}-docs-{ACCOUNT}"
    state["bucket"] = bucket
    save()
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            k: True
            for k in ["BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"]
        },
    )
    s3.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    docs = {
        "clay-rubric.md": Path("docs/clay-rubric.md").read_bytes(),
        "clay-technical-brief.md": Path("docs/Clay-Foundry-Technical-Hackathon.md").read_bytes(),
        "clay-rubric.yaml.txt": Path("rubrics/geo-dataset-v1.yaml").read_bytes(),
    }
    for name, data in docs.items():
        s3.put_object(Bucket=bucket, Key="knowledge/" + name, Body=data, ContentType="text/plain")
    note("Uploaded three team/Clay source documents to private S3.")
    vb = f"{PREFIX}-vectors-{ACCOUNT}"
    try:
        r = sv.get_vector_bucket(vectorBucketName=vb)
    except ClientError:
        sv.create_vector_bucket(vectorBucketName=vb, encryptionConfiguration={"sseType": "AES256"})
        r = sv.get_vector_bucket(vectorBucketName=vb)
    vba = r["vectorBucket"]["vectorBucketArn"]
    state["vector_bucket"] = vb
    try:
        idx = sv.get_index(vectorBucketName=vb, indexName="clay-guidance")["index"]["indexArn"]
    except ClientError:
        sv.create_index(
            vectorBucketName=vb,
            indexName="clay-guidance",
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
            metadataConfiguration={
                "nonFilterableMetadataKeys": ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
            },
        )
        idx = sv.get_index(vectorBucketName=vb, indexName="clay-guidance")["index"]["indexArn"]
    state["index_arn"] = idx
    save()
    rr = role(
        f"{PREFIX}-kb-role",
        "bedrock.amazonaws.com",
        [
            allow(["s3:GetObject"], f"arn:aws:s3:::{bucket}/knowledge/*"),
            allow(["s3:ListBucket"], f"arn:aws:s3:::{bucket}"),
            allow(
                ["bedrock:InvokeModel"],
                f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0",
            ),
            allow(
                [
                    "s3vectors:GetIndex",
                    "s3vectors:PutVectors",
                    "s3vectors:GetVectors",
                    "s3vectors:DeleteVectors",
                    "s3vectors:QueryVectors",
                    "s3vectors:ListVectors",
                ],
                idx,
            ),
        ],
    )
    if not state.get("kb_id"):
        found = next(
            (
                x
                for x in br.list_knowledge_bases()["knowledgeBaseSummaries"]
                if x["name"] == PREFIX + "-clay-kb"
            ),
            None,
        )
        if found:
            state["kb_id"] = found["knowledgeBaseId"]
        else:
            result = retry(
                lambda: br.create_knowledge_base(
                    name=PREFIX + "-clay-kb",
                    roleArn=rr,
                    knowledgeBaseConfiguration={
                        "type": "VECTOR",
                        "vectorKnowledgeBaseConfiguration": {
                            "embeddingModelArn": (
                                f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0"
                            ),
                            "embeddingModelConfiguration": {
                                "bedrockEmbeddingModelConfiguration": {
                                    "dimensions": 1024,
                                    "embeddingDataType": "FLOAT32",
                                }
                            },
                        },
                    },
                    storageConfiguration={
                        "type": "S3_VECTORS",
                        "s3VectorsConfiguration": {"vectorBucketArn": vba, "indexArn": idx},
                    },
                ),
                90,
            )
            state["kb_id"] = result["knowledgeBase"]["knowledgeBaseId"]
        save()
    note("Knowledge Base " + state["kb_id"])
    deadline = time.monotonic() + 120
    while br.get_knowledge_base(knowledgeBaseId=state["kb_id"])["knowledgeBase"]["status"] == "CREATING":
        if time.monotonic() > deadline:
            raise RuntimeError("Knowledge Base is still creating; rerun kb stage")
        time.sleep(4)
    if not state.get("data_source"):
        sources = br.list_data_sources(knowledgeBaseId=state["kb_id"])["dataSourceSummaries"]
        ds = next((x for x in sources if x["name"] == "clay-team-documents"), None)
        if ds:
            state["data_source"] = ds["dataSourceId"]
        else:
            state["data_source"] = br.create_data_source(
                knowledgeBaseId=state["kb_id"],
                name="clay-team-documents",
                dataSourceConfiguration={
                    "type": "S3",
                    "s3Configuration": {
                        "bucketArn": f"arn:aws:s3:::{bucket}",
                        "inclusionPrefixes": ["knowledge/"],
                    },
                },
                vectorIngestionConfiguration={
                    "chunkingConfiguration": {
                        "chunkingStrategy": "FIXED_SIZE",
                        "fixedSizeChunkingConfiguration": {"maxTokens": 400, "overlapPercentage": 10},
                    }
                },
            )["dataSource"]["dataSourceId"]
        save()
    if not state.get("ingestion_job"):
        state["ingestion_job"] = br.start_ingestion_job(
            knowledgeBaseId=state["kb_id"], dataSourceId=state["data_source"]
        )["ingestionJob"]["ingestionJobId"]
        save()
    note("Ingestion started: " + state["ingestion_job"])


def gateway():
    br = session.client("bedrock-agentcore-control")
    lm = session.client("lambda")
    fn = PREFIX + "-tools"
    fnarn = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{fn}"
    logs = f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/{fn}:*"
    lr = role(
        PREFIX + "-lambda-role",
        "lambda.amazonaws.com",
        [
            allow(
                ["bedrock:Retrieve"], f"arn:aws:bedrock:{REGION}:{ACCOUNT}:knowledge-base/{state['kb_id']}"
            ),
            allow(["s3:GetObject"], f"arn:aws:s3:::{state['bucket']}/knowledge/*"),
            allow(["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], logs),
        ],
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write("challenges/lambda_tools.py", "lambda_function.py")
    try:
        lm.get_function(FunctionName=fn)
    except lm.exceptions.ResourceNotFoundException:
        retry(
            lambda: lm.create_function(
                FunctionName=fn,
                Runtime="python3.12",
                Role=lr,
                Handler="lambda_function.handler",
                Code={"ZipFile": buf.getvalue()},
                Timeout=60,
                MemorySize=256,
                Environment={
                    "Variables": {"KNOWLEDGE_BASE_ID": state["kb_id"], "DOC_BUCKET": state["bucket"]}
                },
            ),
            90,
        )
    else:
        lm.update_function_code(FunctionName=fn, ZipFile=buf.getvalue())
    state["lambda_arn"] = fnarn
    save()
    gr = role(
        PREFIX + "-gateway-role", "bedrock-agentcore.amazonaws.com", [allow(["lambda:InvokeFunction"], fnarn)]
    )
    if not state.get("gateway_id"):
        result = retry(
            lambda: br.create_gateway(
                name=PREFIX + "-gateway", roleArn=gr, protocolType="MCP", authorizerType="AWS_IAM"
            ),
            90,
        )
        state["gateway_id"] = result["gatewayId"]
        state["gateway_url"] = result["gatewayUrl"]
        state["gateway_arn"] = result["gatewayArn"]
        save()
    tools = [
        {
            "name": "retrieve_clay_guidance",
            "description": "Retrieve Clay/team Knowledge Base documents with citations.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "rubric_reference",
            "description": "Read the team rubric source document from private S3.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "distance_km",
            "description": "Calculate great-circle distance between two coordinates for evidence checks.",
            "inputSchema": {
                "type": "object",
                "properties": {k: {"type": "number"} for k in ["lat1", "lon1", "lat2", "lon2"]},
                "required": ["lat1", "lon1", "lat2", "lon2"],
            },
        },
    ]
    deadline = time.monotonic() + 120
    while br.get_gateway(gatewayIdentifier=state["gateway_id"])["status"] == "CREATING":
        if time.monotonic() > deadline:
            raise RuntimeError("Gateway still creating; rerun gateway stage")
        time.sleep(4)
    if not state.get("target_id"):
        result = br.create_gateway_target(
            gatewayIdentifier=state["gateway_id"],
            name="clay",
            targetConfiguration={
                "mcp": {"lambda": {"lambdaArn": fnarn, "toolSchema": {"inlinePayload": tools}}}
            },
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
        state["target_id"] = result["targetId"]
        save()
    note("Gateway deployed with three MCP tools: " + state["gateway_id"])


def auth():
    c = session.client("cognito-idp")
    if not state.get("user_pool"):
        state["user_pool"] = c.create_user_pool(
            PoolName=PREFIX + "-oauth",
            MfaConfiguration="OFF",
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
        )["UserPool"]["Id"]
        save()
    pool = state["user_pool"]
    domain = f"team46-{ACCOUNT}-tiered"
    if not state.get("oauth_domain"):
        c.create_user_pool_domain(Domain=domain, UserPoolId=pool)
        state["oauth_domain"] = f"https://{domain}.auth.{REGION}.amazoncognito.com"
        save()
    try:
        c.describe_resource_server(UserPoolId=pool, Identifier="team46")
    except c.exceptions.ResourceNotFoundException:
        c.create_resource_server(
            UserPoolId=pool,
            Identifier="team46",
            Name="Team46 agent invocation",
            Scopes=[{"ScopeName": "invoke", "ScopeDescription": "Invoke the event challenge agent"}],
        )
    if not state.get("client_id"):
        cl = c.create_user_pool_client(
            UserPoolId=pool,
            ClientName=PREFIX + "-judge-demo",
            GenerateSecret=True,
            AllowedOAuthFlowsUserPoolClient=True,
            AllowedOAuthFlows=["client_credentials"],
            AllowedOAuthScopes=["team46/invoke"],
            AccessTokenValidity=1,
            TokenValidityUnits={"AccessToken": "hours"},
        )["UserPoolClient"]
        state["client_id"] = cl["ClientId"]
        save()
        p = ROOT / "oauth-client.private.json"
        p.write_text(json.dumps({"client_id": cl["ClientId"], "client_secret": cl["ClientSecret"]}))
        p.chmod(0o600)
    state["discovery_url"] = (
        f"https://cognito-idp.{REGION}.amazonaws.com/{pool}/.well-known/openid-configuration"
    )
    save()
    note("Cognito OAuth client-credentials issuer ready; secret stays private in out/.")


def runtime():
    c = session.client("bedrock-agentcore-control")
    s3 = session.client("s3")
    original = c.get_agent_runtime(agentRuntimeId="clay_agent_eval-hQEaIrFtgq")
    old = original["agentRuntimeArtifact"]["codeConfiguration"]["code"]["s3"]
    package = io.BytesIO(s3.get_object(Bucket=old["bucket"], Key=old["prefix"])["Body"].read())
    with zipfile.ZipFile(package, "a", zipfile.ZIP_DEFLATED) as z:
        z.write("challenges/runtime_app.py", "challenge_main.py")
    key = "package/team46-tiered.zip"
    s3.put_object(Bucket=state["bucket"], Key=key, Body=package.getvalue())
    rr = role(
        PREFIX + "-runtime-role",
        "bedrock-agentcore.amazonaws.com",
        [
            allow(["s3:GetObject"], f"arn:aws:s3:::{state['bucket']}/package/*"),
            allow(["s3:ListBucket"], f"arn:aws:s3:::{state['bucket']}"),
            allow(
                ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                f"arn:aws:bedrock:{REGION}::foundation-model/moonshotai.kimi-k2.5",
            ),
            allow(["bedrock-agentcore:InvokeGateway"], state["gateway_arn"]),
            allow(
                ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/bedrock-agentcore/runtimes/team46_tiered*",
            ),
        ],
    )
    if not state.get("runtime_id"):
        r = retry(
            lambda: c.create_agent_runtime(
                agentRuntimeName="team46_tiered",
                agentRuntimeArtifact={
                    "codeConfiguration": {
                        "code": {"s3": {"bucket": state["bucket"], "prefix": key}},
                        "runtime": "PYTHON_3_12",
                        "entryPoint": ["challenge_main.py"],
                    }
                },
                roleArn=rr,
                networkConfiguration={"networkMode": "PUBLIC"},
                authorizerConfiguration={
                    "customJWTAuthorizer": {
                        "discoveryUrl": state["discovery_url"],
                        "allowedClients": [state["client_id"]],
                        "allowedScopes": ["team46/invoke"],
                    }
                },
                protocolConfiguration={"serverProtocol": "HTTP", "port": 8080, "path": "/invocations"},
                environmentVariables={
                    "GATEWAY_URL": state["gateway_url"],
                    "MODEL_ID": "moonshotai.kimi-k2.5",
                },
                lifecycleConfiguration={"idleRuntimeSessionTimeout": 300, "maxLifetime": 1800},
            ),
            90,
        )
        state["runtime_id"] = r["agentRuntimeId"]
        state["runtime_arn"] = r["agentRuntimeArn"]
        save()
    note("JWT-authenticated Runtime provisioning: " + state["runtime_id"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["kb", "gateway", "auth", "runtime"])
    args = p.parse_args()
    {"kb": kb, "gateway": gateway, "auth": auth, "runtime": runtime}[args.stage]()
