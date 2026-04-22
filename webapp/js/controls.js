  const DEFAULT_REVIEW_FREQUENCIES = [
    "Annual",
    "Quarterly",
    "Monthly",
    "Per event",
    "After significant change",
  ];
  const controlPolicyPickerState = {
    controlId: "",
    selectedDocumentId: "",
    showAll: false,
  };
  let controlStateMutationVersion = 0;

  function renderControlsPage() {
    const controls = filteredControls();
    renderControlsTable(controls);
    renderControlDetail();
  }
  function controlPersistenceStatusValue() {
    if (!state.controlPersistenceStatus || typeof state.controlPersistenceStatus !== "object") {
      return { message: "", tone: "" };
    }
    return {
      message: typeof state.controlPersistenceStatus.message === "string" ? state.controlPersistenceStatus.message : "",
      tone: typeof state.controlPersistenceStatus.tone === "string" ? state.controlPersistenceStatus.tone : "",
    };
  }
  function controlPersistenceStatusElement() {
    if (!els.controlDetail) {
      return null;
    }
    return els.controlDetail.querySelector("[data-control-save-status]");
  }
  function renderControlPersistenceStatus() {
    const status = controlPersistenceStatusValue();
    const detailStatus = controlPersistenceStatusElement();
    if (detailStatus) {
      setUploadStatus(
        detailStatus,
        status.message || "Control changes sync with the shared portal database.",
        status.tone || ""
      );
    }
  }
  function setControlPersistenceStatus(message, tone) {
    state.controlPersistenceStatus = {
      message: message || "",
      tone: tone || "",
    };
    renderControlPersistenceStatus();
  }
  function cloneControlStateSnapshot() {
    const snapshot = {};
    Object.entries(state.controlState || {}).forEach(([controlId, entry]) => {
      if (!entry || typeof entry !== "object") {
        return;
      }
      const clonedEntry = { ...entry };
      if (Array.isArray(entry.policyDocumentIds)) {
        clonedEntry.policyDocumentIds = entry.policyDocumentIds.slice();
      }
      snapshot[controlId] = clonedEntry;
    });
    return snapshot;
  }
  function renderControlsTable(controls) {
    if (!els.controlsBody) {
      return;
    }
    if (!controls.length) {
      els.controlsBody.innerHTML = `
        <tr>
          <td colspan="3"><div class="empty-state">No controls match the current filters.</div></td>
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
      controlPolicyPickerState.controlId = "";
      controlPolicyPickerState.selectedDocumentId = "";
      controlPolicyPickerState.showAll = false;
      els.controlDetail.innerHTML = '<div class="empty-state">Select a control row to inspect its mapping and linked policies.</div>';
      return;
    }

    if (controlPolicyPickerState.controlId !== control.id) {
      controlPolicyPickerState.selectedDocumentId = "";
      controlPolicyPickerState.showAll = false;
    }
    controlPolicyPickerState.controlId = control.id;

    const mappedDocuments = control.documentIds.map((documentId) => {
      const documentItem = documentsById.get(documentId);
      if (!documentItem) {
        return "";
      }
      return `
        <div class="mapping-row">
          <a class="doc-button ${documentId === control.preferredDocumentId ? "is-active" : ""}" href="${policyUrl(control.id, documentId)}">
            ${escapeHtml(documentItem.id)} / ${escapeHtml(documentItem.title)}
            <small>${escapeHtml(documentItem.type)} / ${escapeHtml(documentItem.reviewFrequency)}</small>
          </a>
          <button
            class="ghost-button danger-button mapping-remove-button"
            type="button"
            data-control-policy-control="${escapeHtml(control.id)}"
            data-control-policy-remove="${escapeHtml(documentId)}"
          >
            Remove
          </button>
        </div>
      `;
    }).join("");
    const availablePolicies = getPolicyLibraryRows()
      .filter((item) => !control.policyDocumentIds.includes(item.id));
    const canMapPolicy = availablePolicies.length > 0;

    const applicabilityOptions = renderSelectOptions(
      ["", "Applicable", "Excluded"],
      control.effectiveApplicability
    );
    const reviewFrequencyOptions = renderSelectOptions(
      buildReviewFrequencyOptions(control.effectiveReviewFrequency),
      control.effectiveReviewFrequency
    );
    const linkedOwner = exactPortalAssignableUsername(control.owner);
    const ownerHelpText = linkedOwner
      ? "Select an active portal user to own this control."
      : control.owner
        ? `Current mapped owner: ${control.owner}. Choose a portal user to override it.`
        : "Select an active portal user to own this control.";

    els.controlDetail.innerHTML = `
      <div class="detail-header">
        <div>
          <p class="panel-kicker">Selected control</p>
          <h3>${escapeHtml(control.id)} / ${escapeHtml(control.name)}</h3>
        </div>
        <div class="chip-row">
          <span class="chip">${escapeHtml(control.domain)}</span>
          <span class="chip">${escapeHtml(control.effectiveApplicability)}</span>
          <span class="status-pill ${control.policyDocumentIds.length ? "is-active" : ""}">${control.policyDocumentIds.length} mapped policies</span>
        </div>
      </div>
      <p class="helper-note" data-control-save-status></p>

      <div class="detail-grid">
        <article class="detail-card">
          <strong>Owner</strong>
          <div class="form-field" data-control-owner-picker="${escapeHtml(control.id)}">
            <div class="recommendation-picker">
              <input
                type="search"
                data-control-owner-search="${escapeHtml(control.id)}"
                placeholder="Select control owner"
                autocomplete="off"
                aria-haspopup="listbox"
                aria-expanded="false"
                aria-controls="control-owner-list-${escapeHtml(control.id)}"
              >
              <div
                class="recommendation-picker-list"
                id="control-owner-list-${escapeHtml(control.id)}"
                data-control-owner-list
                role="listbox"
                hidden
              ></div>
              <input type="hidden" data-control-owner="${escapeHtml(control.id)}" value="${escapeHtml(linkedOwner)}">
            </div>
            <p class="helper-note">${escapeHtml(ownerHelpText)}</p>
          </div>
        </article>
        <article class="detail-card">
          <strong>Review frequency</strong>
          <label class="form-field">
            <select data-control-review-frequency="${escapeHtml(control.id)}">
              ${reviewFrequencyOptions}
            </select>
          </label>
        </article>
      </div>

      <div class="doc-section">
        <strong>Mapped policies</strong>
        <div class="doc-list">
          ${mappedDocuments || '<div class="empty-state">No embedded documents are mapped to this control.</div>'}
        </div>
      </div>

      <div class="doc-section">
        <div class="detail-card">
          <strong>Map policy manually</strong>
          <div class="quick-add-row" data-control-policy-mapper="${escapeHtml(control.id)}">
            <label class="form-field" for="control-policy-picker-input">
              <span>Policy document</span>
              <div class="recommendation-picker">
                <input
                  id="control-policy-picker-input"
                  type="search"
                  data-control-policy-input
                  placeholder="${canMapPolicy ? "Search policy documents" : "No additional policy documents available"}"
                  autocomplete="off"
                  aria-haspopup="listbox"
                  aria-expanded="false"
                  aria-controls="control-policy-picker-list"
                  ${canMapPolicy ? "" : "disabled"}
                >
                <div
                  class="recommendation-picker-list"
                  id="control-policy-picker-list"
                  data-control-policy-list
                  role="listbox"
                  hidden
                ></div>
              </div>
            </label>
            <button class="ghost-button" type="button" data-control-policy-add="${escapeHtml(control.id)}" disabled>Add mapping</button>
          </div>
          <p class="helper-note">Mappings are editable here and from the Policies tab.</p>
        </div>
      </div>

      <div class="doc-section">
        <div class="detail-card exclusion-card">
          <strong>Applicability</strong>
          <label class="form-field">
            <select
              data-control-applicability="${escapeHtml(control.id)}"
              ${control.isBaseExcluded ? "disabled" : ""}
            >
              ${applicabilityOptions}
            </select>
          </label>
          ${control.isBaseExcluded ? '<p class="mini-copy">This control is already excluded in the current mapping data.</p>' : ""}
          ${control.effectiveApplicability === "Excluded" ? `
            <div class="text-area-field">
              <label for="exclusion-reason-${escapeHtml(control.id)}">Exclusion Reason</label>
              <textarea
                id="exclusion-reason-${escapeHtml(control.id)}"
                data-exclusion-reason="${escapeHtml(control.id)}"
                placeholder="Document why this control is excluded."
                ${control.isBaseExcluded ? "readonly" : ""}
              >${escapeHtml(control.exclusionReason)}</textarea>
              ${!control.isBaseExcluded && !control.exclusionReason.trim() ? '<p class="helper-note is-warning">Add an exclusion reason for this excluded control.</p>' : ""}
            </div>
          ` : ""}
        </div>
      </div>
    `;
    controlOwnerPickerState.showAll = false;
    renderControlPolicyOptions();
    renderControlOwnerOptions();
    renderControlPersistenceStatus();
  }
  function controlPolicyMapper() {
    if (!els.controlDetail) {
      return null;
    }
    return els.controlDetail.querySelector("[data-control-policy-mapper]");
  }
  function controlPolicyPickerInput(mapper = controlPolicyMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-control-policy-input]");
  }
  function controlPolicyPickerList(mapper = controlPolicyMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-control-policy-list]");
  }
  function controlPolicyPickerAddButton(mapper = controlPolicyMapper()) {
    if (!mapper) {
      return null;
    }
    return mapper.querySelector("[data-control-policy-add]");
  }
  function normalizeControlPolicyQuery(value) {
    return String(value || "").trim().toLowerCase();
  }
  function controlPolicyLabel(item) {
    return `${item.id} / ${item.title}`;
  }
  function availableControlPolicyOptions(controlId = state.selectedControlId) {
    const control = getControlView(controlId);
    if (!control) {
      return [];
    }
    return getPolicyLibraryRows().filter((item) => !control.policyDocumentIds.includes(item.id));
  }
  function filteredControlPolicyOptions(options, query) {
    const normalizedQuery = normalizeControlPolicyQuery(query);
    if (!normalizedQuery) {
      return options;
    }
    return options.filter((item) => `${item.id} ${item.title}`.toLowerCase().includes(normalizedQuery));
  }
  function findControlPolicyOptionById(controlId, documentId) {
    const normalizedDocumentId = normalizeControlPreferredDocumentId(documentId);
    if (!normalizedDocumentId) {
      return null;
    }
    return availableControlPolicyOptions(controlId).find((item) => item.id === normalizedDocumentId) || null;
  }
  function findExactControlPolicyOptionByInput(controlId, rawValue) {
    const normalizedValue = normalizeControlPolicyQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const options = availableControlPolicyOptions(controlId);
    const exactLabelMatch = options.find((item) => controlPolicyLabel(item).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }
    return options.find((item) => (
      item.id.toLowerCase() === normalizedValue
      || item.title.toLowerCase() === normalizedValue
      || `${item.id} ${item.title}`.toLowerCase() === normalizedValue
    )) || null;
  }
  function findControlPolicyOptionByInputValue(controlId, rawValue, exactOnly = false) {
    const normalizedValue = normalizeControlPolicyQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const options = availableControlPolicyOptions(controlId);
    const exactLabelMatch = options.find((item) => controlPolicyLabel(item).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }

    const exactMatch = options.find((item) => (
      item.id.toLowerCase() === normalizedValue
      || item.title.toLowerCase() === normalizedValue
      || `${item.id} ${item.title}`.toLowerCase() === normalizedValue
    ));
    if (exactMatch) {
      return exactMatch;
    }

    if (exactOnly) {
      return null;
    }
    return options.find((item) => `${item.id} ${item.title}`.toLowerCase().includes(normalizedValue)) || null;
  }
  function openControlPolicyPicker() {
    const mapper = controlPolicyMapper();
    const input = controlPolicyPickerInput(mapper);
    const list = controlPolicyPickerList(mapper);
    openSharedSearchablePicker(mapper, input, list);
  }
  function closeControlPolicyPicker() {
    const mapper = controlPolicyMapper();
    const input = controlPolicyPickerInput(mapper);
    const list = controlPolicyPickerList(mapper);
    closeSharedSearchablePicker(mapper, input, list);
  }
  function applyControlPolicyPickerSelection(documentItem, shouldClose = true) {
    const mapper = controlPolicyMapper();
    const input = controlPolicyPickerInput(mapper);
    const addButton = controlPolicyPickerAddButton(mapper);
    if (!mapper || !input || !addButton || !documentItem) {
      return;
    }
    controlPolicyPickerState.selectedDocumentId = documentItem.id;
    controlPolicyPickerState.showAll = false;
    input.value = controlPolicyLabel(documentItem);
    addButton.disabled = false;
    renderControlPolicyOptions();
    if (shouldClose) {
      closeControlPolicyPicker();
    }
  }
  function bindControlPolicyPickerEvents() {
    const mapper = controlPolicyMapper();
    const input = controlPolicyPickerInput(mapper);
    const list = controlPolicyPickerList(mapper);
    if (!mapper || !input || !list) {
      return;
    }
    bindSharedSearchablePickerEvents({
      picker: mapper,
      input,
      list,
      boundDatasetKey: "controlPolicyPickerBound",
      optionSelector: "[data-control-policy-document-id]",
      onOpen: () => {
        controlPolicyPickerState.showAll = true;
        renderControlPolicyOptions();
        openControlPolicyPicker();
      },
      onClose: () => {
        closeControlPolicyPicker();
      },
      onEnter: () => {
        const controlId = mapper.dataset.controlPolicyMapper || state.selectedControlId;
        const selectedItem = findControlPolicyOptionById(controlId, controlPolicyPickerState.selectedDocumentId)
          || findControlPolicyOptionByInputValue(controlId, input.value);
        if (!selectedItem) {
          return false;
        }
        applyControlPolicyPickerSelection(selectedItem, true);
        return true;
      },
      onOptionClick: (option) => {
        const controlId = mapper.dataset.controlPolicyMapper || state.selectedControlId;
        const selectedItem = findControlPolicyOptionById(controlId, option.dataset.controlPolicyDocumentId);
        if (!selectedItem) {
          return;
        }
        applyControlPolicyPickerSelection(selectedItem, true);
      },
    });
  }
  function renderControlPolicyOptions() {
    const mapper = controlPolicyMapper();
    const input = controlPolicyPickerInput(mapper);
    const list = controlPolicyPickerList(mapper);
    const addButton = controlPolicyPickerAddButton(mapper);
    if (!mapper || !input || !list || !addButton) {
      return;
    }

    bindControlPolicyPickerEvents();

    const controlId = mapper.dataset.controlPolicyMapper || state.selectedControlId;
    const allOptions = availableControlPolicyOptions(controlId);
    const queryForFilter = controlPolicyPickerState.showAll ? "" : input.value;
    const visibleOptions = filteredControlPolicyOptions(allOptions, queryForFilter);

    const hasOptions = allOptions.length > 0;
    input.disabled = !hasOptions;
    input.placeholder = hasOptions
      ? "Search policy documents"
      : "No additional policy documents available";
    if (!hasOptions) {
      controlPolicyPickerState.selectedDocumentId = "";
      addButton.disabled = true;
      input.value = "";
      renderSharedSearchablePickerOptions({
        list,
        options: [],
        selectedId: "",
        optionDataAttribute: "data-control-policy-document-id",
        emptyMessage: "No additional policy documents available",
        getOptionId: (item) => item.id,
        getOptionLabel: (item) => controlPolicyLabel(item),
      });
      closeControlPolicyPicker();
      return;
    }

    const exactMatch = findExactControlPolicyOptionByInput(controlId, input.value);
    if (exactMatch) {
      controlPolicyPickerState.selectedDocumentId = exactMatch.id;
    } else if (!input.value.trim() || !visibleOptions.some((item) => item.id === controlPolicyPickerState.selectedDocumentId)) {
      controlPolicyPickerState.selectedDocumentId = "";
    }

    renderSharedSearchablePickerOptions({
      list,
      options: visibleOptions,
      selectedId: controlPolicyPickerState.selectedDocumentId,
      optionDataAttribute: "data-control-policy-document-id",
      emptyMessage: "No matching policy documents",
      getOptionId: (item) => item.id,
      getOptionLabel: (item) => controlPolicyLabel(item),
    });

    addButton.disabled = !controlPolicyPickerState.selectedDocumentId;
  }
  function handleControlPolicyPickerInputChanged() {
    controlPolicyPickerState.showAll = false;
    renderControlPolicyOptions();
    openControlPolicyPicker();
  }
  function resolveControlPolicyPickerDocumentId(controlId, mapperElement) {
    const mapper = mapperElement || controlPolicyMapper();
    if (!mapper) {
      return "";
    }

    const resolvedControlId = controlId || mapper.dataset.controlPolicyMapper || state.selectedControlId;
    const selectedOption = findControlPolicyOptionById(resolvedControlId, controlPolicyPickerState.selectedDocumentId);
    if (selectedOption) {
      return selectedOption.id;
    }

    const input = controlPolicyPickerInput(mapper);
    if (!input) {
      return "";
    }
    const typedOption = findControlPolicyOptionByInputValue(resolvedControlId, input.value);
    return typedOption ? typedOption.id : "";
  }
  function renderSelectOptions(values, selectedValue) {
    return values.map((value) => {
      const selected = value === selectedValue ? " selected" : "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(value)}</option>`;
    }).join("");
  }
  function buildReviewFrequencyOptions(selectedValue) {
    const options = [""].concat(DEFAULT_REVIEW_FREQUENCIES);
    if (selectedValue && !options.includes(selectedValue)) {
      options.push(selectedValue);
    }
    return options;
  }
  function normalizeControlApplicability(value) {
    const normalized = typeof value === "string" ? value.trim() : "";
    return normalized === "Applicable" || normalized === "Excluded" ? normalized : "";
  }
  function normalizeControlReviewFrequency(value) {
    return typeof value === "string" ? value.trim() : "";
  }
  function normalizeControlOwner(value) {
    return typeof value === "string" ? value.trim() : "";
  }
  function controlOwnerPicker() {
    if (!els.controlDetail) {
      return null;
    }
    return els.controlDetail.querySelector("[data-control-owner-picker]");
  }
  function controlOwnerPickerInput(picker = controlOwnerPicker()) {
    if (!picker) {
      return null;
    }
    return picker.querySelector("[data-control-owner-search]");
  }
  function controlOwnerPickerList(picker = controlOwnerPicker()) {
    if (!picker) {
      return null;
    }
    return picker.querySelector("[data-control-owner-list]");
  }
  function controlOwnerHiddenInput(picker = controlOwnerPicker()) {
    if (!picker) {
      return null;
    }
    return picker.querySelector("[data-control-owner]");
  }
  function openControlOwnerPicker(picker = controlOwnerPicker()) {
    const input = controlOwnerPickerInput(picker);
    const list = controlOwnerPickerList(picker);
    openSharedSearchablePicker(picker, input, list);
  }
  function closeControlOwnerPicker(picker = controlOwnerPicker()) {
    const input = controlOwnerPickerInput(picker);
    const list = controlOwnerPickerList(picker);
    const hiddenInput = controlOwnerHiddenInput(picker);
    if (input && hiddenInput) {
      input.value = hiddenInput.value ? portalDisplayAssignableUserLabel(hiddenInput.value) : "";
    }
    closeSharedSearchablePicker(picker, input, list);
  }
  function applyControlOwnerSelection(username, { shouldNotify = false, shouldClose = true } = {}) {
    const picker = controlOwnerPicker();
    const input = controlOwnerPickerInput(picker);
    const hiddenInput = controlOwnerHiddenInput(picker);
    if (!picker || !input || !hiddenInput) {
      return;
    }

    const resolvedUsername = exactPortalAssignableUsername(username);
    const previousValue = hiddenInput.value;
    hiddenInput.value = resolvedUsername || "";
    controlOwnerPickerState.showAll = false;
    input.value = hiddenInput.value ? portalDisplayAssignableUserLabel(hiddenInput.value) : "";
    renderControlOwnerOptions(picker);
    if (shouldClose) {
      closeControlOwnerPicker(picker);
    }
    if (shouldNotify && previousValue !== hiddenInput.value) {
      hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  function bindControlOwnerPickerEvents(picker = controlOwnerPicker()) {
    const input = controlOwnerPickerInput(picker);
    const list = controlOwnerPickerList(picker);
    if (!picker || !input || !list) {
      return;
    }

    bindSharedSearchablePickerEvents({
      picker,
      input,
      list,
      boundDatasetKey: "controlOwnerPickerBound",
      optionSelector: "[data-control-owner-option]",
      onOpen: () => {
        controlOwnerPickerState.showAll = true;
        renderControlOwnerOptions(picker);
        openControlOwnerPicker(picker);
        window.setTimeout(() => {
          if (document.activeElement === input) {
            input.select();
          }
        }, 0);
      },
      onClose: () => {
        controlOwnerPickerState.showAll = false;
        closeControlOwnerPicker(picker);
      },
      onEnter: () => {
        if (!input.value.trim()) {
          applyControlOwnerSelection("", { shouldNotify: true, shouldClose: true });
          return true;
        }
        const selectedUser = findPortalAssignableUserByInputValue(input.value);
        if (!selectedUser) {
          return false;
        }
        applyControlOwnerSelection(selectedUser.username, { shouldNotify: true, shouldClose: true });
        return true;
      },
      onOptionClick: (option) => {
        applyControlOwnerSelection(option.dataset.controlOwnerOption || "", { shouldNotify: true, shouldClose: true });
      },
    });
  }
  function renderControlOwnerOptions(picker = controlOwnerPicker(), selectedOwner = "") {
    const input = controlOwnerPickerInput(picker);
    const list = controlOwnerPickerList(picker);
    const hiddenInput = controlOwnerHiddenInput(picker);
    if (!picker || !input || !list || !hiddenInput) {
      return;
    }

    bindControlOwnerPickerEvents(picker);

    const committedUsername = exactPortalAssignableUsername(selectedOwner || hiddenInput.value);
    hiddenInput.value = committedUsername || "";
    if (!controlOwnerPickerState.showAll) {
      input.value = hiddenInput.value ? portalDisplayAssignableUserLabel(hiddenInput.value) : "";
    }

    const highlightedUser = controlOwnerPickerState.showAll
      ? null
      : findPortalAssignableUserByInputValue(input.value);
    const { hasUsers } = renderPortalAssignableUserPickerOptions({
      list,
      query: controlOwnerPickerState.showAll ? "" : input.value,
      selectedValue: controlOwnerPickerState.showAll
        ? hiddenInput.value
        : (highlightedUser ? highlightedUser.username : hiddenInput.value),
      optionDataAttribute: "data-control-owner-option",
      blankLabel: "Select control owner",
      emptyLabel: "No assignable users available",
      noMatchesLabel: "No matching users",
      allowBlank: true,
    });

    input.disabled = !hasUsers;
    input.placeholder = hasUsers ? "Select control owner" : "No assignable users available";
    if (!hasUsers) {
      hiddenInput.value = "";
      controlOwnerPickerState.showAll = false;
      closeControlOwnerPicker(picker);
    }
  }
  function handleControlOwnerPickerInputChanged(picker = controlOwnerPicker()) {
    if (!picker) {
      return;
    }
    controlOwnerPickerState.showAll = false;
    renderControlOwnerOptions(picker);
    openControlOwnerPicker(picker);
  }
  function normalizeControlPolicyDocumentIds(value) {
    if (!Array.isArray(value)) {
      return [];
    }

    const uniqueIds = [];
    const seen = new Set();
    value.forEach((item) => {
      const documentId = typeof item === "string" ? item.trim() : "";
      if (!documentId || seen.has(documentId)) {
        return;
      }
      seen.add(documentId);
      uniqueIds.push(documentId);
    });
    return uniqueIds;
  }
  function normalizeControlPreferredDocumentId(value) {
    return typeof value === "string" ? value.trim() : "";
  }
  function defaultControlPolicyDocumentIds(control) {
    return normalizeControlPolicyDocumentIds(control.policyDocumentIds);
  }
  function resolvePreferredControlDocumentId(preferredDocumentId, documentIds) {
    const preferred = normalizeControlPreferredDocumentId(preferredDocumentId);
    if (preferred && documentIds.includes(preferred)) {
      return preferred;
    }

    return documentIds[0] || "";
  }
  function areStringArraysEqual(left, right) {
    if (left.length !== right.length) {
      return false;
    }
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) {
        return false;
      }
    }
    return true;
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
    const basePolicyDocumentIds = defaultControlPolicyDocumentIds(control);
    const hasPolicyDocumentOverride = Array.isArray(stored.policyDocumentIds);
    const storedPolicyDocumentIds = normalizeControlPolicyDocumentIds(stored.policyDocumentIds);
    const effectivePolicyDocumentIds = hasPolicyDocumentOverride
      ? storedPolicyDocumentIds
      : basePolicyDocumentIds;
    const effectivePreferredDocumentId = resolvePreferredControlDocumentId(
      stored.preferredDocumentId || control.preferredDocumentId,
      effectivePolicyDocumentIds
    );
    const storedApplicability = normalizeControlApplicability(stored.applicability);
    const baseApplicability = normalizeControlApplicability(control.applicability);
    const storedReviewFrequency = normalizeControlReviewFrequency(stored.reviewFrequency);
    const baseReviewFrequency = normalizeControlReviewFrequency(control.reviewFrequency);
    const storedOwner = normalizeControlOwner(stored.owner);
    const baseOwner = normalizeControlOwner(control.owner);
    const baseExcluded = isBaseExcluded(control);
    const effectiveApplicability = (baseExcluded || storedApplicability === "Excluded")
      ? "Excluded"
      : (storedApplicability || baseApplicability);
    const effectiveExcluded = effectiveApplicability === "Excluded";
    const effectiveReviewFrequency = storedReviewFrequency || baseReviewFrequency;
    const exclusionReason = effectiveExcluded
      ? (typeof stored.reason === "string" ? stored.reason : "")
      : "";
    const effectiveOwner = storedOwner || baseOwner;

    return {
      ...control,
      documentIds: effectivePolicyDocumentIds,
      policyDocumentIds: effectivePolicyDocumentIds,
      preferredDocumentId: effectivePreferredDocumentId,
      applicability: effectiveApplicability,
      reviewFrequency: effectiveReviewFrequency,
      isBaseExcluded: baseExcluded,
      isLocallyExcluded: storedApplicability === "Excluded" && !baseExcluded,
      isExcluded: effectiveExcluded,
      effectiveApplicability: effectiveApplicability,
      effectiveReviewFrequency: effectiveReviewFrequency,
      exclusionReason: exclusionReason,
      owner: effectiveOwner,
    };
  }
  function isBaseExcluded(control) {
    return normalizeControlApplicability(control.applicability) === "Excluded";
  }
  async function saveControlStateEntry(controlId, nextState) {
    const applicability = normalizeControlApplicability(nextState.applicability);
    const reason = typeof nextState.reason === "string" ? nextState.reason : "";
    const reviewFrequency = normalizeControlReviewFrequency(nextState.reviewFrequency);
    const owner = normalizeControlOwner(nextState.owner);
    const hasPolicyDocumentOverride = Array.isArray(nextState.policyDocumentIds);
    const policyDocumentIds = normalizeControlPolicyDocumentIds(nextState.policyDocumentIds);
    const preferredDocumentId = normalizeControlPreferredDocumentId(nextState.preferredDocumentId);

    const entry = {};
    if (applicability) {
      entry.applicability = applicability;
    }
    if (reason) {
      entry.reason = reason;
    }
    if (reviewFrequency) {
      entry.reviewFrequency = reviewFrequency;
    }
    if (owner) {
      entry.owner = owner;
    }
    if (hasPolicyDocumentOverride) {
      entry.policyDocumentIds = policyDocumentIds;
    }
    if (preferredDocumentId && (!hasPolicyDocumentOverride || policyDocumentIds.includes(preferredDocumentId))) {
      entry.preferredDocumentId = preferredDocumentId;
    }

    const previousControlState = cloneControlStateSnapshot();
    const mutationVersion = ++controlStateMutationVersion;

    if (!Object.keys(entry).length) {
      delete state.controlState[controlId];
    } else {
      state.controlState[controlId] = entry;
    }

    return runAsyncOperation(
      (message, tone) => {
        if (mutationVersion === controlStateMutationVersion) {
          setControlPersistenceStatus(message, tone);
        }
      },
      {
        pending: "Saving control changes...",
        success: (saved) => (saved ? "Control changes saved." : null),
        error: "Unable to save control changes.",
      },
      async () => {
        try {
          await saveControlState();
          return mutationVersion === controlStateMutationVersion;
        } catch (error) {
          if (mutationVersion !== controlStateMutationVersion) {
            return false;
          }
          state.controlState = previousControlState;
          throw error;
        }
      }
    );
  }
  async function setControlApplicability(controlId, applicability) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return false;
    }

    const existing = state.controlState[controlId] || {};
    const nextState = {
      ...existing,
      applicability: normalizeControlApplicability(applicability),
    };
    if (nextState.applicability !== "Excluded") {
      nextState.reason = "";
    }
    return saveControlStateEntry(controlId, nextState);
  }
  async function updateControlReviewFrequency(controlId, reviewFrequency) {
    const control = controlsById.get(controlId);
    if (!control) {
      return false;
    }

    const existing = state.controlState[controlId] || {};
    const normalizedFrequency = normalizeControlReviewFrequency(reviewFrequency);
    const baseReviewFrequency = normalizeControlReviewFrequency(control.reviewFrequency);
    const nextState = {
      ...existing,
      reviewFrequency: normalizedFrequency === baseReviewFrequency ? "" : normalizedFrequency,
    };
    return saveControlStateEntry(controlId, nextState);
  }
  async function updateControlOwner(controlId, owner) {
    const control = controlsById.get(controlId);
    if (!control) {
      return false;
    }

    const existing = state.controlState[controlId] || {};
    const normalizedOwner = normalizeControlOwner(owner);
    const baseOwner = normalizeControlOwner(control.owner);
    const nextState = {
      ...existing,
      owner: normalizedOwner === baseOwner ? "" : normalizedOwner,
    };
    return saveControlStateEntry(controlId, nextState);
  }
  const controlOwnerPickerState = {
    showAll: false,
  };
  async function updateControlReason(controlId, reason) {
    const control = controlsById.get(controlId);
    if (!control || isBaseExcluded(control)) {
      return false;
    }

    const existing = state.controlState[controlId] || {};
    const nextState = {
      ...existing,
      applicability: "Excluded",
      reason,
    };
    return saveControlStateEntry(controlId, nextState);
  }
  async function updateControlPolicyMapping(controlId, nextPolicyDocumentIds, preferredDocumentId) {
    const control = controlsById.get(controlId);
    if (!control) {
      return false;
    }

    const existing = state.controlState[controlId] || {};
    const normalizedNextDocumentIds = normalizeControlPolicyDocumentIds(nextPolicyDocumentIds);
    const basePolicyDocumentIds = defaultControlPolicyDocumentIds(control);
    const hasPolicyDocumentOverride = !areStringArraysEqual(normalizedNextDocumentIds, basePolicyDocumentIds);
    const basePreferredDocumentId = resolvePreferredControlDocumentId(
      control.preferredDocumentId,
      basePolicyDocumentIds
    );
    const resolvedPreferredDocumentId = resolvePreferredControlDocumentId(
      preferredDocumentId || existing.preferredDocumentId || control.preferredDocumentId,
      normalizedNextDocumentIds
    );

    const nextState = {
      ...existing,
    };
    if (hasPolicyDocumentOverride) {
      nextState.policyDocumentIds = normalizedNextDocumentIds;
    } else {
      delete nextState.policyDocumentIds;
    }

    if (resolvedPreferredDocumentId && (hasPolicyDocumentOverride || resolvedPreferredDocumentId !== basePreferredDocumentId)) {
      nextState.preferredDocumentId = resolvedPreferredDocumentId;
    } else {
      delete nextState.preferredDocumentId;
    }

    return saveControlStateEntry(controlId, nextState);
  }
  async function mapPolicyToControl(controlId, documentId) {
    const normalizedDocumentId = normalizeControlPreferredDocumentId(documentId);
    if (!normalizedDocumentId || !documentsById.has(normalizedDocumentId)) {
      return false;
    }

    const control = getControlView(controlId);
    if (!control || control.policyDocumentIds.includes(normalizedDocumentId)) {
      return false;
    }

    const nextPolicyDocumentIds = control.policyDocumentIds.concat(normalizedDocumentId);
    return updateControlPolicyMapping(
      controlId,
      nextPolicyDocumentIds,
      control.preferredDocumentId || normalizedDocumentId
    );
  }
  async function unmapPolicyFromControl(controlId, documentId) {
    const normalizedDocumentId = normalizeControlPreferredDocumentId(documentId);
    if (!normalizedDocumentId) {
      return false;
    }

    const control = getControlView(controlId);
    if (!control || !control.policyDocumentIds.includes(normalizedDocumentId)) {
      return false;
    }

    const nextPolicyDocumentIds = control.policyDocumentIds.filter((item) => item !== normalizedDocumentId);
    const nextPreferredDocumentId = control.preferredDocumentId === normalizedDocumentId
      ? (nextPolicyDocumentIds[0] || "")
      : control.preferredDocumentId;

    return updateControlPolicyMapping(controlId, nextPolicyDocumentIds, nextPreferredDocumentId);
  }
  function filteredControls() {
    const searchLower = state.search.trim().toLowerCase();

    return getAllControlViews().filter((view) => {
      if (page === "controls" && state.domain !== "All" && view.domain !== state.domain) {
        return false;
      }
      if (!searchLower || page !== "controls") {
        return true;
      }

      const searchableText = [
        view.id,
        view.name,
        view.domain,
        view.owner,
        view.effectiveApplicability,
        view.effectiveReviewFrequency,
        view.exclusionReason,
        ...view.documentIds.map((documentId) => {
          const documentItem = documentsById.get(documentId);
          return documentItem ? `${documentItem.id} ${documentItem.title}` : documentId;
        }),
      ].join(" ").toLowerCase();

      return searchableText.includes(searchLower);
    });
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
