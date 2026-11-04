/* Team Foundry console: the Guidance page (docs/judge-feedback/design.md, Console). Lessons the judges get
   from human review: propose, edit a draft, evaluate on held-out runs, approve, switch off, history.
   All text goes in through textContent. The name is kept in sessionStorage only. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const NAME_KEY = "foundry.reviewer";
  const LESSON_MAX = 400;

  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
      n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return n;
  }
  const icon = (name, cls = "") => el("i", { class: `ti ti-${name} ${cls}`.trim() });
  const human = (id) => String(id).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const when = (iso) => {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  };
  const fmt = (v, digits = 2) => (v === null || v === undefined ? "—" : Number(v).toFixed(digits));
  const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
  const usd = (v) => (v === null || v === undefined ? "—" : `$${Number(v).toFixed(2)}`);
  function getName() { try { return sessionStorage.getItem(NAME_KEY) || ""; } catch { return ""; } }
  function setName(v) { try { sessionStorage.setItem(NAME_KEY, v); } catch { /* a convenience only */ } }

  // Errors: 400 {"error"}; 404/409/502 {"detail"}; 422 {"detail": [{msg}]}.
  async function call(url, opts = {}) {
    const res = await fetch(url, { headers: { "content-type": "application/json" }, ...opts });
    let body = null;
    try { body = await res.json(); } catch { body = null; }
    if (!res.ok) {
      const d = body && body.detail;
      throw new Error((body && body.error) || (Array.isArray(d) ? d.map((x) => x.msg).join("; ") : d) || `${res.status} ${res.statusText}`);
    }
    return body;
  }
  const post = (url, body) => call(url, { method: "POST", body: JSON.stringify(body || {}) });
  function message(node, text, kind) {
    node.hidden = !text;
    node.className = `alert alert-${kind || "info"} ${node.className.replace(/\balert(-\w+)?\b/g, "").trim()}`.trim();
    node.textContent = text || "";
  }

  const VERDICT = { adopt: ["success", "adopt"], dont_adopt: ["danger", "don't adopt"], insufficient_evidence: ["warning", "insufficient evidence"] };
  const verdictBadge = (v) => {
    const [c, t] = VERDICT[v] || ["secondary", v || "—"];
    return el("span", { class: `badge bg-${c}-lt`, text: t });
  };
  const STATUS = { active: "success", retired: "secondary", draft: "azure" };
  const statusBadge = (s) => el("span", { class: `badge bg-${STATUS[s] || "secondary"}-lt`, text: s });

  let overview = null;
  let current = null;   // the open version (GET /api/guidance/{n})
  let lessons = [];     // the draft being edited

  // ---------- overview ----------
  async function load() {
    try {
      overview = await call("/api/guidance");
    } catch (e) {
      message($("g-error"), `Couldn't load guidance: ${e.message}`, "danger");
      return;
    }
    $("g-error").hidden = true;
    const o = overview;
    $("g-rubric").textContent = `Rubric ${o.rubric.id} v${o.rubric.version} · ${o.rubric.title || ""}`;
    const active = o.active && o.active.version;
    const badge = $("g-active");
    badge.textContent = active == null ? "none" : `v${active}`;
    badge.className = `badge fs-5 ${active == null ? "bg-secondary-lt" : "bg-success-lt"}`;
    badge.title = o.active && o.active.by ? `since ${when(o.active.at)} by ${o.active.by}` : "";
    $("btn-off").disabled = active == null;
    $("g-disabled").hidden = o.enabled !== false;
    renderAgreement(o);
    renderVersions(o);
    renderLog(o.log || []);
  }

  function renderAgreement(o) {
    const rows = Object.entries((o.agreement || {}).by_guidance || {});
    $("g-agreement").replaceChildren(...(rows.length ? rows.map(([key, a]) => el("tr", {},
      el("td", {}, key === "none" ? "none" : `v${key}`),
      el("td", { class: "text-end", text: fmt(a.alpha, 3) }),
      el("td", { class: "text-secondary", text: a.ci95 ? `${fmt(a.ci95[0], 3)} – ${fmt(a.ci95[1], 3)}` : "—" }),
      el("td", { class: "text-end", text: fmt(a.mad) }),
      el("td", { class: "text-end", text: pct(a.exact) }),
      el("td", { class: "text-end", text: String(a.runs) })))
      : [el("tr", {}, el("td", { colspan: 6, class: "text-secondary small", text: "No reviews yet. Review runs from their run pages." }))]));
    $("g-counts").replaceChildren(
      `${o.reviewed_runs} reviewed runs (${o.reviews} reviews) · ${o.held_out_runs} held out. `,
      el("span", {}, `About a third of reviewed runs are held out for evaluation and never shown to the proposal; at least ${o.min_held_out} held-out runs are needed to evaluate.`));
  }

  function renderVersions(o) {
    const vs = o.versions || [];
    if (!vs.length) {
      $("g-versions").replaceChildren(el("tr", {}, el("td", { colspan: 6, class: "text-secondary small", text: "No guidance yet. Propose a first draft once reviewers disagree with the panel." })));
      return;
    }
    $("g-versions").replaceChildren(...vs.map((v) => {
      const ev = v.latest_evaluation;
      return el("tr", { id: `version-${v.version}` },
        el("td", {}, el("strong", { text: `v${v.version}` }), v.based_on != null ? el("span", { class: "text-secondary small ms-1", text: `from v${v.based_on}` }) : null),
        el("td", {}, statusBadge(v.status)),
        el("td", { class: "text-end", text: String(v.lessons) }),
        el("td", { class: "small" }, v.created_by || "", el("div", { class: "text-secondary", text: when(v.created_at) })),
        el("td", { class: "small" }, ev ? [verdictBadge(ev.verdict), el("span", { class: "text-secondary ms-1", text: `${when(ev.at)}${ev.verdict === "adopt" && !v.evaluation_current ? " · lessons edited since" : ""}` })]
          : el("span", { class: "text-secondary", text: "not evaluated" })),
        el("td", { class: "text-end text-nowrap" },
          el("button", { type: "button", class: "btn btn-sm", onclick: () => openVersion(v.version) }, icon("eye", "me-1"), "Open"), " ",
          el("button", { type: "button", class: "btn btn-sm", onclick: () => openVersion(v.version).then(estimate) }, icon("flask", "me-1"), "Evaluate"), " ",
          v.status !== "active" ? el("button", { type: "button", class: "btn btn-sm", onclick: () => approveDialog(v) }, icon("circle-check", "me-1"), "Approve") : null));
    }));
  }

  function renderLog(log) {
    $("g-log").replaceChildren(...(log.length ? log.map((e) => el("tr", {},
      el("td", { class: "small text-nowrap", text: when(e.at) }),
      el("td", {}, el("span", { class: `badge bg-${e.action === "off" ? "secondary" : "success"}-lt`, text: e.action === "off" ? "switched off" : e.action })),
      el("td", { text: e.version == null ? "none" : `v${e.version}` }),
      el("td", { class: "text-secondary", text: e.previous == null ? "none" : `v${e.previous}` }),
      el("td", { text: e.by || "" }),
      el("td", { class: "small", text: e.reason || "" }),
      el("td", {}, e.evaluation_verdict ? verdictBadge(e.evaluation_verdict) : el("span", { class: "text-secondary small", text: "—" }))))
      : [el("tr", {}, el("td", { colspan: 7, class: "text-secondary small", text: "No changes yet." }))]));
  }

  // ---------- propose ----------
  $("propose-name").value = getName();
  $("propose-name").addEventListener("input", (e) => setName(e.target.value.trim()));
  $("propose-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = $("btn-propose"), msg = $("propose-msg");
    btn.disabled = true;
    message(msg, "The chair judge is drafting lessons…", "info");
    try {
      const v = await post("/api/guidance", { by: $("propose-name").value.trim() });
      const p = v.proposal || {};
      message(msg, `Drafted v${v.version}: ${v.lessons.length} lessons from ${p.disagreements} disagreements in ${p.reviews_read} training reviews${p.dropped ? ` (${p.dropped} unusable lessons dropped)` : ""}, ${usd(p.cost_usd)}.`, "success");
      await load();
      await openVersion(v.version);
    } catch (e) {
      message(msg, e.message, "danger");
    } finally {
      btn.disabled = false;
    }
  });

  // ---------- the version editor ----------
  async function openVersion(n) {
    try {
      current = await call(`/api/guidance/${n}`);
    } catch (e) {
      message($("g-error"), e.message, "danger");
      return;
    }
    lessons = (current.lessons || []).map((l) => ({ criterion: l.criterion, text: l.text, sources: [...(l.sources || [])], id: l.id }));
    renderEditor();
    $("editor").hidden = false;
    $("editor").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderEditor() {
    const v = current;
    const draft = v.status === "draft";
    $("editor-title").replaceChildren(`Guidance v${v.version} `, statusBadge(v.status));
    const p = v.proposal;
    const appr = v.approvals || [];
    $("editor-meta").replaceChildren(
      `Created ${when(v.created_at)} by ${v.created_by || "?"}`,
      v.based_on != null ? ` · based on v${v.based_on}` : "",
      p ? ` · proposed by ${p.model} from ${p.disagreements} disagreements in ${p.reviews_read} reviews, ${usd(p.cost_usd)}` : " · written by hand",
      v.edited_at ? ` · edited ${when(v.edited_at)}` : "",
      appr.length ? ` · approved ${appr.length}× (last by ${appr[appr.length - 1].by}, ${when(appr[appr.length - 1].at)})` : "",
      draft ? "" : el("div", { class: "mt-1" }, icon("lock", "me-1"), "Approved versions are read-only. Propose a new version to change the lessons."));
    $("editor-approve").hidden = v.status === "active";
    $("editor-actions").hidden = !draft;
    $("editor-msg").hidden = true;
    renderLessons(draft);
    renderEvaluations(v.evaluations || []);
  }

  function renderLessons(editable) {
    const box = $("lessons");
    const criteria = (overview && overview.criteria) || [];
    if (!lessons.length) {
      box.replaceChildren(el("div", { class: "text-secondary small", text: editable ? "No lessons. Add one below." : "No lessons." }));
      return;
    }
    box.replaceChildren(...lessons.map((l, i) => {
      const sources = el("div", { class: "d-flex flex-wrap gap-1 align-items-center mt-1" },
        el("span", { class: "small text-secondary me-1", text: l.sources.length ? "Sources (reviews):" : "No source reviews (written by hand)." }),
        ...l.sources.map((s, j) => el("span", { class: "badge bg-azure-lt font-monospace", title: "review ID" },
          (current.source_runs || {})[s] ? el("a", { href: `/runs/${current.source_runs[s]}`, class: "text-reset", text: s }) : s,
          editable ? el("button", { type: "button", class: "btn-close btn-close-white ms-1 foundry-chip-x", "aria-label": `Remove source ${s}`,
            onclick: () => { l.sources.splice(j, 1); renderLessons(true); } }) : null)));
      if (!editable) {
        return el("div", { class: "border rounded p-2 mb-2" },
          el("div", { class: "d-flex gap-2 align-items-center" }, el("span", { class: "badge bg-secondary-lt", text: l.id || `L${i + 1}` }), el("strong", { text: human(l.criterion) })),
          el("div", { class: "mt-1", text: l.text }), sources);
      }
      const sel = el("select", { class: "form-select form-select-sm", "aria-label": `Lesson ${i + 1} criterion` },
        ...criteria.map((c) => el("option", { value: c.id, text: human(c.id), title: c.question })));
      if (!criteria.some((c) => c.id === l.criterion)) sel.prepend(el("option", { value: l.criterion, text: l.criterion || "Pick a criterion" }));
      sel.value = l.criterion;
      sel.addEventListener("change", () => (l.criterion = sel.value));
      const count = el("span", { class: "small text-secondary" });
      const text = el("textarea", { class: "form-control", rows: 2, maxlength: LESSON_MAX, "aria-label": `Lesson ${i + 1} text`, placeholder: "One or two general sentences. Name no run or step." });
      text.value = l.text;
      const upd = () => { count.textContent = `${text.value.length}/${LESSON_MAX}`; count.classList.toggle("text-danger", text.value.length >= LESSON_MAX); };
      text.addEventListener("input", () => { l.text = text.value; upd(); });
      upd();
      return el("div", { class: "border rounded p-2 mb-2" },
        el("div", { class: "d-flex gap-2 align-items-center mb-1" },
          el("span", { class: "badge bg-secondary-lt", text: `L${i + 1}` }),
          el("div", { style: "max-width: 18rem" }, sel),
          el("span", { class: "ms-auto" }, count),
          el("button", { type: "button", class: "btn btn-sm btn-ghost-danger", onclick: () => { lessons.splice(i, 1); renderLessons(true); } }, icon("trash", "me-1"), "Remove")),
        text, sources);
    }));
  }

  $("btn-add-lesson").addEventListener("click", () => {
    const first = ((overview && overview.criteria) || [])[0];
    lessons.push({ criterion: first ? first.id : "", text: "", sources: [] });
    renderLessons(true);
    const areas = $("lessons").querySelectorAll("textarea");
    if (areas.length) areas[areas.length - 1].focus();
  });
  $("btn-save").addEventListener("click", async () => {
    const btn = $("btn-save");
    btn.disabled = true;
    try {
      await call(`/api/guidance/${current.version}`, { method: "PUT", body: JSON.stringify({ lessons: lessons.map(({ criterion, text, sources }) => ({ criterion, text, sources })) }) });
      await openVersion(current.version);
      message($("editor-msg"), "Saved. An edit clears the version's evaluation: evaluate it again before approving.", "success");
      load();
    } catch (e) {
      message($("editor-msg"), e.message, "danger");
    } finally {
      btn.disabled = false;
    }
  });
  $("editor-close").addEventListener("click", () => { $("editor").hidden = true; current = null; });
  $("editor-evaluate").addEventListener("click", estimate);
  $("editor-approve").addEventListener("click", () => current && approveDialog(current));

  // ---------- evaluation ----------
  async function estimate() {
    if (!current) return;
    const panel = $("evaluate-panel");
    panel.hidden = false;
    panel.replaceChildren(el("div", { class: "text-secondary small", text: "Estimating…" }));
    let est;
    try {
      est = await post(`/api/guidance/${current.version}/evaluate`, { confirm: false });
    } catch (e) {
      panel.replaceChildren(el("div", { class: "alert alert-danger mb-0", text: e.message }));
      return;
    }
    const short = est.held_out < est.min_held_out;
    const confirm = el("button", { type: "button", class: "btn btn-primary" }, icon("player-play", "me-1"), "Confirm");
    const cancel = el("button", { type: "button", class: "btn", onclick: () => (panel.hidden = true) }, "Cancel");
    confirm.addEventListener("click", () => runEvaluation(current.version));
    panel.replaceChildren(el("div", { class: "border rounded p-3" },
      el("div", { class: "fw-semibold mb-1" }, icon("flask", "me-1"), `Evaluate v${current.version}`),
      el("div", { class: "small mb-2" },
        `${est.held_out} held-out reviewed runs (of ${est.reviewed_runs} reviewed; at least ${est.min_held_out} needed). `,
        short ? "That's too few: the evaluation will record insufficient evidence, at no cost."
          : `Each is judged with and without this version, then planted-defect calibration runs: ${est.passes} panel passes, about ${usd(est.estimate_usd)}.`),
      el("div", { class: "d-flex gap-2" }, confirm, cancel)));
  }

  async function runEvaluation(n) {
    const panel = $("evaluate-panel");
    try {
      await post(`/api/guidance/${n}/evaluate`, { confirm: true });
    } catch (e) {
      panel.replaceChildren(el("div", { class: "alert alert-danger mb-0", text: e.message }));
      return;
    }
    const text = el("span", { text: "Starting…" });
    const bar = el("div", { class: "progress-bar progress-bar-indeterminate" });
    panel.replaceChildren(el("div", { class: "border rounded p-3" },
      el("div", { class: "d-flex align-items-center gap-2 small text-secondary mb-1" }, el("span", { class: "spinner-border spinner-border-sm" }), text),
      el("div", { class: "progress progress-sm" }, bar)));
    const es = new EventSource(`/api/guidance/${n}/events`);
    es.onmessage = async (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "evaluating") {
        if (ev.stage === "calibration") text.textContent = "Rerunning planted-defect calibration with this guidance…";
        else if (ev.total) {
          text.textContent = `Judged ${ev.done} of ${ev.total} held-out runs (${ev.run_id})`;
          bar.classList.remove("progress-bar-indeterminate");
          bar.style.width = `${Math.round((ev.done / ev.total) * 100)}%`;
        } else text.textContent = `Evaluating v${ev.version}…`;
      } else if (ev.type === "evaluated") {
        text.textContent = `Verdict: ${(VERDICT[ev.verdict] || [0, ev.verdict])[1]}`;
      } else if (ev.type === "done") {
        es.close();
        if (ev.error || !ev.report) {
          panel.replaceChildren(el("div", { class: "alert alert-danger mb-0", text: `The evaluation failed: ${ev.error || "no report"}. Nothing was stored.` }));
          return;
        }
        panel.replaceChildren(el("div", { class: "border rounded p-3" }, el("div", { class: "fw-semibold mb-2", text: "Evaluation finished" }), report(ev.report, current)));
        await load();
        if (current && current.version === n) {
          const keep = panel.firstChild;
          await openVersion(n);
          $("evaluate-panel").hidden = false;
          $("evaluate-panel").replaceChildren(keep);
        }
      }
    };
    es.onerror = () => { /* EventSource retries; the server ends the stream after "done" */ };
  }

  function renderEvaluations(evals) {
    const box = $("evaluations");
    if (!evals.length) { box.replaceChildren(el("div", { class: "text-secondary small", text: "Not evaluated yet." })); return; }
    box.replaceChildren(...evals.map((e) => el("div", { class: "border rounded p-3 mb-2" }, report(e, current))));
  }

  function report(e, v) {
    const stale = v && e.sha256 && v.sha256 && e.sha256 !== v.sha256;
    const out = el("div", { class: "small" },
      el("div", { class: "d-flex flex-wrap align-items-center gap-2 mb-2" }, verdictBadge(e.verdict),
        el("span", { class: "text-secondary", text: when(e.at) }),
        el("span", { class: "text-secondary", text: `· ${(e.held_out || []).length} held-out runs${(e.excluded || []).length ? `, ${e.excluded.length} excluded` : ""}` }),
        el("span", { class: "text-secondary", text: `· baseline ${e.baseline == null ? "no guidance" : `v${e.baseline}`}` }),
        el("span", { class: "text-secondary", text: `· ${usd(e.cost_usd)}` }),
        stale ? el("span", { class: "badge bg-secondary-lt", text: "of earlier lessons" }) : null));
    if ((e.reasons || []).length) out.append(el("ul", { class: "mb-2" }, ...e.reasons.map((r) => el("li", { text: r }))));
    const m = e.metrics;
    if (m) {
      const row = (label, w, g, strong) => el("tr", { class: strong ? "fw-semibold" : "" },
        el("td", { text: label }),
        el("td", { class: "text-end", text: fmt(w.mad) }), el("td", { class: "text-end", text: fmt(g.mad) }),
        el("td", { class: "text-end", text: pct(w.exact) }), el("td", { class: "text-end", text: pct(g.exact) }),
        el("td", { class: "text-end", text: String(g.n ?? w.n ?? "") }));
      out.append(el("div", { class: "table-responsive" }, el("table", { class: "table table-sm mb-2" },
        el("thead", {}, el("tr", {}, el("th", { text: "Criterion" }), el("th", { class: "text-end", text: "MAD without" }), el("th", { class: "text-end", text: "MAD with" }),
          el("th", { class: "text-end", text: "Exact without" }), el("th", { class: "text-end", text: "Exact with" }), el("th", { class: "text-end", text: "N" }))),
        el("tbody", {}, ...Object.entries(m.criteria || {}).map(([cid, c]) => row(human(cid), c.without, c.with)),
          row("Overall", m.overall.without, m.overall.with, true)))));
    }
    const cal = e.calibration;
    if (cal) {
      out.append(el("div", { class: "text-secondary mb-1", text: `Planted-defect calibration on ${cal.run_id}${cal.applicable === false ? " (not applicable to this run)" : ""}` }),
        el("div", { class: "table-responsive" }, el("table", { class: "table table-sm mb-0" },
          el("thead", {}, el("tr", {}, ...["Perturbation", "Target", "Original", "Perturbed", "Drop", "Verdict"].map((h) => el("th", { text: h })))),
          el("tbody", {}, ...(cal.rows || []).map((r) => el("tr", {},
            el("td", { text: r.perturbation || r.check || "" }), el("td", { text: r.target || "—" }),
            el("td", { text: fmt(r.original, 1) }), el("td", { text: fmt(r.perturbed, 1) }), el("td", { text: fmt(r.drop, 1) }),
            el("td", {}, el("span", { class: `badge bg-${{ pass: "success", fail: "danger" }[r.verdict] || "secondary"}-lt`, text: r.verdict }),
              r.why ? el("span", { class: "text-secondary ms-1", text: r.why }) : null)))))));
    }
    return out;
  }

  // ---------- approve / switch off: one dialog ----------
  const dlg = $("action-dialog");
  let action = null;
  function openDialog({ title, help, reasonLabel, ok, run }) {
    $("action-title").textContent = title;
    $("action-help").textContent = help;
    $("action-reason-label").textContent = reasonLabel;
    $("action-ok").textContent = ok;
    $("action-name").value = getName();
    $("action-reason").value = "";
    $("action-error").hidden = true;
    action = run;
    dlg.showModal();
    ($("action-name").value ? $("action-reason") : $("action-name")).focus();
  }
  $("action-cancel").addEventListener("click", () => dlg.close());
  $("action-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const by = $("action-name").value.trim();
    setName(by);
    $("action-ok").disabled = true;
    try {
      await action(by, $("action-reason").value.trim());
      dlg.close();
      await load();
      if (current) await openVersion(current.version);
    } catch (e) {
      $("action-error").hidden = false;
      $("action-error").textContent = e.message;
    } finally {
      $("action-ok").disabled = false;
    }
  });

  function approveDialog(v) {
    const ev = v.latest_evaluation;
    const counts = !!v.evaluation_current;
    const rollback = v.status === "retired";
    openDialog({
      title: `${rollback ? "Roll back to" : "Approve"} guidance v${v.version}`,
      help: counts ? "Its latest evaluation, of these lessons, says adopt. Every later judging and reconsideration will use it."
        : `${ev ? (ev.verdict === "adopt" ? "It was evaluated as adopt, but its lessons changed since." : `Its latest evaluation says ${(VERDICT[ev.verdict] || [0, ev.verdict])[1]}.`) : "It hasn't been evaluated."} A reason is required to approve it anyway.`,
      reasonLabel: counts ? "Reason (optional)" : "Reason (required)",
      ok: rollback ? "Roll back" : "Approve",
      run: (by, reason) => {
        if (!counts && !reason) throw new Error("Give a reason: this version isn't evaluated as adopt in its current form.");
        return post(`/api/guidance/${v.version}/approve`, { by, reason });
      },
    });
  }
  $("btn-off").addEventListener("click", () => openDialog({
    title: "Switch guidance off",
    help: "The judges get no guidance from now on. Approve any version to switch it back on.",
    reasonLabel: "Reason (optional)",
    ok: "Switch off",
    run: (by, reason) => post("/api/guidance/off", { by, reason }),
  }));

  load();
})();
