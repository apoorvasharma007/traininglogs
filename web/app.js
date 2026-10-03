(function () {
  const apiBaseInput = document.getElementById("apiBase");
  const apiKeyInput = document.getElementById("apiKey");
  const contentInput = document.getElementById("content");
  const extractBtn = document.getElementById("extractBtn");
  const statusEl = document.getElementById("status");
  const outputEl = document.getElementById("output");
  const cardEl = document.getElementById("card");
  const composerEl = document.getElementById("composer");
  const corrInputEl = document.getElementById("corrInput");
  const corrSendBtn = document.getElementById("corrSend");
  const correctionsLogEl = document.getElementById("correctionsLog");
  const corrStatusEl = document.getElementById("corrStatus");
  const confirmBarEl = document.getElementById("confirmBar");
  const confirmBtn = document.getElementById("confirmBtn");
  const editNoteBtn = document.getElementById("editNoteBtn");
  const errorBoxEl = document.getElementById("errorBox");
  const errorTitleEl = document.getElementById("errorTitle");
  const errorDetailEl = document.getElementById("errorDetail");
  const confirmedScreenEl = document.getElementById("confirmedScreen");
  const confirmedSidEl = document.getElementById("confirmedSid");
  const logAnotherBtn = document.getElementById("logAnotherBtn");
  const repeatListEl = document.getElementById("repeatList");

  // The extraction being reviewed, and the client's current copy of its extract -- null means
  // "use the extraction's own stored reading," which is only true before the first correction.
  // Every /correct response's own `extract` becomes the new value, exactly the round-trip the
  // endpoint's statelessness was designed for: the server holds nothing between calls.
  let currentExtractionId = null;
  let currentExtract = null;
  // {at, source, edits} (+ instruction for AI corrections) per applied change -- typed
  // corrections and direct edits alike -- accumulated here and sent as ConfirmIn.corrections on
  // /confirm, which records them alongside the extraction.
  let corrections = [];

  // Editable fields per kind of card line, for building the edit form. Presentation only --
  // labels and input types. The server's EDITABLE_FIELDS (agent/card_edits.py) decides what
  // can actually be edited; a field listed here but not there gets a 400 and nothing is saved.
  // `aliases` are the extract names the model may have flagged as uncertain for this field.
  const FIELD_SPECS = {
    session: [
      { field: "focus", label: "Focus", type: "text" },
      { field: "date", label: "Date", type: "date" },
      { field: "duration_minutes", label: "Duration (min)", type: "int",
        aliases: ["session_duration_minutes"] },
      { field: "program", label: "Program", type: "text" },
      { field: "phase", label: "Phase", type: "int" },
      { field: "week", label: "Week", type: "int" },
      { field: "is_deload_week", label: "Deload week", type: "checkbox" },
      { field: "notes", label: "Session notes", type: "text", wide: true },
    ],
    exercise: [
      { field: "name", label: "Name", type: "text", wide: true },
      { field: "notes", label: "Notes", type: "text", wide: true },
      { field: "warmup_notes", label: "Warmup notes", type: "text", wide: true },
    ],
    set: [
      { field: "weight_kg", label: "Weight (kg)", type: "number" },
      { field: "reps", label: "Reps", type: "text", placeholder: "8, 8+1, L8/R7",
        aliases: ["rep_count", "unilateral_rep_count"] },
      { field: "rpe", label: "RPE", type: "number" },
      { field: "quality", label: "Quality", type: "select",
        options: ["", "perfect", "good", "learning", "bad"], aliases: ["rep_quality_assessment"] },
      { field: "duration_seconds", label: "Duration (s)", type: "int" },
      { field: "distance_meters", label: "Distance (m)", type: "number" },
      { field: "heart_rate_bpm", label: "Heart rate", type: "int" },
      { field: "notes", label: "Notes", type: "text", wide: true },
    ],
    warmup_set: [
      { field: "weight_kg", label: "Weight (kg)", type: "number" },
      { field: "rep_count", label: "Reps", type: "int" },
      { field: "notes", label: "Notes", type: "text", wide: true },
    ],
    movement: [
      { field: "name", label: "Name", type: "text", wide: true },
      { field: "reps", label: "Reps", type: "int" },
      { field: "duration_seconds", label: "Duration (s)", type: "int" },
      { field: "notes", label: "Notes", type: "text", wide: true },
    ],
  };

  // Add/remove buttons shown in each kind of line's form: [op, label]. The server decides
  // what each op may be applied to (card_edits.apply_card_op).
  const FORM_OPS = {
    session: [],
    exercise: [["remove", "Remove exercise"]],
    set: [["add_set", "+ Set after this"], ["remove", "Remove set"]],
    warmup_set: [["add_warmup_set", "+ Warmup set after"], ["remove", "Remove"]],
    movement: [["remove", "Remove"]],
  };

  // path -> {kind, values, uncertain} for every editable line in the current render. Rebuilt
  // by renderCard, read when a line is tapped.
  let editables = new Map();
  let openForm = null;

  // Notes from the session being repeated, shown read-only as "last time" -- never copied into
  // the new session (a note belongs to the day it was written). null outside a repeat.
  // {session: string|null, byExercise: Map(lowercased name -> [string])}
  let lastTime = null;

  // Served by the API itself, so its own origin is the default; a saved value (e.g. pointing
  // at a local server) still wins.
  apiBaseInput.value = localStorage.getItem("tl_apiBase") || window.location.origin;
  apiKeyInput.value = localStorage.getItem("tl_apiKey") || "";
  apiBaseInput.addEventListener("change", () => localStorage.setItem("tl_apiBase", apiBaseInput.value));
  apiKeyInput.addEventListener("change", () => localStorage.setItem("tl_apiKey", apiKeyInput.value));

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = isError ? "status error" : "status";
  }

  function showRawOutput(data) {
    outputEl.textContent = JSON.stringify(data, null, 2);
  }

  function showError(title, detail) {
    errorTitleEl.textContent = title;
    errorDetailEl.textContent = detail || "";
    errorBoxEl.className = "error-box active";
  }

  function hideError() {
    errorBoxEl.className = "error-box";
  }

  async function apiFetch(path, options) {
    const base = apiBaseInput.value.replace(/\/$/, "");
    const res = await fetch(base + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Api-Key": apiKeyInput.value,
        ...(options && options.headers),
      },
    });
    const body = await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, body };
  }

  extractBtn.addEventListener("click", async () => {
    const content = contentInput.value.trim();
    if (!content) {
      setStatus("Enter some session notes first.", true);
      return;
    }

    extractBtn.disabled = true;
    resetReview();
    setStatus("Saving...");

    const capture = await apiFetch("/inputs", {
      method: "POST",
      body: JSON.stringify({ content }),
    });

    // capture()'s response always carries raw_input_id once the text is saved, even when
    // extraction then fails (HTTP 502) -- checking capture.ok first would treat that case as an
    // opaque request failure and lose both the raw_input_id and the actual error message, which
    // is exactly the "console error instead of a UI state" this step exists to fix.
    if (!capture.body || !capture.body.raw_input_id) {
      setStatus(
        `POST /inputs failed (${capture.status}): ${
          capture.body && capture.body.detail ? capture.body.detail : "unknown error"
        }`,
        true
      );
      showRawOutput(capture.body);
      extractBtn.disabled = false;
      return;
    }

    const { raw_input_id, extraction_id, error } = capture.body;

    if (error || !extraction_id) {
      setStatus(
        `Saved (raw_input_id: ${raw_input_id}) but extraction failed (${capture.status}): ${error}`,
        true
      );
      extractBtn.disabled = false;
      return;
    }

    setStatus(`Extracted (extraction_id: ${extraction_id}). Fetching card...`);
    await loadCard(extraction_id);
    extractBtn.disabled = false;
  });

  // Clears the review area before a new card: extraction or repeat alike.
  function resetReview() {
    cardEl.className = "";
    cardEl.innerHTML = "";
    outputEl.textContent = "";
    correctionsLogEl.innerHTML = "";
    composerEl.style.display = "none";
    confirmBarEl.style.display = "none";
    confirmedScreenEl.className = "";
    corrStatusEl.textContent = "";
    hideError();
    currentExtractionId = null;
    currentExtract = null;
    corrections = [];
    lastTime = null;
  }

  // Fetches a pending extraction's card and opens it for review.
  async function loadCard(extractionId) {
    const extraction = await apiFetch(`/extractions/${extractionId}`, { method: "GET" });
    if (!extraction.ok) {
      setStatus(`GET /extractions/${extractionId} failed (${extraction.status}).`, true);
      showRawOutput(extraction.body);
      return false;
    }
    setStatus(`Done. extraction_id: ${extractionId}`);
    showRawOutput(extraction.body);
    currentExtractionId = extractionId;
    renderCard(extraction.body);
    composerEl.style.display = "flex";
    confirmBarEl.style.display = "flex";
    return true;
  }

  // ---- repeat a past session ----

  async function loadRecentSessions() {
    if (!apiKeyInput.value) return;
    const result = await apiFetch("/sessions?limit=15", { method: "GET" });
    if (!result.ok) {
      repeatListEl.innerHTML = `<div class="status error">Couldn't load sessions (${result.status}).</div>`;
      return;
    }
    repeatListEl.innerHTML = result.body.length
      ? result.body.map((s) => `
          <button type="button" class="repeat-item" data-session-id="${esc(s.session_id)}">
            <span class="r-date">${esc(s.date)}</span>
            <span class="r-focus">${esc(s.focus || "Session")}</span>
            <span class="r-ex">${esc((s.exercises || []).join(" · "))}</span>
          </button>`).join("")
      : '<div class="status">No sessions yet.</div>';
  }

  repeatListEl.addEventListener("click", async (e) => {
    const item = e.target.closest("[data-session-id]");
    if (!item) return;
    const sessionId = item.dataset.sessionId;
    resetReview();
    setStatus("Starting from that session...");

    const result = await apiFetch(`/sessions/${encodeURIComponent(sessionId)}/repeat`, { method: "POST" });
    if (!result.ok) {
      setStatus(`Couldn't repeat that session (${result.status}).`, true);
      return;
    }
    // Last time's notes first, so the card's first render already shows them.
    const source = await apiFetch(`/sessions/${encodeURIComponent(sessionId)}`, { method: "GET" });
    lastTime = source.ok ? lastTimeNotes(source.body) : null;
    if (await loadCard(result.body.extraction_id)) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  function lastTimeNotes(session) {
    const byExercise = new Map();
    (session.exercises || []).forEach((ex) => {
      const parts = [];
      if (ex.notes) parts.push(ex.notes);
      if (ex.warmup_notes) parts.push(`warmup: ${ex.warmup_notes}`);
      (ex.warmup_sets || []).forEach((w) => { if (w.notes) parts.push(`warmup ${w.number}: ${w.notes}`); });
      (ex.sets || []).forEach((s) => { if (s.notes) parts.push(`set ${s.number}: ${s.notes}`); });
      if (parts.length) byExercise.set(ex.name.toLowerCase(), parts);
    });
    return { session: session.notes || null, byExercise };
  }

  function lastTimeHtml(parts) {
    return parts && parts.length
      ? `<div class="last-time">Last time: ${parts.map(esc).join(" · ")}</div>` : "";
  }

  apiKeyInput.addEventListener("change", loadRecentSessions);
  loadRecentSessions();

  // ---- correction loop ----

  async function applyCorrection() {
    const instruction = corrInputEl.value.trim();
    if (!instruction) return;

    corrInputEl.disabled = true;
    corrSendBtn.disabled = true;
    corrStatusEl.textContent = "Applying correction...";
    corrStatusEl.className = "status";

    const result = await apiFetch(`/extractions/${currentExtractionId}/correct`, {
      method: "POST",
      body: JSON.stringify({ extract: currentExtract, instruction }),
    });

    corrInputEl.disabled = false;
    corrSendBtn.disabled = false;

    if (!result.ok) {
      const detail = result.body && result.body.detail ? result.body.detail : "unknown error";
      const prefix = result.status === 400 ? "Couldn't apply that correction" : "Correction service failed";
      corrStatusEl.textContent = `${prefix} (${result.status}): ${detail}`;
      corrStatusEl.className = "status error";
      return;
    }

    corrStatusEl.textContent = "";
    applyUpdate(result.body);
    corrInputEl.value = "";
    corrInputEl.focus();
  }

  // A /correct or /edit reply -- both share one shape (CorrectOut) and are handled identically.
  function applyUpdate(body) {
    currentExtract = body.extract;
    corrections.push(body.correction);
    showRawOutput(body);
    renderCard(body.card);
    appendCorrectionRow(body.correction);
  }

  function appendCorrectionRow(correction) {
    const row = document.createElement("div");
    row.className = "corr-row";
    const editSummary = (correction.edits || [])
      .map((e) => `${e.path} → ${JSON.stringify(e.value)}`)
      .join(", ");
    const label = correction.source === "manual"
      ? "Edited"
      : `"${esc(correction.instruction)}"`;
    row.innerHTML = `<span class="ico">✓</span><span>${label}${
      editSummary ? ` — ${esc(editSummary)}` : ""
    }</span>`;
    correctionsLogEl.appendChild(row);
  }

  // ---- direct editing ----

  cardEl.addEventListener("click", (e) => {
    if (e.target.closest(".edit-form")) return;
    const opBtn = e.target.closest("[data-op]");
    if (opBtn) {
      runOp(opBtn.dataset.op, opBtn.dataset.opPath, null);
      return;
    }
    const line = e.target.closest("[data-path]");
    if (!line) return;
    const tapped = e.target.closest("[data-field]");
    openEditor(line, tapped ? tapped.dataset.field : null);
  });

  function inputValue(spec, value) {
    if (value === null || value === undefined) return "";
    return String(value);
  }

  function fieldHtml(spec, value, uncertain) {
    const id = `edit-${spec.field}`;
    const cls = ["edit-field", spec.wide ? "wide" : "", uncertain ? "uncertain" : ""].join(" ");
    let control;
    if (spec.type === "checkbox") {
      control = `<input id="${id}" data-field="${spec.field}" type="checkbox"${value ? " checked" : ""}>`;
    } else if (spec.type === "select") {
      const current = inputValue(spec, value);
      control = `<select id="${id}" data-field="${spec.field}">${spec.options
        .map((o) => `<option value="${esc(o)}"${o === current ? " selected" : ""}>${esc(o || "—")}</option>`)
        .join("")}</select>`;
    } else {
      const typeAttr = spec.type === "date" ? "date" : "text";
      const mode = spec.type === "int" ? ' inputmode="numeric"'
        : spec.type === "number" ? ' inputmode="decimal"' : "";
      const ph = spec.placeholder ? ` placeholder="${esc(spec.placeholder)}"` : "";
      control = `<input id="${id}" data-field="${spec.field}" type="${typeAttr}"${mode}${ph} value="${esc(inputValue(spec, value))}">`;
    }
    return `<div class="${cls}"><label for="${id}">${esc(spec.label)}${
      uncertain ? ' <span class="flag">AI inferred</span>' : ""
    }</label>${control}</div>`;
  }

  function openEditor(line, focusField) {
    closeEditor();
    const entry = editables.get(line.dataset.path);
    if (!entry) return;
    const specs = FIELD_SPECS[entry.kind];
    const isUncertain = (spec) =>
      [spec.field, ...(spec.aliases || [])].some((f) => entry.uncertain.includes(f));

    const form = document.createElement("div");
    form.className = "edit-form";
    form.innerHTML = `
      <div class="edit-fields">${specs
        .map((s) => fieldHtml(s, entry.values[s.field], isUncertain(s)))
        .join("")}</div>
      <div class="edit-error" role="alert"></div>
      <div class="edit-actions">
        ${FORM_OPS[entry.kind]
          .map(([op, label]) => `<button type="button" class="btn-ghost${op === "remove" ? " danger" : ""}" data-form-op="${op}">${label}</button>`)
          .join("")}
        <span class="spacer"></span>
        <button type="button" class="btn-ghost" data-action="cancel">Cancel</button>
        <button type="button" class="btn-primary" data-action="save">Save</button>
      </div>`;
    line.after(form);
    line.hidden = true;
    openForm = { form, line, entry, path: line.dataset.path };

    form.addEventListener("click", (e) => {
      const action = e.target.dataset && e.target.dataset.action;
      if (action === "cancel") closeEditor();
      if (action === "save") saveEditor();
      const op = e.target.dataset && e.target.dataset.formOp;
      if (!op) return;
      // Remove asks once more, in place, before anything is sent.
      if (op === "remove" && e.target.dataset.armed !== "1") {
        e.target.dataset.armed = "1";
        e.target.textContent = "Really remove?";
        return;
      }
      runOp(op, openForm.path, form.querySelector(".edit-error"));
    });
    form.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeEditor();
      if (e.key === "Enter" && e.target.tagName !== "BUTTON") { e.preventDefault(); saveEditor(); }
    });

    const target = (focusField && form.querySelector(`[data-field="${focusField}"]`))
      || form.querySelector(".uncertain [data-field]")
      || form.querySelector("[data-field]");
    target.focus();
    if (target.select) target.select();
  }

  function closeEditor() {
    if (!openForm) return;
    openForm.form.remove();
    openForm.line.hidden = false;
    openForm = null;
  }

  function changedEdits() {
    const { form, entry, path } = openForm;
    const edits = [];
    FIELD_SPECS[entry.kind].forEach((spec) => {
      const input = form.querySelector(`[data-field="${spec.field}"]`);
      const before = entry.values[spec.field];
      if (spec.type === "checkbox") {
        if (input.checked !== Boolean(before)) edits.push({ path, field: spec.field, value: input.checked });
      } else if (input.value.trim() !== inputValue(spec, before)) {
        edits.push({ path, field: spec.field, value: input.value.trim() });
      }
    });
    return edits;
  }

  async function saveEditor() {
    const { form } = openForm;
    const edits = changedEdits();
    if (!edits.length) { closeEditor(); return; }

    const errorEl = form.querySelector(".edit-error");
    const controls = form.querySelectorAll("input, select, button");
    controls.forEach((c) => { c.disabled = true; });
    errorEl.textContent = "Saving...";

    const result = await apiFetch(`/extractions/${currentExtractionId}/edit`, {
      method: "POST",
      body: JSON.stringify({ extract: currentExtract, edits }),
    });

    if (!result.ok) {
      controls.forEach((c) => { c.disabled = false; });
      const detail = result.body && result.body.detail;
      errorEl.textContent = typeof detail === "string"
        ? detail
        : `Couldn't save (${result.status})`;
      return;
    }

    openForm = null;
    applyUpdate(result.body);
  }

  // Add or remove one line. `errorEl` is the open form's error line when the op came from a
  // form; otherwise errors go to the status line under the corrections box.
  async function runOp(op, path, errorEl) {
    const show = (text) => {
      if (errorEl) errorEl.textContent = text;
      else { corrStatusEl.textContent = text; corrStatusEl.className = text ? "status error" : "status"; }
    };
    show("");
    const result = await apiFetch(`/extractions/${currentExtractionId}/edit`, {
      method: "POST",
      body: JSON.stringify({ extract: currentExtract, op: { op, path } }),
    });
    if (!result.ok) {
      const detail = result.body && result.body.detail;
      show(typeof detail === "string" ? detail : `Couldn't change the card (${result.status})`);
      return;
    }
    applyUpdate(result.body);
    // A new line opens straight into its form, ready for its real values.
    if (result.body.created_path != null) {
      const line = cardEl.querySelector(`[data-path="${CSS.escape(result.body.created_path)}"]`);
      if (line) openEditor(line, null);
    }
  }

  corrSendBtn.addEventListener("click", applyCorrection);
  corrInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") applyCorrection();
  });

  // ---- confirm ----

  confirmBtn.addEventListener("click", async () => {
    hideError();
    confirmBtn.disabled = true;
    editNoteBtn.disabled = true;
    setStatus("Confirming...");

    const result = await apiFetch(`/extractions/${currentExtractionId}/confirm`, {
      method: "POST",
      body: JSON.stringify({
        extract: currentExtract,
        corrections: corrections.length ? corrections : undefined,
      }),
    });

    confirmBtn.disabled = false;
    editNoteBtn.disabled = false;

    if (!result.ok) {
      const detail = result.body && result.body.detail ? result.body.detail : "unknown error";
      if (result.status === 409) {
        showError(
          "This session already exists",
          `${detail} Use the correction box above to fix the date, then confirm again.`
        );
      } else {
        showError(`Confirm failed (${result.status})`, detail);
      }
      setStatus("");
      return;
    }

    setStatus("");
    cardEl.className = "";
    composerEl.style.display = "none";
    confirmBarEl.style.display = "none";
    correctionsLogEl.innerHTML = "";
    confirmedSidEl.textContent = result.body.session_id;
    confirmedScreenEl.className = "active";
  });

  editNoteBtn.addEventListener("click", () => {
    contentInput.focus();
    contentInput.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  logAnotherBtn.addEventListener("click", () => {
    contentInput.value = "";
    cardEl.innerHTML = "";
    cardEl.className = "";
    correctionsLogEl.innerHTML = "";
    outputEl.textContent = "";
    composerEl.style.display = "none";
    confirmBarEl.style.display = "none";
    confirmedScreenEl.className = "";
    hideError();
    setStatus("");
    currentExtractionId = null;
    currentExtract = null;
    corrections = [];
    lastTime = null;
    loadRecentSessions();
    contentInput.focus();
  });

  // ---- card rendering ----

  function esc(s) {
    if (s === null || s === undefined) return "";
    const div = document.createElement("div");
    div.textContent = String(s);
    return div.innerHTML;
  }

  function fmtDuration(seconds) {
    if (seconds === null || seconds === undefined) return null;
    if (seconds >= 60) {
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${m}:${String(s).padStart(2, "0")}`;
    }
    return `${seconds}s`;
  }

  function fmtGoal(g) {
    if (!g) return "";
    const parts = [];
    if (g.sets != null) parts.push(`${g.sets} sets`);
    if (g.rep_range_min != null || g.rep_range_max != null) {
      if (g.rep_range_min != null && g.rep_range_max != null && g.rep_range_min !== g.rep_range_max) {
        parts.push(`${g.rep_range_min}-${g.rep_range_max} reps`);
      } else {
        parts.push(`${g.rep_range_min ?? g.rep_range_max} reps`);
      }
    }
    if (g.weight_kg != null) parts.push(`${g.weight_kg}kg`);
    if (g.distance_meters != null) parts.push(`${g.distance_meters}m`);
    if (g.target_duration_seconds != null) parts.push(fmtDuration(g.target_duration_seconds));
    if (g.rest_minutes != null || g.rest_seconds != null) {
      const restParts = [];
      if (g.rest_minutes) restParts.push(`${g.rest_minutes}m`);
      if (g.rest_seconds) restParts.push(`${g.rest_seconds}s`);
      parts.push(`rest ${restParts.join(" ")}`);
    }
    return parts.length ? "Goal: " + parts.join(" · ") : "";
  }

  // Marks a line as editable: `data-path` finds it in `editables` when tapped. Lines without a
  // path (none, from the builder -- but rows built by hand could) stay plain text.
  function editable(path, kind, values, uncertain) {
    if (path === null || path === undefined) return "";
    editables.set(path, { kind, values, uncertain: uncertain || [] });
    return ` data-path="${esc(path)}"`;
  }

  // Wraps one displayed value so a tap on it focuses that field in the edit form.
  function val(field, html) {
    return `<span data-field="${field}">${html}</span>`;
  }

  function setValsHtml(row) {
    const parts = [];
    if (row.weight_kg != null) parts.push(val("weight_kg", `${esc(row.weight_kg)}kg`));
    if (row.reps != null) parts.push(val("reps", `× ${esc(row.reps)}`));
    if (row.duration_seconds != null) parts.push(val("duration_seconds", fmtDuration(row.duration_seconds)));
    if (row.distance_meters != null) parts.push(val("distance_meters", `${esc(row.distance_meters)}m`));
    if (row.heart_rate_bpm != null) parts.push(val("heart_rate_bpm", `${esc(row.heart_rate_bpm)}bpm`));
    let html = parts.join(" ");
    if (row.rpe != null) html += ` <span class="chip" data-field="rpe">RPE ${esc(row.rpe)}</span>`;
    if (row.quality) html += ` <span class="chip" data-field="quality">${esc(row.quality)}</span>`;
    if (row.failure_technique) html += ` <span class="chip">${esc(row.failure_technique)}</span>`;
    return html;
  }

  function warmupValsHtml(row) {
    const parts = [];
    if (row.weight_kg != null) parts.push(val("weight_kg", `${esc(row.weight_kg)}kg`));
    if (row.rep_count != null) parts.push(val("rep_count", `× ${esc(row.rep_count)}`));
    return parts.join(" ");
  }

  function setRowHtml(row, valsHtml) {
    const flag = row.uncertain_fields && row.uncertain_fields.length
      ? '<span class="flag">AI inferred</span>' : "<span></span>";
    const note = row.notes
      ? `<span class="note" data-field="notes">${esc(row.notes)}</span>` : "";
    return `
      <div class="set-row"${editable(row.path, "set", row, row.uncertain_fields)}>
        <span class="idx">${row.number}</span>
        <span class="vals">${valsHtml}</span>
        ${flag}
        ${note}
      </div>`;
  }

  function movementSectionHtml(section) {
    if (!section) return "";
    const rows = section.movements.map((m) => `
      <div class="movement-row"${editable(m.path, "movement", m)}>
        ${m.number}. ${val("name", esc(m.name))}${m.reps != null ? ` — ${val("reps", `× ${esc(m.reps)}`)}` : ""}${m.duration_seconds != null ? ` — ${val("duration_seconds", fmtDuration(m.duration_seconds))}` : ""}
        ${m.notes ? `<div class="m-note" data-field="notes">${esc(m.notes)}</div>` : ""}
      </div>`).join("");
    return `
      <div class="movement-block">
        <div class="m-title">${esc(section.title)}</div>
        ${rows}
      </div>`;
  }

  function exerciseCardHtml(ex) {
    const h = ex.header;
    const goalHtml = fmtGoal(h.goal);

    if (h.failed) {
      return `
        <div class="ex-card">
          <div class="ex-head">
            <span class="name">${h.number}. ${esc(h.name)}</span>
          </div>
          <div class="failed-note">Could not extract this exercise: ${esc(ex.failure_reason)}</div>
        </div>`;
    }

    const warmupHtml = ex.warmup_rows && ex.warmup_rows.length
      ? `
        <div class="sub-block">
          <div class="sb-title">Warmup</div>
          ${ex.warmup_rows.map((r) => `
            <div class="sub-row"${editable(r.path, "warmup_set", r, r.uncertain_fields)}>
              ${r.number}. ${warmupValsHtml(r)}
              ${r.uncertain_fields && r.uncertain_fields.length ? '<span class="flag">AI inferred</span>' : ""}
              ${r.notes ? `<div class="note" data-field="notes">${esc(r.notes)}</div>` : ""}
            </div>`).join("")}
        </div>` : "";

    // The header, notes and warmup notes are all the exercise's own fields: one path, one form.
    const exAttr = editable(h.path, "exercise", {
      name: h.name,
      notes: ex.note_preview ? ex.note_preview.full_text : null,
      warmup_notes: ex.warmup_note_preview ? ex.warmup_note_preview.full_text : null,
    }, h.uncertain_fields);

    const warmupNoteHtml = ex.warmup_note_preview
      ? `<div class="ex-note"${exAttr} data-field="warmup_notes">Warmup notes: ${esc(ex.warmup_note_preview.full_text)}</div>` : "";

    const setsHtml = (ex.working_set_rows || [])
      .map((r) => setRowHtml(r, setValsHtml(r)))
      .join("");

    const noteHtml = ex.note_preview
      ? `<div class="ex-note"${exAttr} data-field="notes">${esc(ex.note_preview.full_text)}</div>` : "";

    return `
      <div class="ex-card">
        <div class="ex-head"${exAttr} data-field="name">
          <span class="name">${h.number}. ${esc(h.name)}</span>
          ${goalHtml ? `<span class="goal">${esc(goalHtml)}</span>` : ""}
        </div>
        ${lastTime ? lastTimeHtml(lastTime.byExercise.get(h.name.toLowerCase())) : ""}
        ${warmupHtml}
        ${warmupNoteHtml}
        ${setsHtml}
        ${noteHtml}
        ${h.path != null ? `
        <div class="add-row">
          <button type="button" class="btn-ghost btn-small" data-op="add_set" data-op-path="${esc(h.path)}">+ Set</button>
          <button type="button" class="btn-ghost btn-small" data-op="add_warmup_set" data-op-path="${esc(h.path)}">+ Warmup set</button>
        </div>` : ""}
      </div>`;
  }

  function renderCard(card) {
    // innerHTML below replaces every line, so any open form and the old lookup go with it.
    openForm = null;
    editables = new Map();
    const sh = card.session_header;
    const shAttr = editable(sh.path, "session", {
      ...sh,
      notes: card.note_preview ? card.note_preview.full_text : null,
    }, sh.uncertain_fields);
    const metaParts = [sh.date];
    if (sh.phase != null) metaParts.push(`Phase ${sh.phase}`);
    if (sh.week != null) metaParts.push(`Week ${sh.week}`);
    if (sh.duration_minutes != null) metaParts.push(`~${sh.duration_minutes} min`);
    if (card.exercises) metaParts.push(`${card.exercises.length} exercises`);
    if (sh.is_deload_week) metaParts.push("deload");

    const shFlags = sh.uncertain_fields && sh.uncertain_fields.length
      ? `<div class="sh-flags">${sh.uncertain_fields.map((f) => `<span class="flag">${esc(f)} inferred</span>`).join(" ")}</div>`
      : "";

    let html = `
      <div class="session-head"${shAttr}>
        <div class="focus">${esc(sh.focus || "Session")}</div>
        <div class="meta">${esc(metaParts.join(" · "))}</div>
        ${shFlags}
      </div>`;

    if (lastTime && lastTime.session) html += lastTimeHtml([lastTime.session]);

    if (card.warnings && card.warnings.length) {
      html += `
        <div class="warnings-box">
          <div class="w-title">Warnings</div>
          <ul>${card.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
        </div>`;
    }

    html += movementSectionHtml(card.warmup_section);

    if (card.note_preview) {
      html += `<div class="ex-note"${shAttr} data-field="notes">Session notes: ${esc(card.note_preview.full_text)}</div>`;
    }

    (card.exercises || []).forEach((ex) => {
      html += exerciseCardHtml(ex);
    });

    html += movementSectionHtml(card.cooldown_section);
    html += `<div class="add-row"><button type="button" class="btn-ghost btn-small" data-op="add_exercise" data-op-path="">+ Exercise</button></div>`;
    html += `<div class="edit-hint">Tap any line to edit it. For a change across many lines, describe it below.</div>`;

    cardEl.innerHTML = html;
    cardEl.className = "active";
  }

  // ---- progress (Phase 7) ----
  // Key lifts and other lifts from GET /progress/lifts; one lift's sessions and chart from
  // GET /progress/lifts/{name}. The server does every calculation; this only draws.

  const logViewEl = document.getElementById("logView");
  const progressViewEl = document.getElementById("progressView");
  const progressStatusEl = document.getElementById("progressStatus");
  const liftListEl = document.getElementById("liftList");
  const keyLiftsEl = document.getElementById("keyLifts");
  const otherLiftsEl = document.getElementById("otherLifts");
  const liftDetailEl = document.getElementById("liftDetail");
  let liftChart = null;

  document.querySelectorAll(".tabs [data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const progress = tab.dataset.tab === "progress";
      document.querySelectorAll(".tabs [data-tab]").forEach((t) => {
        t.setAttribute("aria-selected", String(t === tab));
      });
      logViewEl.hidden = progress;
      progressViewEl.hidden = !progress;
      if (progress) loadLifts();
    });
  });

  const TREND = { up: ["↑", "trend-up", "up"], flat: ["→", "trend-flat", "flat"], down: ["↓", "trend-down", "down"] };

  function liftValue(measure, value) {
    if (value === null || value === undefined) return null;
    return measure === "bodyweight_reps" ? `${value} reps` : `${value} kg`;
  }

  function liftCardHtml(lift) {
    const latest = liftValue(lift.measure, lift.latest);
    if (!lift.sessions || latest === null) {
      return `<button type="button" class="lift-card empty" data-lift="${esc(lift.name)}">
        <span class="l-name">${esc(lift.name)}</span>
        <span class="l-value">No countable sets yet</span></button>`;
    }
    const t = lift.trend ? TREND[lift.trend] : null;
    const label = lift.measure === "bodyweight_reps" ? "best reps at bodyweight" : "estimated max";
    return `<button type="button" class="lift-card" data-lift="${esc(lift.name)}">
      <span class="l-name">${esc(lift.name)}</span>
      <span class="l-value">${esc(latest)}${t ? ` <span class="${t[1]}" title="4-week trend: ${t[2]}">${t[0]}</span>` : ""}</span>
      <span class="l-meta">${esc(label)} · best ${esc(liftValue(lift.measure, lift.best))}</span>
      <span class="l-meta">${lift.sessions} session${lift.sessions === 1 ? "" : "s"} · last ${esc(lift.last_date)}</span></button>`;
  }

  async function loadLifts() {
    liftDetailEl.hidden = true;
    liftListEl.hidden = false;
    progressStatusEl.textContent = "Loading...";
    progressStatusEl.className = "status";
    const result = await apiFetch("/progress/lifts", { method: "GET" });
    if (!result.ok) {
      progressStatusEl.textContent = `Couldn't load lifts (${result.status}).`;
      progressStatusEl.className = "status error";
      return;
    }
    progressStatusEl.textContent = "";
    keyLiftsEl.innerHTML = result.body.key_lifts.map(liftCardHtml).join("");
    otherLiftsEl.innerHTML = result.body.other_lifts.length
      ? result.body.other_lifts.map(liftCardHtml).join("")
      : '<div class="status">No other lifts with 3 or more sessions yet.</div>';
  }

  liftListEl.addEventListener("click", (e) => {
    const card = e.target.closest("[data-lift]");
    if (card) openLift(card.dataset.lift);
  });

  document.getElementById("liftBack").addEventListener("click", loadLifts);

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function setText(set) {
    let reps = set.reps_full;
    if (reps === null && (set.left_reps_full !== null || set.right_reps_full !== null)) {
      reps = `${set.left_reps_full ?? "?"}L/${set.right_reps_full ?? "?"}R`;
    }
    const weight = set.weight_kg ? `${set.weight_kg} kg` : "bodyweight";
    return `${weight} × ${reps ?? "?"}${set.rpe !== null ? ` @ RPE ${set.rpe}` : ""}`;
  }

  const RECORD_LABEL = { estimated_max: "best estimate", heaviest: "heaviest", reps: "most reps" };

  async function openLift(name) {
    progressStatusEl.textContent = "Loading...";
    progressStatusEl.className = "status";
    const result = await apiFetch(`/progress/lifts/${encodeURIComponent(name)}`, { method: "GET" });
    if (!result.ok) {
      progressStatusEl.textContent = `Couldn't load ${name} (${result.status}).`;
      progressStatusEl.className = "status error";
      return;
    }
    progressStatusEl.textContent = "";
    const lift = result.body;
    const bodyweight = lift.measure === "bodyweight_reps";
    liftListEl.hidden = true;
    liftDetailEl.hidden = false;

    document.getElementById("liftTitle").textContent = lift.name;
    const t = lift.trend ? TREND[lift.trend] : null;
    document.getElementById("liftSummary").innerHTML = lift.sessions
      ? `${bodyweight ? "Best reps at bodyweight" : "Estimated max"}: latest <strong>${esc(liftValue(lift.measure, lift.latest))}</strong>, best ${esc(liftValue(lift.measure, lift.best))}, over ${lift.sessions} sessions.${t ? ` 4-week trend: <span class="${t[1]}">${t[2]} ${t[0]}</span>.` : " Not enough sessions yet for a 4-week trend."}`
      : "No countable sets yet: sets need a weight above 0 and 1 to 12 reps.";
    document.getElementById("liftHow").textContent = bodyweight
      ? "Each point is the session's most reps at bodyweight. Added weight is drawn separately, because the app doesn't store bodyweight."
      : "Each point is the session's best estimated max: weight × (1 + (reps + reps left) / 30), where reps left = 10 − RPE. Sets without RPE are treated as taken to failure. Counted: working sets with a weight above 0 and 1 to 12 reps.";

    const points = lift.points;
    const labels = points.map((p) => p.date);
    const red = cssVar("--red"), ink = cssVar("--ink"), muted = cssVar("--muted"), border = cssVar("--border");
    const datasets = [{
      label: bodyweight ? "Reps at bodyweight" : "Estimated max (kg)",
      data: points.map((p) => p.value),
      borderColor: ink,
      backgroundColor: points.map((p) => (p.records.length ? red : ink)),
      pointRadius: points.map((p) => (p.records.length ? 6 : 3)),
      spanGaps: true,
      yAxisID: "y",
    }];
    if (bodyweight) {
      datasets.push({
        label: "Added weight (kg)", data: points.map((p) => p.heaviest_kg),
        borderColor: muted, backgroundColor: muted, borderDash: [4, 4], spanGaps: true, yAxisID: "y2",
      });
    } else if (points.some((p) => p.goal_weight_kg)) {
      datasets.push({
        label: "Goal weight (kg)", data: points.map((p) => p.goal_weight_kg),
        borderColor: muted, backgroundColor: muted, borderDash: [4, 4], pointRadius: 0, spanGaps: true, yAxisID: "y",
      });
    }
    const axisTitle = (text) => ({ display: true, text, color: muted });
    const scales = {
      x: { ticks: { color: muted }, grid: { color: border } },
      y: bodyweight
        ? { beginAtZero: true, title: axisTitle("reps"), ticks: { color: muted, precision: 0 }, grid: { color: border } }
        : { title: axisTitle("kg"), ticks: { color: muted }, grid: { color: border } },
    };
    if (bodyweight) {
      scales.y2 = { position: "right", beginAtZero: true, title: axisTitle("added kg"),
                    ticks: { color: muted }, grid: { drawOnChartArea: false } };
    }

    if (liftChart) liftChart.destroy();
    liftChart = window.Chart
      ? new window.Chart(document.getElementById("liftChart"), {
          type: "line",
          data: { labels, datasets },
          options: {
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: ink } } },
            scales,
          },
        })
      : null;

    document.getElementById("liftSessions").innerHTML = points.slice().reverse().map((p) => `
      <div class="lift-session">
        <div class="ls-head">
          <span class="ls-date">${esc(p.date)}</span>
          <span class="ls-value">${esc(liftValue(lift.measure, p.value) ?? "no bodyweight sets")}</span>
          ${!bodyweight ? `<span>from ${esc(setText({ ...p.best_set, reps_full: p.best_set.reps }))}${p.method === "epley" ? ", no RPE" : ""}</span>` : ""}
          ${bodyweight && p.heaviest_kg ? `<span>added ${esc(p.heaviest_kg)} kg</span>` : ""}
          ${p.records.map((r) => `<span class="record">record: ${esc(RECORD_LABEL[r] || r)}</span>`).join(" ")}
        </div>
        <div class="ls-sets">${p.sets.map((s) => esc(`${s.number}. ${setText(s)}`)).join(" · ")}</div>
      </div>`).join("");
  }
})();
