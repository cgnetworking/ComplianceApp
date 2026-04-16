  let vendorResponsesLoadPromise = null;

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
    syncVendorSelection();
    renderVendorOverview();
    renderVendorResponseList();
    renderVendorDetail();
  }
  function renderVendorOverview() {
    if (!els.vendorOverview) {
      return;
    }

    const responses = filteredVendorResponses();
    const vendorCount = new Set(responses.map((response) => response.vendorName)).size;
    const previewCount = responses.filter((response) => response.previewText).length;
    const metadataOnlyCount = responses.filter((response) => !response.previewText).length;
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
        label: "Preview ready",
        value: previewCount,
        note: metadataOnlyCount ? `${metadataOnlyCount} file(s) are metadata only.` : "All visible files include an inline preview.",
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
          const statusClass = response.previewText ? "is-success" : "is-active";
          return `
            <button class="vendor-card ${isActive ? "is-selected" : ""}" type="button" data-vendor-response="${escapeHtml(response.id)}">
              <div class="vendor-card-top">
                <div>
                  <strong>${escapeHtml(response.vendorName)}</strong>
                  <div class="mini-copy">${escapeHtml(response.fileName)}</div>
                </div>
                <span class="status-pill ${statusClass}">${escapeHtml(response.status)}</span>
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
              Import completed due diligence questionnaires, spreadsheets, or exported response files into the ${escapeHtml(portalWorkspaceLabel())}. Text-based uploads create searchable previews in this queue.
            </p>
          </div>
          <div class="detail-grid">
            <div class="detail-card">
              <strong>Accepted formats</strong>
              <div class="mini-copy">CSV, JSON, TXT, Markdown, HTML, PDF, Word, and Excel exports.</div>
            </div>
            <div class="detail-card">
              <strong>Search behavior</strong>
              <div class="mini-copy">Search matches vendor names, file names, extracted previews, and import summaries.</div>
            </div>
          </div>
          <div class="preview-block">
            <ul class="detail-list">
              <li>Use one file per vendor response when possible so the queue stays attributable.</li>
              <li>Re-upload text exports if you want inline preview content for PDF or spreadsheet responses.</li>
              <li>After import, use the selected response as the intake source for supplier review and evidence mapping.</li>
            </ul>
          </div>
        </div>
      `;
      return;
    }

    const statusClass = response.previewText ? "is-success" : "is-active";
    els.vendorDetail.innerHTML = `
      <article class="detail-panel">
        <div class="detail-header">
          <div>
            <p class="panel-kicker">Imported response</p>
            <h3>${escapeHtml(response.vendorName)}</h3>
          </div>
          <div class="chip-row">
            <span class="status-pill ${statusClass}">${escapeHtml(response.status)}</span>
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
          <strong>Suggested next steps</strong>
          <div class="preview-block">
            <ul class="detail-list">
              <li>Confirm the vendor owner and risk tier before the response is used in a review package.</li>
              <li>Check whether the response covers security clauses, incident notification, access control, and subprocessor handling.</li>
              <li>Link the imported response to supplier review evidence once the intake workflow is finalized.</li>
            </ul>
          </div>
        </div>
        <div class="doc-section">
          <strong>Imported preview</strong>
          <div class="preview-block">
            ${response.previewText
              ? `<pre class="response-preview">${escapeHtml(response.previewText)}</pre>`
              : '<div class="empty-state">This file was staged with metadata only. Upload a text export if you need searchable inline preview content.</div>'}
          </div>
        </div>
      </article>
    `;
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
          response.previewText,
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
