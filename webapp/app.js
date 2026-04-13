(function () {
  const data = window.ISMS_DATA;
  if (!data) {
    return;
  }

  const monthNames = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
  ];
  const shortMonths = monthNames.map((month) => month.slice(0, 3));
  const cadenceLabels = ["Annual", "Quarterly", "Monthly", "Event", "Change"];
  const domainColors = {
    Organizational: "#7442b8",
    People: "#9d3f9d",
    Physical: "#d05ad4",
    Technological: "#4e92e6",
  };
  const documentTypeOrder = {
    POL: 0,
    GOV: 1,
    PR: 2,
    UPL: 3,
  };
  const apiBaseUrl = resolveApiBaseUrl();
  const loginUrl = resolveLoginUrl();
  const storageKey = "isms-policy-portal-review-state-v1";
  const controlStateKey = "isms-policy-portal-control-state-v1";
  const uploadedPolicyKey = "isms-policy-portal-uploaded-policies-v1";
  const vendorSurveyKey = "isms-policy-portal-vendor-surveys-v1";
  const riskRegisterKey = "isms-policy-portal-risk-register-v1";
  let persistenceMode = "local";
  const controlsById = new Map(data.controls.map((control) => [control.id, control]));
  let uploadedDocuments = loadUploadedPolicies();
  let vendorSurveyResponses = loadVendorResponses();
  const documentsById = new Map(data.documents.concat(uploadedDocuments).map((documentItem) => [documentItem.id, documentItem]));
  const today = new Date();
  const page = document.body.dataset.page || "home";
  const params = new URLSearchParams(window.location.search);

  const state = {
    search: params.get("q") || "",
    domain: params.get("domain") || "All",
    applicability: params.get("applicability") || "All",
    frequency: params.get("frequency") || "All",
    monthIndex: parseMonth(params.get("month")),
    selectedControlId: params.get("control"),
    policyContextControlId: params.get("control"),
    activeDocumentId: params.get("doc"),
    selectedRiskId: params.get("risk") || "",
    selectedVendorResponseId: params.get("vendor"),
    riskRegister: loadRiskRegister(),
    isAddingRisk: false,
    riskFormStatus: { message: "", tone: "" },
    reviewState: loadReviewState(),
    controlState: loadControlState(),
  };

  const els = {
    runtimeMode: document.getElementById("runtime-mode"),
    generatedAt: document.getElementById("generated-at"),
    searchInput: document.getElementById("search-input"),
    domainFilter: document.getElementById("domain-filter"),
    applicabilityFilter: document.getElementById("applicability-filter"),
    frequencyFilter: document.getElementById("frequency-filter"),
    clearFilters: document.getElementById("clear-filters"),
    overview: document.getElementById("overview"),
    frameworkChart: document.getElementById("framework-chart"),
    timelineChart: document.getElementById("timeline-chart"),
    reportDomains: document.getElementById("report-domains"),
    controlsBody: document.getElementById("controls-body"),
    controlDetail: document.getElementById("control-detail"),
    selectedControlBanner: document.getElementById("selected-control-banner"),
    policyCoverage: document.getElementById("policy-coverage"),
    documentViewer: document.getElementById("document-viewer"),
    policyUploadTrigger: document.getElementById("policy-upload-trigger"),
    policyUploadInput: document.getElementById("policy-upload-input"),
    policyUploadStatus: document.getElementById("policy-upload-status"),
    vendorUploadTrigger: document.getElementById("vendor-upload-trigger"),
    vendorUploadInput: document.getElementById("vendor-upload-input"),
    vendorUploadStatus: document.getElementById("vendor-upload-status"),
    vendorOverview: document.getElementById("vendor-overview"),
    vendorResponses: document.getElementById("vendor-responses"),
    vendorDetail: document.getElementById("vendor-detail"),
    monthTabs: document.getElementById("month-tabs"),
    activities: document.getElementById("activities"),
    checklistSummary: document.getElementById("checklist-summary"),
    checklist: document.getElementById("checklist"),
    homeUpcoming: document.getElementById("home-upcoming"),
    homeDomains: document.getElementById("home-domains"),
    homePolicies: document.getElementById("home-policies"),
    addRiskTrigger: document.getElementById("add-risk-trigger"),
    riskList: document.getElementById("risk-list"),
    riskForm: document.getElementById("risk-form"),
    riskFormKicker: document.getElementById("risk-form-kicker"),
    riskFormTitle: document.getElementById("risk-form-title"),
    riskFormCopy: document.getElementById("risk-form-copy"),
    riskNameInput: document.getElementById("risk-name"),
    riskDateInput: document.getElementById("risk-date"),
    riskOwnerInput: document.getElementById("risk-owner"),
    riskClosedDateInput: document.getElementById("risk-closed-date"),
    riskSubmitButton: document.getElementById("risk-submit-button"),
    riskFormStatus: document.getElementById("risk-form-status"),
    riskLevelInputs: Array.from(document.querySelectorAll('input[name="initial-risk-level"]')),
  };

  void init();

  async function init() {
    await loadRemoteState();
    updateRuntimeMode();
    updatePersistenceCopy();
    if (els.generatedAt) {
      els.generatedAt.textContent = formatDateTime(data.generatedAt);
    }
    if (els.searchInput) {
      els.searchInput.value = state.search;
    }

    populateFilters();
    initializeSelection();
    bindEvents();
    renderPage();
  }

  function populateFilters() {
    const controls = getAllControlViews();
    if (els.domainFilter) {
      populateSelect(els.domainFilter, ["All"].concat(uniqueValues(controls, "domain")));
      els.domainFilter.value = valueOrFallback(els.domainFilter, state.domain);
      state.domain = els.domainFilter.value;
    }
    if (els.applicabilityFilter) {
      populateSelect(els.applicabilityFilter, ["All"].concat(uniqueValues(controls, "effectiveApplicability")));
      els.applicabilityFilter.value = valueOrFallback(els.applicabilityFilter, state.applicability);
      state.applicability = els.applicabilityFilter.value;
    }
    if (els.frequencyFilter) {
      populateSelect(els.frequencyFilter, ["All"].concat(uniqueValues(controls, "reviewFrequency")));
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
    if (els.searchInput) {
      if (page === "controls" || page === "reports" || page === "policies" || page === "risks" || page === "vendors") {
        els.searchInput.addEventListener("input", (event) => {
          state.search = event.target.value.trim();
          if (page === "policies") {
            initializePolicySelection();
          } else if (page === "risks") {
            syncSelectionToVisibleRisks();
          } else if (page === "vendors") {
            syncVendorSelection();
          } else {
            syncSelectionToVisibleControls();
          }
          syncUrl();
          renderPage();
        });
      } else {
        els.searchInput.addEventListener("keydown", (event) => {
          if (event.key !== "Enter") {
            return;
          }
          const query = els.searchInput.value.trim();
          const target = query ? `./controls.html?q=${encodeURIComponent(query)}` : "./controls.html";
          window.location.href = target;
        });
      }
    }

    if (els.domainFilter) {
      els.domainFilter.addEventListener("change", (event) => {
        state.domain = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });
    }

    if (els.applicabilityFilter) {
      els.applicabilityFilter.addEventListener("change", (event) => {
        state.applicability = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });
    }

    if (els.frequencyFilter) {
      els.frequencyFilter.addEventListener("change", (event) => {
        state.frequency = event.target.value;
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
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
        syncUrl();
        renderPage();
      });
    }

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
        syncUrl();
        renderControlsPage();
      });
    }

    if (els.controlDetail) {
      els.controlDetail.addEventListener("change", (event) => {
        const toggle = event.target.closest("[data-control-excluded]");
        if (!toggle) {
          return;
        }
        const controlId = toggle.dataset.controlExcluded;
        setControlExclusion(controlId, toggle.checked);
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrl();
        renderPage();
      });

      els.controlDetail.addEventListener("input", (event) => {
        const reason = event.target.closest("[data-exclusion-reason]");
        if (!reason) {
          return;
        }
        updateControlReason(reason.dataset.exclusionReason, reason.value);
      });
    }

    if (els.policyCoverage) {
      els.policyCoverage.addEventListener("click", (event) => {
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        syncUrl();
        renderPoliciesPage();
      });
    }

    if (els.selectedControlBanner) {
      els.selectedControlBanner.addEventListener("click", (event) => {
        const clear = event.target.closest("[data-clear-policy-context]");
        if (clear) {
          state.policyContextControlId = "";
          syncUrl();
          renderPoliciesPage();
          return;
        }
        const target = event.target.closest("[data-policy-doc]");
        if (!target) {
          return;
        }
        state.activeDocumentId = target.dataset.policyDoc;
        syncUrl();
        renderPoliciesPage();
      });
    }

    if (els.policyUploadTrigger && els.policyUploadInput) {
      els.policyUploadTrigger.addEventListener("click", () => {
        els.policyUploadInput.click();
      });

      els.policyUploadInput.addEventListener("change", async (event) => {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        await handlePolicyUpload(files);
      });
    }

    if (els.vendorUploadTrigger && els.vendorUploadInput) {
      els.vendorUploadTrigger.addEventListener("click", () => {
        els.vendorUploadInput.click();
      });

      els.vendorUploadInput.addEventListener("change", async (event) => {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        await handleVendorUpload(files);
      });
    }

    if (els.vendorResponses) {
      els.vendorResponses.addEventListener("click", (event) => {
        const target = event.target.closest("[data-vendor-response]");
        if (!target) {
          return;
        }
        state.selectedVendorResponseId = target.dataset.vendorResponse;
        syncUrl();
        renderVendorsPage();
      });
    }

    if (els.monthTabs) {
      els.monthTabs.addEventListener("click", (event) => {
        const target = event.target.closest("[data-month-index]");
        if (!target) {
          return;
        }
        state.monthIndex = Number(target.dataset.monthIndex);
        syncUrl();
        renderReviewsPage();
      });
    }

    if (els.activities) {
      els.activities.addEventListener("change", (event) => {
        const target = event.target.closest("[data-activity-id]");
        if (!target) {
          return;
        }
        state.reviewState.activities[target.dataset.activityId] = target.checked;
        saveReviewState();
        renderReviewsPage();
      });
    }

    if (els.checklist) {
      els.checklist.addEventListener("change", (event) => {
        const target = event.target.closest("[data-check-id]");
        if (!target) {
          return;
        }
        state.reviewState.checklist[target.dataset.checkId] = target.checked;
        saveReviewState();
        renderReviewsPage();
      });
    }

    if (els.addRiskTrigger) {
      els.addRiskTrigger.addEventListener("click", () => {
        state.isAddingRisk = true;
        state.selectedRiskId = "";
        clearRiskFormStatus();
        syncUrl();
        renderRisksPage();
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
        syncUrl();
        renderRisksPage();
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

  function renderHomePage() {
    const controls = getAllControlViews();
    renderGlobalOverview(controls, {
      mode: "home",
      currentMonthActivities: monthlyActivities(state.monthIndex),
    });
    renderHomeUpcoming();
    renderHomeDomains(controls);
    renderHomePolicies();
  }

  function renderReportsPage() {
    const controls = filteredControls();
    renderGlobalOverview(controls, {
      mode: "reports",
      currentMonthActivities: monthlyActivities(state.monthIndex),
    });
    renderFrameworkChart(controls);
    renderTimelineChart();
    renderReportDomains(controls);
    renderPolicyCoverageList(visiblePoliciesForControls(controls), false);
  }

  function renderControlsPage() {
    const controls = filteredControls();
    renderControlsTable(controls);
    renderControlDetail();
  }

  function renderReviewsPage() {
    renderReviewOverview();
    renderMonthTabs();
    renderActivities();
    renderChecklist();
  }

  function renderPoliciesPage() {
    initializePolicySelection();
    renderSelectedControlBanner();
    renderPolicyCoverageList(filteredPolicyCoverage(), true);
    renderDocumentViewer();
  }

  function renderRisksPage() {
    const risks = filteredRisks();
    syncSelectionToVisibleRisks(risks);
    renderRiskOverview();
    renderRiskList(risks);
    renderRiskForm();
  }

  function renderRiskOverview() {
    if (!els.overview) {
      return;
    }

    const openRisks = state.riskRegister.filter((risk) => !isRiskClosed(risk));
    const closedRisks = state.riskRegister.filter((risk) => isRiskClosed(risk));
    const highRisks = openRisks.filter((risk) => risk.initialRiskLevel >= 4);

    const cards = [
      {
        label: "Total risks",
        value: state.riskRegister.length,
        note: state.riskRegister.length ? `Business risks currently stored in the ${riskRegisterLabel()}.` : "No business risks have been captured yet.",
      },
      {
        label: "Open risks",
        value: openRisks.length,
        note: openRisks.length ? "Risks without a closure date." : "All captured risks are currently closed.",
      },
      {
        label: "High risks",
        value: highRisks.length,
        note: highRisks.length ? "Open risks with an initial risk level of 4 or 5." : "No open risks are currently rated at level 4 or 5.",
      },
      {
        label: "Closed risks",
        value: closedRisks.length,
        note: closedRisks.length ? "Risks with a recorded closure date." : "No risks have been marked closed yet.",
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

  function renderRiskList(risks) {
    if (!els.riskList) {
      return;
    }

    if (!state.riskRegister.length) {
      els.riskList.innerHTML = '<div class="empty-state">No risks are in the register yet. Use <strong>Add New Risk</strong> to create the first entry.</div>';
      return;
    }

    if (!risks.length) {
      els.riskList.innerHTML = '<div class="empty-state">No risks match the current search.</div>';
      return;
    }

    const activeRiskId = state.isAddingRisk ? "" : state.selectedRiskId;
    els.riskList.innerHTML = `
      <div class="table-shell risk-table-shell">
        <table>
          <thead>
            <tr>
              <th>Risk</th>
              <th>Level</th>
              <th>Date</th>
              <th>Risk Owner</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${risks.map((risk) => `
              <tr class="${risk.id === activeRiskId ? "is-selected" : ""}" data-risk-row="${escapeHtml(risk.id)}">
                <td class="risk-title-cell">
                  <strong>${escapeHtml(risk.risk)}</strong>
                  <div class="mini-copy">${escapeHtml(isRiskClosed(risk) ? `Closed on ${formatDate(risk.closedDate)}` : "Open risk")}</div>
                </td>
                <td>
                  <span class="risk-level-badge level-${risk.initialRiskLevel}">Level ${escapeHtml(String(risk.initialRiskLevel))}</span>
                </td>
                <td>${escapeHtml(formatDate(risk.date))}</td>
                <td>${escapeHtml(risk.owner)}</td>
                <td>
                  <span class="status-pill ${isRiskClosed(risk) ? "is-closed" : "is-active"}">
                    ${escapeHtml(isRiskClosed(risk) ? `Closed ${formatDate(risk.closedDate)}` : "Open")}
                  </span>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderRiskForm() {
    const selectedRisk = getSelectedRisk();
    const isEditing = Boolean(selectedRisk);

    if (els.riskFormKicker) {
      els.riskFormKicker.textContent = isEditing ? "Selected risk" : "New risk";
    }
    if (els.riskFormTitle) {
      els.riskFormTitle.textContent = isEditing ? "Update risk register entry" : "Capture a new risk";
    }
    if (els.riskFormCopy) {
      els.riskFormCopy.textContent = isEditing
        ? `Update the selected risk and save changes to keep the ${riskRegisterLabel()} current.`
        : `Use this form to add a new risk entry to the ${riskRegisterLabel()}.`;
    }
    if (els.riskNameInput) {
      els.riskNameInput.value = isEditing ? selectedRisk.risk : "";
    }
    if (els.riskDateInput) {
      els.riskDateInput.value = isEditing ? selectedRisk.date : todayDateValue();
    }
    if (els.riskOwnerInput) {
      els.riskOwnerInput.value = isEditing ? selectedRisk.owner : "";
    }
    if (els.riskClosedDateInput) {
      els.riskClosedDateInput.value = isEditing ? selectedRisk.closedDate : "";
    }
    if (els.riskSubmitButton) {
      els.riskSubmitButton.textContent = isEditing ? "Save Changes" : "Save Risk";
    }

    setRiskLevelSelection(isEditing ? selectedRisk.initialRiskLevel : 3);
    renderRiskFormStatus();
  }

  function renderRiskFormStatus() {
    if (!els.riskFormStatus) {
      return;
    }

    const { message, tone } = state.riskFormStatus;
    els.riskFormStatus.textContent = message || `Risk entries are ${storageSentence()}`;
    els.riskFormStatus.className = "helper-note risk-form-status";
    if (tone === "success") {
      els.riskFormStatus.classList.add("is-success");
    }
    if (tone === "error") {
      els.riskFormStatus.classList.add("is-error");
    }
  }

  async function handleRiskFormSubmit(event) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const riskText = String(formData.get("risk") || "").trim();
    const initialRiskLevel = normalizeRiskLevel(formData.get("initial-risk-level"));
    const raisedDate = normalizeDateInputValue(formData.get("risk-date"));
    const riskOwner = String(formData.get("risk-owner") || "").trim();
    const closedDate = normalizeDateInputValue(formData.get("risk-closed-date"));
    const existingRisk = getSelectedRisk();
    const isEditing = Boolean(existingRisk);

    if (!riskText || !initialRiskLevel || !raisedDate || !riskOwner) {
      setRiskFormStatus("Complete the risk, initial risk level, date, and risk owner before saving.", "error");
      renderRiskFormStatus();
      return;
    }

    if (closedDate && closedDate < raisedDate) {
      setRiskFormStatus("Risk Closed Date cannot be earlier than the Date raised.", "error");
      renderRiskFormStatus();
      return;
    }

    const now = new Date().toISOString();
    const riskId = isEditing ? existingRisk.id : createRiskId();
    const nextRisk = {
      id: riskId,
      risk: riskText,
      initialRiskLevel,
      date: raisedDate,
      owner: riskOwner,
      closedDate,
      createdAt: isEditing ? existingRisk.createdAt || now : now,
      updatedAt: now,
    };

    const previousRiskRegister = state.riskRegister.slice();
    state.riskRegister = isEditing
      ? state.riskRegister.map((risk) => (risk.id === riskId ? nextRisk : risk))
      : [nextRisk].concat(state.riskRegister);

    try {
      await saveRiskRegister();
    } catch (error) {
      state.riskRegister = previousRiskRegister;
      setRiskFormStatus(error.message || "Unable to save the risk register entry.", "error");
      renderRiskFormStatus();
      return;
    }

    state.selectedRiskId = riskId;
    state.isAddingRisk = false;
    setRiskFormStatus(
      isEditing ? `Risk updated in the ${riskRegisterLabel()}.` : `Risk added to the ${riskRegisterLabel()}.`,
      "success"
    );
    syncUrl();
    renderRisksPage();
  }

  function setRiskFormStatus(message, tone) {
    state.riskFormStatus = {
      message: message || "",
      tone: tone || "",
    };
  }

  function clearRiskFormStatus() {
    setRiskFormStatus("", "");
  }

  function setRiskLevelSelection(level) {
    els.riskLevelInputs.forEach((input) => {
      input.checked = Number(input.value) === level;
    });
  }

  function renderVendorsPage() {
    syncVendorSelection();
    renderVendorOverview();
    renderVendorResponseList();
    renderVendorDetail();
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

  function renderGlobalOverview(controls, options) {
    if (!els.overview) {
      return;
    }

    const checklistDone = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;
    const activityDone = options.currentMonthActivities.filter((item) => state.reviewState.activities[item.id]).length;
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
            note: "Review activities completed in this browser.",
          },
        ]
      : [
          {
            label: "Total controls",
            value: controls.length,
            note: "Embedded Annex A register available locally.",
          },
          {
            label: "Policies embedded",
            value: data.summary.policyCount,
            note: "Policy pages remain available without the workbook.",
          },
          {
            label: `${monthNames[state.monthIndex]} queue`,
            value: `${activityDone}/${options.currentMonthActivities.length}`,
            note: "Current month review completion.",
          },
          {
            label: "Checklist progress",
            value: `${checklistDone}/${data.checklist.length}`,
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

  function renderReviewOverview() {
    if (!els.overview) {
      return;
    }

    const monthItems = monthlyActivities(state.monthIndex);
    const completedMonthItems = monthItems.filter((item) => state.reviewState.activities[item.id]).length;
    const completedChecklist = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;

    const cards = [
      {
        label: `${monthNames[state.monthIndex]} queue`,
        value: `${completedMonthItems}/${monthItems.length}`,
        note: "Scheduled activities completed this month.",
      },
      {
        label: "Annual activities",
        value: data.activities.length,
        note: "Review tasks loaded from the annual schedule snapshot.",
      },
      {
        label: "Checklist progress",
        value: `${completedChecklist}/${data.checklist.length}`,
        note: "Recurring checks completed in this browser.",
      },
      {
        label: "Quarterly checks",
        value: data.checklist.filter((item) => item.frequency === "Quarterly").length,
        note: "Recurring quarterly checks in the embedded checklist.",
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

  function renderHomeUpcoming() {
    if (!els.homeUpcoming) {
      return;
    }

    const upcoming = orderedActivitiesFromCurrentMonth().slice(0, 5);
    els.homeUpcoming.innerHTML = `
      <div class="stack-list">
        ${upcoming.map((activity) => `
          <article class="list-card">
            <strong>${escapeHtml(activity.activity)}</strong>
            <div class="mini-copy">${escapeHtml(activity.month)} / ${escapeHtml(activity.frequency)} / ${escapeHtml(activity.owner)}</div>
            <div class="mini-copy">Evidence: ${escapeHtml(activity.evidence)}</div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderHomeDomains(controls) {
    if (!els.homeDomains) {
      return;
    }

    const total = controls.length || 1;
    const rows = uniqueValues(controls, "domain").map((domain) => {
      const count = controls.filter((control) => control.domain === domain).length;
      return { domain, count, width: (count / total) * 100 };
    });

    els.homeDomains.innerHTML = `
      <div class="stack-list">
        ${rows.map((row) => `
          <article class="metric-row">
            <div class="metric-head">
              <strong>${escapeHtml(row.domain)}</strong>
              <span>${row.count}</span>
            </div>
            <div class="metric-bar">
              <span style="width:${row.width}%;background:${domainColors[row.domain] || "#7442b8"}"></span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderHomePolicies() {
    if (!els.homePolicies) {
      return;
    }

    const topPolicies = data.policyCoverage.slice(0, 6);
    els.homePolicies.innerHTML = `
      <div class="coverage-list">
        ${topPolicies.map((item) => `
          <a class="coverage-card coverage-link" href="${policyUrl(null, item.id)}">
            <div>
              <strong>${escapeHtml(item.id)} / ${escapeHtml(item.title)}</strong>
              <div class="mini-copy">${item.controlCount} mapped controls / ${escapeHtml(item.reviewFrequency)}</div>
            </div>
            <span class="doc-type">${item.controlCount}</span>
          </a>
        `).join("")}
      </div>
    `;
  }

  function renderFrameworkChart(controls) {
    if (!els.frameworkChart) {
      return;
    }
    if (!controls.length) {
      els.frameworkChart.innerHTML = '<div class="empty-state">No controls are available for the current filter set.</div>';
      return;
    }

    const visibleDomains = uniqueValues(controls, "domain");
    const series = visibleDomains.map((domain) => {
      const scopedControls = controls.filter((control) => control.domain === domain);
      return {
        name: domain,
        color: domainColors[domain] || "#7442b8",
        values: cadenceLabels.map((label) => scopedControls.filter((control) => reviewCadence(control.reviewFrequency) === label).length),
      };
    });

    const width = 760;
    const height = 240;
    const padding = { top: 16, right: 20, bottom: 42, left: 36 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(1, ...series.flatMap((item) => item.values));
    const stepX = plotWidth / Math.max(1, cadenceLabels.length - 1);

    const gridLines = [];
    for (let index = 0; index <= 4; index += 1) {
      const y = padding.top + (plotHeight * index) / 4;
      const label = Math.round(maxValue - (maxValue * index) / 4);
      gridLines.push(`
        <line class="chart-grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>
        <text class="axis-label" x="${padding.left - 10}" y="${y + 4}" text-anchor="end">${label}</text>
      `);
    }

    const paths = series.map((item) => {
      const points = item.values.map((value, index) => ({
        x: padding.left + stepX * index,
        y: padding.top + plotHeight - (value / maxValue) * plotHeight,
      }));

      return `
        <path d="${buildSmoothPath(points)}" fill="none" stroke="${item.color}" stroke-width="3.5" stroke-linecap="round"></path>
        ${points.map((point) => `<circle class="chart-point" cx="${point.x}" cy="${point.y}" r="4.5" fill="${item.color}"></circle>`).join("")}
      `;
    }).join("");

    const axisLabels = cadenceLabels.map((label, index) => {
      const x = padding.left + stepX * index;
      return `<text class="axis-label" x="${x}" y="${height - 10}" text-anchor="middle">${escapeHtml(label)}</text>`;
    }).join("");

    els.frameworkChart.innerHTML = `
      <div class="chart-wrap">
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Coverage by review cadence">
          ${gridLines.join("")}
          <line class="chart-axis-line" x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}"></line>
          ${paths}
          ${axisLabels}
        </svg>
        <div class="legend-row">
          ${series.map((item) => `
            <span class="legend-item">
              <span class="legend-swatch" style="background:${item.color}"></span>
              ${escapeHtml(item.name)}
            </span>
          `).join("")}
        </div>
      </div>
    `;
  }

  function renderTimelineChart() {
    if (!els.timelineChart) {
      return;
    }

    const windows = buildAuditWindows();
    if (!windows.length) {
      els.timelineChart.innerHTML = '<div class="empty-state">No annual review windows are available.</div>';
      return;
    }

    els.timelineChart.innerHTML = `
      <div class="timeline-grid">
        <div class="timeline-head">
          <div class="timeline-label-slot"></div>
          <div class="timeline-month-row">
            ${shortMonths.map((month, index) => `
              <span class="timeline-month ${index === today.getMonth() ? "is-current" : ""}">${escapeHtml(month)}</span>
            `).join("")}
          </div>
        </div>
        ${windows.map((windowItem) => {
          const left = `${(windowItem.start / 12) * 100}%`;
          const width = `${((windowItem.end - windowItem.start + 1) / 12) * 100}%`;
          return `
            <div class="timeline-row">
              <div class="timeline-label-block">
                <strong>${escapeHtml(windowItem.label)}</strong>
                <span>${windowItem.count} activities</span>
              </div>
              <div class="timeline-track">
                <div class="timeline-columns">
                  ${shortMonths.map((_, index) => `<span class="${index === today.getMonth() ? "is-current" : ""}"></span>`).join("")}
                </div>
                <div class="timeline-bar" style="left:${left};width:${width};background:${windowItem.color}"></div>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderReportDomains(controls) {
    if (!els.reportDomains) {
      return;
    }
    if (!controls.length) {
      els.reportDomains.innerHTML = '<div class="empty-state">No control counts are available for the current filter set.</div>';
      return;
    }

    const total = controls.length;
    const rows = uniqueValues(controls, "domain").map((domain) => {
      const count = controls.filter((control) => control.domain === domain).length;
      return { domain, count, width: (count / total) * 100 };
    });

    els.reportDomains.innerHTML = `
      <div class="stack-list">
        ${rows.map((row) => `
          <article class="metric-row">
            <div class="metric-head">
              <strong>${escapeHtml(row.domain)}</strong>
              <span>${row.count} controls</span>
            </div>
            <div class="metric-bar">
              <span style="width:${row.width}%;background:${domainColors[row.domain] || "#7442b8"}"></span>
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderControlsTable(controls) {
    if (!els.controlsBody) {
      return;
    }
    if (!controls.length) {
      els.controlsBody.innerHTML = `
        <tr>
          <td colspan="5"><div class="empty-state">No controls match the current filters.</div></td>
        </tr>
      `;
      return;
    }

    els.controlsBody.innerHTML = controls.map((control) => {
      return `
      <tr class="${control.id === state.selectedControlId ? "is-selected" : ""}" data-control-row="${escapeHtml(control.id)}">
        <td><a class="control-link" data-policy-link="true" href="${policyUrl(control.id, control.preferredDocumentId)}">${escapeHtml(control.id)}</a></td>
        <td>${escapeHtml(control.name)}</td>
        <td>${escapeHtml(control.domain)}</td>
        <td>${escapeHtml(control.effectiveImplementationModel)}</td>
        <td>${escapeHtml(control.reviewFrequency)}</td>
      </tr>
    `;
    }).join("");
  }

  function renderControlDetail() {
    if (!els.controlDetail) {
      return;
    }
    const control = getControlView(state.selectedControlId);
    if (!control) {
      els.controlDetail.innerHTML = '<div class="empty-state">Select a control row to inspect its mapping and linked policies.</div>';
      return;
    }

    const mappedDocuments = control.documentIds.map((documentId) => {
      const documentItem = documentsById.get(documentId);
      if (!documentItem) {
        return "";
      }
      return `
        <a class="doc-button ${documentId === control.preferredDocumentId ? "is-active" : ""}" href="${policyUrl(control.id, documentId)}">
          ${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}
          <small>${escapeHtml(documentItem.type)} / ${escapeHtml(documentItem.reviewFrequency)}</small>
        </a>
      `;
    }).join("");

    els.controlDetail.innerHTML = `
      <div class="detail-header">
        <div>
          <p class="panel-kicker">Selected control</p>
          <h3>${escapeHtml(control.id)} / ${escapeHtml(control.name)}</h3>
        </div>
        <div class="chip-row">
          <span class="chip">${escapeHtml(control.domain)}</span>
          <span class="chip">${escapeHtml(control.effectiveApplicability)}</span>
          <span class="chip">${escapeHtml(control.effectiveImplementationModel)}</span>
          <span class="status-pill ${control.policyDocumentIds.length ? "is-active" : ""}">${control.policyDocumentIds.length} mapped policies</span>
        </div>
      </div>

      <div class="detail-grid">
        <article class="detail-card">
          <strong>Rationale</strong>
          <div class="mini-copy">${escapeHtml(control.rationale)}</div>
        </article>
        <article class="detail-card">
          <strong>Evidence</strong>
          <div class="mini-copy">${escapeHtml(control.evidence)}</div>
        </article>
        <article class="detail-card">
          <strong>Owner</strong>
          <div class="mini-copy">${escapeHtml(control.owner)}</div>
        </article>
        <article class="detail-card">
          <strong>Review frequency</strong>
          <div class="mini-copy">${escapeHtml(control.reviewFrequency)}</div>
        </article>
      </div>

      <div class="doc-section">
        <strong>Open mapped policy page</strong>
        <div class="doc-list">
          ${mappedDocuments || '<div class="empty-state">No embedded documents are mapped to this control.</div>'}
        </div>
      </div>

      <div class="doc-section">
        <div class="detail-card exclusion-card">
          <strong>Exclusion status</strong>
          <label class="toggle-row ${control.isBaseExcluded ? "is-disabled" : ""}">
            <input
              type="checkbox"
              data-control-excluded="${escapeHtml(control.id)}"
              ${control.isExcluded ? "checked" : ""}
              ${control.isBaseExcluded ? "disabled" : ""}
            >
            <span>${control.isBaseExcluded ? "Excluded in source snapshot" : "Mark control as excluded"}</span>
          </label>
          <p class="mini-copy">
            ${escapeHtml(control.isBaseExcluded ? "This control is already excluded in the embedded source data." : "Locally excluded controls display as Excluded in this portal and retain an exclusion rationale in browser storage.")}
          </p>
          ${control.isExcluded ? `
            <div class="text-area-field">
              <label for="exclusion-reason-${escapeHtml(control.id)}">Exclusion Reason</label>
              <textarea
                id="exclusion-reason-${escapeHtml(control.id)}"
                data-exclusion-reason="${escapeHtml(control.id)}"
                placeholder="Document why this control is excluded."
                ${control.isBaseExcluded ? "readonly" : ""}
              >${escapeHtml(control.exclusionReason)}</textarea>
              ${!control.isBaseExcluded && !control.exclusionReason.trim() ? '<p class="helper-note is-warning">Add an exclusion reason for this locally excluded control.</p>' : ""}
            </div>
          ` : ""}
        </div>
      </div>
    `;
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
          <p class="detail-subline">${escapeHtml(control.rationale)}</p>
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

    const relatedControls = data.controls
      .filter((control) => control.documentIds.includes(documentItem.id))
      .slice(0, 8)
      .map((control) => `<a class="chip" href="./controls.html?control=${encodeURIComponent(control.id)}">${escapeHtml(control.id)}</a>`)
      .join("");
    const documentMeta = [
      `Approver: ${escapeHtml(documentItem.approver)}`,
      `Source: ${escapeHtml(documentItem.path)}`,
    ];
    if (documentItem.isUploaded && documentItem.uploadedAt) {
      documentMeta.push(`Uploaded: ${escapeHtml(formatDateTime(documentItem.uploadedAt))}`);
    }

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
      </div>
      <div class="content-frame">${documentItem.contentHtml}</div>
    `;
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

  function renderMonthTabs() {
    if (!els.monthTabs) {
      return;
    }
    els.monthTabs.innerHTML = monthNames.map((month, index) => `
      <button class="month-tab ${index === state.monthIndex ? "is-active" : ""}" type="button" data-month-index="${index}">
        ${escapeHtml(month)}
      </button>
    `).join("");
  }

  function renderActivities() {
    if (!els.activities) {
      return;
    }
    const activities = monthlyActivities(state.monthIndex);
    if (!activities.length) {
      els.activities.innerHTML = `<div class="empty-state">No scheduled activities for ${escapeHtml(monthNames[state.monthIndex])}.</div>`;
      return;
    }

    els.activities.innerHTML = `
      <div class="activity-list">
        ${activities.map((activity) => {
          const isDone = Boolean(state.reviewState.activities[activity.id]);
          return `
            <article class="activity-card ${isDone ? "is-done" : ""}">
              <div class="activity-top">
                <div>
                  <strong>${escapeHtml(activity.activity)}</strong>
                  <div class="mini-copy">${escapeHtml(activity.owner)} / ${escapeHtml(activity.frequency)}</div>
                </div>
                <span class="status-pill ${isDone ? "is-success" : "is-active"}">${isDone ? "Done" : "Open"}</span>
              </div>
              <p class="activity-evidence">Evidence: ${escapeHtml(activity.evidence)}</p>
              <label>
                <input type="checkbox" data-activity-id="${escapeHtml(activity.id)}" ${isDone ? "checked" : ""}>
                Mark this review activity complete
              </label>
            </article>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderChecklist() {
    if (!els.checklist || !els.checklistSummary) {
      return;
    }

    const completedCount = data.checklist.filter((item) => state.reviewState.checklist[item.id]).length;
    const grouped = groupBy(data.checklist, "category");

    els.checklistSummary.innerHTML = [
      `<span class="chip">${completedCount}/${data.checklist.length} complete</span>`,
      ...Object.entries(data.summary.checklistFrequencies).map(([frequency, count]) => `<span class="chip">${escapeHtml(frequency)} / ${count}</span>`),
    ].join("");

    els.checklist.innerHTML = Object.entries(grouped).map(([category, items]) => `
      <section class="checklist-section">
        <h3>${escapeHtml(category)}</h3>
        ${items.map((item) => {
          const isDone = Boolean(state.reviewState.checklist[item.id]);
          return `
            <article class="check-item ${isDone ? "is-done" : ""}">
              <div class="check-top">
                <div>
                  <strong>${escapeHtml(item.item)}</strong>
                  <div class="mini-copy">${escapeHtml(item.frequency)} / ${escapeHtml(item.owner)}</div>
                </div>
                <span class="status-pill ${isDone ? "is-success" : ""}">${isDone ? "Done" : "Track"}</span>
              </div>
              <label>
                <input type="checkbox" data-check-id="${escapeHtml(item.id)}" ${isDone ? "checked" : ""}>
                Mark this checklist item complete
              </label>
            </article>
          `;
        }).join("")}
      </section>
    `).join("");
  }

  function getAllControlViews() {
    return data.controls.map((control) => getControlView(control)).filter(Boolean);
  }

  function getControlView(controlOrId) {
    const control = typeof controlOrId === "string" ? controlsById.get(controlOrId) : controlOrId;
    if (!control) {
      return null;
    }
    const stored = state.controlState[control.id] || {};
    const baseExcluded = isBaseExcluded(control);
    const localExcluded = Boolean(stored.excluded) && !baseExcluded;
    const effectiveExcluded = baseExcluded || localExcluded;
    return {
      ...control,
      isBaseExcluded: baseExcluded,
      isLocallyExcluded: localExcluded,
      isExcluded: effectiveExcluded,
      effectiveApplicability: effectiveExcluded ? "Excluded" : control.applicability,
      effectiveImplementationModel: effectiveExcluded ? "Excluded" : control.implementationModel,
      exclusionReason: localExcluded ? (stored.reason || "") : (baseExcluded ? control.rationale : ""),
    };
  }

  function isBaseExcluded(control) {
    return control.implementationModel === "Excluded" || control.applicability === "Excluded";
  }

  function setControlExclusion(controlId, excluded) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }

    if (excluded) {
      const existing = state.controlState[controlId] || {};
      state.controlState[controlId] = {
        excluded: true,
        reason: existing.reason || "",
      };
    } else {
      delete state.controlState[controlId];
    }
    saveControlState();
  }

  function updateControlReason(controlId, reason) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return;
    }
    const existing = state.controlState[controlId] || { excluded: true, reason: "" };
    state.controlState[controlId] = {
      excluded: existing.excluded !== false,
      reason,
    };
    saveControlState();
  }

  function filteredControls() {
    const searchLower = state.search.trim().toLowerCase();

    return getAllControlViews().filter((view) => {
      if (page !== "policies" && state.domain !== "All" && view.domain !== state.domain) {
        return false;
      }
      if (page !== "policies" && state.applicability !== "All" && view.effectiveApplicability !== state.applicability) {
        return false;
      }
      if (page !== "policies" && state.frequency !== "All" && view.reviewFrequency !== state.frequency) {
        return false;
      }
      if (!searchLower || (page !== "controls" && page !== "reports")) {
        return true;
      }

      const searchableText = [
        view.id,
        view.name,
        view.domain,
        view.rationale,
        view.evidence,
        view.effectiveImplementationModel,
        view.effectiveApplicability,
        view.exclusionReason,
        ...view.documentIds.map((documentId) => {
          const documentItem = documentsById.get(documentId);
          return documentItem ? `${documentItem.id} ${documentItem.title}` : documentId;
        }),
      ].join(" ").toLowerCase();

      return searchableText.includes(searchLower);
    });
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
    return data.policyCoverage.filter((item) => visibleIds.has(item.id));
  }

  function getPolicyLibraryRows() {
    return data.documents
      .concat(uploadedDocuments)
      .filter((documentItem) => isPolicyLibraryDocument(documentItem))
      .map((documentItem) => ({
        id: documentItem.id,
        title: documentItem.title,
        reviewFrequency: documentItem.reviewFrequency,
        type: documentItem.type,
        controlCount: data.controls.filter((control) => control.documentIds.includes(documentItem.id)).length,
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

  function filteredRisks() {
    const searchLower = state.search.trim().toLowerCase();
    return state.riskRegister
      .slice()
      .filter((risk) => {
        if (!searchLower) {
          return true;
        }
        const searchableText = [
          risk.risk,
          risk.owner,
          risk.date,
          risk.closedDate,
          `level ${risk.initialRiskLevel}`,
          isRiskClosed(risk) ? "closed" : "open",
        ].join(" ").toLowerCase();
        return searchableText.includes(searchLower);
      })
      .sort((left, right) => {
        const closedDelta = Number(isRiskClosed(left)) - Number(isRiskClosed(right));
        if (closedDelta !== 0) {
          return closedDelta;
        }
        if (left.initialRiskLevel !== right.initialRiskLevel) {
          return right.initialRiskLevel - left.initialRiskLevel;
        }
        if (left.date !== right.date) {
          return right.date.localeCompare(left.date);
        }
        return (right.updatedAt || right.createdAt || "").localeCompare(left.updatedAt || left.createdAt || "");
      });
  }

  function getSelectedRisk() {
    if (state.isAddingRisk || !state.selectedRiskId) {
      return null;
    }
    return state.riskRegister.find((risk) => risk.id === state.selectedRiskId) || null;
  }

  function syncSelectionToVisibleRisks(risks) {
    if (state.isAddingRisk) {
      return;
    }

    const visibleRisks = Array.isArray(risks) ? risks : filteredRisks();
    const selectionExists = state.riskRegister.some((risk) => risk.id === state.selectedRiskId);
    if (selectionExists) {
      return;
    }
    state.selectedRiskId = visibleRisks[0] ? visibleRisks[0].id : "";
  }

  function isRiskClosed(risk) {
    return Boolean(risk.closedDate);
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

  function syncSelectionToVisibleControls() {
    const controls = filteredControls();
    if (!controls.length) {
      state.selectedControlId = null;
      return;
    }
    if (!state.selectedControlId || !controls.some((control) => control.id === state.selectedControlId)) {
      state.selectedControlId = controls[0].id;
    }
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

  function monthlyActivities(monthIndex) {
    return data.activities.filter((activity) => activity.monthIndex === monthIndex);
  }

  function orderedActivitiesFromCurrentMonth() {
    return data.activities
      .slice()
      .sort((left, right) => {
        const deltaLeft = (left.monthIndex - today.getMonth() + 12) % 12;
        const deltaRight = (right.monthIndex - today.getMonth() + 12) % 12;
        if (deltaLeft !== deltaRight) {
          return deltaLeft - deltaRight;
        }
        return left.activity.localeCompare(right.activity);
      });
  }

  function buildAuditWindows() {
    const definitions = [
      {
        label: "Governance",
        color: "#7442b8",
        matchers: ["policy", "objectives", "statement of applicability", "internal audit", "management review", "compliance", "training"],
      },
      {
        label: "Access reviews",
        color: "#4e92e6",
        matchers: ["access", "privileged"],
      },
      {
        label: "Risk and suppliers",
        color: "#d05ad4",
        matchers: ["risk", "supplier", "vulnerability"],
      },
      {
        label: "Resilience",
        color: "#71cadb",
        matchers: ["backup", "restore", "recovery", "continuity", "physical"],
      },
    ];

    return definitions.map((definition) => {
      const matchingActivities = data.activities.filter((activity) => {
        const text = activity.activity.toLowerCase();
        return definition.matchers.some((matcher) => text.includes(matcher));
      });
      if (!matchingActivities.length) {
        return null;
      }
      return {
        label: definition.label,
        color: definition.color,
        start: Math.min(...matchingActivities.map((activity) => activity.monthIndex)),
        end: Math.max(...matchingActivities.map((activity) => activity.monthIndex)),
        count: matchingActivities.length,
      };
    }).filter(Boolean);
  }

  function firstControlIdForDocument(documentId) {
    const match = data.controls.find((control) => control.documentIds.includes(documentId));
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

  function reviewCadence(reviewFrequency) {
    const value = reviewFrequency.toLowerCase();
    if (value.includes("monthly")) {
      return "Monthly";
    }
    if (value.includes("quarterly")) {
      return "Quarterly";
    }
    if (value.includes("significant change")) {
      return "Change";
    }
    if (value.includes("per event") || value.includes("after incidents")) {
      return "Event";
    }
    return "Annual";
  }

  function buildSmoothPath(points) {
    if (!points.length) {
      return "";
    }
    if (points.length === 1) {
      return `M ${points[0].x} ${points[0].y}`;
    }

    let path = `M ${points[0].x} ${points[0].y}`;
    for (let index = 0; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const midX = (current.x + next.x) / 2;
      path += ` C ${midX} ${current.y}, ${midX} ${next.y}, ${next.x} ${next.y}`;
    }
    return path;
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
      const additions = isApiPersistence()
        ? await uploadVendorsToApi(files)
        : await createVendorSurveyResponses(files);

      vendorSurveyResponses = additions
        .concat(vendorSurveyResponses)
        .sort((left, right) => new Date(right.importedAt) - new Date(left.importedAt))
        .slice(0, 60);

      await saveVendorResponses();
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

  async function createVendorSurveyResponses(files) {
    const importedAt = new Date();
    const additions = [];
    for (let index = 0; index < files.length; index += 1) {
      additions.push(await buildVendorSurveyResponse(files[index], importedAt, index + 1));
    }
    return additions;
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

  async function saveVendorResponses() {
    if (isApiPersistence()) {
      return;
    }
    window.localStorage.setItem(vendorSurveyKey, JSON.stringify(vendorSurveyResponses.slice(0, 60)));
  }

  function loadVendorResponses() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(vendorSurveyKey) || "[]");
      return Array.isArray(saved) ? saved.filter((item) => item && typeof item.id === "string") : [];
    } catch (error) {
      return [];
    }
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

  function renderUploadedDocumentContent(rawText) {
    return `<pre class="document-pre">${escapeHtml(rawText)}</pre>`;
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

  async function saveRiskRegister() {
    if (!isApiPersistence()) {
      window.localStorage.setItem(riskRegisterKey, JSON.stringify(state.riskRegister));
      return;
    }

    const payload = await apiRequest("/risks/", {
      method: "PUT",
      body: JSON.stringify({ riskRegister: state.riskRegister }),
    });

    if (payload && Array.isArray(payload.riskRegister)) {
      state.riskRegister = payload.riskRegister.map((item) => normalizeRiskRecord(item)).filter(Boolean);
    }
  }

  function loadRiskRegister() {
    try {
      const saved = JSON.parse(window.localStorage.getItem(riskRegisterKey) || "[]");
      if (!Array.isArray(saved)) {
        return [];
      }
      return saved
        .map((item) => normalizeRiskRecord(item))
        .filter(Boolean);
    } catch (error) {
      return [];
    }
  }

  function normalizeRiskRecord(item) {
    if (!item || typeof item !== "object") {
      return null;
    }

    const riskText = typeof item.risk === "string" ? item.risk.trim() : "";
    const initialRiskLevel = normalizeRiskLevel(item.initialRiskLevel);
    const raisedDate = normalizeDateInputValue(item.date);
    if (!riskText || !initialRiskLevel || !raisedDate) {
      return null;
    }

    return {
      id: typeof item.id === "string" && item.id ? item.id : createRiskId(),
      risk: riskText,
      initialRiskLevel,
      date: raisedDate,
      owner: typeof item.owner === "string" ? item.owner.trim() : "",
      closedDate: normalizeDateInputValue(item.closedDate),
      createdAt: typeof item.createdAt === "string" ? item.createdAt : "",
      updatedAt: typeof item.updatedAt === "string" ? item.updatedAt : "",
    };
  }

  function createRiskId() {
    return `risk-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
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

    const baseLabel = data.sourceSnapshot.runtimeDependency ? "Workbook dependent" : "Embedded snapshot";
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
      return;
    }

    try {
      const payload = await apiRequest("/state/");
      persistenceMode = payload && payload.persistenceMode === "api" ? "api" : "local";
      applyRemoteState(payload);
    } catch (error) {
      persistenceMode = "local";
    }
  }

  function applyRemoteState(payload) {
    if (!payload || typeof payload !== "object") {
      return;
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
    if (payload.reviewState && typeof payload.reviewState === "object") {
      state.reviewState = {
        activities: payload.reviewState.activities || {},
        checklist: payload.reviewState.checklist || {},
      };
    }
    if (payload.controlState && typeof payload.controlState === "object") {
      state.controlState = payload.controlState;
    }

    refreshDocumentsIndex();
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

  function riskRegisterLabel() {
    return isApiPersistence() ? "shared portal register" : "browser register";
  }

  function storageSentence() {
    return isApiPersistence() ? "stored in the shared portal." : "stored locally in this browser.";
  }

  function normalizeRiskLevel(value) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 1 && parsed <= 5 ? parsed : 0;
  }

  function normalizeDateInputValue(value) {
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.trim())) {
      return value.trim();
    }

    if (typeof value !== "string" || !value.trim()) {
      return "";
    }

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return formatDateInputValue(parsed);
  }

  function formatDateInputValue(date) {
    const normalizedDate = date instanceof Date ? date : new Date(date);
    if (Number.isNaN(normalizedDate.getTime())) {
      return "";
    }
    const year = normalizedDate.getFullYear();
    const month = String(normalizedDate.getMonth() + 1).padStart(2, "0");
    const day = String(normalizedDate.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function todayDateValue() {
    return formatDateInputValue(new Date());
  }

  function formatDate(value) {
    const normalizedValue = normalizeDateInputValue(value);
    if (!normalizedValue) {
      return "-";
    }

    const [year, month, day] = normalizedValue.split("-").map(Number);
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(year, month - 1, day));
  }

  function formatShortDateTime(value) {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
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

  function formatDateTime(value) {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(new Date(value));
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
})();
