"""Layer separation (docs/layering/spec.md): imports follow the layer table; prompts are files; tool knowledge
stays in tools/."""

import ast
import re
from pathlib import Path

from tools.lgnd import descriptors as lgnd
from tools.roda import descriptors as roda

REPO = Path(__file__).resolve().parents[1]
LAYERS = ["core", "tools", "agent", "analysis", "harness"]

# AC1: which first-party packages each layer may import.
ALLOWED = {
    "core": set(),
    "tools": {"core", "tools"},
    "agent": {"core", "tools", "agent"},
    "analysis": {
        "core",
        "analysis",
        "tools.lgnd.descriptors",
        "tools.lgnd.results",
        "tools.roda.descriptors",
        "tools.describe",  # pure plain-English describers (no clients)
        "tools.lgnd.describe",
        "tools.roda.describe",
    },
    "harness": {"core", "analysis", "tools", "harness"},
}


def modules(layer):
    return sorted((REPO / layer).rglob("*.py"))


def first_party_imports(path):
    """Each import as (target, candidates): it passes if any candidate is allowed.

    `from tools.lgnd import descriptors` passes when `tools.lgnd.descriptors` is allowed.
    """
    out = []
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            out += [(a.name, [a.name]) for a in node.names if a.name.split(".")[0] in LAYERS]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in LAYERS:
                for a in node.names:
                    out.append((f"{node.module}.{a.name}", [node.module, f"{node.module}.{a.name}"]))
    return out


def allowed(layer, name):
    return any(name == a or name.startswith(a + ".") for a in ALLOWED[layer])


def violations(layer, path):
    return [t for t, cands in first_party_imports(path) if not any(allowed(layer, c) for c in cands)]


def test_ac1_imports_follow_the_layer_table():
    bad = [
        f"{p.relative_to(REPO)} imports {t}"
        for layer in LAYERS
        for p in modules(layer)
        for t in violations(layer, p)
    ]
    assert bad == []


INSTRUCTION = re.compile(r"^\s*(You|Reply|Return|Respond|Answer)\b")


def test_ac2_no_inline_model_instructions():
    bad = []
    for layer in LAYERS:
        for path in modules(layer):
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value
                    if len(text) > 160 and INSTRUCTION.match(text):
                        bad.append(f"{path.relative_to(REPO)}:{node.lineno}: {text[:60]!r}")
    assert bad == []
    for name in [
        "agent/system",
        "agent/search_area",
        "agent/search_area_enforced",
        "harness/narrative",
        "harness/area_extract",
        "judge/system",
    ]:
        assert (REPO / "prompts" / f"{name}.md").is_file(), name


def test_ac3_tool_knowledge_stays_in_tools():
    needles = sorted(lgnd.TOOL_NAMES | roda.TOOL_NAMES | {"geo.lgnd.ai", "roda-mcp-server"})
    bad = []
    for layer in ["core", "agent", "analysis", "harness"]:
        for path in modules(layer):
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    hits = [n for n in needles if n in node.value]
                    if hits:
                        bad.append(f"{path.relative_to(REPO)}:{node.lineno}: {hits}")
    assert bad == []
