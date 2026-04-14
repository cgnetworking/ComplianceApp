  function populateFilters() {
    const controls = getAllControlViews();
    if (els.domainFilter) {
      populateSelect(els.domainFilter, ["All"].concat(uniqueValues(controls, "domain")));
      els.domainFilter.value = valueOrFallback(els.domainFilter, state.domain);
      state.domain = els.domainFilter.value;
    }
    if (els.applicabilityFilter) {
      populateSelect(els.applicabilityFilter, ["All", "Applicable", "Excluded"]);
      els.applicabilityFilter.value = valueOrFallback(els.applicabilityFilter, state.applicability);
      state.applicability = els.applicabilityFilter.value;
    }
    if (els.frequencyFilter) {
      populateSelect(
        els.frequencyFilter,
        ["All"].concat(uniqueValues(controls, "effectiveReviewFrequency").filter((value) => value))
      );
      els.frequencyFilter.value = valueOrFallback(els.frequencyFilter, state.frequency);
      state.frequency = els.frequencyFilter.value;
    }
  }
  function initializeSelection() {
    if (page === "controls" || page === "reports") {
      syncSelectionToVisibleControls();
    }
    if (page === "policies") {
      initializePolicySelection();
    }
    if (page === "risks") {
      syncSelectionToVisibleRisks();
    }
    if (page === "vendors") {
      syncVendorSelection();
    }
  }
  function bindEvents() {
    bindSearchEvents();
    bindFilterEvents();
    bindControlEvents();
    bindPolicyEvents();
    bindUploadEvents();
    bindVendorEvents();
    bindReviewEvents();
    bindRiskEvents();
  }
  function bindSearchEvents() {
    if (!els.searchInput) {
      return;
    }

    const searchablePages = new Set(["controls", "reports", "policies", "risks", "vendors"]);
    if (!searchablePages.has(page)) {
      els.searchInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") {
          return;
        }
        const query = els.searchInput.value.trim();
        const target = query ? `./controls.html?q=${encodeURIComponent(query)}` : "./controls.html";
        window.location.href = target;
      });
      return;
    }

    els.searchInput.addEventListener("input", (event) => {
      state.search = event.target.value.trim();
      syncSearchSelection();
      syncUrlAndRender();
    });
  }
  function bindFilterEvents() {
    if (els.domainFilter) {
      els.domainFilter.addEventListener("change", (event) => {
        state.domain = event.target.value;
        syncSelectionToVisibleControls();
        syncUrlAndRender();
      });
    }

    if (els.applicabilityFilter) {
      els.applicabilityFilter.addEventListener("change", (event) => {
        state.applicability = event.target.value;
        syncSelectionToVisibleControls();
        syncUrlAndRender();
      });
    }

    if (els.frequencyFilter) {
      els.frequencyFilter.addEventListener("change", (event) => {
        state.frequency = event.target.value;
        syncSelectionToVisibleControls();
        syncUrlAndRender();
      });
    }

    if (els.clearFilters) {
      els.clearFilters.addEventListener("click", () => {
        state.search = "";
        state.domain = "All";
        state.applicability = "All";
        state.frequency = "All";
        if (els.searchInput) {
          els.searchInput.value = "";
        }
        if (els.domainFilter) {
          els.domainFilter.value = "All";
        }
        if (els.applicabilityFilter) {
          els.applicabilityFilter.value = "All";
        }
        if (els.frequencyFilter) {
          els.frequencyFilter.value = "All";
        }
        if (page === "policies") {
          initializePolicySelection();
        } else {
          syncSelectionToVisibleControls();
        }
        syncUrlAndRender();
      });
    }
  }
  function bindControlEvents() {
    if (els.controlsBody) {
      els.controlsBody.addEventListener("click", (event) => {
        const policyLink = event.target.closest("a[data-policy-link]");
        if (policyLink) {
          return;
        }
        const row = event.target.closest("[data-control-row]");
        if (!row) {
          return;
        }
        state.selectedControlId = row.dataset.controlRow;
        syncUrlAndRender(renderControlsPage);
      });
    }

    if (!els.controlDetail) {
      return;
    }

    els.controlDetail.addEventListener("change", (event) => {
      const applicability = event.target.closest("[data-control-applicability]");
      if (applicability) {
        setControlApplicability(applicability.dataset.controlApplicability, applicability.value);
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }

      const reviewFrequency = event.target.closest("[data-control-review-frequency]");
      if (reviewFrequency) {
        updateControlReviewFrequency(reviewFrequency.dataset.controlReviewFrequency, reviewFrequency.value);
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }

      const toggle = event.target.closest("[data-control-excluded]");
      if (!toggle) {
        return;
      }
      const controlId = toggle.dataset.controlExcluded;
      setControlExclusion(controlId, toggle.checked);
      populateFilters();
      syncSelectionToVisibleControls();
      syncUrlAndRender();
    });

    els.controlDetail.addEventListener("input", (event) => {
      const reason = event.target.closest("[data-exclusion-reason]");
      if (!reason) {
        return;
      }
      updateControlReason(reason.dataset.exclusionReason, reason.value);
    });
  }
  function bindPolicyEvents() {
    if (els.policyCoverage) {
      els.policyCoverage.addEventListener("click", (event) => {
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        syncUrlAndRender(renderPoliciesPage);
      });
    }

    if (els.selectedControlBanner) {
      els.selectedControlBanner.addEventListener("click", (event) => {
        const clear = event.target.closest("[data-clear-policy-context]");
        if (clear) {
          state.policyContextControlId = "";
          syncUrlAndRender(renderPoliciesPage);
          return;
        }
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        syncUrlAndRender(renderPoliciesPage);
      });
    }

    if (els.documentViewer) {
      els.documentViewer.addEventListener("click", async (event) => {
        const removeButton = event.target.closest("[data-delete-policy]");
        if (!removeButton) {
          return;
        }
        await handlePolicyDelete(removeButton.dataset.deletePolicy);
      });
    }
  }
  function bindUploadEvents() {
    bindFilePicker(els.policyUploadTrigger, els.policyUploadInput, handlePolicyUpload);
    bindFilePicker(els.mappingUploadTrigger, els.mappingUploadInput, handleMappingUpload);
    bindFilePicker(els.vendorUploadTrigger, els.vendorUploadInput, handleVendorUpload);
  }
  function bindVendorEvents() {
    if (!els.vendorResponses) {
      return;
    }
    els.vendorResponses.addEventListener("click", (event) => {
      const target = event.target.closest("[data-vendor-response]");
      if (!target) {
        return;
      }
      state.selectedVendorResponseId = target.dataset.vendorResponse;
      syncUrlAndRender(renderVendorsPage);
    });
  }
  function bindReviewEvents() {
    if (els.monthTabs) {
      els.monthTabs.addEventListener("click", (event) => {
        const target = event.target.closest("[data-month-index]");
        if (!target) {
          return;
        }
        state.monthIndex = Number(target.dataset.monthIndex);
        syncUrlAndRender(renderReviewsPage);
      });
    }

    if (els.activities) {
      els.activities.addEventListener("change", (event) => {
        const target = event.target.closest("[data-activity-id]");
        if (!target) {
          return;
        }
        updateReviewStateSelection(target.dataset.activityId, target.checked);
      });
    }

    if (els.checklist) {
      els.checklist.addEventListener("change", (event) => {
        const target = event.target.closest("[data-check-id]");
        if (!target) {
          return;
        }
        updateReviewStateSelection(target.dataset.checkId, target.checked);
      });
    }

    if (els.checklistAddTrigger) {
      els.checklistAddTrigger.addEventListener("click", () => {
        toggleChecklistAddForm(true);
      });
    }

    if (els.checklistAddCancel) {
      els.checklistAddCancel.addEventListener("click", () => {
        toggleChecklistAddForm(false);
      });
    }

    if (els.checklistRecommendationSelect) {
      els.checklistRecommendationSelect.addEventListener("change", handleChecklistRecommendationSelected);
    }

    if (els.checklistRecommendationAdd) {
      els.checklistRecommendationAdd.addEventListener("click", () => {
        void handleChecklistRecommendationQuickAdd();
      });
    }

    if (els.checklistAddForm) {
      els.checklistAddForm.addEventListener("submit", handleChecklistAddSubmit);
    }

  }
  function bindRiskEvents() {
    if (els.addRiskTrigger) {
      els.addRiskTrigger.addEventListener("click", () => {
        state.isAddingRisk = true;
        state.selectedRiskId = "";
        clearRiskFormStatus();
        syncUrlAndRender(renderRisksPage);
      });
    }

    if (els.riskList) {
      els.riskList.addEventListener("click", (event) => {
        const row = event.target.closest("[data-risk-row]");
        if (!row) {
          return;
        }
        state.selectedRiskId = row.dataset.riskRow;
        state.isAddingRisk = false;
        clearRiskFormStatus();
        syncUrlAndRender(renderRisksPage);
      });
    }

    if (els.riskForm) {
      els.riskForm.addEventListener("input", () => {
        if (!state.riskFormStatus.message) {
          return;
        }
        clearRiskFormStatus();
        renderRiskFormStatus();
      });
      els.riskForm.addEventListener("submit", handleRiskFormSubmit);
    }
  }
  function bindFilePicker(trigger, input, onFilesSelected) {
    if (!trigger || !input) {
      return;
    }
    trigger.addEventListener("click", () => {
      input.click();
    });
    input.addEventListener("change", async (event) => {
      const files = Array.from(event.target.files || []);
      event.target.value = "";
      await onFilesSelected(files);
    });
  }
  function updateReviewStateSelection(itemId, checked) {
    state.reviewState.checklist[itemId] = checked;
    state.reviewState.activities[itemId] = checked;
    saveReviewState();
    renderReviewsPage();
  }
  function syncSearchSelection() {
    if (page === "policies") {
      initializePolicySelection();
      return;
    }
    if (page === "risks") {
      syncSelectionToVisibleRisks();
      return;
    }
    if (page === "vendors") {
      syncVendorSelection();
      return;
    }
    syncSelectionToVisibleControls();
  }
  function syncUrlAndRender(renderer = renderPage) {
    syncUrl();
    renderer();
  }
  function renderPage() {
    switch (page) {
      case "home":
        renderHomePage();
        break;
      case "reports":
        renderReportsPage();
        break;
      case "controls":
        renderControlsPage();
        break;
      case "reviews":
        renderReviewsPage();
        break;
      case "policies":
        renderPoliciesPage();
        break;
      case "risks":
        renderRisksPage();
        break;
      case "vendors":
        renderVendorsPage();
        break;
      default:
        renderHomePage();
        break;
    }
  }
  function renderGlobalOverview(controls, options) {
    if (!els.overview) {
      return;
    }

    const checklistItems = getAllChecklistItems();
    const checklistDone = checklistItems.filter((item) => state.reviewState.checklist[item.id]).length;
    const activityDone = options.currentMonthActivities.filter((item) => state.reviewState.checklist[item.id]).length;
    const mappedPolicies = new Set(controls.flatMap((control) => control.policyDocumentIds)).size;

    const cards = options.mode === "reports"
      ? [
          {
            label: "Controls in view",
            value: controls.length,
            note: controls.length === getAllControlViews().length ? "All controls included in the report." : "Filtered control population for this report.",
          },
          {
            label: "Applicable controls",
            value: controls.filter((control) => getControlView(control).effectiveApplicability === "Applicable").length,
            note: "Applicable controls in the currently filtered set.",
          },
          {
            label: "Mapped policies",
            value: mappedPolicies,
            note: "Unique policies referenced by the visible controls.",
          },
          {
            label: "Current month queue",
            value: `${activityDone}/${options.currentMonthActivities.length}`,
            note: "Review activities completed in the shared checklist tracker.",
          },
        ]
      : [
          {
            label: "Total controls",
            value: controls.length,
            note: "Default Annex A control list available in the portal.",
          },
          {
            label: "Policies embedded",
            value: data.summary.policyCount,
            note: "Policy pages appear when mapping documents are provided.",
          },
          {
            label: `${monthNames[state.monthIndex]} queue`,
            value: `${activityDone}/${options.currentMonthActivities.length}`,
            note: "Checklist tasks due this month.",
          },
          {
            label: "Checklist progress",
            value: `${checklistDone}/${checklistItems.length}`,
            note: "Recurring review checks marked complete.",
          },
        ];

    els.overview.innerHTML = cards.map((card) => `
      <article class="stat-card">
        <span class="stat-label">${escapeHtml(card.label)}</span>
        <p class="stat-value">${escapeHtml(String(card.value))}</p>
        <p class="stat-note">${escapeHtml(card.note)}</p>
      </article>
    `).join("");
  }
  function syncUrl() {
    const query = new URLSearchParams();

    if (page === "controls" || page === "reports" || page === "policies" || page === "risks" || page === "vendors") {
      if (state.search) {
        query.set("q", state.search);
      }
    }
    if ((page === "controls" || page === "reports") && state.domain !== "All") {
      query.set("domain", state.domain);
    }
    if ((page === "controls" || page === "reports") && state.applicability !== "All") {
      query.set("applicability", state.applicability);
    }
    if ((page === "controls" || page === "reports") && state.frequency !== "All") {
      query.set("frequency", state.frequency);
    }
    if (page === "controls" && state.selectedControlId) {
      query.set("control", state.selectedControlId);
    }
    if (page === "policies" && state.policyContextControlId) {
      query.set("control", state.policyContextControlId);
    }
    if (page === "policies" && state.activeDocumentId) {
      query.set("doc", state.activeDocumentId);
    }
    if (page === "reviews" && state.monthIndex !== today.getMonth()) {
      query.set("month", String(state.monthIndex));
    }
    if (page === "risks" && state.selectedRiskId && !state.isAddingRisk) {
      query.set("risk", state.selectedRiskId);
    }
    if (page === "vendors" && state.selectedVendorResponseId) {
      query.set("vendor", state.selectedVendorResponseId);
    }

    const next = query.toString();
    const url = `${window.location.pathname}${next ? `?${next}` : ""}`;
    window.history.replaceState(null, "", url);
  }
  function populateSelect(select, values) {
    select.innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  }
  function valueOrFallback(select, value) {
    const exists = Array.from(select.options).some((option) => option.value === value);
    return exists ? value : select.options[0].value;
  }
  function uniqueValues(items, key) {
    return Array.from(new Set(items.map((item) => item[key]))).sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  }
  function parseMonth(rawValue) {
    const parsed = Number(rawValue);
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 11 ? parsed : today.getMonth();
  }
  function groupBy(items, key) {
    return items.reduce((groups, item) => {
      const group = item[key];
      groups[group] = groups[group] || [];
      groups[group].push(item);
      return groups;
    }, {});
  }
  function loadUploadedPolicies() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(uploadedPolicyKey) || "[]");
      if (!Array.isArray(saved)) {
        return [];
      }
      return saved
        .filter((item) => item && typeof item.id === "string" && typeof item.title === "string" && typeof item.contentHtml === "string")
        .map((item) => ({
          ...item,
          type: item.type || "Uploaded policy",
          owner: item.owner || "Local browser",
          approver: item.approver || "Pending review",
          reviewFrequency: item.reviewFrequency || "Not scheduled",
          path: item.path || "Local upload",
          folder: item.folder || "Uploaded",
          purpose: item.purpose || "",
          isUploaded: true,
        }));
    } catch (error) {
      return [];
    }
  }
  async function saveUploadedPolicies(items) {
    if (isApiPersistence()) {
      return;
    }
    window.localStorage.setItem(uploadedPolicyKey, JSON.stringify(items));
  }
  function loadReviewState() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
      return {
        activities: saved.activities || {},
        checklist: saved.checklist || {},
      };
    } catch (error) {
      return { activities: {}, checklist: {} };
    }
  }
  function saveReviewState() {
    if (!isApiPersistence()) {
      window.localStorage.setItem(storageKey, JSON.stringify(state.reviewState));
      return;
    }

    void apiRequest("/state/review/", {
      method: "PUT",
      body: JSON.stringify({ reviewState: state.reviewState }),
    }).catch(() => {
      window.localStorage.setItem(storageKey, JSON.stringify(state.reviewState));
    });
  }
  function loadControlState() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(controlStateKey) || "{}");
      return typeof saved === "object" && saved ? saved : {};
    } catch (error) {
      return {};
    }
  }
  function saveControlState() {
    if (!isApiPersistence()) {
      window.localStorage.setItem(controlStateKey, JSON.stringify(state.controlState));
      return;
    }

    void apiRequest("/state/control/", {
      method: "PUT",
      body: JSON.stringify({ controlState: state.controlState }),
    }).catch(() => {
      window.localStorage.setItem(controlStateKey, JSON.stringify(state.controlState));
    });
  }
  function setUploadStatus(element, message, tone) {
    if (!element) {
      return;
    }

    element.textContent = message;
    element.classList.remove("is-success", "is-error", "is-warning", "is-info");
    if (tone) {
      element.classList.add(`is-${tone}`);
    }
  }
  function emptySummary() {
    return {
      controlCount: 0,
      documentCount: 0,
      policyCount: 0,
      activityCount: 0,
      checklistCount: 0,
      domainCounts: {},
      documentReviewFrequencies: {},
      checklistFrequencies: {},
    };
  }
  function normalizeDataPayload(payload) {
    if (!payload || typeof payload !== "object") {
      return;
    }

    payload.generatedAt = typeof payload.generatedAt === "string" && payload.generatedAt.trim()
      ? payload.generatedAt
      : new Date().toISOString();
    payload.sourceSnapshot = payload.sourceSnapshot && typeof payload.sourceSnapshot === "object"
      ? payload.sourceSnapshot
      : {};

    const summary = payload.summary && typeof payload.summary === "object" ? payload.summary : {};
    payload.summary = {
      ...emptySummary(),
      ...summary,
      domainCounts: summary.domainCounts && typeof summary.domainCounts === "object" ? summary.domainCounts : {},
      documentReviewFrequencies: summary.documentReviewFrequencies && typeof summary.documentReviewFrequencies === "object"
        ? summary.documentReviewFrequencies
        : {},
      checklistFrequencies: summary.checklistFrequencies && typeof summary.checklistFrequencies === "object"
        ? summary.checklistFrequencies
        : {},
    };

    payload.controls = Array.isArray(payload.controls) ? payload.controls : [];
    payload.documents = Array.isArray(payload.documents) ? payload.documents : [];
    payload.activities = Array.isArray(payload.activities) ? payload.activities : [];
    payload.checklist = Array.isArray(payload.checklist) ? payload.checklist : [];
    payload.policyCoverage = Array.isArray(payload.policyCoverage) ? payload.policyCoverage : [];
  }
  function applyMappingPayload(payload) {
    const mappingPayload = payload && typeof payload === "object" ? payload : {};
    normalizeDataPayload(mappingPayload);

    data.generatedAt = mappingPayload.generatedAt;
    data.sourceSnapshot = mappingPayload.sourceSnapshot;
    data.summary = mappingPayload.summary;
    data.controls = mappingPayload.controls;
    data.documents = mappingPayload.documents;
    data.activities = mappingPayload.activities;
    data.checklist = mappingPayload.checklist;
    data.policyCoverage = mappingPayload.policyCoverage;

    refreshControlsIndex();
    refreshDocumentsIndex();
    pruneControlState();
  }
  function refreshControlsIndex() {
    controlsById.clear();
    data.controls.forEach((control) => {
      if (!control || typeof control !== "object" || typeof control.id !== "string") {
        return;
      }
      if (!Array.isArray(control.documentIds)) {
        control.documentIds = [];
      }
      if (!Array.isArray(control.policyDocumentIds)) {
        control.policyDocumentIds = Array.isArray(control.documentIds) ? control.documentIds : [];
      }
      controlsById.set(control.id, control);
    });
  }
  function pruneControlState() {
    Object.keys(state.controlState).forEach((controlId) => {
      if (!controlsById.has(controlId)) {
        delete state.controlState[controlId];
      }
    });
  }
  function resolveApiBaseUrl() {
    if (window.ISMS_PORTAL_CONFIG && typeof window.ISMS_PORTAL_CONFIG.apiBaseUrl === "string") {
      return window.ISMS_PORTAL_CONFIG.apiBaseUrl.replace(/\/+$/, "");
    }
    return "/api";
  }
  function resolveLoginUrl() {
    if (window.ISMS_PORTAL_CONFIG && typeof window.ISMS_PORTAL_CONFIG.loginUrl === "string") {
      return window.ISMS_PORTAL_CONFIG.loginUrl;
    }
    return "/login/";
  }
  function isApiPersistence() {
    return persistenceMode === "api";
  }
  function updateRuntimeMode() {
    if (!els.runtimeMode) {
      return;
    }

    const hasControls = Array.isArray(data.controls) && data.controls.length > 0;
    const hasExpandedMapping = Array.isArray(data.documents) && data.documents.length > 0;
    const baseLabel = hasControls
      ? (hasExpandedMapping ? "Custom mapping" : "Default controls")
      : "No controls loaded";
    els.runtimeMode.textContent = isApiPersistence() ? `${baseLabel} + API` : baseLabel;
  }
  function updatePersistenceCopy() {
    if (els.policyUploadStatus) {
      els.policyUploadStatus.textContent = isApiPersistence()
        ? "Add markdown, text, or HTML policy files to the shared portal library."
        : "Add markdown, text, or HTML policy files to this browser's library.";
    }
    if (els.vendorUploadStatus) {
      els.vendorUploadStatus.textContent = isApiPersistence()
        ? "Upload completed questionnaires, spreadsheets, or exported response files into the shared portal workspace. Text-based files generate inline previews."
        : "Upload completed questionnaires, spreadsheets, or exported response files. Text-based files generate inline previews.";
    }
    if (els.mappingUploadStatus) {
      els.mappingUploadStatus.textContent = isApiPersistence()
        ? "Upload a control mapping JSON file (.json) to add mapped policy metadata."
        : "Mapping upload requires API mode so it can be stored in PostgreSQL.";
    }
  }
  function refreshDocumentsIndex() {
    documentsById.clear();
    data.documents.concat(uploadedDocuments).forEach((documentItem) => {
      documentsById.set(documentItem.id, documentItem);
    });
  }
  async function loadRemoteState() {
    if (window.location.protocol === "file:") {
      persistenceMode = "local";
      await loadDefaultControls();
      return;
    }

    try {
      const payload = await apiRequest("/state/");
      persistenceMode = payload && payload.persistenceMode === "api" ? "api" : "local";
      applyRemoteState(payload);
    } catch (error) {
      persistenceMode = "local";
      await loadDefaultControls();
    }
  }
  async function loadDefaultControls() {
    try {
      const response = await fetch("/static/default_controls.json", {
        credentials: "same-origin",
      });
      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      if (!Array.isArray(payload)) {
        return;
      }

      const controls = payload
        .filter((item) => item && typeof item.id === "string" && typeof item.name === "string")
        .map((item) => ({
          id: item.id.trim(),
          name: item.name.trim(),
          domain: typeof item.domain === "string" ? item.domain.trim() : "",
          applicability: typeof item.applicability === "string" ? item.applicability.trim() : "",
          implementationModel: "Implemented",
          owner: "",
          reviewFrequency: typeof item.reviewFrequency === "string" && item.reviewFrequency.trim()
            ? item.reviewFrequency.trim()
            : "Annual",
          rationale: "",
          evidence: "",
          documentIds: [],
          policyDocumentIds: [],
          preferredDocumentId: "",
        }))
        .filter((item) => item.id && item.name);
      if (!controls.length) {
        return;
      }

      applyMappingPayload({
        sourceSnapshot: {
          controlRegister: "default_controls.json",
          reviewSchedule: "",
          runtimeDependency: false,
        },
        controls,
      });
    } catch (error) {
      // Ignore local loading errors and continue with empty defaults.
    }
  }
  function applyRemoteState(payload) {
    if (!payload || typeof payload !== "object") {
      return;
    }

    if (payload.mapping && typeof payload.mapping === "object") {
      const remoteControls = Array.isArray(payload.mapping.controls) ? payload.mapping.controls : [];
      if (remoteControls.length) {
        applyMappingPayload(payload.mapping);
      }
    }
    if (Array.isArray(payload.uploadedDocuments)) {
      uploadedDocuments = payload.uploadedDocuments;
    }
    if (Array.isArray(payload.vendorSurveyResponses)) {
      vendorSurveyResponses = payload.vendorSurveyResponses;
    }
    if (Array.isArray(payload.riskRegister)) {
      state.riskRegister = payload.riskRegister.map((item) => normalizeRiskRecord(item)).filter(Boolean);
    }
    if (Array.isArray(payload.checklistItems)) {
      state.checklistItems = normalizeChecklistItems(payload.checklistItems);
    }
    if (Array.isArray(payload.recommendedChecklistItems)) {
      state.recommendedChecklistItems = normalizeChecklistItems(payload.recommendedChecklistItems);
    }
    if (payload.reviewState && typeof payload.reviewState === "object") {
      state.reviewState = {
        activities: payload.reviewState.activities || {},
        checklist: payload.reviewState.checklist || {},
      };
    }
    if (payload.controlState && typeof payload.controlState === "object") {
      state.controlState = payload.controlState;
    }

    refreshControlsIndex();
    refreshDocumentsIndex();
    pruneControlState();
  }
  async function apiRequest(path, options) {
    const requestOptions = options || {};
    const method = requestOptions.method || "GET";
    const headers = new Headers(requestOptions.headers || {});
    const isFormData = typeof FormData !== "undefined" && requestOptions.body instanceof FormData;

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }
    if (requestOptions.body && !isFormData && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const csrfToken = readCookie("csrftoken");
    if (csrfToken && !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(method)) {
      headers.set("X-CSRFToken", csrfToken);
    }

    const response = await fetch(`${apiBaseUrl}${path}`, {
      ...requestOptions,
      method,
      headers,
      credentials: "same-origin",
    });

    if (response.status === 401) {
      const next = `${window.location.pathname}${window.location.search}`;
      window.location.href = `${loginUrl}?next=${encodeURIComponent(next)}`;
      throw new Error("Authentication required.");
    }

    const responseText = await response.text();
    let payload = null;
    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch (error) {
        payload = null;
      }
    }

    if (!response.ok) {
      throw new Error((payload && (payload.detail || payload.message)) || `Request failed (${response.status}).`);
    }

    return payload;
  }
  function readCookie(name) {
    const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : "";
  }
  function portalWorkspaceLabel() {
    return isApiPersistence() ? "shared portal workspace" : "browser workspace";
  }
  function storageSentence() {
    return isApiPersistence() ? "stored in the shared portal." : "stored locally in this browser.";
  }
  function formatDateTime(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "-";
    }
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(parsed);
  }
  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
