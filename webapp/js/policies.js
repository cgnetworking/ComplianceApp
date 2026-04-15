  const policyLibraryTabs = {
    all: "all",
    approvals: "approvals",
  };
  const pendingPolicyApprover = "Pending review";
  const policyControlPickerState = {
    documentId: "",
    selectedControlId: "",
    showAll: false,
  };

  function normalizePolicyLibraryTab(value) {
    const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
    return normalized === policyLibraryTabs.approvals ? policyLibraryTabs.approvals : policyLibraryTabs.all;
  }

  function normalizePolicyApproverIdentity(value) {
    return typeof value === "string" ? value.trim().toLowerCase() : "";
  }

  function getPolicyLibraryTab() {
    state.policyLibraryTab = normalizePolicyLibraryTab(state.policyLibraryTab);
    return state.policyLibraryTab;
  }

  function currentPolicyUsername() {
    if (!window.ISMS_PORTAL_CONFIG || typeof window.ISMS_PORTAL_CONFIG !== "object") {
      return "";
    }
    const currentUser = window.ISMS_PORTAL_CONFIG.currentUser;
    if (!currentUser || typeof currentUser !== "object") {
      return "";
    }
    return typeof currentUser.username === "string" ? currentUser.username.trim() : "";
  }
  function currentPolicyActorLabel() {
    return currentPolicyUsername() || "Unknown user";
  }
  function currentPolicyUserIsStaff() {
    if (!window.ISMS_PORTAL_CONFIG || typeof window.ISMS_PORTAL_CONFIG !== "object") {
      return false;
    }
    const currentUser = window.ISMS_PORTAL_CONFIG.currentUser;
    if (!currentUser || typeof currentUser !== "object") {
      return false;
    }
    return Boolean(currentUser.isStaff);
  }
  function currentPolicyUserIsPolicyReader() {
    if (!window.ISMS_PORTAL_CONFIG || typeof window.ISMS_PORTAL_CONFIG !== "object") {
      return false;
    }
    const currentUser = window.ISMS_PORTAL_CONFIG.currentUser;
    if (!currentUser || typeof currentUser !== "object") {
      return false;
    }
    return Boolean(currentUser.isPolicyReader);
  }
  function normalizePolicyApproverValue(value) {
    const normalized = typeof value === "string" ? value.trim() : "";
    return normalized || pendingPolicyApprover;
  }
  function syncPoliciesPageCapabilities() {
    const isPolicyReader = currentPolicyUserIsPolicyReader();
    if (els.policyUploadTrigger) {
      els.policyUploadTrigger.hidden = isPolicyReader;
      els.policyUploadTrigger.disabled = isPolicyReader;
    }
    if (els.policyUploadStatus && isPolicyReader) {
      setPolicyUploadStatus("Policy Reader access is view-only.", "info");
    }
  }
  function updateUploadedDocumentEntry(updatedDocument) {
    if (!updatedDocument || typeof updatedDocument !== "object" || typeof updatedDocument.id !== "string") {
      return false;
    }
    const index = uploadedDocuments.findIndex((item) => item.id === updatedDocument.id);
    if (index < 0) {
      return false;
    }
    const mergedDocument = {
      ...uploadedDocuments[index],
      ...updatedDocument,
    };
    const normalizedDocument = typeof normalizeUploadedPolicyItem === "function"
      ? normalizeUploadedPolicyItem(mergedDocument)
      : mergedDocument;
    if (!normalizedDocument) {
      return false;
    }
    uploadedDocuments[index] = normalizedDocument;
    return true;
  }
  async function updatePolicyApproverViaApi(documentId, approver) {
    return apiRequest(`/policies/${encodeURIComponent(documentId)}/approver/`, {
      method: "PATCH",
      body: JSON.stringify({ approver }),
    });
  }
  async function approvePolicyViaApi(documentId) {
    return apiRequest(`/policies/${encodeURIComponent(documentId)}/approval/`, {
      method: "POST",
    });
  }
  function policyApprovalDateLabel(value) {
    const formatted = typeof formatDateWithOrdinal === "function" ? formatDateWithOrdinal(value) : "";
    return formatted && formatted !== "-" ? formatted : "";
  }
  function canCurrentUserApprovePolicy(documentItem) {
    if (!documentItem || !documentItem.isUploaded || currentPolicyUserIsPolicyReader()) {
      return false;
    }
    const currentIdentity = normalizePolicyApproverIdentity(currentPolicyUsername());
    if (!currentIdentity) {
      return false;
    }
    if (documentItem.approvedAt) {
      return false;
    }
    const approverIdentity = normalizePolicyApproverIdentity(documentItem.approver);
    return approverIdentity === currentIdentity;
  }
  function ensurePolicyAuditLogState() {
    if (!state.reviewState || typeof state.reviewState !== "object") {
      state.reviewState = { activities: {}, checklist: {}, completedAt: {}, auditLog: [] };
    }
    if (!Array.isArray(state.reviewState.auditLog)) {
      state.reviewState.auditLog = [];
    }
  }
  function buildLocalPolicyApprovalAuditEntry(documentItem, occurredAt) {
    const approvalDate = policyApprovalDateLabel(occurredAt) || occurredAt;
    return {
      id: `audit-${Math.random().toString(16).slice(2, 14)}`,
      action: "policy_approved",
      entityType: "policy",
      entityId: documentItem.id,
      summary: `Approved ${documentItem.id} / ${documentItem.title} on ${approvalDate}.`,
      occurredAt,
      actor: {
        username: currentPolicyUsername() || "local-user",
        displayName: currentPolicyActorLabel(),
      },
      metadata: {
        source: "policies",
        policyId: documentItem.id,
        policyTitle: documentItem.title,
        approvedBy: currentPolicyUsername() || "local-user",
        approvedAt: occurredAt,
      },
    };
  }
  async function handlePolicyApprovalSelection(checkbox) {
    if (!checkbox) {
      return;
    }
    const documentId = typeof checkbox.dataset.policyApprovalDocument === "string"
      ? checkbox.dataset.policyApprovalDocument.trim()
      : "";
    if (!documentId) {
      checkbox.checked = false;
      return;
    }

    const documentItem = documentsById.get(documentId);
    if (!canCurrentUserApprovePolicy(documentItem)) {
      checkbox.checked = false;
      setPolicyUploadStatus("Only the assigned approver can approve this policy.", "error");
      return;
    }

    checkbox.disabled = true;
    setPolicyUploadStatus(`Recording approval for ${documentItem.id}...`, "info");
    try {
      if (isApiPersistence()) {
        const payload = await approvePolicyViaApi(documentId);
        const updatedDocument = payload && payload.document && typeof payload.document === "object"
          ? payload.document
          : null;
        if (!updatedDocument || !updateUploadedDocumentEntry(updatedDocument)) {
          throw new Error("Approved policy response was invalid.");
        }
        if (payload && payload.reviewState && typeof payload.reviewState === "object") {
          state.reviewState = normalizeReviewStateValue(payload.reviewState);
        }
      } else {
        const occurredAt = new Date().toISOString();
        if (!updateUploadedDocumentEntry({
          id: documentId,
          approvedAt: occurredAt,
          approvedBy: currentPolicyUsername() || "local-user",
        })) {
          throw new Error("Uploaded policy was not found in local storage.");
        }
        ensurePolicyAuditLogState();
        state.reviewState.auditLog = normalizeReviewAuditLogEntries(
          state.reviewState.auditLog.concat(buildLocalPolicyApprovalAuditEntry(documentItem, occurredAt)),
        );
        await saveUploadedPolicies(uploadedDocuments);
        saveReviewState();
      }

      refreshDocumentsIndex();
      initializePolicySelection();
      syncUrl();
      renderPoliciesPage();
      setPolicyUploadStatus(`Approved ${documentItem.id} / ${documentItem.title}.`, "success");
    } catch (error) {
      checkbox.checked = false;
      checkbox.disabled = false;
      const detail = error instanceof Error && error.message
        ? error.message
        : "Policy approval could not be recorded.";
      setPolicyUploadStatus(detail, "error");
    }
  }
  function policyApproverOptions(documentItem) {
    const options = [
      { value: pendingPolicyApprover, label: pendingPolicyApprover },
    ];
    const seenValues = new Set([pendingPolicyApprover.toLowerCase()]);

    state.assignableUsers.forEach((user) => {
      if (!user || typeof user !== "object") {
        return;
      }
      const username = typeof user.username === "string" ? user.username.trim() : "";
      if (!username) {
        return;
      }
      const key = username.toLowerCase();
      if (seenValues.has(key)) {
        return;
      }
      seenValues.add(key);
      const displayName = typeof user.displayName === "string" ? user.displayName.trim() : "";
      const label = displayName && displayName.toLowerCase() !== key
        ? `${displayName} (${username})`
        : username;
      options.push({ value: username, label });
    });

    const currentApprover = normalizePolicyApproverValue(documentItem && documentItem.approver);
    const currentKey = currentApprover.toLowerCase();
    if (!seenValues.has(currentKey)) {
      options.push({ value: currentApprover, label: currentApprover });
    }
    return options;
  }
  function renderPolicyApproverField(documentItem) {
    if (!documentItem || !documentItem.isUploaded || !currentPolicyUserIsStaff()) {
      return "";
    }
    const options = policyApproverOptions(documentItem);
    const selectedApprover = normalizePolicyApproverValue(documentItem.approver);
    return `
      <div class="doc-section">
        <label class="form-field document-approver-field">
          <span>Policy approver</span>
          <select
            data-policy-approver-select
            data-policy-approver-document="${escapeHtml(documentItem.id)}"
          >
            ${options.map((item) => {
              const selected = item.value.toLowerCase() === selectedApprover.toLowerCase() ? " selected" : "";
              return `<option value="${escapeHtml(item.value)}"${selected}>${escapeHtml(item.label)}</option>`;
            }).join("")}
          </select>
        </label>
        <p class="helper-note">Only admins can update policy approver assignments.</p>
      </div>
    `;
  }
  async function handlePolicyApproverSelection(selectElement) {
    if (!selectElement) {
      return;
    }
    const documentId = typeof selectElement.dataset.policyApproverDocument === "string"
      ? selectElement.dataset.policyApproverDocument.trim()
      : "";
    if (!documentId || !currentPolicyUserIsStaff()) {
      return;
    }

    const selectedApprover = normalizePolicyApproverValue(selectElement.value);
    const documentItem = documentsById.get(documentId);
    if (!documentItem || !documentItem.isUploaded) {
      setPolicyUploadStatus("Only uploaded policies can have approvers assigned.", "error");
      return;
    }
    if (normalizePolicyApproverValue(documentItem.approver).toLowerCase() === selectedApprover.toLowerCase()) {
      return;
    }

    setPolicyUploadStatus(`Updating approver for ${documentItem.id}...`, "info");
    try {
      if (isApiPersistence()) {
        const payload = await updatePolicyApproverViaApi(documentId, selectedApprover);
        const updatedDocument = payload && payload.document && typeof payload.document === "object"
          ? payload.document
          : null;
        if (!updatedDocument || !updateUploadedDocumentEntry(updatedDocument)) {
          throw new Error("Updated policy response was invalid.");
        }
      } else {
        if (!updateUploadedDocumentEntry({
          id: documentId,
          approver: selectedApprover,
          approvedAt: "",
          approvedBy: "",
        })) {
          throw new Error("Uploaded policy was not found in local storage.");
        }
        await saveUploadedPolicies(uploadedDocuments);
      }

      refreshDocumentsIndex();
      initializePolicySelection();
      syncUrl();
      renderPoliciesPage();
      setPolicyUploadStatus("Policy approver updated.", "success");
    } catch (error) {
      const detail = error instanceof Error && error.message
        ? error.message
        : "Policy approver could not be updated.";
      setPolicyUploadStatus(detail, "error");
    }
  }

  function renderPolicyLibraryTabs() {
    const tabContainer = document.getElementById("policy-library-tabs");
    if (!tabContainer) {
      return;
    }
    const activeTab = getPolicyLibraryTab();
    tabContainer.querySelectorAll("[data-policy-library-tab]").forEach((button) => {
      const tabValue = normalizePolicyLibraryTab(button.dataset.policyLibraryTab);
      const isActive = tabValue === activeTab;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  }

  function bindPolicyLibraryTabs() {
    const tabContainer = document.getElementById("policy-library-tabs");
    if (!tabContainer || tabContainer.dataset.policyTabsBound === "true") {
      return;
    }
    tabContainer.dataset.policyTabsBound = "true";
    tabContainer.addEventListener("click", (event) => {
      const tabButton = event.target.closest("[data-policy-library-tab]");
      if (!tabButton) {
        return;
      }
      const nextTab = normalizePolicyLibraryTab(tabButton.dataset.policyLibraryTab);
      if (nextTab === getPolicyLibraryTab()) {
        return;
      }
      state.policyLibraryTab = nextTab;
      initializePolicySelection();
      syncUrlAndRender(renderPoliciesPage);
    });
  }

  function renderPoliciesPage() {
    bindPolicyLibraryTabs();
    renderPolicyLibraryTabs();
    syncPoliciesPageCapabilities();
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
      approver: "Pending review",
      approvedAt: "",
      approvedBy: "",
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
    if (tone === "info") {
      els.policyUploadStatus.classList.add("is-info");
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
            <span class="chip">${escapeHtml(control.effectiveApplicability)}</span>
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
    const activeTab = getPolicyLibraryTab();
    if (!rows.length) {
      if (activeTab === policyLibraryTabs.approvals) {
        const username = normalizePolicyApproverIdentity(currentPolicyUsername());
        const message = username
          ? "No policies are currently assigned to you for approval."
          : "My approvals is unavailable because the current user could not be resolved.";
        els.policyCoverage.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
        return;
      }
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
          const approvedDate = policyApprovalDateLabel(documentItem ? documentItem.approvedAt : "");
          const approvalNote = approvedDate
            ? `<div class="mini-copy">Approved ${escapeHtml(approvedDate)}</div>`
            : "";
          if (!interactive) {
            return `
              <a class="coverage-card coverage-link" href="${href}">
                <div>
                  <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                  <div class="mini-copy">${coverageNote}</div>
                  ${approvalNote}
                </div>
                <span class="doc-type">${coverageBadge}</span>
              </a>
            `;
          }
          if (activeTab === policyLibraryTabs.approvals && canCurrentUserApprovePolicy(documentItem)) {
            return `
              <article class="coverage-card coverage-approval-card ${active ? "is-selected" : ""}">
                <label class="policy-approval-toggle">
                  <input
                    type="checkbox"
                    data-policy-approval-checkbox="true"
                    data-policy-approval-document="${escapeHtml(item.id)}"
                    aria-label="Approve ${escapeHtml(item.id)} / ${escapeHtml(item.title)}"
                  >
                  <span>Approve</span>
                </label>
                <button class="coverage-approval-button" type="button" data-policy-doc="${escapeHtml(item.id)}">
                  <div>
                    <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                    <div class="mini-copy">${coverageNote}</div>
                    <div class="mini-copy">Waiting on your approval</div>
                  </div>
                </button>
              </article>
            `;
          }
          return `
            <button class="coverage-card coverage-button ${active ? "is-selected" : ""}" type="button" data-policy-doc="${escapeHtml(item.id)}">
              <div>
                <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
                <div class="mini-copy">${coverageNote}</div>
                <div class="mini-copy">${escapeHtml(documentItem ? documentItem.type : "Document")}</div>
                ${approvalNote}
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
    const visibleRows = filteredPolicyCoverage();
    const activeDocumentIsVisible = visibleRows.some((item) => item.id === state.activeDocumentId);
    const documentItem = documentsById.get(state.activeDocumentId);
    if (!documentItem || !activeDocumentIsVisible) {
      policyControlPickerState.documentId = "";
      policyControlPickerState.selectedControlId = "";
      policyControlPickerState.showAll = false;
      els.documentViewer.innerHTML = '<div class="empty-state">Choose a policy to display its embedded content.</div>';
      return;
    }
    if (policyControlPickerState.documentId !== documentItem.id) {
      policyControlPickerState.selectedControlId = "";
      policyControlPickerState.showAll = false;
    }
    policyControlPickerState.documentId = documentItem.id;

    const relatedControlViews = getAllControlViews()
      .filter((control) => control.policyDocumentIds.includes(documentItem.id))
      .sort(compareControlViews);
    const isPolicyReader = currentPolicyUserIsPolicyReader();
    const relatedControlIds = new Set(relatedControlViews.map((control) => control.id));
    const relatedControls = relatedControlViews
      .slice(0, 8)
      .map((control) => `<a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)}</a>`)
      .join("");
    const mappedControlRows = relatedControlViews.map((control) => `
      <div class="mapping-row">
        <a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)} / ${escapeHtml(control.name)}</a>
        ${isPolicyReader ? "" : `
          <button
            class="ghost-button danger-button mapping-remove-button"
            type="button"
            data-policy-control-remove="${escapeHtml(control.id)}"
            data-policy-control-document="${escapeHtml(documentItem.id)}"
          >
            Remove
          </button>
        `}
      </div>
    `).join("");
    const availableControls = getAllControlViews()
      .filter((control) => !relatedControlIds.has(control.id))
      .sort(compareControlViews);
    const canMapControl = !isPolicyReader && availableControls.length > 0;
    const documentMeta = [];
    if (documentItem.isUploaded) {
      documentMeta.push(`Approver: ${escapeHtml(normalizePolicyApproverValue(documentItem.approver))}`);
      if (documentItem.path) {
        documentMeta.push(`Source: ${escapeHtml(documentItem.path)}`);
      }
      if (documentItem.approvedAt) {
        const approvedDate = policyApprovalDateLabel(documentItem.approvedAt) || formatDateTime(documentItem.approvedAt);
        const approvedBy = typeof documentItem.approvedBy === "string" && documentItem.approvedBy.trim()
          ? ` by ${documentItem.approvedBy.trim()}`
          : "";
        documentMeta.push(`Approved: ${escapeHtml(approvedDate)}${escapeHtml(approvedBy)}`);
      } else {
        documentMeta.push("Approval: Pending");
      }
    } else if (documentItem.path) {
      documentMeta.push(`Source: ${escapeHtml(documentItem.path)}`);
    }
    if (documentItem.isUploaded && documentItem.uploadedAt) {
      documentMeta.push(`Uploaded: ${escapeHtml(formatDateTime(documentItem.uploadedAt))}`);
    }
    const documentChips = documentItem.isUploaded
      ? ""
      : `
        <div class="chip-row">
          ${documentItem.type ? `<span class="doc-type">${escapeHtml(documentItem.type)}</span>` : ""}
          ${documentItem.reviewFrequency ? `<span class="chip">${escapeHtml(documentItem.reviewFrequency)}</span>` : ""}
        </div>
      `;
    const documentActions = documentItem.isUploaded && !isPolicyReader
      ? `<button class="ghost-button danger-button" type="button" data-delete-policy="${escapeHtml(documentItem.id)}">Delete Policy</button>`
      : "";
    const approverFieldMarkup = renderPolicyApproverField(documentItem);
    const controlMappingEditor = isPolicyReader
      ? '<p class="helper-note">Policy Reader access is view-only. Control mappings cannot be edited.</p>'
      : `
        <div class="quick-add-row" data-policy-control-mapper="${escapeHtml(documentItem.id)}">
          <label class="form-field" for="policy-control-picker-input">
            <span>Control</span>
            <div class="recommendation-picker" data-policy-control-picker>
              <input
                id="policy-control-picker-input"
                type="search"
                data-policy-control-input
                placeholder="${canMapControl ? "Search controls" : "No additional controls available"}"
                autocomplete="off"
                aria-haspopup="listbox"
                aria-expanded="false"
                aria-controls="policy-control-picker-list"
                ${canMapControl ? "" : "disabled"}
              >
              <div
                class="recommendation-picker-list"
                id="policy-control-picker-list"
                data-policy-control-list
                role="listbox"
                hidden
              ></div>
            </div>
          </label>
          <button class="ghost-button" type="button" data-policy-control-add="${escapeHtml(documentItem.id)}" disabled>Add mapping</button>
        </div>
      `;

    els.documentViewer.innerHTML = `
      <div class="document-heading">
        <div>
          <p class="panel-kicker">${escapeHtml(documentItem.isUploaded ? "Uploaded document" : "Policy document")}</p>
          <h3>${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}</h3>
        </div>
        ${documentChips}
        <p class="doc-purpose">${escapeHtml(documentItem.purpose || "No purpose summary found.")}</p>
        <div class="document-meta">
          ${documentMeta.map((item) => `<span>${item}</span>`).join("")}
        </div>
        ${approverFieldMarkup}
        <div class="chip-row">${relatedControls || '<span class="chip">Not mapped to controls</span>'}</div>
        <div class="doc-section">
          <strong>Control mappings</strong>
          <div class="stack-list">
            ${mappedControlRows || '<div class="empty-state">Not mapped to any controls yet.</div>'}
          </div>
          ${controlMappingEditor}
        </div>
        ${documentActions ? `<div class="document-actions">${documentActions}</div>` : ""}
      </div>
      <div class="content-frame">${documentItem.contentHtml}</div>
    `;
    renderPolicyControlOptions();
  }
  function policyControlMapper() {
    if (!els.documentViewer) {
      return null;
    }
    return els.documentViewer.querySelector("[data-policy-control-mapper]");
  }
  function policyControlPickerInput(mapper = policyControlMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-policy-control-input]");
  }
  function policyControlPickerList(mapper = policyControlMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-policy-control-list]");
  }
  function policyControlPickerAddButton(mapper = policyControlMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-policy-control-add]");
  }
  function normalizePolicyControlQuery(value) {
    return String(value || "").trim().toLowerCase();
  }
  function policyControlLabel(control) {
    return `${control.id} / ${control.name}`;
  }
  function availablePolicyControlOptions(documentId = state.activeDocumentId) {
    const normalizedDocumentId = String(documentId || "").trim();
    if (!normalizedDocumentId) {
      return [];
    }
    return getAllControlViews()
      .filter((control) => !control.policyDocumentIds.includes(normalizedDocumentId))
      .sort(compareControlViews);
  }
  function filteredPolicyControlOptions(options, query) {
    const normalizedQuery = normalizePolicyControlQuery(query);
    if (!normalizedQuery) {
      return options;
    }
    return options.filter((control) => `${control.id} ${control.name}`.toLowerCase().includes(normalizedQuery));
  }
  function findPolicyControlOptionById(documentId, controlId) {
    const normalizedControlId = String(controlId || "").trim();
    if (!normalizedControlId) {
      return null;
    }
    return availablePolicyControlOptions(documentId).find((control) => control.id === normalizedControlId) || null;
  }
  function findExactPolicyControlOptionByInput(documentId, rawValue) {
    const normalizedValue = normalizePolicyControlQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const options = availablePolicyControlOptions(documentId);
    const exactLabelMatch = options.find((control) => policyControlLabel(control).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }
    return options.find((control) => (
      control.id.toLowerCase() === normalizedValue
      || control.name.toLowerCase() === normalizedValue
      || `${control.id} ${control.name}`.toLowerCase() === normalizedValue
    )) || null;
  }
  function findPolicyControlOptionByInputValue(documentId, rawValue, exactOnly = false) {
    const normalizedValue = normalizePolicyControlQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const options = availablePolicyControlOptions(documentId);
    const exactLabelMatch = options.find((control) => policyControlLabel(control).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }

    const exactMatch = options.find((control) => (
      control.id.toLowerCase() === normalizedValue
      || control.name.toLowerCase() === normalizedValue
      || `${control.id} ${control.name}`.toLowerCase() === normalizedValue
    ));
    if (exactMatch) {
      return exactMatch;
    }

    if (exactOnly) {
      return null;
    }
    return options.find((control) => `${control.id} ${control.name}`.toLowerCase().includes(normalizedValue)) || null;
  }
  function openPolicyControlPicker() {
    const mapper = policyControlMapper();
    const input = policyControlPickerInput(mapper);
    const list = policyControlPickerList(mapper);
    if (!mapper || !input || !list || input.disabled) {
      return;
    }
    list.hidden = false;
    mapper.classList.add("is-open");
    input.setAttribute("aria-expanded", "true");
  }
  function closePolicyControlPicker() {
    const mapper = policyControlMapper();
    const input = policyControlPickerInput(mapper);
    const list = policyControlPickerList(mapper);
    if (!mapper || !input || !list) {
      return;
    }
    list.hidden = true;
    mapper.classList.remove("is-open");
    input.setAttribute("aria-expanded", "false");
  }
  function applyPolicyControlPickerSelection(control, shouldClose = true) {
    const mapper = policyControlMapper();
    const input = policyControlPickerInput(mapper);
    const addButton = policyControlPickerAddButton(mapper);
    if (!mapper || !input || !addButton || !control) {
      return;
    }
    policyControlPickerState.selectedControlId = control.id;
    policyControlPickerState.showAll = false;
    input.value = policyControlLabel(control);
    addButton.disabled = false;
    renderPolicyControlOptions();
    if (shouldClose) {
      closePolicyControlPicker();
    }
  }
  function bindPolicyControlPickerEvents() {
    const mapper = policyControlMapper();
    const input = policyControlPickerInput(mapper);
    const list = policyControlPickerList(mapper);
    if (!mapper || !input || !list || input.dataset.policyControlPickerBound) {
      return;
    }

    input.dataset.policyControlPickerBound = "true";

    input.addEventListener("focus", () => {
      policyControlPickerState.showAll = true;
      renderPolicyControlOptions();
      openPolicyControlPicker();
    });
    input.addEventListener("click", () => {
      policyControlPickerState.showAll = true;
      renderPolicyControlOptions();
      openPolicyControlPicker();
    });
    input.addEventListener("blur", () => {
      window.setTimeout(closePolicyControlPicker, 120);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closePolicyControlPicker();
        return;
      }
      if (event.key !== "Enter") {
        return;
      }
      const documentId = mapper.dataset.policyControlMapper || state.activeDocumentId;
      const selectedControl = findPolicyControlOptionById(documentId, policyControlPickerState.selectedControlId)
        || findPolicyControlOptionByInputValue(documentId, input.value);
      if (!selectedControl) {
        return;
      }
      applyPolicyControlPickerSelection(selectedControl, true);
      event.preventDefault();
    });

    list.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    list.addEventListener("click", (event) => {
      const option = event.target.closest("[data-policy-control-id]");
      if (!option) {
        return;
      }
      const documentId = mapper.dataset.policyControlMapper || state.activeDocumentId;
      const selectedControl = findPolicyControlOptionById(documentId, option.dataset.policyControlId);
      if (!selectedControl) {
        return;
      }
      applyPolicyControlPickerSelection(selectedControl, true);
    });
  }
  function renderPolicyControlOptions() {
    const mapper = policyControlMapper();
    const input = policyControlPickerInput(mapper);
    const list = policyControlPickerList(mapper);
    const addButton = policyControlPickerAddButton(mapper);
    if (!mapper || !input || !list || !addButton) {
      return;
    }

    bindPolicyControlPickerEvents();

    const documentId = mapper.dataset.policyControlMapper || state.activeDocumentId;
    const allOptions = availablePolicyControlOptions(documentId);
    const queryForFilter = policyControlPickerState.showAll ? "" : input.value;
    const visibleOptions = filteredPolicyControlOptions(allOptions, queryForFilter);

    const hasOptions = allOptions.length > 0;
    input.disabled = !hasOptions;
    input.placeholder = hasOptions
      ? "Search controls"
      : "No additional controls available";
    if (!hasOptions) {
      policyControlPickerState.selectedControlId = "";
      addButton.disabled = true;
      input.value = "";
      list.innerHTML = '<div class="recommendation-option-empty">No additional controls available</div>';
      closePolicyControlPicker();
      return;
    }

    const exactMatch = findExactPolicyControlOptionByInput(documentId, input.value);
    if (exactMatch) {
      policyControlPickerState.selectedControlId = exactMatch.id;
    } else if (!input.value.trim() || !visibleOptions.some((item) => item.id === policyControlPickerState.selectedControlId)) {
      policyControlPickerState.selectedControlId = "";
    }

    if (!visibleOptions.length) {
      list.innerHTML = '<div class="recommendation-option-empty">No matching controls</div>';
    } else {
      list.innerHTML = visibleOptions.map((item) => `
        <button
          class="recommendation-option ${item.id === policyControlPickerState.selectedControlId ? "is-active" : ""}"
          type="button"
          data-policy-control-id="${escapeHtml(item.id)}"
          role="option"
          aria-selected="${item.id === policyControlPickerState.selectedControlId ? "true" : "false"}"
        >
          ${escapeHtml(policyControlLabel(item))}
        </button>
      `).join("");
    }

    addButton.disabled = !policyControlPickerState.selectedControlId;
  }
  function handlePolicyControlPickerInputChanged() {
    policyControlPickerState.showAll = false;
    renderPolicyControlOptions();
    openPolicyControlPicker();
  }
  function resolvePolicyControlPickerControlId(documentId, mapperElement) {
    const mapper = mapperElement || policyControlMapper();
    if (!mapper) {
      return "";
    }

    const resolvedDocumentId = documentId || mapper.dataset.policyControlMapper || state.activeDocumentId;
    const selectedOption = findPolicyControlOptionById(resolvedDocumentId, policyControlPickerState.selectedControlId);
    if (selectedOption) {
      return selectedOption.id;
    }

    const input = policyControlPickerInput(mapper);
    if (!input) {
      return "";
    }
    const typedOption = findPolicyControlOptionByInputValue(resolvedDocumentId, input.value);
    return typedOption ? typedOption.id : "";
  }
  function filteredPolicyCoverage() {
    const searchLower = state.search.trim().toLowerCase();
    const contextControl = state.policyContextControlId && controlsById.has(state.policyContextControlId)
      ? getControlView(state.policyContextControlId)
      : null;
    const allowedIds = contextControl ? new Set(contextControl.documentIds) : null;
    const activeTab = getPolicyLibraryTab();
    const myApproverIdentity = normalizePolicyApproverIdentity(currentPolicyUsername());

    return getPolicyLibraryRows().filter((item) => {
      if (allowedIds && !allowedIds.has(item.id)) {
        return false;
      }
      const documentItem = documentsById.get(item.id);
      if (activeTab === policyLibraryTabs.approvals) {
        if (!myApproverIdentity) {
          return false;
        }
        if (!documentItem || !documentItem.isUploaded || documentItem.approvedAt) {
          return false;
        }
        const approverIdentity = normalizePolicyApproverIdentity(documentItem ? documentItem.approver : "");
        if (approverIdentity !== myApproverIdentity) {
          return false;
        }
      }
      if (!searchLower) {
        return true;
      }
      const text = [
        item.id,
        item.title,
        item.reviewFrequency,
        documentItem ? documentItem.type : "",
        documentItem ? documentItem.path : "",
        documentItem ? documentItem.approvedBy || "" : "",
        documentItem ? documentItem.approvedAt || "" : "",
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

    if (
      contextControl
      && contextControl.preferredDocumentId
      && coverageRows.some((item) => item.id === contextControl.preferredDocumentId)
    ) {
      state.activeDocumentId = contextControl.preferredDocumentId;
      return;
    }

    if (coverageRows.length) {
      state.activeDocumentId = coverageRows[0].id;
      return;
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
