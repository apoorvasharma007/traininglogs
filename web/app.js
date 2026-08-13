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

  // The extraction being reviewed, and the client's current copy of its extract -- null means
  // "use the extraction's own stored reading," which is only true before the first correction.
  // Every /correct response's own `extract` becomes the new value, exactly the round-trip the
  // endpoint's statelessness was designed for: the server holds nothing between calls.
  let currentExtractionId = null;
  let currentExtract = null;
  // {at, instruction, edits} per applied correction -- accumulated here and sent as
  // ConfirmIn.corrections on /confirm, which records them alongside the extraction.
  let corrections = [];

  apiBaseInput.value = localStorage.getItem("tl_apiBase") || apiBaseInput.value;
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

    const extraction = await apiFetch(`/extractions/${extraction_id}`, { method: "GET" });

    if (!extraction.ok) {
      setStatus(`GET /extractions/${extraction_id} failed (${extraction.status}).`, true);
      showRawOutput(extraction.body);
      extractBtn.disabled = false;
      return;
    }

    setStatus(`Done. extraction_id: ${extraction_id}`);
    showRawOutput(extraction.body);
    renderCard(extraction.body);
    currentExtractionId = extraction_id;
    composerEl.style.display = "flex";
    confirmBarEl.style.display = "flex";
    extractBtn.disabled = false;
  });

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
    currentExtract = result.body.extract;
    corrections.push(result.body.correction);
    showRawOutput(result.body);
    renderCard(result.body.card);
    appendCorrectionRow(result.body.correction);
    corrInputEl.value = "";
    corrInputEl.focus();
  }

  function appendCorrectionRow(correction) {
    const row = document.createElement("div");
    row.className = "corr-row";
    const editSummary = (correction.edits || [])
      .map((e) => `${e.path} → ${JSON.stringify(e.value)}`)
      .join(", ");
    row.innerHTML = `<span class="ico">✓</span><span>"${esc(correction.instruction)}"${
      editSummary ? ` — ${esc(editSummary)}` : ""
    }</span>`;
    correctionsLogEl.appendChild(row);
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

  function setValsHtml(row) {
    const parts = [];
    if (row.weight_kg != null) parts.push(`${row.weight_kg}kg`);
    if (row.reps != null) parts.push(`× ${esc(row.reps)}`);
    if (row.duration_seconds != null) parts.push(fmtDuration(row.duration_seconds));
    if (row.distance_meters != null) parts.push(`${row.distance_meters}m`);
    if (row.heart_rate_bpm != null) parts.push(`${row.heart_rate_bpm}bpm`);
    let html = esc(parts.join(" "));
    if (row.rpe != null) html += ` <span class="chip">RPE ${row.rpe}</span>`;
    if (row.quality) html += ` <span class="chip">${esc(row.quality)}</span>`;
    if (row.failure_technique) html += ` <span class="chip">${esc(row.failure_technique)}</span>`;
    return html;
  }

  function warmupValsHtml(row) {
    const parts = [];
    if (row.weight_kg != null) parts.push(`${row.weight_kg}kg`);
    if (row.rep_count != null) parts.push(`× ${row.rep_count}`);
    return esc(parts.join(" "));
  }

  function setRowHtml(row, valsHtml) {
    const flag = row.uncertain_fields && row.uncertain_fields.length
      ? '<span class="flag">AI inferred</span>' : "<span></span>";
    const note = row.notes
      ? `<span class="note">${esc(row.notes)}</span>` : "";
    return `
      <div class="set-row">
        <span class="idx">${row.number}</span>
        <span class="vals">${valsHtml}</span>
        ${flag}
        ${note}
      </div>`;
  }

  function movementSectionHtml(section) {
    if (!section) return "";
    const rows = section.movements.map((m) => `
      <div class="movement-row">
        ${m.number}. ${esc(m.name)}${m.reps != null ? ` — × ${m.reps}` : ""}${m.duration_seconds != null ? ` — ${fmtDuration(m.duration_seconds)}` : ""}
        ${m.notes ? `<div class="m-note">${esc(m.notes)}</div>` : ""}
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
            <div class="sub-row">
              ${r.number}. ${warmupValsHtml(r)}
              ${r.uncertain_fields && r.uncertain_fields.length ? '<span class="flag">AI inferred</span>' : ""}
              ${r.notes ? `<div class="note">${esc(r.notes)}</div>` : ""}
            </div>`).join("")}
        </div>` : "";

    const warmupNoteHtml = ex.warmup_note_preview
      ? `<div class="ex-note">Warmup notes: ${esc(ex.warmup_note_preview.full_text)}</div>` : "";

    const setsHtml = (ex.working_set_rows || [])
      .map((r) => setRowHtml(r, setValsHtml(r)))
      .join("");

    const noteHtml = ex.note_preview
      ? `<div class="ex-note">${esc(ex.note_preview.full_text)}</div>` : "";

    return `
      <div class="ex-card">
        <div class="ex-head">
          <span class="name">${h.number}. ${esc(h.name)}</span>
          ${goalHtml ? `<span class="goal">${esc(goalHtml)}</span>` : ""}
        </div>
        ${warmupHtml}
        ${warmupNoteHtml}
        ${setsHtml}
        ${noteHtml}
      </div>`;
  }

  function renderCard(card) {
    const sh = card.session_header;
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
      <div class="session-head">
        <div class="focus">${esc(sh.focus || "Session")}</div>
        <div class="meta">${esc(metaParts.join(" · "))}</div>
        ${shFlags}
      </div>`;

    if (card.warnings && card.warnings.length) {
      html += `
        <div class="warnings-box">
          <div class="w-title">Warnings</div>
          <ul>${card.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
        </div>`;
    }

    html += movementSectionHtml(card.warmup_section);

    if (card.note_preview) {
      html += `<div class="ex-note">Session notes: ${esc(card.note_preview.full_text)}</div>`;
    }

    (card.exercises || []).forEach((ex) => {
      html += exerciseCardHtml(ex);
    });

    html += movementSectionHtml(card.cooldown_section);

    cardEl.innerHTML = html;
    cardEl.className = "active";
  }
})();
