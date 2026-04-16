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

    setUploadStatus(
      els.vendorUploadStatus,
      `Importing ${files.length} vendor response file${files.length === 1 ? "" : "s"}...`,
      "info"
    );

    try {
      const additions = await uploadVendorsToApi(files);

      vendorSurveyResponses = additions
        .concat(vendorSurveyResponses)
        .sort((left, right) => new Date(right.importedAt) - new Date(left.importedAt))
        .slice(0, 60);
      state.vendorResponsesLoaded = true;

      syncVendorSelection();
      syncUrl();
      renderVendorsPage();
      setUploadStatus(
        els.vendorUploadStatus,
        `${additions.length} vendor response file${additions.length === 1 ? "" : "s"} imported into the intake queue.`,
        "success"
      );
    } catch (error) {
      setUploadStatus(
        els.vendorUploadStatus,
        error instanceof Error ? error.message : "Unable to import the selected vendor response file.",
        "error"
      );
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
  async function buildVendorSurveyResponse(file, importedAt, sequence) {
    const extension = extractFileExtension(file.name);
    const rawText = isTextLikeFile(file, extension) ? (await file.text()).replace(/\u0000/g, "").trim() : "";
    const previewText = buildPreviewText(rawText, 1400, 20);

    return {
      id: `vendor-${importedAt.getTime()}-${sequence}`,
      vendorName: inferVendorName(file.name, rawText, extension),
      fileName: file.name,
      extension: extension ? extension.slice(1) : "file",
      mimeType: file.type || "Unknown",
      fileSize: file.size || 0,
      importedAt: new Date(importedAt.getTime() + sequence).toISOString(),
      previewText,
      summary: summarizeVendorSurvey(file, rawText, extension, previewText),
      status: previewText ? "Preview ready" : "Metadata only",
    };
  }
  function summarizeVendorSurvey(file, rawText, extension, previewText) {
    const nonEmptyLines = rawText ? rawText.split(/\r?\n/).filter((line) => line.trim()).length : 0;
    if (extension === ".csv") {
      const rowCount = Math.max(nonEmptyLines - 1, 0);
      return rowCount ? `${rowCount} questionnaire row(s) staged from CSV.` : "CSV questionnaire staged for review.";
    }
    if (extension === ".json") {
      try {
        const parsed = JSON.parse(rawText);
        if (Array.isArray(parsed)) {
          return `${parsed.length} JSON record(s) staged for vendor review.`;
        }
        if (parsed && typeof parsed === "object") {
          return `${Object.keys(parsed).length} JSON field(s) staged for vendor review.`;
        }
      } catch (error) {
        return "JSON response staged with inline preview.";
      }
    }
    if (previewText) {
      return nonEmptyLines
        ? `${nonEmptyLines} non-empty line(s) detected; preview trimmed for inline review.`
        : "Text response staged with inline preview.";
    }
    if (extension === ".xls" || extension === ".xlsx") {
      return "Spreadsheet response staged with metadata only.";
    }
    if (extension === ".pdf") {
      return "PDF response staged with metadata only.";
    }
    if (extension === ".doc" || extension === ".docx") {
      return "Word document response staged with metadata only.";
    }
    return `${file.name} staged with metadata only.`;
  }
  function inferVendorName(fileName, rawText, extension) {
    const jsonName = extension === ".json" ? findVendorNameInJson(rawText) : "";
    if (jsonName) {
      return jsonName;
    }

    const csvName = extension === ".csv" ? findVendorNameInCsv(rawText) : "";
    if (csvName) {
      return csvName;
    }

    const baseName = fileName.replace(/\.[^.]+$/, "");
    const cleaned = baseName
      .replace(/\b(ddq|due diligence|questionnaire|security|survey|response|responses|sig lite|sig|caiq)\b/gi, " ")
      .replace(/\b20\d{2}[-_ ]?\d{2}[-_ ]?\d{2}\b/g, " ")
      .replace(/\b\d{8}\b/g, " ")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    return cleaned || deriveDisplayName(fileName) || "Unknown vendor";
  }
  function findVendorNameInJson(rawText) {
    try {
      return findVendorNameInObject(JSON.parse(rawText));
    } catch (error) {
      return "";
    }
  }
  function findVendorNameInObject(value, depth = 0) {
    if (!value || depth > 2) {
      return "";
    }

    if (Array.isArray(value)) {
      for (let index = 0; index < value.length && index < 3; index += 1) {
        const match = findVendorNameInObject(value[index], depth + 1);
        if (match) {
          return match;
        }
      }
      return "";
    }

    if (typeof value !== "object") {
      return "";
    }

    const preferredKeys = [
      "vendor",
      "vendor_name",
      "vendorName",
      "supplier",
      "supplier_name",
      "supplierName",
      "provider",
      "provider_name",
      "providerName",
      "company",
      "company_name",
      "companyName",
      "organization",
      "organization_name",
      "organizationName",
    ];

    for (let index = 0; index < preferredKeys.length; index += 1) {
      const valueAtKey = value[preferredKeys[index]];
      if (typeof valueAtKey === "string" && valueAtKey.trim()) {
        return valueAtKey.trim();
      }
    }

    const nestedValues = Object.values(value);
    for (let index = 0; index < nestedValues.length; index += 1) {
      const nestedValue = nestedValues[index];
      if (nestedValue && typeof nestedValue === "object") {
        const match = findVendorNameInObject(nestedValue, depth + 1);
        if (match) {
          return match;
        }
      }
    }

    return "";
  }
  function findVendorNameInCsv(rawText) {
    const rows = rawText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 4)
      .map((line) => line.split(",").map((cell) => cell.trim().replace(/^"(.*)"$/, "$1")));

    if (rows.length < 2) {
      return "";
    }

    const headers = rows[0].map((cell) => cell.toLowerCase());
    const vendorIndex = headers.findIndex((cell) => /vendor|supplier|provider|company|organization/.test(cell));
    if (vendorIndex >= 0 && rows[1][vendorIndex]) {
      return rows[1][vendorIndex].trim();
    }

    if (rows[0].length >= 2 && /vendor|supplier|provider|company|organization/.test(rows[0][0].toLowerCase())) {
      return rows[0][1].trim();
    }

    return "";
  }
  function buildPreviewText(rawText, maxCharacters, maxLines) {
    if (!rawText) {
      return "";
    }

    const normalized = rawText.replace(/\r\n/g, "\n").trim();
    if (!normalized) {
      return "";
    }

    const lines = normalized.split("\n");
    const limitedLines = lines.slice(0, maxLines);
    let preview = limitedLines.join("\n");
    let truncated = limitedLines.length < lines.length;

    if (preview.length > maxCharacters) {
      preview = `${preview.slice(0, maxCharacters).trimEnd()}\n...`;
      truncated = true;
    } else if (truncated) {
      preview = `${preview}\n...`;
    }

    return preview;
  }
  function extractFileExtension(fileName) {
    const match = /\.[^.]+$/.exec(fileName);
    return match ? match[0].toLowerCase() : "";
  }
  function deriveDisplayName(fileName) {
    return fileName
      .replace(/\.[^.]+$/, "")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }
  function isTextLikeFile(file, extension) {
    const textExtensions = new Set([".csv", ".json", ".txt", ".md", ".markdown", ".html", ".htm", ".xml"]);
    if (textExtensions.has(extension)) {
      return true;
    }

    const type = (file.type || "").toLowerCase();
    return type.startsWith("text/") || type.includes("json") || type.includes("xml");
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
