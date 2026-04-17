  function renderReviewsPage() {
    renderReviewOverview();
    renderMonthTabs();
    renderActivities();
    renderChecklist();
  }
  function reviewPersistenceStatusValue() {
    if (!state.reviewPersistenceStatus || typeof state.reviewPersistenceStatus !== "object") {
      return { message: "", tone: "" };
    }
    return {
      message: typeof state.reviewPersistenceStatus.message === "string" ? state.reviewPersistenceStatus.message : "",
      tone: typeof state.reviewPersistenceStatus.tone === "string" ? state.reviewPersistenceStatus.tone : "",
    };
  }
  function reviewPersistenceStatusMarkup() {
    return '<p class="helper-note" data-review-save-status></p>';
  }
  function renderReviewPersistenceStatus() {
    if (!els.activities) {
      return;
    }
    const statusElement = els.activities.querySelector("[data-review-save-status]");
    if (!statusElement) {
      return;
    }
    const status = reviewPersistenceStatusValue();
    setUploadStatus(
      statusElement,
      status.message || "Review checklist updates sync with the shared portal database.",
      status.tone || ""
    );
  }
  function setReviewPersistenceStatus(message, tone) {
    state.reviewPersistenceStatus = {
      message: message || "",
      tone: tone || "",
    };
    renderReviewPersistenceStatus();
  }
  function renderReviewOverview() {
    if (!els.overview) {
      return;
    }

    const monthItems = monthlyActivities(state.monthIndex);
    const completedMonthItems = monthItems.filter((item) => isReviewTaskCompleted(item.id, state.monthIndex)).length;
    const checklistItems = getAllChecklistItems();
    const completedChecklist = checklistItems.filter((item) => isReviewTaskCompleted(item.id, state.monthIndex)).length;

    const cards = [
      {
        label: `${monthNames[state.monthIndex]} queue`,
        value: `${completedMonthItems}/${monthItems.length}`,
        note: "Checklist tasks due this month.",
      },
      {
        label: "Checklist tasks",
        value: checklistItems.length,
        note: "Review tasks currently stored in the checklist.",
      },
      {
        label: "Checklist progress",
        value: `${completedChecklist}/${checklistItems.length}`,
        note: "Recurring checks completed in the shared tracker.",
      },
      {
        label: "Quarterly checks",
        value: checklistItems.filter((item) => item.frequency === "Quarterly").length,
        note: "Recurring quarterly checks currently in the shared checklist.",
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
      els.activities.innerHTML = `
        <div class="empty-state">No checklist tasks are due for ${escapeHtml(monthNames[state.monthIndex])}.</div>
        ${reviewPersistenceStatusMarkup()}
      `;
      renderReviewPersistenceStatus();
      return;
    }

    els.activities.innerHTML = `
      <div class="activity-list">
        ${activities.map((activity) => {
          const isDone = isReviewTaskCompleted(activity.id, state.monthIndex);
          return `
            <article class="activity-card ${isDone ? "is-done" : ""}">
              <div class="activity-top">
                <div>
                  <strong>${escapeHtml(activity.activity)}</strong>
                  <div class="mini-copy">${escapeHtml(activity.owner)} / ${escapeHtml(activity.scheduleLabel)} / ${escapeHtml(activity.category)}</div>
                </div>
                <span class="status-pill ${isDone ? "is-success" : "is-active"}">${isDone ? "Done" : "Open"}</span>
              </div>
              <p class="activity-evidence">Evidence: ${escapeHtml(activity.evidence)}</p>
              <label>
                <input type="checkbox" data-activity-id="${escapeHtml(activity.id)}" ${isDone ? "checked" : ""}>
                Mark this checklist task complete
              </label>
            </article>
          `;
        }).join("")}
      </div>
      ${reviewPersistenceStatusMarkup()}
    `;
    renderReviewPersistenceStatus();
  }
  function renderChecklist() {
    if (!els.checklist || !els.checklistSummary) {
      return;
    }

    const checklistItems = getAllChecklistItems();
    if (!checklistItems.length) {
      els.checklistSummary.innerHTML = `<span class="chip">0/0 complete</span>`;
      els.checklist.innerHTML = `<div class="empty-state">No checklist items are stored in the database yet.</div>`;
      refreshChecklistAddFormOptions();
      return;
    }

    const completedCount = checklistItems.filter((item) => isReviewTaskCompleted(item.id, state.monthIndex)).length;
    const frequencyCounts = checklistItems.reduce((counts, item) => {
      const frequency = item.frequency || "Not scheduled";
      counts[frequency] = (counts[frequency] || 0) + 1;
      return counts;
    }, {});

    els.checklistSummary.innerHTML = [
      `<span class="chip">${completedCount}/${checklistItems.length} complete</span>`,
      ...Object.entries(frequencyCounts).map(([frequency, count]) => `<span class="chip">${escapeHtml(frequency)} / ${count}</span>`),
    ].join("");

    els.checklist.innerHTML = `
      <div class="empty-state">
        Recurring checklist tasks are shown in the monthly review program only. Use the month tabs to track completion.
      </div>
    `;
    refreshChecklistAddFormOptions();
  }
  function getAllChecklistItems() {
    return normalizeChecklistItems(state.checklistItems);
  }
  function getRecommendedChecklistItems() {
    return normalizeChecklistItems(state.recommendedChecklistItems);
  }
  function checklistSignature(item) {
    return [
      String(item.category || "").trim().toLowerCase(),
      String(item.item || "").trim().toLowerCase(),
      String(item.frequency || "").trim().toLowerCase(),
      normalizeChecklistStartDate(item.startDate),
      String(item.owner || "").trim().toLowerCase(),
    ].join("||");
  }
  function availableChecklistRecommendations() {
    const existingSignatures = new Set(getAllChecklistItems().map((item) => checklistSignature(item)));
    return getRecommendedChecklistItems().filter((item) => !existingSignatures.has(checklistSignature(item)));
  }
  function checklistRecommendationPicker() {
    return document.getElementById("checklist-recommendation-picker");
  }
  function checklistRecommendationList() {
    return document.getElementById("checklist-recommendation-list");
  }
  function checklistRecommendationLabel(item) {
    const scheduleLabel = checklistFrequencyWithAnchorLabel(item.frequency, item.startDate);
    return `${item.item} (${scheduleLabel} / ${item.owner})`;
  }
  function normalizeRecommendationQuery(value) {
    return String(value || "").trim().toLowerCase();
  }
  function filteredChecklistRecommendations(recommendations, query) {
    const normalizedQuery = normalizeRecommendationQuery(query);
    if (!normalizedQuery) {
      return recommendations;
    }
    return recommendations.filter((item) => item.item.toLowerCase().includes(normalizedQuery));
  }
  function findChecklistRecommendationById(id) {
    const normalizedId = String(id || "").trim();
    if (!normalizedId) {
      return null;
    }
    return availableChecklistRecommendations().find((item) => item.id === normalizedId) || null;
  }
  function findExactChecklistRecommendationByInput(rawValue) {
    const normalizedValue = normalizeRecommendationQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const recommendations = availableChecklistRecommendations();
    const exactLabelMatch = recommendations.find((item) => checklistRecommendationLabel(item).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }
    return recommendations.find((item) => item.item.toLowerCase() === normalizedValue) || null;
  }
  function findChecklistRecommendationByInputValue(rawValue, exactOnly = false) {
    const normalizedValue = normalizeRecommendationQuery(rawValue);
    if (!normalizedValue) {
      return null;
    }

    const recommendations = availableChecklistRecommendations();
    const exactLabelMatch = recommendations.find((item) => checklistRecommendationLabel(item).toLowerCase() === normalizedValue);
    if (exactLabelMatch) {
      return exactLabelMatch;
    }
    const exactItemMatch = recommendations.find((item) => item.item.toLowerCase() === normalizedValue);
    if (exactItemMatch) {
      return exactItemMatch;
    }
    if (exactOnly) {
      return null;
    }
    return recommendations.find((item) => item.item.toLowerCase().includes(normalizedValue)) || null;
  }
  function fillChecklistFormFromRecommendation(recommendation) {
    if (!recommendation) {
      return;
    }
    if (els.checklistAddCategory) {
      els.checklistAddCategory.value = valueOrFallback(els.checklistAddCategory, recommendation.category);
    }
    if (els.checklistAddFrequency) {
      els.checklistAddFrequency.value = valueOrFallback(els.checklistAddFrequency, recommendation.frequency);
    }
    if (els.checklistAddStartDate && recommendation.startDate) {
      els.checklistAddStartDate.value = normalizeChecklistStartDate(recommendation.startDate);
    }
    if (els.checklistAddOwner) {
      els.checklistAddOwner.value = valueOrFallback(els.checklistAddOwner, recommendation.owner);
    }
    if (els.checklistAddItem) {
      els.checklistAddItem.value = recommendation.item;
    }
  }
  function openChecklistRecommendationPicker() {
    const picker = checklistRecommendationPicker();
    const input = els.checklistRecommendationSelect;
    const list = checklistRecommendationList();
    openSharedSearchablePicker(picker, input, list);
  }
  function closeChecklistRecommendationPicker() {
    const picker = checklistRecommendationPicker();
    const input = els.checklistRecommendationSelect;
    const list = checklistRecommendationList();
    closeSharedSearchablePicker(picker, input, list);
  }
  function applyChecklistRecommendationSelection(recommendation, shouldClose = true) {
    if (!els.checklistRecommendationSelect || !els.checklistRecommendationAdd || !recommendation) {
      return;
    }
    recommendationPickerState.selectedId = recommendation.id;
    recommendationPickerState.showAll = false;
    els.checklistRecommendationSelect.value = checklistRecommendationLabel(recommendation);
    els.checklistRecommendationAdd.disabled = false;
    fillChecklistFormFromRecommendation(recommendation);
    renderChecklistRecommendationOptions();
    if (shouldClose) {
      closeChecklistRecommendationPicker();
    }
  }
  function bindChecklistRecommendationPickerEvents() {
    if (!els.checklistRecommendationSelect) {
      return;
    }

    const picker = checklistRecommendationPicker();
    const input = els.checklistRecommendationSelect;
    const list = checklistRecommendationList();
    if (!picker || !input || !list) {
      return;
    }
    bindSharedSearchablePickerEvents({
      picker,
      input,
      list,
      boundDatasetKey: "recommendationPickerBound",
      optionSelector: "[data-recommendation-id]",
      onOpen: () => {
        recommendationPickerState.showAll = true;
        renderChecklistRecommendationOptions();
        openChecklistRecommendationPicker();
      },
      onClose: () => {
        closeChecklistRecommendationPicker();
      },
      onEnter: () => {
        const recommendation = findChecklistRecommendationById(recommendationPickerState.selectedId)
          || findChecklistRecommendationByInputValue(input.value);
        if (!recommendation) {
          return false;
        }
        applyChecklistRecommendationSelection(recommendation, true);
        return true;
      },
      onOptionClick: (option) => {
        const recommendation = findChecklistRecommendationById(option.dataset.recommendationId);
        if (!recommendation) {
          return;
        }
        applyChecklistRecommendationSelection(recommendation, true);
      },
    });
  }
  function renderChecklistRecommendationOptions() {
    if (!els.checklistRecommendationSelect || !els.checklistRecommendationAdd) {
      return;
    }

    const list = checklistRecommendationList();
    if (!list) {
      return;
    }

    bindChecklistRecommendationPickerEvents();

    const typedValue = els.checklistRecommendationSelect.value;
    const allRecommendations = availableChecklistRecommendations();
    const queryForFilter = recommendationPickerState.showAll ? "" : typedValue;
    const visibleRecommendations = filteredChecklistRecommendations(allRecommendations, queryForFilter);

    const hasRecommendations = allRecommendations.length > 0;
    els.checklistRecommendationSelect.disabled = !hasRecommendations;
    els.checklistRecommendationSelect.placeholder = hasRecommendations
      ? "Search recommended tasks"
      : "No recommended tasks available";
    if (!hasRecommendations) {
      recommendationPickerState.selectedId = "";
      els.checklistRecommendationAdd.disabled = true;
      renderSharedSearchablePickerOptions({
        list,
        options: [],
        selectedId: "",
        optionDataAttribute: "data-recommendation-id",
        emptyMessage: "No recommended tasks available",
        getOptionId: (item) => item.id,
        getOptionLabel: (item) => checklistRecommendationLabel(item),
      });
      closeChecklistRecommendationPicker();
      return;
    }

    const exactRecommendation = findExactChecklistRecommendationByInput(typedValue);
    if (exactRecommendation) {
      recommendationPickerState.selectedId = exactRecommendation.id;
      fillChecklistFormFromRecommendation(exactRecommendation);
    } else if (!typedValue.trim() || !visibleRecommendations.some((item) => item.id === recommendationPickerState.selectedId)) {
      recommendationPickerState.selectedId = "";
    }

    renderSharedSearchablePickerOptions({
      list,
      options: visibleRecommendations,
      selectedId: recommendationPickerState.selectedId,
      optionDataAttribute: "data-recommendation-id",
      emptyMessage: "No matching recommended tasks",
      getOptionId: (item) => item.id,
      getOptionLabel: (item) => checklistRecommendationLabel(item),
    });

    els.checklistRecommendationAdd.disabled = !recommendationPickerState.selectedId;
  }
  function handleChecklistRecommendationSelected() {
    if (!els.checklistRecommendationSelect || !els.checklistRecommendationAdd) {
      return;
    }

    recommendationPickerState.showAll = false;
    renderChecklistRecommendationOptions();
    openChecklistRecommendationPicker();
  }
  function refreshChecklistAddFormOptions() {
    if (!els.checklistAddCategory || !els.checklistAddFrequency || !els.checklistAddOwner) {
      return;
    }

    const checklistItems = getAllChecklistItems();
    const recommendedItems = getRecommendedChecklistItems();
    const categories = buildChecklistOptionList(
      defaultChecklistCategories,
      checklistItems.map((item) => item.category).concat(recommendedItems.map((item) => item.category))
    );
    const frequencies = buildChecklistOptionList(
      defaultChecklistFrequencies,
      checklistItems.map((item) => item.frequency).concat(recommendedItems.map((item) => item.frequency))
    );
    const owners = buildChecklistOptionList(
      defaultChecklistOwners,
      checklistItems.map((item) => item.owner).concat(recommendedItems.map((item) => item.owner))
    );

    const selectedCategory = els.checklistAddCategory.value;
    const selectedFrequency = els.checklistAddFrequency.value;
    const selectedOwner = els.checklistAddOwner.value;

    populateSelect(els.checklistAddCategory, categories);
    populateSelect(els.checklistAddFrequency, frequencies);
    populateSelect(els.checklistAddOwner, owners);

    els.checklistAddCategory.value = valueOrFallback(els.checklistAddCategory, selectedCategory || "Custom");
    els.checklistAddFrequency.value = valueOrFallback(els.checklistAddFrequency, selectedFrequency || "Annual");
    els.checklistAddOwner.value = valueOrFallback(els.checklistAddOwner, selectedOwner || "Head of IT");
    renderChecklistRecommendationOptions();
  }
  function buildChecklistOptionList(defaultValues, dynamicValues) {
    const options = defaultValues.slice();
    dynamicValues.forEach((value) => {
      if (typeof value !== "string") {
        return;
      }
      const normalized = value.trim();
      if (!normalized || options.includes(normalized)) {
        return;
      }
      options.push(normalized);
    });
    return options;
  }
  function toggleChecklistAddForm(visible) {
    if (!els.checklistAddForm) {
      return;
    }

    if (!visible) {
      hideChecklistAddForm();
      return;
    }

    showChecklistAddForm();
  }
  function showChecklistAddForm() {
    if (!els.checklistAddForm) {
      return;
    }
    els.checklistAddForm.hidden = false;
    recommendationPickerState.selectedId = "";
    refreshChecklistAddFormOptions();
    if (els.checklistAddCategory && !els.checklistAddCategory.value) {
      els.checklistAddCategory.value = valueOrFallback(els.checklistAddCategory, "Custom");
    }
    if (els.checklistAddFrequency && !els.checklistAddFrequency.value) {
      els.checklistAddFrequency.value = valueOrFallback(els.checklistAddFrequency, "Annual");
    }
    if (els.checklistAddOwner && !els.checklistAddOwner.value) {
      els.checklistAddOwner.value = valueOrFallback(els.checklistAddOwner, "Head of IT");
    }
    renderChecklistRecommendationOptions();
    if (els.checklistAddItem) {
      els.checklistAddItem.focus();
    }
  }
  function hideChecklistAddForm() {
    if (!els.checklistAddForm) {
      return;
    }
    els.checklistAddForm.hidden = true;
    els.checklistAddForm.reset();
    setUploadStatus(els.checklistAddStatus, "", "");
    if (els.checklistAddFrequency) {
      els.checklistAddFrequency.value = "";
    }
    if (els.checklistRecommendationSelect) {
      els.checklistRecommendationSelect.value = "";
    }
    if (els.checklistRecommendationAdd) {
      els.checklistRecommendationAdd.disabled = true;
    }
    recommendationPickerState.selectedId = "";
    recommendationPickerState.showAll = false;
    closeChecklistRecommendationPicker();
  }
  async function handleChecklistAddSubmit(event) {
    event.preventDefault();
    if (!els.checklistAddForm || !els.checklistAddItem) {
      return;
    }

    const itemText = els.checklistAddItem.value.trim();
    const category = els.checklistAddCategory ? els.checklistAddCategory.value : "";
    const frequency = els.checklistAddFrequency ? els.checklistAddFrequency.value : "";
    const startDate = els.checklistAddStartDate ? normalizeChecklistStartDate(els.checklistAddStartDate.value) : "";
    const owner = els.checklistAddOwner ? els.checklistAddOwner.value : "";

    if (!itemText) {
      setUploadStatus(els.checklistAddStatus, "Checklist item text is required.", "error");
      return;
    }

    const payload = {
      category: category || "Custom",
      item: itemText,
      frequency: frequency || "Annual",
      startDate,
      owner: owner || "Shared portal",
    };

    await submitChecklistItem(payload, {
      statusMessage: "Saving checklist item...",
      successMessage: "Checklist item saved.",
      closeFormOnSuccess: true,
    });
  }
  async function handleChecklistRecommendationQuickAdd() {
    if (!els.checklistRecommendationSelect) {
      return;
    }
    const recommendation = findChecklistRecommendationById(recommendationPickerState.selectedId)
      || findExactChecklistRecommendationByInput(els.checklistRecommendationSelect.value);
    if (!recommendation) {
      setUploadStatus(
        els.checklistAddStatus,
        "Select a recommended task from the search dropdown to quick add.",
        "error"
      );
      return;
    }

    const startDate = els.checklistAddStartDate ? normalizeChecklistStartDate(els.checklistAddStartDate.value) : "";

    await submitChecklistItem(
      {
        category: recommendation.category,
        item: recommendation.item,
        frequency: recommendation.frequency,
        startDate: startDate || normalizeChecklistStartDate(recommendation.startDate),
        owner: recommendation.owner,
      },
      {
        statusMessage: "Adding recommended checklist task...",
        successMessage: "Recommended task added to the checklist.",
        closeFormOnSuccess: false,
      }
    );
  }
  async function submitChecklistItem(payload, options) {
    try {
      await runAsyncOperation(
        (message, tone) => {
          setUploadStatus(els.checklistAddStatus, message, tone);
        },
        {
          pending: options && options.statusMessage ? options.statusMessage : "Saving checklist item...",
          success: (result) => {
            if (options && options.closeFormOnSuccess) {
              return null;
            }
            return options && options.successMessage ? options.successMessage : "Checklist item saved.";
          },
          error: "Checklist item could not be saved to the database.",
        },
        async () => {
          await createChecklistItem(payload);
        }
      );
      if (options && options.closeFormOnSuccess) {
        hideChecklistAddForm();
      } else {
        if (els.checklistRecommendationSelect) {
          els.checklistRecommendationSelect.value = "";
        }
        if (els.checklistRecommendationAdd) {
          els.checklistRecommendationAdd.disabled = true;
        }
        renderChecklistRecommendationOptions();
      }
      return true;
    } catch (error) {
      return false;
    }
  }
  async function createChecklistItem(payload) {
    const response = await apiRequest("/checklist/", {
      method: "POST",
      body: JSON.stringify({ checklistItem: payload }),
    });
    const created = normalizeChecklistItems([response && response.checklistItem ? response.checklistItem : null])[0];
    if (!created) {
      throw new Error("Created checklist item response was invalid.");
    }

    await applyCreatedChecklistItem(created);
    return created;
  }
  async function applyCreatedChecklistItem(created) {
    const previousReviewState = normalizeReviewStateValue(state.reviewState);
    state.checklistItems = getAllChecklistItems().concat(created);
    let reviewSaveError = null;
    try {
      await runAsyncOperation(
        (message, tone) => {
          setReviewPersistenceStatus(message, tone);
        },
        {
          pending: "Saving review tracking...",
          success: "Review tracking saved.",
          error: "Review tracking could not be synced.",
        },
        async () => {
          try {
            await saveReviewState();
          } catch (error) {
            state.reviewState = previousReviewState;
            throw error;
          }
        }
      );
    } catch (error) {
      reviewSaveError = error;
    }
    renderReviewsPage();
    refreshChecklistAddFormOptions();
    renderChecklistRecommendationOptions();

    if (reviewSaveError) {
      const detail = reviewSaveError instanceof Error && reviewSaveError.message
        ? reviewSaveError.message
        : "Review tracking could not be synced.";
      throw new Error(`Checklist item was added, but review tracking did not sync: ${detail}`);
    }
  }
  function monthlyActivities(monthIndex) {
    return getAllChecklistItems()
      .filter((item) => isChecklistItemDueInMonth(item, monthIndex))
      .map((item) => ({
        id: item.id,
        month: monthNames[monthIndex],
        monthIndex,
        frequency: item.frequency,
        startDate: item.startDate,
        scheduleLabel: checklistFrequencyWithAnchorLabel(item.frequency, item.startDate, monthIndex),
        activity: item.item,
        owner: item.owner,
        evidence: `Checklist category: ${item.category}`,
        category: item.category,
      }));
  }
  function orderedActivitiesFromCurrentMonth() {
    const recurringActivities = monthNames.flatMap((_, monthIndex) => monthlyActivities(monthIndex));
    return recurringActivities
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
        matchers: ["policy", "objectives", "statement of applicability", "internal audit", "audit", "management review", "compliance", "training"],
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
      const matchingActivities = monthNames.flatMap((_, monthIndex) => monthlyActivities(monthIndex)).filter((activity) => {
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
  function isChecklistItemDueInMonth(item, monthIndex) {
    return dueMonthsForFrequency(item.frequency, item.startDate).includes(monthIndex);
  }
  const recommendationPickerState = {
    selectedId: "",
    showAll: false,
  };
