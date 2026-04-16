  function reviewTaskItems() {
    if (!Array.isArray(state.checklistItems)) {
      return [];
    }

    const seenIds = new Set();
    return state.checklistItems
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
          startDate: typeof normalizeChecklistStartDate === "function" ? normalizeChecklistStartDate(item.startDate) : "",
          owner: typeof item.owner === "string" && item.owner.trim() ? item.owner.trim() : "Shared portal",
          createdAt: typeof normalizeChecklistCreatedAt === "function" ? normalizeChecklistCreatedAt(item.createdAt) : "",
        };
      })
      .filter(Boolean);
  }
  function reviewTaskScheduleLabel(item) {
    if (typeof checklistFrequencyWithAnchorLabel === "function") {
      return checklistFrequencyWithAnchorLabel(item.frequency, item.startDate);
    }
    return item.frequency;
  }

  function renderReviewTasksPage() {
    if (!els.reviewTasksList) {
      return;
    }

    const checklistItems = reviewTaskItems();
    if (!checklistItems.length) {
      els.reviewTasksList.innerHTML = '<div class="empty-state">No recurring review tasks are stored in the shared checklist.</div>';
      if (els.reviewTasksStatus) {
        setUploadStatus(els.reviewTasksStatus, "", "");
      }
      return;
    }

    const grouped = groupBy(checklistItems, "category");
    els.reviewTasksList.innerHTML = Object.entries(grouped).map(([category, items]) => `
      <section class="checklist-section">
        <h3>${escapeHtml(category)}</h3>
        ${items.map((item) => `
          <article class="activity-card">
            <div class="activity-top">
              <div>
                <strong>${escapeHtml(item.item)}</strong>
                <div class="mini-copy">${escapeHtml(reviewTaskScheduleLabel(item))} / ${escapeHtml(item.owner)}</div>
              </div>
              <button class="ghost-button" type="button" data-review-task-delete="${escapeHtml(item.id)}">Remove</button>
            </div>
          </article>
        `).join("")}
      </section>
    `).join("");

    if (els.reviewTasksStatus) {
      setUploadStatus(els.reviewTasksStatus, "", "");
    }
  }

  function bindReviewTaskEvents() {
    if (!els.reviewTasksList) {
      return;
    }
    els.reviewTasksList.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-review-task-delete]");
      if (!removeButton) {
        return;
      }
      void handleReviewTaskDelete(removeButton.dataset.reviewTaskDelete);
    });
  }

  function clearReviewTaskState(itemId) {
    Object.keys(state.reviewState.checklist || {}).forEach((key) => {
      if (key === itemId || key.endsWith(`::${itemId}`)) {
        delete state.reviewState.checklist[key];
      }
    });
    Object.keys(state.reviewState.activities || {}).forEach((key) => {
      if (key === itemId || key.endsWith(`::${itemId}`)) {
        delete state.reviewState.activities[key];
      }
    });
  }

  async function handleReviewTaskDelete(itemId) {
    const normalizedId = typeof itemId === "string" ? itemId.trim() : "";
    if (!normalizedId) {
      return;
    }

    const task = reviewTaskItems().find((item) => item.id === normalizedId);
    const label = task ? task.item : normalizedId;
    if (!window.confirm(`Remove this task from the shared checklist?\n\n${label}`)) {
      return;
    }

    setUploadStatus(els.reviewTasksStatus, "Removing checklist item...", "info");
    try {
      await apiRequest(`/checklist/${encodeURIComponent(normalizedId)}/`, {
        method: "DELETE",
      });

      state.checklistItems = reviewTaskItems().filter((item) => item.id !== normalizedId);
      clearReviewTaskState(normalizedId);
      saveReviewState();
      renderReviewTasksPage();
      setUploadStatus(els.reviewTasksStatus, "Checklist item removed from the shared database.", "success");
    } catch (error) {
      const detail = error instanceof Error && error.message
        ? error.message
        : "Checklist item could not be removed.";
      setUploadStatus(els.reviewTasksStatus, detail, "error");
    }
  }
