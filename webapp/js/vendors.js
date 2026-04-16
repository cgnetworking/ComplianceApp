  let vendorResponsesLoadPromise = null;

  const vendorHelperCopy = "Download the sample CSV, replace the sample answers, and import completed questionnaires or exports into the shared database.";

  async function loadVendorResponsesState(force = false) {
    if (force) {
      state.vendorResponsesLoaded = false;
    }
    if (state.vendorResponsesLoaded) {
      return;
    }
    if (vendorResponsesLoadPromise) {
      await vendorResponsesLoadPromise;
      return;
    }

    vendorResponsesLoadPromise = (async () => {
      if (!vendorSurveyResponses.length) {
        setUploadStatus(els.vendorUploadStatus, "Loading vendor response queue...", "info");
      }
      try {
        const payload = await apiRequest("/vendors/uploads/");
        vendorSurveyResponses = Array.isArray(payload.responses) ? payload.responses : [];
        state.vendorResponsesLoaded = true;
      } catch (error) {
        const detail = error instanceof Error ? error.message : "Unable to load vendor response queue.";
        setUploadStatus(els.vendorUploadStatus, detail, "error");
      } finally {
        vendorResponsesLoadPromise = null;
      }
    })();

    await vendorResponsesLoadPromise;
  }

  function renderVendorsPage() {
    bindVendorDownloadEvents();
    bindVendorDetailEvents();
    syncVendorSelection();
    updateVendorDownloadControls();
    ensureVendorUploadHelperCopy();
    renderVendorOverview();
    renderVendorResponseList();
    renderVendorDetail();
  }
  function ensureVendorUploadHelperCopy() {
    if (!els.vendorUploadStatus) {
      return;
    }
    if (els.vendorUploadStatus.classList.contains("is-success") || els.vendorUploadStatus.classList.contains("is-error")) {
      return;
    }
    setUploadStatus(els.vendorUploadStatus, vendorHelperCopy, "");
  }
  function bindVendorDownloadEvents() {
    const selectedButton = document.getElementById("vendor-download-trigger");
    if (selectedButton && selectedButton.dataset.vendorDownloadBound !== "true") {
      selectedButton.dataset.vendorDownloadBound = "true";
      selectedButton.addEventListener("click", () => {
        handleVendorDownloadSelected();
      });
    }

    const allButton = document.getElementById("vendor-download-all-trigger");
    if (allButton && allButton.dataset.vendorDownloadBound !== "true") {
      allButton.dataset.vendorDownloadBound = "true";
      allButton.addEventListener("click", () => {
        handleVendorDownloadAll();
      });
    }
  }
  function bindVendorDetailEvents() {
    if (!els.vendorDetail || els.vendorDetail.dataset.vendorDetailBound === "true") {
      return;
    }
    els.vendorDetail.dataset.vendorDetailBound = "true";
    els.vendorDetail.addEventListener("click", (event) => {
      const deleteButton = event.target.closest("[data-vendor-delete]");
      if (!deleteButton || !deleteButton.dataset.vendorDelete) {
        return;
      }
      void handleVendorDelete(deleteButton.dataset.vendorDelete);
    });
  }
  function updateVendorDownloadControls() {
    const selectedButton = document.getElementById("vendor-download-trigger");
    const allButton = document.getElementById("vendor-download-all-trigger");
    const selectedResponse = vendorSurveyResponses.find((response) => response.id === state.selectedVendorResponseId);

    if (selectedButton) {
      selectedButton.disabled = !selectedResponse;
      selectedButton.title = selectedResponse
        ? `Download ${selectedResponse.fileName}`
        : "Select an imported vendor response to download.";
    }
    if (allButton) {
      allButton.disabled = vendorSurveyResponses.length === 0;
      allButton.title = vendorSurveyResponses.length
        ? "Download all imported vendor responses as a CSV export."
        : "Import vendor responses to enable download.";
    }
  }
  function handleVendorDownloadSelected() {
    const selectedResponse = vendorSurveyResponses.find((response) => response.id === state.selectedVendorResponseId);
    if (!selectedResponse) {
      setUploadStatus(els.vendorUploadStatus, "Select an imported vendor response to download.", "warning");
      updateVendorDownloadControls();
      return;
    }
    setUploadStatus(els.vendorUploadStatus, `Preparing download for ${selectedResponse.fileName}...`, "info");
    triggerVendorDownload({ responseId: selectedResponse.id });
  }
  function handleVendorDownloadAll() {
    if (!vendorSurveyResponses.length) {
      setUploadStatus(els.vendorUploadStatus, "Import vendor responses before downloading all responses.", "warning");
      updateVendorDownloadControls();
      return;
    }
    setUploadStatus(
      els.vendorUploadStatus,
      `Preparing download for ${vendorSurveyResponses.length} imported vendor response${vendorSurveyResponses.length === 1 ? "" : "s"}...`,
      "info"
    );
    triggerVendorDownload({ scope: "all" });
  }
  function triggerVendorDownload(options) {
    const query = new URLSearchParams();
    if (options.scope === "all") {
      query.set("scope", "all");
    } else if (options.responseId) {
      query.set("responseId", options.responseId);
    }

    const apiBaseUrl = resolveApiBaseUrl();
    window.location.assign(`${apiBaseUrl}/vendors/downloads/?${query.toString()}`);
  }
  function renderVendorOverview() {
    if (!els.vendorOverview) {
      return;
    }

    const responses = filteredVendorResponses();
    const vendorCount = new Set(responses.map((response) => response.vendorName)).size;
    const selectedResponse = responses.find((response) => response.id === state.selectedVendorResponseId) || null;
    const lastImported = responses[0] ? formatShortDateTime(responses[0].importedAt) : "None";

    const cards = [
      {
        label: "Vendors in view",
        value: vendorCount,
        note: responses.length ? "Distinct vendors represented in the filtered intake queue." : "No vendor responses have been staged yet.",
      },
      {
        label: "Responses staged",
        value: responses.length,
        note: `Files stored in the ${portalWorkspaceLabel()} for follow-up review.`,
      },
      {
        label: "Selected response",
        value: selectedResponse ? selectedResponse.vendorName : "None",
        note: selectedResponse
          ? "Use Download to export the selected vendor response."
          : "Select an imported response to enable single-file download.",
      },
      {
        label: "Last import",
        value: lastImported,
        note: responses.length ? "Most recent vendor response imported into the queue." : "Import survey responses to start building the intake queue.",
      },
    ];

    els.vendorOverview.innerHTML = cards.map((card) => `
      <article class="stat-card">
        <span class="stat-label">${escapeHtml(card.label)}</span>
        <p class="stat-value">${escapeHtml(String(card.value))}</p>
        <p class="stat-note">${escapeHtml(card.note)}</p>
      </article>
    `).join("");
  }
  function renderVendorResponseList() {
    if (!els.vendorResponses) {
      return;
    }

    const responses = filteredVendorResponses();
    if (!responses.length) {
      els.vendorResponses.innerHTML = `
        <div class="empty-state">
          ${state.search ? "No imported vendor responses match the current search." : "No vendor due diligence survey responses have been imported yet."}
        </div>
      `;
      return;
    }

    els.vendorResponses.innerHTML = `
      <div class="vendor-list">
        ${responses.map((response) => {
          const isActive = response.id === state.selectedVendorResponseId;
          const statusClass = "is-success";
          return `
            <button class="vendor-card ${isActive ? "is-selected" : ""}" type="button" data-vendor-response="${escapeHtml(response.id)}">
              <div class="vendor-card-top">
                <div>
                  <strong>${escapeHtml(response.vendorName)}</strong>
                  <div class="mini-copy">${escapeHtml(response.fileName)}</div>
                </div>
                <span class="status-pill ${statusClass}">Imported</span>
              </div>
              <div class="vendor-meta-row">
                <span class="chip">${escapeHtml(response.extension.toUpperCase())}</span>
                <span class="chip">${escapeHtml(formatFileSize(response.fileSize))}</span>
                <span class="chip">${escapeHtml(formatShortDateTime(response.importedAt))}</span>
              </div>
              <p class="mini-copy">${escapeHtml(response.summary)}</p>
            </button>
          `;
        }).join("")}
      </div>
    `;
  }
  function renderVendorDetail() {
    if (!els.vendorDetail) {
      return;
    }

    const response = vendorSurveyResponses.find((item) => item.id === state.selectedVendorResponseId);
    if (!response) {
      els.vendorDetail.innerHTML = `
        <div class="detail-stack">
          <div class="detail-header">
            <div>
              <p class="panel-kicker">Vendor import</p>
              <h3>Stage supplier responses for review</h3>
            </div>
            <p class="detail-subline">
              Import completed due diligence questionnaires, spreadsheets, or exported response files into the ${escapeHtml(portalWorkspaceLabel())}. Imported responses can be downloaded from this page for follow-up review and evidence mapping.
            </p>
          </div>
          <div class="detail-grid">
            <div class="detail-card">
              <strong>Accepted formats</strong>
              <div class="mini-copy">CSV, JSON, TXT, Markdown, HTML, PDF, Word, and Excel exports.</div>
            </div>
            <div class="detail-card">
              <strong>Search behavior</strong>
              <div class="mini-copy">Search matches vendor names, file names, import summaries, and file metadata.</div>
            </div>
          </div>
          <div class="preview-block">
            <ul class="detail-list">
              <li>Use one file per vendor response when possible so the queue stays attributable.</li>
              <li>Use Download to export the selected response or Download All for bulk export.</li>
              <li>After import, use the selected response as the intake source for supplier review and evidence mapping.</li>
            </ul>
          </div>
        </div>
      `;
      return;
    }

    const statusClass = "is-success";
    els.vendorDetail.innerHTML = `
      <article class="detail-panel">
        <div class="detail-header">
          <div>
            <p class="panel-kicker">Imported response</p>
            <h3>${escapeHtml(response.vendorName)}</h3>
          </div>
          <div class="chip-row">
            <span class="status-pill ${statusClass}">Imported</span>
            <span class="chip">${escapeHtml(response.extension.toUpperCase())}</span>
            <span class="chip">${escapeHtml(formatFileSize(response.fileSize))}</span>
          </div>
          <p class="detail-subline">${escapeHtml(response.summary)}</p>
        </div>
        <div class="detail-grid">
          <div class="detail-card">
            <strong>Imported file</strong>
            <div class="mini-copy">${escapeHtml(response.fileName)}</div>
          </div>
          <div class="detail-card">
            <strong>Imported at</strong>
            <div class="mini-copy">${escapeHtml(formatDateTime(response.importedAt))}</div>
          </div>
          <div class="detail-card">
            <strong>Detected vendor</strong>
            <div class="mini-copy">${escapeHtml(response.vendorName)}</div>
          </div>
          <div class="detail-card">
            <strong>Detected type</strong>
            <div class="mini-copy">${escapeHtml(response.mimeType || response.extension.toUpperCase())}</div>
          </div>
        </div>
        <div class="doc-section">
          <div class="button-row button-row-wrap">
            <button class="ghost-button danger-button" type="button" data-vendor-delete="${escapeHtml(response.id)}">Delete Response</button>
          </div>
        </div>
        <div class="doc-section">
          <strong>Suggested next steps</strong>
          <div class="preview-block">
            <ul class="detail-list">
              <li>Confirm the vendor owner and risk tier before the response is used in a review package.</li>
              <li>Check whether the response covers security clauses, incident notification, access control, and subprocessor handling.</li>
              <li>Link the imported response to supplier review evidence once the intake workflow is finalized.</li>
            </ul>
          </div>
        </div>
      </article>
    `;
  }
  async function deleteVendorResponseFromApi(responseId) {
    return apiRequest(`/vendors/responses/${encodeURIComponent(responseId)}/`, {
      method: "DELETE",
    });
  }
  async function handleVendorDelete(responseId) {
    const selectedResponse = vendorSurveyResponses.find((item) => item.id === responseId);
    if (!selectedResponse) {
      setUploadStatus(els.vendorUploadStatus, "Select an imported vendor response to delete.", "error");
      return;
    }

    if (!window.confirm(`Delete ${selectedResponse.vendorName} / ${selectedResponse.fileName}? This cannot be undone.`)) {
      return;
    }

    const previousResponses = vendorSurveyResponses.slice();
    vendorSurveyResponses = vendorSurveyResponses.filter((item) => item.id !== responseId);
    if (state.selectedVendorResponseId === responseId) {
      state.selectedVendorResponseId = "";
    }
    syncVendorSelection();
    syncUrl();
    renderVendorsPage();

    try {
      await runAsyncOperation(
        (message, tone) => {
          setUploadStatus(els.vendorUploadStatus, message, tone);
        },
        {
          pending: `Deleting ${selectedResponse.fileName}...`,
          success: "Vendor response deleted from the intake queue.",
          error: "Unable to delete the selected vendor response.",
        },
        async () => {
          await deleteVendorResponseFromApi(responseId);
          return true;
        }
      );
    } catch (error) {
      vendorSurveyResponses = previousResponses;
      if (!vendorSurveyResponses.some((item) => item.id === state.selectedVendorResponseId)) {
        state.selectedVendorResponseId = selectedResponse.id;
      }
      syncVendorSelection();
      syncUrl();
      renderVendorsPage();
    }
  }
  function filteredVendorResponses() {
    const searchLower = state.search.trim().toLowerCase();
    return vendorSurveyResponses
      .slice()
      .sort((left, right) => new Date(right.importedAt) - new Date(left.importedAt))
      .filter((response) => {
        if (!searchLower) {
          return true;
        }
        const searchableText = [
          response.vendorName,
          response.fileName,
          response.summary,
          response.extension,
          response.mimeType,
          response.status,
        ].join(" ").toLowerCase();
        return searchableText.includes(searchLower);
      });
  }
  function syncVendorSelection() {
    const responses = filteredVendorResponses();
    if (!responses.length) {
      state.selectedVendorResponseId = "";
      return;
    }
    if (!state.selectedVendorResponseId || !responses.some((response) => response.id === state.selectedVendorResponseId)) {
      state.selectedVendorResponseId = responses[0].id;
    }
  }
  async function handleVendorUpload(files) {
    if (!files.length) {
      return;
    }
    try {
      await runAsyncOperation(
        (message, tone) => {
          setUploadStatus(els.vendorUploadStatus, message, tone);
        },
        {
          pending: `Importing ${files.length} vendor response file${files.length === 1 ? "" : "s"}...`,
          success: (additions) => `${additions.length} vendor response file${additions.length === 1 ? "" : "s"} imported into the intake queue.`,
          error: "Unable to import the selected vendor response file.",
        },
        async () => {
          const additions = await uploadVendorsToApi(files);

          vendorSurveyResponses = additions
            .concat(vendorSurveyResponses)
            .sort((left, right) => new Date(right.importedAt) - new Date(left.importedAt))
            .slice(0, 60);
          state.vendorResponsesLoaded = true;

          syncVendorSelection();
          syncUrl();
          renderVendorsPage();
          return additions;
        }
      );
    } catch (error) {
      // The shared helper already set the error status.
    }
  }
  async function uploadVendorsToApi(files) {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });

    const payload = await apiRequest("/vendors/uploads/", {
      method: "POST",
      body: formData,
    });

    return Array.isArray(payload.responses) ? payload.responses : [];
  }
  function formatShortDateTime(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "-";
    }
    const time = new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(parsed);
    return `${formatDateWithOrdinal(parsed)}, ${time}`;
  }
  function formatFileSize(value) {
    const bytes = Number(value) || 0;
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    const units = ["KB", "MB", "GB"];
    let size = bytes / 1024;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    return `${size >= 10 ? size.toFixed(0) : size.toFixed(1)} ${units[unitIndex]}`;
  }
