(function () {
  const apiBaseInput = document.getElementById("apiBase");
  const apiKeyInput = document.getElementById("apiKey");
  const contentInput = document.getElementById("content");
  const extractBtn = document.getElementById("extractBtn");
  const statusEl = document.getElementById("status");
  const outputEl = document.getElementById("output");

  apiBaseInput.value = localStorage.getItem("tl_apiBase") || apiBaseInput.value;
  apiKeyInput.value = localStorage.getItem("tl_apiKey") || "";
  apiBaseInput.addEventListener("change", () => localStorage.setItem("tl_apiBase", apiBaseInput.value));
  apiKeyInput.addEventListener("change", () => localStorage.setItem("tl_apiKey", apiKeyInput.value));

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = isError ? "status error" : "status";
  }

  function showOutput(data) {
    outputEl.style.display = "block";
    outputEl.textContent = JSON.stringify(data, null, 2);
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
    outputEl.style.display = "none";
    setStatus("Saving...");

    const capture = await apiFetch("/inputs", {
      method: "POST",
      body: JSON.stringify({ content }),
    });

    if (!capture.ok) {
      setStatus(`POST /inputs failed (${capture.status}).`, true);
      showOutput(capture.body);
      extractBtn.disabled = false;
      return;
    }

    const { raw_input_id, extraction_id, error } = capture.body;

    if (error || !extraction_id) {
      setStatus(`Saved (raw_input_id: ${raw_input_id}) but extraction failed: ${error}`, true);
      extractBtn.disabled = false;
      return;
    }

    setStatus(`Extracted (extraction_id: ${extraction_id}). Fetching card...`);

    const extraction = await apiFetch(`/extractions/${extraction_id}`, { method: "GET" });

    if (!extraction.ok) {
      setStatus(`GET /extractions/${extraction_id} failed (${extraction.status}).`, true);
      showOutput(extraction.body);
      extractBtn.disabled = false;
      return;
    }

    setStatus(`Done. extraction_id: ${extraction_id}`);
    showOutput(extraction.body);
    extractBtn.disabled = false;
  });
})();
