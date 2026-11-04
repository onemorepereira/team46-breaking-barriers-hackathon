/* Team Foundry console: the "Your review" card on the run page, and the revision notes on the scorecard
   (docs/judge-feedback/design.md, Console). Rendered after app.js renders a run view (FOUNDRY.onView).
   All text goes in through textContent. The reviewer's name is kept in sessionStorage only. */
(() => {
  "use strict";
  const F = window.FOUNDRY;
  const $ = (id) => document.getElementById(id);
  const { el, icon } = F;
  const NAME_KEY = "foundry.reviewer";

  const human = (id) => id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  const when = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  };
  function getName() { try { return sessionStorage.getItem(NAME_KEY) || ""; } catch { return ""; } }
  function setName(v) { try { sessionStorage.setItem(NAME_KEY, v); } catch { /* a convenience only */ } }
  // Our errors: 400 {"error"}; 404/409/502 {"detail"}; 422 {"detail": [{msg}]}.
  const errorOf = (body, fallback) => (body && (body.error || F.apiError(body))) || fallback;
  async function call(url, opts = {}) {
    const res = await fetch(url, { headers: { "content-type": "application/json" }, ...opts });
    let body = null;
    try { body = await res.json(); } catch { body = null; }
    if (!res.ok) throw new Error(errorOf(body, `${res.status} ${res.statusText}`));
    return body;
  }

  let view = null;   // the run view last rendered
  let draft = {};    // criterion id -> {mode: "agree"|"disagree"|"", score, reason, refs}; kept across re-renders
  let draftFor = null;
  let streaming = false;

  F.onView.push((v) => { view = v; renderRevision(v.scorecard); renderCard(v); });

  // ---------- scorecard notes: revision badge, original judgement, guidance error ----------
  function renderRevision(card) {
    const box = $("revision");
    box.replaceChildren();
    if (!card) { box.hidden = true; return; }
    const rev = card.revision;
    if (rev) {
      box.append(el("div", { class: "d-flex flex-wrap align-items-center gap-2" },
        el("span", { class: "badge bg-orange-lt text-wrap text-start lh-base" }, icon("user-check", "me-1"), `Revised after human review by ${rev.reviewer}, ${when(rev.at)}`),
        el("button", { type: "button", class: "btn btn-link btn-sm p-0", onclick: () => openOriginal(rev.previous) }, "View the original judgement")));
    }
    if (card.guidance_error) {
      box.append(el("div", { class: "alert alert-warning small mt-2 mb-0" }, icon("alert-triangle", "me-1"),
        `Guidance wasn't used: ${card.guidance_error}`));
    }
    box.hidden = !box.childNodes.length;
  }

  async function openOriginal(judgedAt) {
    const dlg = $("original-dialog"), body = $("original-body");
    body.replaceChildren(el("div", { class: "text-secondary", text: "Loading…" }));
    dlg.showModal();
    try {
      const jd = await call(`/api/runs/${view.run.id}/judgements/${encodeURIComponent(judgedAt)}`);
      const p = jd.panel || {};
      const judges = ((jd.passes || [{}])[0].judges || []).filter((j) => j.status === "ok");
      body.replaceChildren(
        el("div", { class: "text-secondary mb-2" }, `Judged ${when(jd.judged_at)} · score ${p.overall == null ? "n/a" : Math.round(p.overall)} · ${p.verdict || ""}`,
          jd.guidance ? ` · guidance v${jd.guidance.version}` : " · no guidance"),
        el("div", { class: "list-group list-group-flush" }, ...(p.criteria || []).filter((c) => c.kind === "judged").map((c) =>
          el("div", { class: "list-group-item px-0" },
            el("div", { class: "d-flex align-items-center gap-2" },
              el("strong", { text: human(c.id) }),
              el("span", { class: "ms-auto votes" }, Object.entries(c.votes || {}).map(([k, v]) => el("span", { class: `vote vote-${v}`, title: `${k}: ${v}` }, v))),
              el("span", { class: "badge bg-secondary-lt", text: `median ${c.median}` })),
            ...judges.map((j) => el("div", { class: "rationale" }, el("strong", { text: j.key }), ` (${(j.scores || {})[c.id] ?? "–"}) `,
              (j.rationales || {})[c.id] || ""))))));
    } catch (e) {
      body.replaceChildren(el("div", { class: "alert alert-danger mb-0", text: `Couldn't load the original judgement: ${e.message}` }));
    }
  }
  $("original-close").addEventListener("click", () => $("original-dialog").close());

  // ---------- the review card ----------
  const scaleOf = (card, cid) => {
    const keys = Object.keys((card.anchors || {})[cid] || {}).map(Number).filter((n) => !isNaN(n)).sort((a, b) => a - b);
    return keys.length ? keys : [0, 1, 2];
  };

  function renderCard(v) {
    const card = v.scorecard;
    const box = $("review-card");
    const reviewable = card && card.verdict !== "not scored" && (v.kpis || {}).verdict !== "not scored";
    box.hidden = !reviewable;
    if (!reviewable || streaming) return;
    if (draftFor !== `${v.run.id}@${card.judged_at}`) { draft = {}; draftFor = `${v.run.id}@${card.judged_at}`; }
    const judged = card.criteria.filter((c) => c.kind === "judged");
    const err = el("div", { class: "alert alert-danger", hidden: true });
    const ok = el("div", { class: "alert alert-success", hidden: true });
    const name = el("input", { class: "form-control", id: "review-name", maxlength: 80, placeholder: "Ada", value: getName(), autocomplete: "name" });
    name.addEventListener("input", () => setName(name.value.trim()));
    const note = el("textarea", { class: "form-control", id: "review-note", rows: 2, maxlength: 4000, placeholder: "Anything the judges should weigh overall (they see it)." });
    const measured = el("textarea", { class: "form-control", id: "review-measured", rows: 2, maxlength: 4000, placeholder: "On claim provenance or area compliance (stored and shown, never sent to a judge)." });
    const submit = el("button", { type: "submit", class: "btn btn-primary" }, icon("send", "me-1"), "Submit review");

    const form = el("form", { class: "mb-4", novalidate: true },
      el("div", { class: "row g-2 mb-3" },
        el("div", { class: "col-12 col-md-4" }, el("label", { class: "form-label", for: "review-name", text: "Your name" }), name),
        el("div", { class: "col-12 col-md-8 d-flex align-items-end" },
          el("div", { class: "small text-secondary" }, `Reviewing the judgement of ${when(card.judged_at)}. Leave a criterion blank to skip it.`))),
      el("div", { class: "list-group list-group-flush border rounded mb-3" }, ...judged.map((c) => criterionRow(card, c))),
      el("div", { class: "row g-2 mb-3" },
        el("div", { class: "col-12 col-lg-6" }, el("label", { class: "form-label", for: "review-note", text: "Overall note" }), note),
        el("div", { class: "col-12 col-lg-6" }, el("label", { class: "form-label", for: "review-measured", text: "Measured checks note" }), measured)),
      err, ok,
      el("div", { class: "d-flex" }, submit));
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      err.hidden = true; ok.hidden = true;
      const criteria = {};
      for (const [cid, d] of Object.entries(draft)) {
        if (d.mode === "agree") criteria[cid] = { agree: true, refs: splitRefs(d.refs) };
        else if (d.mode === "disagree") criteria[cid] = { agree: false, score: d.score === "" || d.score == null ? null : Number(d.score), reason: d.reason || "", refs: splitRefs(d.refs) };
      }
      submit.disabled = true;
      try {
        await call(`/api/runs/${v.run.id}/reviews`, { method: "POST", body: JSON.stringify({ reviewer: name.value.trim(), criteria, note: note.value, measured_note: measured.value }) });
        draft = {};
        const fresh = await call(`/api/runs/${v.run.id}`);
        F.renderScorecard(fresh.scorecard);
        view = fresh;
        renderRevision(fresh.scorecard);
        renderCard(fresh);
        const msg = $("review-ok");
        if (msg) { msg.hidden = false; msg.textContent = "Review saved. Ask the judges to reconsider below, or leave it as a record."; }
      } catch (e) {
        err.hidden = false; err.textContent = e.message;
        submit.disabled = false;
      }
    });
    ok.id = "review-ok";
    $("review-body").replaceChildren(form, reviewsList(v));
  }

  const splitRefs = (s) => String(s || "").split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);

  function criterionRow(card, c) {
    const d = draft[c.id] || (draft[c.id] = { mode: "", score: "", reason: "", refs: "" });
    const extra = el("div", { class: "row g-2 mt-1", hidden: d.mode !== "disagree" });
    const refsAgree = el("div", { class: "mt-1", hidden: d.mode !== "agree" });
    const btn = (mode, label, cls) => {
      const b = el("button", { type: "button", class: `btn btn-sm ${d.mode === mode ? cls : "btn-outline-secondary"}`, "aria-pressed": String(d.mode === mode) }, label);
      b.addEventListener("click", () => {
        d.mode = d.mode === mode ? "" : mode;
        const fresh = criterionRow(card, c);
        row.replaceWith(fresh);
      });
      return b;
    };
    const id = (k) => `rv-${c.id}-${k}`;
    const score = el("select", { class: "form-select form-select-sm", id: id("score") },
      el("option", { value: "", text: "Score…" }),
      ...scaleOf(card, c.id).map((n) => el("option", { value: String(n), text: `${n}${((card.anchors || {})[c.id] || {})[n] ? ` · ${((card.anchors || {})[c.id] || {})[n].slice(0, 60)}…` : ""}` })));
    score.value = d.score === "" ? "" : String(d.score);
    score.addEventListener("change", () => (d.score = score.value));
    const reason = el("textarea", { class: "form-control form-control-sm", id: id("reason"), rows: 2, maxlength: 2000, placeholder: "Why the steps support a different score." });
    reason.value = d.reason;
    reason.addEventListener("input", () => (d.reason = reason.value));
    const refsInput = (k) => {
      const r = el("input", { class: "form-control form-control-sm", id: id(k), placeholder: "T3, M2" });
      r.value = d.refs;
      r.addEventListener("input", () => (d.refs = r.value));
      return r;
    };
    extra.append(
      el("div", { class: "col-12 col-md-3" }, el("label", { class: "form-label small mb-1", for: id("score"), text: "Your score" }), score),
      el("div", { class: "col-12 col-md-6" }, el("label", { class: "form-label small mb-1", for: id("reason"), text: "Reason" }), reason),
      el("div", { class: "col-12 col-md-3" }, el("label", { class: "form-label small mb-1", for: id("refs"), text: "Steps that show it" }), refsInput("refs")));
    refsAgree.append(el("div", { class: "d-flex align-items-center gap-2" },
      el("label", { class: "small text-secondary text-nowrap", for: id("arefs"), text: "Steps (optional)" }), refsInput("arefs")));
    const row = el("div", { class: "list-group-item" },
      el("div", { class: "d-flex flex-wrap align-items-center gap-2" },
        el("span", { class: "fw-semibold", text: human(c.id) }),
        el("span", { class: "badge bg-secondary-lt", title: "panel median (pass 1)", text: `panel ${c.median == null ? "n/a" : c.median}` }),
        el("span", { class: "small text-secondary d-none d-lg-inline text-truncate", style: "max-width: 40rem", text: c.question || "" }),
        el("div", { class: "btn-group ms-auto", role: "group", "aria-label": `${human(c.id)}: agree or disagree` },
          btn("agree", "Agree", "btn-success"), btn("disagree", "Disagree", "btn-warning"))),
      refsAgree, extra);
    return row;
  }

  function reviewsList(v) {
    const card = v.scorecard;
    const reviews = card.reviews || [];
    const wrap = el("div", {}, el("h4", { class: "mb-2" }, `Reviews of this run (${reviews.length})`));
    if (!reviews.length) { wrap.append(el("div", { class: "text-secondary small", text: "No reviews yet." })); return wrap; }
    if (!card.reconsider_enabled) wrap.append(el("div", { class: "small text-secondary mb-2", text: "Reconsideration is switched off for this deployment." }));
    const list = el("div", { class: "list-group" });
    for (const rv of reviews) {
      const log = el("div", { class: "small mt-2", hidden: true });
      const badges = [
        !rv.current ? el("span", { class: "badge bg-secondary-lt", text: "reviews an older judgement" }) : null,
        rv.reconsidered ? el("span", { class: "badge bg-green-lt", text: `reconsidered ${when(rv.reconsidered)}` }) : null,
        rv.guidance_version != null ? el("span", { class: "badge bg-azure-lt", text: `guidance v${rv.guidance_version}` }) : null,
      ];
      const crits = Object.entries(rv.criteria || {}).map(([cid, c]) => el("div", { class: "rationale" },
        el("strong", { text: human(cid) }), " ",
        c.agree ? el("span", { class: "badge bg-success-lt", text: `agrees (${c.panel_median})` })
          : el("span", { class: "badge bg-warning-lt", text: `${c.panel_median} → ${c.score}` }),
        c.reason ? ` ${c.reason}` : "",
        (c.refs || []).length ? el("span", { class: "text-secondary", text: ` · ${c.refs.join(", ")}` }) : null));
      const item = el("div", { class: "list-group-item" },
        el("div", { class: "d-flex flex-wrap align-items-center gap-2" },
          el("strong", { text: rv.reviewer }), el("span", { class: "text-secondary small", text: when(rv.created_at) }), ...badges,
          el("span", { class: "text-secondary small ms-auto font-monospace", text: rv.id })),
        ...crits,
        rv.note ? el("div", { class: "small mt-1" }, el("span", { class: "text-secondary", text: "Note: " }), rv.note) : null,
        rv.measured_note ? el("div", { class: "small mt-1" }, el("span", { class: "text-secondary", text: "Measured checks: " }), rv.measured_note) : null);
      if (rv.current && !rv.reconsidered && card.reconsider_enabled) {
        const b = el("button", { type: "button", class: "btn btn-sm btn-primary mt-2" }, icon("gavel", "me-1"), "Ask the judges to reconsider");
        b.addEventListener("click", () => reconsider(v.run.id, rv.id, b, log));
        item.append(b);
      }
      item.append(log);
      list.append(item);
    }
    wrap.append(list);
    return wrap;
  }

  // ---------- reconsideration: POST, then follow the run's event stream in the card ----------
  async function reconsider(runId, reviewId, button, log) {
    button.disabled = true;
    log.hidden = false;
    const line = (text, cls = "") => log.append(el("div", { class: cls }, text));
    log.replaceChildren();
    try {
      await call(`/api/runs/${runId}/reviews/${reviewId}/reconsider`, { method: "POST" });
    } catch (e) {
      line(e.message, "text-danger");
      button.disabled = false;
      return;
    }
    streaming = true;
    const spin = el("div", { class: "d-flex align-items-center gap-2 text-secondary" }, el("span", { class: "spinner-border spinner-border-sm" }), "Asking the judges…");
    log.append(spin);
    const es = new EventSource(`/api/runs/${runId}/events`);
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      if (ev.type === "judging") {
        F.judgeRows(ev.seats);
        line(`${ev.seats.length} judges reconsider: ${ev.seats.map((s) => s.key).join(", ")}${ev.guidance ? ` (guidance v${ev.guidance})` : ""}`);
      } else if (ev.type === "judge") {
        F.judgeResult(ev);
        line(ev.status === "ok" ? `${ev.key}${ev.stood_in_for ? ` (for ${ev.stood_in_for})` : ""}: ${Math.round(ev.score)}` : `${ev.key} failed: ${ev.error || ""}`,
          ev.status === "ok" ? "" : "text-danger");
      } else if (ev.type === "done") {
        es.close();
        streaming = false;
        spin.remove();
        if (ev.error || !ev.view) {
          line(`Reconsideration failed: ${ev.error || "no result"}. The judgement is unchanged.`, "text-danger");
          button.disabled = false;
          return;
        }
        F.renderView(ev.view);  // re-renders this card too, via onView
      }
    };
    es.onerror = () => { /* EventSource retries; the server ends the stream after "done" */ };
  }
})();
