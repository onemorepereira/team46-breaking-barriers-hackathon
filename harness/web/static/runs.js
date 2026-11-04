/* Runs table: every archived run in out/index.json, newest first. Text only, via textContent. */
(() => {
  "use strict";
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined) continue;
      if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid instanceof Node ? kid : String(kid));
    return n;
  };
  const usd = (v) => (v === null || v === undefined ? "—" : `$${v.toFixed(v < 0.1 ? 3 : 2)}`);
  const tone = (s) => (s === null || s === undefined ? "secondary" : s >= 80 ? "success" : s >= 50 ? "warning" : "danger");
  const statusTone = (s) => (s === "ok" ? "success" : s === "limit_exceeded" ? "warning" : "danger");
  const body = document.getElementById("runs-body");
  const message = (text, cls) => body.replaceChildren(el("tr", {}, el("td", { colspan: 11, class: cls, text })));
  fetch("/api/runs").then((r) => r.json()).then(({ runs }) => {
    if (!runs.length) { message("No runs yet. Start one from the console.", "text-secondary"); return; }
    body.replaceChildren(...runs.map((r) => {
      const score = r.verdict === "FAILED" ? el("span", { class: "badge bg-danger-lt", text: "FAILED" })
        : r.score === null ? el("span", { class: "text-secondary small", text: r.verdict })
        : el("span", { class: `badge bg-${tone(r.score)}-lt`, text: Math.round(r.score) });
      const tr = el("tr", { style: "cursor:pointer" },
        el("td", { class: "text-secondary small text-nowrap", text: (r.started_at || "").replace("T", " ").replace("Z", "") }),
        el("td", { class: "small text-truncate", style: "max-width:26rem", title: r.prompt || "" },
          el("a", { href: `/runs/${r.id}`, text: r.prompt || r.prompt_file || r.id })),
        el("td", {}, el("span", { class: "badge bg-azure-lt", text: r.model_key || "?" })),
        el("td", { class: "small text-secondary", text: r.area || "—" }),
        el("td", {}, el("span", { class: `badge bg-${statusTone(r.status)}-lt`, text: r.status })),
        el("td", { class: "text-end" }, score),
        el("td", { class: "small", text: r.confidence || "" }),
        el("td", { class: "text-end small", text: usd(r.cost_usd) }),
        el("td", { class: "text-end small", text: usd(r.judging_cost_usd) }),
        el("td", { class: "text-end small", text: `${r.tool_calls}${r.errors ? ` (${r.errors} err)` : ""}` }),
        el("td", { class: "text-end small", text: r.runtime_s === null ? "—" : `${Math.round(r.runtime_s)}s` }));
      tr.addEventListener("click", (e) => { if (e.target.tagName !== "A") location.href = `/runs/${r.id}`; });
      return tr;
    }));
  }).catch((e) => message(`Couldn't load runs: ${e}`, "text-danger"));
})();
