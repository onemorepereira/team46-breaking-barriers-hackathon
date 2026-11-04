"""AC3: no observability-backend SDK anywhere (design ADR-2, the import-lint rule)."""

import ast
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGES = ["core", "tools", "agent", "harness", "analysis"]
FIRST_PARTY = set(PACKAGES)
# import name -> distribution name, where they differ
IMPORT_TO_DIST = {
    "yaml": "pyyaml",
    "botocore": "boto3",
    "strands": "strands-agents",
    "bedrock_agentcore": "bedrock-agentcore",
    "opentelemetry": "opentelemetry-sdk",  # namespace package (api, sdk, exporters)
}


def _dist_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0].strip().lower()


def declared_deps() -> set[str]:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    return {_dist_name(r) for r in data["project"]["dependencies"]}


def allowed_deps() -> set[str]:
    lines = (REPO / "tests/allowed_deps.txt").read_text().splitlines()
    return {line.strip().lower() for line in lines if line.strip() and not line.startswith("#")}


def _covered(dist: str, allowed: set[str]) -> bool:
    return any(dist == a or (a.endswith("*") and dist.startswith(a[:-1])) for a in allowed)


def top_level_imports() -> list[tuple[Path, str]]:
    found = []
    for pkg in PACKAGES:
        for path in (REPO / pkg).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                if isinstance(node, ast.Import):
                    found += [(path, a.name.split(".")[0]) for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    found.append((path, node.module.split(".")[0]))
    return found


def test_declared_dependencies_are_all_on_the_reviewed_allowlist():
    allowed = allowed_deps()
    assert [d for d in declared_deps() if not _covered(d, allowed)] == []


def test_every_import_is_stdlib_first_party_or_declared():
    deps = declared_deps()
    bad = []
    for path, mod in top_level_imports():
        if mod in sys.stdlib_module_names or mod in FIRST_PARTY or mod == "__future__":
            continue
        dist = IMPORT_TO_DIST.get(mod, mod.replace("_", "-")).lower()
        if not any(dist == d or dist.startswith(d.rstrip("*")) for d in deps):
            bad.append(f"{path.relative_to(REPO)}: {mod}")
    assert bad == []


def test_allowlist_has_no_known_backend_sdk():
    backends = {
        "arize-phoenix",
        "arize-phoenix-otel",
        "langfuse",
        "aws-xray-sdk",
        "datadog",
        "ddtrace",
        "newrelic",
    }
    assert not (allowed_deps() & backends)
