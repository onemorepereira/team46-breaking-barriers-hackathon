"""harness.local.yaml (git-ignored) overrides the committed harness.yaml, so a teammate's own sandbox never
needs a change to the shared file."""

import subprocess
from pathlib import Path

from harness import config

REPO = Path(__file__).resolve().parents[1]


def test_local_file_overrides_the_shared_config_key_by_key(tmp_path):
    (tmp_path / "harness.yaml").write_text(
        "archive_uri: s3://shared-bucket\nlgnd_secret_id: shared-secret\n"
        "judging: {panel: [opus, deepseek, kimi], passes: 1}\n"
    )
    assert (
        config.load(tmp_path / "harness.yaml")["archive_uri"] == "s3://shared-bucket"
    )  # no local file: as is
    (tmp_path / "harness.local.yaml").write_text("archive_uri: s3://my-bucket\njudging: {passes: 3}\n")
    cfg = config.load(tmp_path / "harness.yaml")
    assert cfg["archive_uri"] == "s3://my-bucket" and cfg["lgnd_secret_id"] == "shared-secret"
    assert cfg["judging"] == {"panel": ["opus", "deepseek", "kimi"], "passes": 3}  # nested keys merge


def test_local_config_is_git_ignored():
    out = subprocess.run(
        ["git", "check-ignore", "harness.local.yaml"], cwd=REPO, capture_output=True, text=True
    )
    assert out.stdout.strip() == "harness.local.yaml"
