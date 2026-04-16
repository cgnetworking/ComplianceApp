  function populateFilters() {
    const controls = getAllControlViews();
    if (els.domainFilter) {
      populateSelect(els.domainFilter, ["All"].concat(uniqueValues(controls, "domain")));
      els.domainFilter.value = valueOrFallback(els.domainFilter, state.domain);
      state.domain = els.domainFilter.value;
    }
  }
  function initializeSelection() {
    if (page === "controls") {
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
    if (page === "assessments" && typeof syncZeroTrustSelection === "function") {
      syncZeroTrustSelection();
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
    bindReviewTaskEvents();
    bindRiskEvents();
    if (typeof bindZeroTrustEvents === "function") {
      bindZeroTrustEvents();
    }
  }
  function bindSearchEvents() {
    if (!els.searchInput) {
      return;
    }

    const searchablePages = new Set(["controls", "policies", "risks", "vendors", "audit-log", "assessments"]);
    if (!searchablePages.has(page)) {
      els.searchInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") {
          return;
        }
        const query = els.searchInput.value.trim();
        const target = query ? `/controls/?q=${encodeURIComponent(query)}` : "/controls/";
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

    if (els.clearFilters) {
      els.clearFilters.addEventListener("click", () => {
        state.search = "";
        state.domain = "All";
        if (els.searchInput) {
          els.searchInput.value = "";
        }
        if (els.domainFilter) {
          els.domainFilter.value = "All";
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
      els.controlsBody.addEventListener("keydown", (event) => {
        if (!isRowActivationKey(event) || isInteractiveTarget(event.target)) {
          return;
        }
        const row = event.target.closest("[data-control-row]");
        if (!row) {
          return;
        }
        event.preventDefault();
        state.selectedControlId = row.dataset.controlRow;
        syncUrlAndRender(renderControlsPage);
      });
      observeSelectableRows(
        els.controlsBody,
        "[data-control-row]",
        ".is-selected",
        "controlRowAccessibilityObserved"
      );
    }

    if (!els.controlDetail) {
      return;
    }

    els.controlDetail.addEventListener("click", async (event) => {
      const addMapping = event.target.closest("[data-control-policy-add]");
      if (addMapping) {
        const controlId = addMapping.dataset.controlPolicyAdd;
        const mapper = addMapping.closest("[data-control-policy-mapper]");
        const documentId = resolveControlPolicyPickerDocumentId(controlId, mapper);
        if (!controlId || !documentId) {
          return;
        }
        try {
          await mapPolicyToControl(controlId, documentId);
        } catch (error) {
          syncUrlAndRender(renderControlsPage);
          return;
        }
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }

      const removeMapping = event.target.closest("[data-control-policy-remove]");
      if (!removeMapping) {
        return;
      }
      const controlId = removeMapping.dataset.controlPolicyControl;
      const documentId = removeMapping.dataset.controlPolicyRemove;
      if (!controlId || !documentId) {
        return;
      }
      try {
        await unmapPolicyFromControl(controlId, documentId);
      } catch (error) {
        syncUrlAndRender(renderControlsPage);
        return;
      }
      populateFilters();
      syncSelectionToVisibleControls();
      syncUrlAndRender();
    });

    els.controlDetail.addEventListener("change", async (event) => {
      const policyInput = event.target.closest("[data-control-policy-input]");
      if (policyInput) {
        handleControlPolicyPickerInputChanged();
        return;
      }

      const applicability = event.target.closest("[data-control-applicability]");
      if (applicability) {
        try {
          await setControlApplicability(applicability.dataset.controlApplicability, applicability.value);
        } catch (error) {
          syncUrlAndRender(renderControlsPage);
          return;
        }
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }

      const reviewFrequency = event.target.closest("[data-control-review-frequency]");
      if (reviewFrequency) {
        try {
          await updateControlReviewFrequency(reviewFrequency.dataset.controlReviewFrequency, reviewFrequency.value);
        } catch (error) {
          syncUrlAndRender(renderControlsPage);
          return;
        }
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }

      const owner = event.target.closest("[data-control-owner]");
      if (owner) {
        try {
          await updateControlOwner(owner.dataset.controlOwner, owner.value);
        } catch (error) {
          syncUrlAndRender(renderControlsPage);
          return;
        }
        populateFilters();
        syncSelectionToVisibleControls();
        syncUrlAndRender();
        return;
      }
    });

    els.controlDetail.addEventListener("input", (event) => {
      const policyInput = event.target.closest("[data-control-policy-input]");
      if (policyInput) {
        handleControlPolicyPickerInputChanged();
        return;
      }

      const reason = event.target.closest("[data-exclusion-reason]");
      if (!reason) {
        return;
      }
      void updateControlReason(reason.dataset.exclusionReason, reason.value).catch(() => {
        syncUrlAndRender(renderControlsPage);
      });
    });
  }
  function bindPolicyEvents() {
    if (els.policyCoverage) {
      els.policyCoverage.addEventListener("change", (event) => {
        const approvalCheckbox = event.target.closest("[data-policy-approval-checkbox]");
        if (!approvalCheckbox || !approvalCheckbox.checked || typeof handlePolicyApprovalSelection !== "function") {
          return;
        }
        void handlePolicyApprovalSelection(approvalCheckbox);
      });

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
      els.documentViewer.addEventListener("change", (event) => {
        const approverSelect = event.target.closest("[data-policy-approver-select]");
        if (approverSelect) {
          if (typeof handlePolicyApproverSelection === "function") {
            void handlePolicyApproverSelection(approverSelect);
          }
          return;
        }

        const controlInput = event.target.closest("[data-policy-control-input]");
        if (!controlInput || typeof handlePolicyControlPickerInputChanged !== "function") {
          return;
        }
        handlePolicyControlPickerInputChanged();
      });

      els.documentViewer.addEventListener("click", async (event) => {
        const addControlMapping = event.target.closest("[data-policy-control-add]");
        if (addControlMapping) {
          const documentId = addControlMapping.dataset.policyControlAdd;
          const mapper = addControlMapping.closest("[data-policy-control-mapper]");
          const controlId = typeof resolvePolicyControlPickerControlId === "function"
            ? resolvePolicyControlPickerControlId(documentId, mapper)
            : "";
          if (!documentId || !controlId) {
            return;
          }
          try {
            await mapPolicyToControl(controlId, documentId);
          } catch (error) {
            initializePolicySelection();
            syncUrlAndRender(renderPoliciesPage);
            return;
          }
          initializePolicySelection();
          syncUrlAndRender(renderPoliciesPage);
          return;
        }

        const removeControlMapping = event.target.closest("[data-policy-control-remove]");
        if (removeControlMapping) {
          const controlId = removeControlMapping.dataset.policyControlRemove;
          const documentId = removeControlMapping.dataset.policyControlDocument;
          if (!controlId || !documentId) {
            return;
          }
          try {
            await unmapPolicyFromControl(controlId, documentId);
          } catch (error) {
            initializePolicySelection();
            syncUrlAndRender(renderPoliciesPage);
            return;
          }
          initializePolicySelection();
          syncUrlAndRender(renderPoliciesPage);
          return;
        }

        const removeButton = event.target.closest("[data-delete-policy]");
        if (!removeButton) {
          return;
        }
        await handlePolicyDelete(removeButton.dataset.deletePolicy);
      });

      els.documentViewer.addEventListener("input", (event) => {
        const controlInput = event.target.closest("[data-policy-control-input]");
        if (!controlInput || typeof handlePolicyControlPickerInputChanged !== "function") {
          return;
        }
        handlePolicyControlPickerInputChanged();
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
        syncUrlAndRender();
      });
    }

    if (els.activities) {
      els.activities.addEventListener("change", async (event) => {
        const target = event.target.closest("[data-activity-id]");
        if (!target) {
          return;
        }
        els.activities.querySelectorAll("[data-activity-id]").forEach((checkbox) => {
          checkbox.disabled = true;
        });
        try {
          await updateReviewStateSelection(target.dataset.activityId, target.checked);
        } catch (error) {
          // The save helper already surfaces a visible error state.
        } finally {
          if (els.activities) {
            els.activities.querySelectorAll("[data-activity-id]").forEach((checkbox) => {
              checkbox.disabled = false;
            });
          }
        }
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
      els.checklistRecommendationSelect.addEventListener("input", handleChecklistRecommendationSelected);
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
      observeSelectableRows(
        els.riskList,
        "[data-risk-row]",
        ".is-selected",
        "riskRowAccessibilityObserved"
      );
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
      els.riskList.addEventListener("keydown", (event) => {
        if (!isRowActivationKey(event) || isInteractiveTarget(event.target)) {
          return;
        }
        const row = event.target.closest("[data-risk-row]");
        if (!row) {
          return;
        }
        event.preventDefault();
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
  function isReviewTaskCompleted(itemId, monthIndex = state.monthIndex) {
    const key = buildReviewStateMonthKey(itemId, monthIndex);
    if (!key) {
      return false;
    }
    return Boolean(state.reviewState.checklist[key] || state.reviewState.activities[key]);
  }
  function getReviewTaskCompletedAt(itemId, monthIndex = state.monthIndex) {
    const key = buildReviewStateMonthKey(itemId, monthIndex);
    if (!key || !state.reviewState.completedAt || typeof state.reviewState.completedAt !== "object") {
      return "";
    }
    const timestamp = state.reviewState.completedAt[key];
    return typeof timestamp === "string" && timestamp.trim() ? timestamp.trim() : "";
  }
  function renderReviewCompletionIndicators() {
    if (page !== "reviews" || !els.activities) {
      return;
    }

    els.activities.querySelectorAll(".activity-card.is-done").forEach((card) => {
      const indicator = card.querySelector(".status-pill.is-success");
      const checkbox = card.querySelector("[data-activity-id]");
      if (!indicator || !checkbox) {
        return;
      }
      const completedAt = getReviewTaskCompletedAt(checkbox.dataset.activityId, state.monthIndex);
      if (!completedAt) {
        return;
      }
      const formattedTimestamp = formatDateTime(completedAt);
      indicator.textContent = `Done (${formattedTimestamp})`;
      indicator.title = `Completed ${formattedTimestamp}`;
    });
  }
  async function updateReviewStateSelection(itemId, checked) {
    const key = buildReviewStateMonthKey(itemId, state.monthIndex);
    if (!key || state.reviewStateSaving) {
      return;
    }

    if (!state.reviewState.checklist || typeof state.reviewState.checklist !== "object") {
      state.reviewState.checklist = {};
    }
    if (!state.reviewState.activities || typeof state.reviewState.activities !== "object") {
      state.reviewState.activities = {};
    }
    if (!state.reviewState.completedAt || typeof state.reviewState.completedAt !== "object") {
      state.reviewState.completedAt = {};
    }

    const hadChecklistValue = Object.prototype.hasOwnProperty.call(state.reviewState.checklist, key);
    const hadActivityValue = Object.prototype.hasOwnProperty.call(state.reviewState.activities, key);
    const hadCompletedAtValue = Object.prototype.hasOwnProperty.call(state.reviewState.completedAt, key);
    const previousChecklistValue = state.reviewState.checklist[key];
    const previousActivityValue = state.reviewState.activities[key];
    const previousCompletedAtValue = state.reviewState.completedAt[key];
    const wasCompleted = Boolean(previousChecklistValue || previousActivityValue);

    state.reviewStateSaving = true;
    return runAsyncOperation(
      (message, tone) => {
        if (typeof setReviewPersistenceStatus === "function") {
          setReviewPersistenceStatus(message, tone);
        }
      },
      {
        pending: "Saving review activity...",
        success: "Review activity saved.",
        error: "Unable to save review activity.",
      },
      async () => {
        try {
          state.reviewState.checklist[key] = checked;
          state.reviewState.activities[key] = checked;
          if (checked) {
            if (!wasCompleted || !state.reviewState.completedAt[key]) {
              state.reviewState.completedAt[key] = new Date().toISOString();
            }
          } else {
            delete state.reviewState.completedAt[key];
          }
          renderReviewsPage();
          renderReviewCompletionIndicators();

          await saveReviewState();
          renderReviewsPage();
          renderReviewCompletionIndicators();
          return true;
        } catch (error) {
          if (hadChecklistValue) {
            state.reviewState.checklist[key] = previousChecklistValue;
          } else {
            delete state.reviewState.checklist[key];
          }
          if (hadActivityValue) {
            state.reviewState.activities[key] = previousActivityValue;
          } else {
            delete state.reviewState.activities[key];
          }
          if (hadCompletedAtValue) {
            state.reviewState.completedAt[key] = previousCompletedAtValue;
          } else {
            delete state.reviewState.completedAt[key];
          }

          renderReviewsPage();
          renderReviewCompletionIndicators();
          throw error;
        } finally {
          state.reviewStateSaving = false;
        }
      }
    );
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
    if (page === "assessments" && typeof syncZeroTrustSelection === "function") {
      syncZeroTrustSelection();
      if (typeof handleZeroTrustSelectionChanged === "function") {
        handleZeroTrustSelectionChanged();
      }
      return;
    }
    if (page === "audit-log") {
      return;
    }
    syncSelectionToVisibleControls();
  }
  function syncUrlAndRender(renderer = renderPage) {
    syncUrl();
    renderer();
    applyRowSelectionAccessibility();
  }
  function renderPage() {
    switch (page) {
      case "home":
        renderHomePage();
        break;
      case "controls":
        renderControlsPage();
        break;
      case "reviews":
        renderReviewsPage();
        renderReviewCompletionIndicators();
        break;
      case "review-tasks":
        renderReviewTasksPage();
        break;
      case "audit-log":
        if (typeof renderAuditLogPage === "function") {
          renderAuditLogPage();
        }
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
      case "assessments":
        if (typeof renderZeroTrustPage === "function") {
          renderZeroTrustPage();
        }
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
    const overviewMonthIndex = page === "reviews" ? parseMonth(state.monthIndex) : today.getMonth();
    const monthActivities = page === "reviews"
      ? options.currentMonthActivities
      : monthlyActivities(overviewMonthIndex);
    const checklistDone = checklistItems.filter((item) => isReviewTaskCompleted(item.id, overviewMonthIndex)).length;
    const activityDone = monthActivities.filter((item) => isReviewTaskCompleted(item.id, overviewMonthIndex)).length;
    const cards = [
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
        label: `${monthNames[overviewMonthIndex]} queue`,
        value: `${activityDone}/${monthActivities.length}`,
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

    if (page === "controls" || page === "policies" || page === "risks" || page === "vendors" || page === "audit-log" || page === "assessments") {
      if (state.search) {
        query.set("q", state.search);
      }
    }
    if (page === "controls" && state.domain !== "All") {
      query.set("domain", state.domain);
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
    if (page === "risks" && state.riskAssignee && state.riskAssignee !== "All") {
      query.set("assignee", state.riskAssignee);
    }
    if (page === "risks" && state.riskStatus && state.riskStatus !== "All") {
      query.set("status", state.riskStatus);
    }
    if (page === "risks" && state.riskLevel && state.riskLevel !== "All") {
      query.set("level", state.riskLevel);
    }
    if (page === "vendors" && state.selectedVendorResponseId) {
      query.set("vendor", state.selectedVendorResponseId);
    }
    if (page === "assessments" && state.selectedAssessmentProfileId) {
      query.set("profile", state.selectedAssessmentProfileId);
    }
    if (page === "assessments" && state.selectedAssessmentRunId) {
      query.set("run", state.selectedAssessmentRunId);
    }

    const next = query.toString();
    const url = `${window.location.pathname}${next ? `?${next}` : ""}`;
    window.history.replaceState(null, "", url);
  }
  function populateSelect(select, values) {
    select.innerHTML = values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  }
  function openSharedSearchablePicker(picker, input, list) {
    if (!picker || !input || !list || input.disabled) {
      return;
    }
    list.hidden = false;
    picker.classList.add("is-open");
    input.setAttribute("aria-expanded", "true");
  }
  function closeSharedSearchablePicker(picker, input, list) {
    if (!picker || !input || !list) {
      return;
    }
    list.hidden = true;
    picker.classList.remove("is-open");
    input.setAttribute("aria-expanded", "false");
  }
  function bindSharedSearchablePickerEvents({
    picker,
    input,
    list,
    boundDatasetKey,
    optionSelector,
    onOpen,
    onClose,
    onEnter,
    onOptionClick,
  }) {
    if (!picker || !input || !list || !boundDatasetKey || input.dataset[boundDatasetKey]) {
      return;
    }
    input.dataset[boundDatasetKey] = "true";

    const requestOpen = () => {
      if (typeof onOpen === "function") {
        onOpen();
      }
    };
    const requestClose = () => {
      if (typeof onClose === "function") {
        onClose();
      }
    };

    input.addEventListener("focus", requestOpen);
    input.addEventListener("click", requestOpen);
    input.addEventListener("blur", () => {
      window.setTimeout(requestClose, 120);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        requestClose();
        return;
      }
      if (event.key !== "Enter") {
        return;
      }
      const handled = typeof onEnter === "function" ? Boolean(onEnter(event)) : false;
      if (handled) {
        event.preventDefault();
      }
    });

    list.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });
    list.addEventListener("click", (event) => {
      if (!optionSelector || typeof onOptionClick !== "function") {
        return;
      }
      const option = event.target.closest(optionSelector);
      if (!option) {
        return;
      }
      onOptionClick(option, event);
    });
  }
  function renderSharedSearchablePickerOptions({
    list,
    options,
    selectedId,
    optionDataAttribute,
    emptyMessage,
    getOptionId,
    getOptionLabel,
  }) {
    if (!list) {
      return;
    }
    if (!Array.isArray(options) || !options.length) {
      list.innerHTML = `<div class="recommendation-option-empty">${escapeHtml(emptyMessage || "")}</div>`;
      return;
    }

    const normalizedSelectedId = String(selectedId || "");
    list.innerHTML = options.map((item) => {
      const optionId = String(getOptionId(item) || "");
      const isSelected = optionId === normalizedSelectedId;
      return `
        <button
          class="recommendation-option ${isSelected ? "is-active" : ""}"
          type="button"
          ${optionDataAttribute}="${escapeHtml(optionId)}"
          role="option"
          aria-selected="${isSelected ? "true" : "false"}"
        >
          ${escapeHtml(getOptionLabel(item))}
        </button>
      `;
    }).join("");
  }
  function valueOrFallback(select, value) {
    const exists = Array.from(select.options).some((option) => option.value === value);
    return exists ? value : select.options[0].value;
  }
  function uniqueValues(items, key) {
    return Array.from(new Set(items.map((item) => item[key]))).sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  }
  function parseMonth(rawValue) {
    const fallbackMonth = today.getMonth();
    if (page !== "reviews") {
      return fallbackMonth;
    }
    if (rawValue === null || rawValue === undefined) {
      return fallbackMonth;
    }
    const normalizedValue = typeof rawValue === "string" ? rawValue.trim() : String(rawValue).trim();
    if (!normalizedValue) {
      return fallbackMonth;
    }
    const parsed = Number(normalizedValue);
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 11 ? parsed : fallbackMonth;
  }
  function groupBy(items, key) {
    return items.reduce((groups, item) => {
      const group = item[key];
      groups[group] = groups[group] || [];
      groups[group].push(item);
      return groups;
    }, {});
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
  function updateRuntimeMode() {
    if (!els.runtimeMode) {
      return;
    }

    const hasControls = Array.isArray(data.controls) && data.controls.length > 0;
    const hasExpandedMapping = Array.isArray(data.documents) && data.documents.length > 0;
    const baseLabel = hasControls
      ? (hasExpandedMapping ? "Custom mapping" : "Default controls")
      : "No controls loaded";
    els.runtimeMode.textContent = `${baseLabel} + API`;
  }
  function updatePersistenceCopy() {
    if (els.policyUploadStatus) {
      els.policyUploadStatus.textContent = "Add markdown, text, or HTML policy files to the shared portal library.";
    }
    if (els.vendorUploadStatus) {
      els.vendorUploadStatus.textContent = "Download the sample CSV, replace the sample answers, and upload completed questionnaires or exports into the shared portal workspace. Text-based files generate inline previews.";
    }
    if (els.mappingUploadStatus) {
      els.mappingUploadStatus.textContent = "Upload an optional mapping file (.json or .csv), or map policies manually from Controls and Policies.";
    }
  }
  function portalWorkspaceLabel() {
    return "shared portal workspace";
  }
  function storageSentence() {
    return "stored in the shared portal database.";
  }
  function parseDisplayDateValue(value) {
    if (value instanceof Date) {
      return Number.isNaN(value.getTime()) ? null : value;
    }

    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.trim())) {
      const [year, month, day] = value.trim().split("-").map(Number);
      const parsedLocalDate = new Date(year, month - 1, day);
      return Number.isNaN(parsedLocalDate.getTime()) ? null : parsedLocalDate;
    }

    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  function ordinalSuffix(day) {
    const normalizedDay = Number(day);
    if (!Number.isInteger(normalizedDay)) {
      return "";
    }
    const lastTwoDigits = normalizedDay % 100;
    if (lastTwoDigits >= 11 && lastTwoDigits <= 13) {
      return "th";
    }
    const lastDigit = normalizedDay % 10;
    if (lastDigit === 1) {
      return "st";
    }
    if (lastDigit === 2) {
      return "nd";
    }
    if (lastDigit === 3) {
      return "rd";
    }
    return "th";
  }
  function formatDateWithOrdinal(value) {
    const parsed = parseDisplayDateValue(value);
    if (!parsed) {
      return "-";
    }

    const month = new Intl.DateTimeFormat(undefined, {
      month: "long",
    }).format(parsed);
    const day = parsed.getDate();
    return `${month} ${day}${ordinalSuffix(day)} ${parsed.getFullYear()}`;
  }
  function formatDateTime(value) {
    const parsed = parseDisplayDateValue(value);
    if (!parsed) {
      return "-";
    }

    const time = new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(parsed);
    return `${formatDateWithOrdinal(parsed)}, ${time}`;
  }
  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
