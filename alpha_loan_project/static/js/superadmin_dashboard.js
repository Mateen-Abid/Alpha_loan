(function () {
  const root = document.getElementById("dashboard-root");
  if (!root) return;

  const button = document.getElementById("execute-btn");
  const statusEl = document.getElementById("execute-status");
  const rowsBody = document.getElementById("rows-body");
  const ingestBody = document.getElementById("ingest-body");
  const geminiBody = document.getElementById("gemini-body");

  function getCookie(name) {
    const cookieValue = document.cookie
      .split(";")
      .map((c) => c.trim())
      .find((c) => c.startsWith(name + "="));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  }

  function setStatus(text, tone) {
    statusEl.textContent = text;
    statusEl.className =
      "rounded-md px-3 py-2 text-sm font-medium " +
      (tone === "ok"
        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
        : tone === "bad"
          ? "bg-rose-50 text-rose-700 border border-rose-200"
          : "bg-slate-50 text-slate-700 border border-slate-200");
  }

  function rowCell(value) {
    const td = document.createElement("td");
    td.className = "px-3 py-2 text-sm text-slate-700 border-b border-slate-100 align-top";
    td.textContent = value == null || value === "" ? "-" : String(value);
    return td;
  }

  function renderRows(rows) {
    rowsBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.appendChild(rowCell(r.row_id));
      tr.appendChild(rowCell(r.client));
      tr.appendChild(rowCell(r.reason));
      tr.appendChild(rowCell(r.amount));
      tr.appendChild(rowCell(r.balance));
      tr.appendChild(rowCell(r.action));
      tr.appendChild(rowCell(r.wave));
      rowsBody.appendChild(tr);
    });
  }

  function renderIngestion(rows) {
    ingestBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.appendChild(rowCell(r.row_id));
      tr.appendChild(rowCell(r.borrower_name));
      tr.appendChild(rowCell(r.reason_code));
      tr.appendChild(rowCell(r.amount));
      tr.appendChild(rowCell(r.immediate_due_with_fee));
      tr.appendChild(rowCell(r.balance));
      tr.appendChild(rowCell(r.phone));
      tr.appendChild(rowCell(r.email));
      ingestBody.appendChild(tr);
    });
  }

  function renderGemini(rows) {
    geminiBody.innerHTML = "";
    rows.forEach((r) => {
      const card = document.createElement("div");
      card.className = "rounded-lg border border-slate-200 bg-white p-3";
      const head = document.createElement("div");
      head.className = "mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500";
      head.textContent = "Row " + (r.row_id || "-") + " · " + (r.borrower_name || "N/A");
      const body = document.createElement("div");
      body.className = "text-sm leading-6 text-slate-700";
      body.textContent = r.message || "";
      card.appendChild(head);
      card.appendChild(body);
      geminiBody.appendChild(card);
    });
  }

  async function executePipeline() {
    button.disabled = true;
    setStatus("Fetching CRM rows and generating previews...", "neutral");
    try {
      const res = await fetch("/admin/superadmin-dashboard/execute/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ board_id: 70, group_id: 91, limit: 5 }),
      });
      const data = await res.json();
      if (!res.ok || data.status !== "success") {
        throw new Error(data.error || "Execution failed.");
      }
      renderRows(data.recent_rows || []);
      renderIngestion(data.ingestion_preview || []);
      renderGemini(data.gemini_preview || []);
      setStatus("Preview generated from CRM board 70/group 91.", "ok");
    } catch (err) {
      setStatus(String(err.message || err), "bad");
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", executePipeline);
})();
