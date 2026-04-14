  function renderReviewsPage() {
    renderReviewOverview();
    renderMonthTabs();
    renderActivities();
    renderChecklist();
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
        note: "Review tasks currently stored in the shared database checklist.",
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
      els.activities.innerHTML = `<div class="empty-state">No checklist tasks are due for ${escapeHtml(monthNames[state.monthIndex])}.</div>`;
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
                  <div class="mini-copy">${escapeHtml(activity.owner)} / ${escapeHtml(activity.frequency)} / ${escapeHtml(activity.category)}</div>
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
    `;
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
  function normalizeChecklistItems(items) {
    if (!Array.isArray(items)) {
      return [];
    }

    const seenIds = new Set();
    return items
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }
        const id = typeof item.id === "string" ? item.id.trim() : "";
        const checklistItem = typeof item.item === "string" ? item.item.trim() : "";
        if (!id || !checklistItem || seenIds.has(id)) {
          return null;
        }
        seenIds.add(id);
        return {
          id,
          category: typeof item.category === "string" && item.category.trim() ? item.category.trim() : "Custom",
          item: checklistItem,
          frequency: typeof item.frequency === "string" && item.frequency.trim() ? item.frequency.trim() : "Annual",
          owner: typeof item.owner === "string" && item.owner.trim() ? item.owner.trim() : "Shared portal",
        };
      })
      .filter(Boolean);
  }
  function checklistSignature(item) {
    return [
      String(item.category || "").trim().toLowerCase(),
      String(item.item || "").trim().toLowerCase(),
      String(item.frequency || "").trim().toLowerCase(),
      String(item.owner || "").trim().toLowerCase(),
    ].join("||");
  }
  function availableChecklistRecommendations() {
    const existingSignatures = new Set(getAllChecklistItems().map((item) => checklistSignature(item)));
    return getRecommendedChecklistItems().filter((item) => !existingSignatures.has(checklistSignature(item)));
  }
  function renderChecklistRecommendationOptions() {
    if (!els.checklistRecommendationSelect || !els.checklistRecommendationAdd) {
      return;
    }

    const recommendations = availableChecklistRecommendations();
    const selectedValue = els.checklistRecommendationSelect.value;
    const options = [{ value: "", label: "Select a recommended task" }].concat(
      recommendations.map((item) => ({
        value: item.id,
        label: `${item.item} (${item.frequency} / ${item.owner})`,
      }))
    );

    els.checklistRecommendationSelect.innerHTML = options
      .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
      .join("");

    els.checklistRecommendationSelect.value = valueOrFallback(els.checklistRecommendationSelect, selectedValue || "");
    els.checklistRecommendationAdd.disabled = recommendations.length === 0 || !els.checklistRecommendationSelect.value;
  }
  function handleChecklistRecommendationSelected() {
    if (!els.checklistRecommendationSelect || !els.checklistRecommendationAdd) {
      return;
    }

    const selectedId = els.checklistRecommendationSelect.value;
    const recommendation = getRecommendedChecklistItems().find((item) => item.id === selectedId);
    els.checklistRecommendationAdd.disabled = !recommendation;
    if (!recommendation) {
      return;
    }

    if (els.checklistAddCategory) {
      els.checklistAddCategory.value = valueOrFallback(els.checklistAddCategory, recommendation.category);
    }
    if (els.checklistAddFrequency) {
      els.checklistAddFrequency.value = valueOrFallback(els.checklistAddFrequency, recommendation.frequency);
    }
    if (els.checklistAddOwner) {
      els.checklistAddOwner.value = valueOrFallback(els.checklistAddOwner, recommendation.owner);
    }
    if (els.checklistAddItem) {
      els.checklistAddItem.value = recommendation.item;
    }
  }
  function refreshChecklistAddFormOptions() {
    if (!els.checklistAddCategory || !els.checklistAddFrequency || !els.checklistAddOwner) {
      return;
    }

    const checklistItems = getAllChecklistItems();
    const recommendedItems = getRecommendedChecklistItems();
    const categories = buildChecklistOptionList(
      defaultChecklistCategories,
      checklistItems.map((item) => item.category).concat(recommendedItems.map((item) => item.category)),
      "Custom"
    );
    const frequencies = buildChecklistOptionList(
      defaultChecklistFrequencies,
      checklistItems.map((item) => item.frequency).concat(recommendedItems.map((item) => item.frequency)),
      "Annual"
    );
    const owners = buildChecklistOptionList(
      defaultChecklistOwners,
      checklistItems.map((item) => item.owner).concat(recommendedItems.map((item) => item.owner)),
      "Head of IT"
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
  function buildChecklistOptionList(defaultValues, dynamicValues, fallbackValue) {
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
    if (!options.length && fallbackValue) {
      options.push(fallbackValue);
    }
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
  }
  async function handleChecklistAddSubmit(event) {
    event.preventDefault();
    if (!els.checklistAddForm || !els.checklistAddItem) {
      return;
    }

    const itemText = els.checklistAddItem.value.trim();
    const category = els.checklistAddCategory ? els.checklistAddCategory.value : "";
    const frequency = els.checklistAddFrequency ? els.checklistAddFrequency.value : "";
    const owner = els.checklistAddOwner ? els.checklistAddOwner.value : "";

    if (!itemText) {
      setUploadStatus(els.checklistAddStatus, "Checklist item text is required.", "error");
      return;
    }

    const payload = {
      category: category || "Custom",
      item: itemText,
      frequency: frequency || "Annual",
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
    const selectedId = els.checklistRecommendationSelect.value;
    const recommendation = availableChecklistRecommendations().find((item) => item.id === selectedId);
    if (!recommendation) {
      setUploadStatus(els.checklistAddStatus, "Select a recommended task to quick add.", "error");
      return;
    }

    await submitChecklistItem(
      {
        category: recommendation.category,
        item: recommendation.item,
        frequency: recommendation.frequency,
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
    const statusMessage = options && options.statusMessage ? options.statusMessage : "Saving checklist item...";
    setUploadStatus(els.checklistAddStatus, statusMessage, "info");
    try {
      await createChecklistItem(payload);
      if (options && options.closeFormOnSuccess) {
        hideChecklistAddForm();
      } else {
        const successMessage = options && options.successMessage ? options.successMessage : "Checklist item saved.";
        setUploadStatus(els.checklistAddStatus, successMessage, "success");
        if (els.checklistRecommendationSelect) {
          els.checklistRecommendationSelect.value = "";
        }
        if (els.checklistRecommendationAdd) {
          els.checklistRecommendationAdd.disabled = true;
        }
      }
      return true;
    } catch (error) {
      const detail = error instanceof Error && error.message
        ? error.message
        : "Checklist item could not be saved to the database.";
      setUploadStatus(els.checklistAddStatus, detail, "error");
      return false;
    }
  }
  async function createChecklistItem(payload) {
    if (!isApiPersistence()) {
      throw new Error("Checklist items can only be added in API/database mode.");
    }

    const response = await apiRequest("/checklist/", {
      method: "POST",
      body: JSON.stringify({ checklistItem: payload }),
    });
    const created = normalizeChecklistItems([response && response.checklistItem ? response.checklistItem : null])[0];
    if (!created) {
      throw new Error("Created checklist item response was invalid.");
    }

    applyCreatedChecklistItem(created);
    return created;
  }
  function applyCreatedChecklistItem(created) {
    state.checklistItems = getAllChecklistItems().concat(created);
    saveReviewState();
    renderReviewsPage();
    refreshChecklistAddFormOptions();
    renderChecklistRecommendationOptions();
  }
  function monthlyActivities(monthIndex) {
    return getAllChecklistItems()
      .filter((item) => isChecklistItemDueInMonth(item, monthIndex))
      .map((item) => ({
        id: item.id,
        month: monthNames[monthIndex],
        monthIndex,
        frequency: item.frequency,
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
    return dueMonthsForFrequency(item.frequency).includes(monthIndex);
  }
  function dueMonthsForFrequency(frequency) {
    const value = String(frequency || "").trim().toLowerCase();
    if (value.includes("monthly")) {
      return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    }
    if (value.includes("quarterly")) {
      return [2, 5, 8, 11];
    }
    if (value.includes("semi")) {
      return [5, 11];
    }
    if (value.includes("annual")) {
      return [11];
    }
    return [];
  }
