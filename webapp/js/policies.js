  function renderPoliciesPage() {
    initializePolicySelection();
    renderSelectedControlBanner();
    renderPolicyCoverageList(filteredPolicyCoverage(), true);
    renderDocumentViewer();
  }
  async function handlePolicyUpload(files) {
    if (!files.length) {
      return;
    }

    setPolicyUploadStatus(
      files.length === 1 ? `Uploading ${files[0].name}...` : `Uploading ${files.length} policy files...`,
    );

    try {
      const result = isApiPersistence() ? await uploadPoliciesToApi(files) : await createUploadedDocuments(files);
      if (!result.documents.length) {
        setPolicyUploadStatus(result.messages[0] || "No supported policy files were selected.", "error");
        return;
      }

      const nextUploadedDocuments = uploadedDocuments.concat(result.documents);
      await saveUploadedPolicies(nextUploadedDocuments);
      uploadedDocuments = nextUploadedDocuments;
      refreshDocumentsIndex();

      state.policyContextControlId = "";
      state.search = "";
      state.activeDocumentId = result.documents[result.documents.length - 1].id;
      if (els.searchInput) {
        els.searchInput.value = "";
      }
      syncUrl();
      renderPoliciesPage();

      const message = result.documents.length === 1
        ? `Uploaded ${result.documents[0].title}.`
        : `Uploaded ${result.documents.length} policies.`;
      setPolicyUploadStatus([message].concat(result.messages).join(" "), "success");
    } catch (error) {
      setPolicyUploadStatus(error.message || "Policy upload failed.", "error");
    }
  }
  async function handleMappingUpload(files) {
    if (!files.length) {
      return;
    }

    const selectedFile = files[0];
    setMappingUploadStatus(`Uploading mapping from ${selectedFile.name}...`, "info");

    if (!isApiPersistence()) {
      setMappingUploadStatus("Mapping uploads require API persistence so the mapping can be stored in PostgreSQL.", "error");
      return;
    }

    try {
      const payload = await uploadMappingToApi(selectedFile);
      applyMappingPayload(payload.mapping);
      initializeSelection();
      syncUrl();
      renderPage();

      setMappingUploadStatus(
        `Mapping uploaded (${data.controls.length} controls, ${data.documents.length} documents).`,
        "success"
      );
    } catch (error) {
      setMappingUploadStatus(error.message || "Mapping upload failed.", "error");
    }
  }
  async function uploadMappingToApi(file) {
    const formData = new FormData();
    formData.append("file", file);

    return apiRequest("/mapping/uploads/", {
      method: "POST",
      body: formData,
    });
  }
  async function createUploadedDocuments(files) {
    const documents = [];
    const messages = [];
    let nextNumber = nextUploadedPolicyNumber(uploadedDocuments);

    for (const file of files) {
      const extension = fileExtension(file.name);
      if (!isSupportedUploadedPolicyType(extension)) {
        messages.push(`${file.name} was skipped because only markdown, text, and HTML files are supported.`);
        continue;
      }

      const rawContent = await readFileAsText(file);
      documents.push(buildUploadedPolicyDocument(file, rawContent, nextNumber));
      nextNumber += 1;
    }

    return { documents, messages };
  }
  async function uploadPoliciesToApi(files) {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });

    const payload = await apiRequest("/policies/uploads/", {
      method: "POST",
      body: formData,
    });

    return {
      documents: Array.isArray(payload.documents) ? payload.documents : [],
      messages: Array.isArray(payload.messages) ? payload.messages : [],
    };
  }
  async function deletePolicyFromApi(documentId) {
    return apiRequest(`/policies/${encodeURIComponent(documentId)}/`, {
      method: "DELETE",
    });
  }
  async function handlePolicyDelete(documentId) {
    const selectedDocumentId = String(documentId || "").trim();
    if (!selectedDocumentId) {
      setPolicyUploadStatus("A policy id is required to delete a policy.", "error");
      return;
    }

    const documentItem = uploadedDocuments.find((item) => item.id === selectedDocumentId);
    if (!documentItem) {
      setPolicyUploadStatus("Only uploaded policies can be deleted from this page.", "error");
      return;
    }

    const shouldDelete = window.confirm(`Delete ${documentItem.id} / ${documentItem.title}? This cannot be undone.`);
    if (!shouldDelete) {
      return;
    }

    setPolicyUploadStatus(`Deleting ${documentItem.id}...`, "info");

    try {
      if (isApiPersistence()) {
        await deletePolicyFromApi(selectedDocumentId);
      }

      const nextUploadedDocuments = uploadedDocuments.filter((item) => item.id !== selectedDocumentId);
      if (!isApiPersistence()) {
        await saveUploadedPolicies(nextUploadedDocuments);
      }
      uploadedDocuments = nextUploadedDocuments;
      refreshDocumentsIndex();

      if (state.activeDocumentId === selectedDocumentId) {
        state.activeDocumentId = "";
      }
      initializePolicySelection();
      syncUrl();
      renderPoliciesPage();
      setPolicyUploadStatus(`Deleted ${documentItem.id} / ${documentItem.title}.`, "success");
    } catch (error) {
      setPolicyUploadStatus(error.message || "Unable to delete the selected policy.", "error");
    }
  }
  function buildUploadedPolicyDocument(file, rawContent, number) {
    const extension = fileExtension(file.name);
    const isHtmlUpload = extension === "html" || extension === "htm";
    const contentHtml = isHtmlUpload ? sanitizeUploadedHtml(rawContent) : markdownToHtml(rawContent);

    return {
      id: formatUploadedPolicyId(number),
      title: fileNameBase(file.name),
      type: "Uploaded policy",
      owner: "Local browser",
      approver: "Pending review",
      reviewFrequency: "Not scheduled",
      path: `Local upload / ${file.name}`,
      folder: "Uploaded",
      purpose: extractPurposeFromMarkdown(rawContent) || `Uploaded from ${file.name}.`,
      contentHtml: contentHtml || "<p>No content was found in the uploaded file.</p>",
      isUploaded: true,
      originalFilename: file.name,
      uploadedAt: new Date().toISOString(),
    };
  }
  function setPolicyUploadStatus(message, tone) {
    if (!els.policyUploadStatus) {
      return;
    }

    els.policyUploadStatus.textContent = message;
    els.policyUploadStatus.className = "helper-note upload-status";
    if (tone === "success") {
      els.policyUploadStatus.classList.add("is-success");
    }
    if (tone === "error") {
      els.policyUploadStatus.classList.add("is-error");
    }
  }
  function setMappingUploadStatus(message, tone) {
    if (!els.mappingUploadStatus) {
      return;
    }
    setUploadStatus(els.mappingUploadStatus, message, tone);
  }
  function isSupportedUploadedPolicyType(extension) {
    return ["md", "markdown", "txt", "html", "htm"].includes(extension);
  }
  function fileExtension(fileName) {
    const parts = String(fileName).toLowerCase().split(".");
    return parts.length > 1 ? parts.pop() : "";
  }
  function fileNameBase(fileName) {
    const withoutExtension = String(fileName).replace(/\.[^.]+$/, "");
    const normalized = withoutExtension.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
    return normalized || fileName;
  }
  function nextUploadedPolicyNumber(items) {
    return items.reduce((max, item) => {
      const match = /^UPL-(\d+)$/i.exec(item.id || "");
      return match ? Math.max(max, Number(match[1])) : max;
    }, 0) + 1;
  }
  function formatUploadedPolicyId(number) {
    return `UPL-${String(number).padStart(2, "0")}`;
  }
  function readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error(`Unable to read ${file.name}.`));
      reader.readAsText(file);
    });
  }
  function inlineMarkup(text) {
    let rendered = escapeHtml(text);
    rendered = rendered.replace(/`([^`]+)`/g, "<code>$1</code>");
    rendered = rendered.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    rendered = rendered.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    return rendered;
  }
  function tableCells(line) {
    return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  }
  function isTableSeparator(line) {
    const stripped = line.trim();
    if (!stripped.startsWith("|")) {
      return false;
    }
    const cells = tableCells(stripped);
    return cells.length > 0 && cells.every((cell) => cell && /^[\-:]+$/.test(cell));
  }
  function markdownToHtml(markdown) {
    const lines = String(markdown).split(/\r?\n/);
    const blocks = [];

    for (let index = 0; index < lines.length;) {
      const line = lines[index].replace(/\s+$/, "");
      const stripped = line.trim();

      if (!stripped) {
        index += 1;
        continue;
      }

      if (stripped.startsWith("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
        const header = tableCells(lines[index]);
        index += 2;
        const body = [];
        while (index < lines.length && lines[index].trim().startsWith("|")) {
          body.push(tableCells(lines[index]));
          index += 1;
        }
        blocks.push(
          "<table><thead><tr>"
            + header.map((cell) => `<th>${inlineMarkup(cell)}</th>`).join("")
            + "</tr></thead><tbody>"
            + body.map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkup(cell)}</td>`).join("")}</tr>`).join("")
            + "</tbody></table>",
        );
        continue;
      }

      if (stripped.startsWith("- ")) {
        const items = [];
        while (index < lines.length && lines[index].trim().startsWith("- ")) {
          items.push(lines[index].trim().slice(2));
          index += 1;
        }
        blocks.push(`<ul>${items.map((item) => `<li>${inlineMarkup(item)}</li>`).join("")}</ul>`);
        continue;
      }

      if (stripped.startsWith("#")) {
        const level = Math.min(stripped.match(/^#+/)[0].length, 6);
        blocks.push(`<h${level}>${inlineMarkup(stripped.slice(level).trim())}</h${level}>`);
        index += 1;
        continue;
      }

      const paragraph = [stripped];
      index += 1;
      while (index < lines.length) {
        const candidate = lines[index].trim();
        if (!candidate) {
          index += 1;
          break;
        }
        if (candidate.startsWith("#") || candidate.startsWith("- ")) {
          break;
        }
        if (candidate.startsWith("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
          break;
        }
        paragraph.push(candidate);
        index += 1;
      }
      blocks.push(`<p>${inlineMarkup(paragraph.join(" "))}</p>`);
    }

    return blocks.join("\n");
  }
  function extractPurposeFromMarkdown(markdown) {
    const match = /^## 1\. Purpose\s+([\s\S]*?)\s+## /m.exec(String(markdown));
    if (!match) {
      return "";
    }
    return match[1]
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .join(" ");
  }
  function sanitizeUploadedHtml(html) {
    const parser = new DOMParser();
    const parsed = parser.parseFromString(String(html), "text/html");

    parsed.querySelectorAll("script,style,iframe,object,embed,form,link,meta").forEach((node) => {
      node.remove();
    });

    parsed.querySelectorAll("*").forEach((element) => {
      Array.from(element.attributes).forEach((attribute) => {
        const name = attribute.name.toLowerCase();
        const value = attribute.value.trim().toLowerCase();
        if (name.startsWith("on")) {
          element.removeAttribute(attribute.name);
        }
        if ((name === "href" || name === "src") && value.startsWith("javascript:")) {
          element.removeAttribute(attribute.name);
        }
      });
    });

    return parsed.body.innerHTML.trim() || `<p>${escapeHtml(html)}</p>`;
  }
  function renderSelectedControlBanner() {
    if (!els.selectedControlBanner) {
      return;
    }
    const control = getControlView(state.policyContextControlId);
    if (!control) {
      els.selectedControlBanner.hidden = true;
      els.selectedControlBanner.innerHTML = "";
      return;
    }
    els.selectedControlBanner.hidden = false;

    const docButtons = control.documentIds.map((documentId) => {
      const documentItem = documentsById.get(documentId);
      if (!documentItem) {
        return "";
      }
      return `
        <button class="doc-button ${documentId === state.activeDocumentId ? "is-active" : ""}" type="button" data-policy-doc="${escapeHtml(documentId)}">
          ${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}
          <small>${escapeHtml(documentItem.type)} / ${escapeHtml(documentItem.reviewFrequency)}</small>
        </button>
      `;
    }).join("");

    els.selectedControlBanner.innerHTML = `
      <article class="panel">
        <div class="detail-header">
          <div>
            <p class="panel-kicker">Opened from control</p>
            <h3>${escapeHtml(control.id)} / ${escapeHtml(control.name)}</h3>
          </div>
          <div class="chip-row">
            <span class="chip">${escapeHtml(control.domain)}</span>
            <span class="chip">${escapeHtml(control.effectiveImplementationModel)}</span>
            <span class="chip">${escapeHtml(control.reviewFrequency)}</span>
          </div>
          <div>
            <button class="ghost-button" type="button" data-clear-policy-context="true">Back to Full Policy List</button>
          </div>
        </div>
        <div class="doc-section">
          <strong>Mapped documents</strong>
          <div class="doc-list">
            ${docButtons || '<div class="empty-state">No embedded documents are mapped to this control.</div>'}
          </div>
        </div>
      </article>
    `;
  }
  function renderPolicyCoverageList(rows, interactive) {
    if (!els.policyCoverage) {
      return;
    }
    if (!rows.length) {
      els.policyCoverage.innerHTML = '<div class="empty-state">No policies match the current selection.</div>';
      return;
    }

    els.policyCoverage.innerHTML = `
      <div class="coverage-list">
        ${rows.map((item) => {
          const documentItem = documentsById.get(item.id);
          const controlId = firstControlIdForDocument(item.id);
          const active = state.activeDocumentId === item.id;
          const href = policyUrl(controlId, item.id);
          const coverageNote = item.controlCount
            ? `${item.controlCount} mapped controls / ${escapeHtml(item.reviewFrequency)}`
            : `Not yet mapped / ${escapeHtml(item.reviewFrequency)}`;
          const coverageBadge = item.controlCount || "New";
          if (!interactive) {
            return `
              <a class="coverage-card coverage-link" href="${href}">
                <div>
                  <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                  <div class="mini-copy">${coverageNote}</div>
                </div>
                <span class="doc-type">${coverageBadge}</span>
              </a>
            `;
          }
          return `
            <button class="coverage-card coverage-button ${active ? "is-selected" : ""}" type="button" data-policy-doc="${escapeHtml(item.id)}">
              <div>
                <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                <div class="mini-copy">${coverageNote}</div>
                <div class="mini-copy">${escapeHtml(documentItem ? documentItem.type : "Document")}</div>
              </div>
              <span class="doc-type">${coverageBadge}</span>
            </button>
          `;
        }).join("")}
      </div>
    `;
  }
  function renderDocumentViewer() {
    if (!els.documentViewer) {
      return;
    }
    const documentItem = documentsById.get(state.activeDocumentId);
    if (!documentItem) {
      els.documentViewer.innerHTML = '<div class="empty-state">Choose a policy to display its embedded content.</div>';
      return;
    }

    const relatedControlViews = getAllControlViews()
      .filter((control) => control.policyDocumentIds.includes(documentItem.id))
      .sort(compareControlViews);
    const relatedControlIds = new Set(relatedControlViews.map((control) => control.id));
    const relatedControls = relatedControlViews
      .slice(0, 8)
      .map((control) => `<a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)}</a>`)
      .join("");
    const mappedControlRows = relatedControlViews.map((control) => `
      <div class="mapping-row">
        <a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)} / ${escapeHtml(control.name)}</a>
        <button
          class="ghost-button danger-button mapping-remove-button"
          type="button"
          data-policy-control-remove="${escapeHtml(control.id)}"
          data-policy-control-document="${escapeHtml(documentItem.id)}"
        >
          Remove
        </button>
      </div>
    `).join("");
    const availableControls = getAllControlViews()
      .filter((control) => !relatedControlIds.has(control.id))
      .sort(compareControlViews);
    const canMapControl = availableControls.length > 0;
    const availableControlOptions = canMapControl
      ? ['<option value="" selected disabled>Select Control</option>'].concat(
        availableControls.map((control) => (
          `<option value="${escapeHtml(control.id)}">${escapeHtml(control.id)} / ${escapeHtml(control.name)}</option>`
        ))
      ).join("")
      : '<option value="" selected>No additional controls available</option>';
    const documentMeta = [
      `Approver: ${escapeHtml(documentItem.approver)}`,
      `Source: ${escapeHtml(documentItem.path)}`,
    ];
    if (documentItem.isUploaded && documentItem.uploadedAt) {
      documentMeta.push(`Uploaded: ${escapeHtml(formatDateTime(documentItem.uploadedAt))}`);
    }
    const documentActions = documentItem.isUploaded
      ? `<button class="ghost-button danger-button" type="button" data-delete-policy="${escapeHtml(documentItem.id)}">Delete Policy</button>`
      : "";

    els.documentViewer.innerHTML = `
      <div class="document-heading">
        <div>
          <p class="panel-kicker">${escapeHtml(documentItem.isUploaded ? "Uploaded document" : "Policy document")}</p>
          <h3>${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}</h3>
        </div>
        <div class="chip-row">
          <span class="doc-type">${escapeHtml(documentItem.type)}</span>
          <span class="chip">${escapeHtml(documentItem.reviewFrequency)}</span>
          <span class="chip">${escapeHtml(documentItem.owner)}</span>
        </div>
        <p class="doc-purpose">${escapeHtml(documentItem.purpose || "No purpose summary found.")}</p>
        <div class="document-meta">
          ${documentMeta.map((item) => `<span>${item}</span>`).join("")}
        </div>
        <div class="chip-row">${relatedControls || '<span class="chip">Not mapped to controls</span>'}</div>
        <div class="doc-section">
          <strong>Control mappings</strong>
          <div class="stack-list">
            ${mappedControlRows || '<div class="empty-state">Not mapped to any controls yet.</div>'}
          </div>
          <div class="quick-add-row" data-policy-control-mapper="${escapeHtml(documentItem.id)}">
            <label class="form-field">
              <span>Control</span>
              <select data-policy-control-select ${canMapControl ? "" : "disabled"}>
                ${availableControlOptions}
              </select>
            </label>
            <button class="ghost-button" type="button" data-policy-control-add="${escapeHtml(documentItem.id)}" disabled>Add mapping</button>
          </div>
        </div>
        ${documentActions ? `<div class="document-actions">${documentActions}</div>` : ""}
      </div>
      <div class="content-frame">${documentItem.contentHtml}</div>
    `;
  }
  function filteredPolicyCoverage() {
    const searchLower = state.search.trim().toLowerCase();
    const contextControl = state.policyContextControlId && controlsById.has(state.policyContextControlId)
      ? getControlView(state.policyContextControlId)
      : null;
    const allowedIds = contextControl ? new Set(contextControl.documentIds) : null;

    return getPolicyLibraryRows().filter((item) => {
      if (allowedIds && !allowedIds.has(item.id)) {
        return false;
      }
      if (!searchLower) {
        return true;
      }
      const documentItem = documentsById.get(item.id);
      const text = [
        item.id,
        item.title,
        item.reviewFrequency,
        documentItem ? documentItem.type : "",
        documentItem ? documentItem.path : "",
        documentItem ? documentItem.originalFilename || "" : "",
      ].join(" ").toLowerCase();
      return text.includes(searchLower);
    });
  }
  function visiblePoliciesForControls(controls) {
    const visibleIds = new Set(controls.flatMap((control) => control.policyDocumentIds));
    return getPolicyLibraryRows().filter((item) => visibleIds.has(item.id));
  }
  function getPolicyLibraryRows() {
    const controlCounts = {};
    getAllControlViews().forEach((control) => {
      control.policyDocumentIds.forEach((documentId) => {
        controlCounts[documentId] = (controlCounts[documentId] || 0) + 1;
      });
    });

    return data.documents
      .concat(uploadedDocuments)
      .filter((documentItem) => isPolicyLibraryDocument(documentItem))
      .map((documentItem) => ({
        id: documentItem.id,
        title: documentItem.title,
        reviewFrequency: documentItem.reviewFrequency,
        type: documentItem.type,
        controlCount: controlCounts[documentItem.id] || 0,
      }))
      .sort(compareDocumentIds);
  }
  function isPolicyLibraryDocument(documentItem) {
    return Boolean(documentItem.isUploaded) || /^(POL|GOV|PR|UPL)-\d+$/i.test(documentItem.id);
  }
  function compareDocumentIds(left, right) {
    const leftParts = splitDocumentId(left.id);
    const rightParts = splitDocumentId(right.id);
    if (leftParts.rank !== rightParts.rank) {
      return leftParts.rank - rightParts.rank;
    }
    if (leftParts.number !== rightParts.number) {
      return leftParts.number - rightParts.number;
    }
    return left.id.localeCompare(right.id, undefined, { numeric: true });
  }
  function splitDocumentId(documentId) {
    const match = /^([A-Z]+)-(\d+)$/i.exec(documentId);
    if (!match) {
      return { rank: Number.MAX_SAFE_INTEGER, number: Number.MAX_SAFE_INTEGER };
    }
    const prefix = match[1].toUpperCase();
    return {
      rank: documentTypeOrder[prefix] ?? Number.MAX_SAFE_INTEGER,
      number: Number(match[2]),
    };
  }
  function compareControlViews(left, right) {
    return String(left.id).localeCompare(String(right.id), undefined, { numeric: true });
  }
  function initializePolicySelection() {
    const coverageRows = filteredPolicyCoverage();
    const contextControl = state.policyContextControlId && controlsById.has(state.policyContextControlId)
      ? getControlView(state.policyContextControlId)
      : null;

    if (state.activeDocumentId && coverageRows.some((item) => item.id === state.activeDocumentId)) {
      return;
    }

    if (contextControl) {
      state.activeDocumentId = contextControl.preferredDocumentId;
      return;
    }

    if (coverageRows.length) {
      state.activeDocumentId = coverageRows[0].id;
    }
  }
  function firstControlIdForDocument(documentId) {
    const match = getAllControlViews().find((control) => control.policyDocumentIds.includes(documentId));
    return match ? match.id : "";
  }
  function policyUrl(controlId, documentId) {
    const query = new URLSearchParams();
    if (controlId) {
      query.set("control", controlId);
    }
    if (documentId) {
      query.set("doc", documentId);
    }
    const suffix = query.toString();
    return `./policies.html${suffix ? `?${suffix}` : ""}`;
  }
