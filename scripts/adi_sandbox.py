"""Start Aditya's separate event-sandbox copy; refuse personal/wrong AWS identities."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

EXPECTED_ACCOUNT = "952337755619"


def check_identity(identity: dict[str, Any], cfg: Any) -> None:
    if os.environ.get("AWS_PROFILE"):
        raise ValueError("Unset AWS_PROFILE; use the supplied workshop identity.")
    if identity.get("Account") != EXPECTED_ACCOUNT or ":assumed-role/WSParticipantRole/" not in identity.get(
        "Arn", ""
    ):
        raise ValueError("Refusing AWS access: this is not Aditya's event WSParticipantRole account.")
    if cfg["region"] != "us-west-2":
        raise ValueError("This sandbox copy is configured for Oregon only.")
    if cfg.get("runtime_arn") or cfg.get("lgnd_secret_id"):
        for key in ("runtime_arn", "lgnd_secret_id"):
            value = cfg.get(key)
            if value and f":{EXPECTED_ACCOUNT}:" not in value:
                raise ValueError(f"{key} belongs to another account.")
    if not str(cfg["archive_uri"]).startswith("file://") or not str(cfg["local_archive_uri"]).startswith(
        "file://"
    ):
        raise ValueError("Use local archives in this isolated copy; do not inherit Miguel's S3 bucket.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["ui", "run", "check"])
    p.add_argument("--prompt")
    p.add_argument("--model", default="sonnet")
    p.add_argument("--port", type=int, default=8787)
    args = p.parse_args()
    import boto3

    from harness.config import load

    if not Path("harness.local.yaml").is_file():
        raise SystemExit("Missing private harness.local.yaml for your event sandbox.")
    cfg = load()
    check_identity(boto3.client("sts", region_name="us-west-2").get_caller_identity(), cfg)
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
    os.environ["AWS_REGION"] = "us-west-2"
    print(f"Verified event account {EXPECTED_ACCOUNT}; personal profiles refused.", flush=True)
    if args.mode == "check":
        return 0
    from harness.cli import main as harness_main

    if args.mode == "ui":
        return harness_main(["ui", "--port", str(args.port)])
    if not args.prompt:
        raise SystemExit("--prompt is required")
    return harness_main(["run", "--prompt", args.prompt, "--model", args.model, "--backend", "local"])


if __name__ == "__main__":
    raise SystemExit(main())
