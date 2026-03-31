(function () {
  const root = document.getElementById("dashboard-root");
  if (!root) return;

  const crmBtn = document.getElementById("execute-crm-btn");
  const ingestBtn = document.getElementById("execute-ingest-btn");
  const geminiBtn = document.getElementById("execute-gemini-btn");
  const legacyBtn = document.getElementById("execute-btn");
  const prevBtn = document.getElementById("crm-prev-btn");
  const nextBtn = document.getElementById("crm-next-btn");
  const pageInfo = document.getElementById("crm-page-info");
  const limitInput = document.getElementById("page-limit");
  const rowIdInput = document.getElementById("row-id-filter");
  const statusEl = document.getElementById("execute-status");
  const rowsHead = document.getElementById("rows-head");
  const rowsBody = document.getElementById("rows-body");
  const ingestBody = document.getElementById("ingest-body");
  const geminiBody = document.getElementById("gemini-body");
  const state = {
    page: 1,
    limit: 25,
    totalPages: 1,
    boardId: 70,
    groupId: 91,
  };

  if (!statusEl || !rowsHead || !rowsBody || !ingestBody || !geminiBody) return;

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

  function buildHeadCell(label) {
    const th = document.createElement("th");
    th.className = "px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500";
    th.textContent = label;
    return th;
  }

  function flattenField(prefix, value, out) {
    if (value == null || value === "") {
      out[prefix] = "-";
      return;
    }
    if (Array.isArray(value)) {
      if (value.length === 0) {
        out[prefix] = "-";
        return;
      }
      value.forEach((item, idx) => {
        const next = `${prefix}[${idx}]`;
        if (item !== null && typeof item === "object" && !Array.isArray(item)) {
          flattenField(next, item, out);
        } else {
          out[next] = item == null || item === "" ? "-" : String(item);
        }
      });
      return;
    }
    if (typeof value === "object") {
      const keys = Object.keys(value);
      if (!keys.length) {
        out[prefix] = "-";
        return;
      }
      keys.forEach((k) => {
        flattenField(`${prefix}.${k}`, value[k], out);
      });
      return;
    }
    out[prefix] = String(value);
  }

  function flattenRawColumns(rawColumns) {
    const out = {};
    const src = rawColumns || {};
    Object.keys(src).forEach((k) => {
      flattenField(k, src[k], out);
    });
    return out;
  }

  function collectRawColumnKeys(flatRows) {
    const keys = new Set();
    flatRows.forEach((fr) => {
      Object.keys(fr).forEach((k) => keys.add(k));
    });
    return Array.from(keys).sort((a, b) => a.localeCompare(b));
  }

  function renderRowsHeader(dynamicKeys) {
    rowsHead.innerHTML = "";
    ["Row", "Client", "Reason", "Amount", "Balance", "Action", "Wave"].forEach((label) => {
      rowsHead.appendChild(buildHeadCell(label));
    });
    dynamicKeys.forEach((key) => {
      rowsHead.appendChild(buildHeadCell(key));
    });
  }

  function renderRows(rows) {
    const flatRows = rows.map((r) => flattenRawColumns(r.raw_columns || {}));
    const dynamicKeys = collectRawColumnKeys(flatRows);
    renderRowsHeader(dynamicKeys);
    rowsBody.innerHTML = "";
    rows.forEach((r, idx) => {
      const tr = document.createElement("tr");
      tr.appendChild(rowCell(r.row_id));
      tr.appendChild(rowCell(r.client));
      tr.appendChild(rowCell(r.reason));
      tr.appendChild(rowCell(r.amount));
      tr.appendChild(rowCell(r.balance));
      tr.appendChild(rowCell(r.action));
      tr.appendChild(rowCell(r.wave));
      dynamicKeys.forEach((key) => {
        tr.appendChild(rowCell(flatRows[idx][key] || "-"));
      });
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
      const actions = document.createElement("div");
      actions.className = "mt-3 flex items-center gap-2";
      const sendBtn = document.createElement("button");
      sendBtn.className =
        "send-sms-btn rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed";
      sendBtn.textContent = "Send SMS";
      sendBtn.dataset.rowId = String(r.row_id || "");
      sendBtn.dataset.phone = String(r.phone || "");
      sendBtn.dataset.message = String(r.message || "");
      if (!r.phone || !r.message || r.status !== "success") {
        sendBtn.disabled = true;
      }
      actions.appendChild(sendBtn);
      card.appendChild(head);
      card.appendChild(body);
      card.appendChild(actions);
      geminiBody.appendChild(card);
    });
  }

  async function sendSms(btn) {
    const rowId = btn.dataset.rowId || "";
    const phone = btn.dataset.phone || "";
    const message = btn.dataset.message || "";
    if (!rowId || !phone || !message) {
      setStatus("Missing row_id, phone, or message for sending SMS.", "bad");
      return;
    }
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Sending...";
    try {
      const res = await fetch("/admin/superadmin-dashboard/send-sms/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ row_id: rowId, phone, message }),
      });
      const data = await res.json();
      if (!res.ok || data.status !== "success") {
        throw new Error(data.error || "SMS send failed.");
      }
      setStatus(`SMS sent for row ${rowId} to ${phone}.`, "ok");
      btn.textContent = "Sent";
    } catch (err) {
      setStatus(String(err.message || err), "bad");
      btn.disabled = false;
      btn.textContent = original || "Send SMS";
    }
  }

  function getPayload(action) {
    state.boardId = 70;
    state.groupId = 91;
    state.limit = Number((limitInput && limitInput.value) || 25);
    const rowIdRaw = rowIdInput && rowIdInput.value ? String(rowIdInput.value).trim() : "";
    return {
      action,
      board_id: state.boardId,
      group_id: state.groupId,
      page: state.page,
      limit: state.limit,
      row_id: rowIdRaw || null,
      temperature: 0.2,
      max_new_tokens: 220,
    };
  }

  function setBusy(isBusy) {
    if (crmBtn) crmBtn.disabled = isBusy;
    if (ingestBtn) ingestBtn.disabled = isBusy;
    if (geminiBtn) geminiBtn.disabled = isBusy;
    if (legacyBtn) legacyBtn.disabled = isBusy;
    if (prevBtn) prevBtn.disabled = isBusy || state.page <= 1;
    if (nextBtn) nextBtn.disabled = isBusy || state.page >= state.totalPages;
  }

  function renderPagination(meta) {
    if (!meta) return;
    state.page = Number(meta.page || 1);
    state.totalPages = Number(meta.total_pages || 1);
    if (pageInfo) pageInfo.textContent = `Page ${state.page} / ${state.totalPages} · Total ${meta.count || 0}`;
    if (prevBtn) prevBtn.disabled = state.page <= 1;
    if (nextBtn) nextBtn.disabled = state.page >= state.totalPages;
  }

  async function executeAction(action) {
    setBusy(true);
    setStatus(`Executing ${action.toUpperCase()}...`, "neutral");
    try {
      const res = await fetch("/admin/superadmin-dashboard/execute/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(getPayload(action)),
      });
      const data = await res.json();
      if (!res.ok || data.status !== "success") {
        throw new Error(data.error || "Execution failed.");
      }
      renderPagination(data.meta);
      if (action === "crm" || action === "all") {
        renderRows(data.recent_rows || []);
      }
      if (action === "ingestion" || action === "all") {
        renderIngestion(data.ingestion_preview || []);
      }
      if (action === "gemini" || action === "all") {
        renderGemini(data.gemini_preview || []);
      }
      setStatus(`${action.toUpperCase()} completed for board ${state.boardId}, group ${state.groupId}.`, "ok");
    } catch (err) {
      setStatus(String(err.message || err), "bad");
    } finally {
      setBusy(false);
    }
  }

  if (crmBtn) {
    crmBtn.addEventListener("click", function () {
      state.page = 1;
      executeAction("crm");
    });
  }

  if (ingestBtn) {
    ingestBtn.addEventListener("click", function () {
      executeAction("ingestion");
    });
  }

  if (geminiBtn) {
    geminiBtn.addEventListener("click", function () {
      executeAction("gemini");
    });
  }

  if (legacyBtn) {
    legacyBtn.addEventListener("click", function () {
      state.page = 1;
      executeAction("all");
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", function () {
      if (state.page <= 1) return;
      state.page -= 1;
      executeAction("crm");
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      if (state.page >= state.totalPages) return;
      state.page += 1;
      executeAction("crm");
    });
  }

  // Fallback: handle clicks even if direct bindings are stale/mismatched.
  root.addEventListener("click", function (evt) {
    const target = evt.target;
    if (!(target instanceof Element)) return;
    const btn = target.closest("button");
    if (!btn || !btn.id) return;

    if (btn.id === "execute-crm-btn") {
      state.page = 1;
      executeAction("crm");
      return;
    }
    if (btn.id === "execute-ingest-btn") {
      executeAction("ingestion");
      return;
    }
    if (btn.id === "execute-gemini-btn") {
      executeAction("gemini");
      return;
    }
    if (btn.id === "execute-btn") {
      state.page = 1;
      executeAction("all");
      return;
    }
    if (btn.id === "crm-prev-btn" && state.page > 1) {
      state.page -= 1;
      executeAction("crm");
      return;
    }
    if (btn.id === "crm-next-btn" && state.page < state.totalPages) {
      state.page += 1;
      executeAction("crm");
      return;
    }
    if (btn.classList.contains("send-sms-btn")) {
      sendSms(btn);
    }
  });
})();
