"""docs-pass AC5: the docs stay true to the repo. Relative links resolve, the developer guide's commands exist
in the CLI, and every harness.yaml key is documented."""

import re
from pathlib import Path
from urllib.parse import unquote

import yaml

from harness.cli import build_parser

REPO = Path(__file__).resolve().parents[1]
DOCS = [REPO / "README.md", REPO / "CONTRIBUTING.md", *sorted((REPO / "docs").rglob("*.md"))]
LINK = re.compile(r"\]\((<[^>]+>|[^)\s]+)\)")  # [text](target) or [text](<target with spaces>)
GUIDE = REPO / "docs" / "developer-guide.md"


def relative_links(path: Path) -> list[str]:
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)  # code blocks aren't links
    out = []
    for raw in LINK.findall(text):
        target = raw.strip("<>")
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # external URL, mailto, or same-page anchor
        out.append(unquote(target.split("#", 1)[0]))
    return out


def test_every_relative_link_in_the_docs_resolves():
    broken = [
        f"{doc.relative_to(REPO)} -> {target}"
        for doc in DOCS
        for target in relative_links(doc)
        if target and not (doc.parent / target).exists()
    ]
    assert broken == []


def test_every_doc_is_reachable_from_the_readme_within_two_links():
    def links_of(doc: Path) -> set[Path]:
        return {(doc.parent / t).resolve() for t in relative_links(doc) if t.endswith(".md")}

    seen = {(REPO / "README.md").resolve()}
    frontier = set(seen)
    for _ in range(2):
        frontier = {p for doc in frontier if doc.exists() for p in links_of(doc)} - seen
        seen |= frontier
    unreachable = [str(d.relative_to(REPO)) for d in DOCS if d.resolve() not in seen]
    assert unreachable == []


def test_developer_guide_commands_exist_in_the_cli():
    sub = next(a for a in build_parser()._actions if isinstance(a.choices, dict))
    commands = set(sub.choices)
    text = GUIDE.read_text(encoding="utf-8")
    cli_section = text.split("## 6. CLI reference", 1)[1].split("\n## ", 1)[0]
    documented = set(re.findall(r"^\| `([a-z-]+)", cli_section, flags=re.M)) - {"Command"}
    assert documented == commands  # every command documented, nothing documented that doesn't exist
    mentioned = set(re.findall(r"`(?:uv run )?harness (?:--config \S+ )?([a-z][a-z-]+)", text))
    assert mentioned <= commands, mentioned - commands


def test_every_harness_yaml_key_is_in_the_configuration_reference():
    cfg = yaml.safe_load((REPO / "harness.yaml").read_text(encoding="utf-8"))
    text = GUIDE.read_text(encoding="utf-8")
    missing = [k for k in cfg if f"`{k}" not in text]
    for section in ("judging", "tiles"):
        missing += [f"{section}.{k}" for k in cfg[section] if f"`{section}.{k}`" not in text]
    assert missing == []


def test_the_factory_ledger_lists_every_feature_folder():
    """docs/factory.md has a row linking each docs/<slug>/spec.md, so no effort goes untracked."""
    ledger = (REPO / "docs" / "factory.md").read_text(encoding="utf-8")
    folders = sorted(p.parent.name for p in (REPO / "docs").glob("*/spec.md"))
    assert folders and [f for f in folders if f"]({f}/spec.md)" not in ledger] == []
