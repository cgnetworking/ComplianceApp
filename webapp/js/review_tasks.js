  function reviewTaskItems() {
    return normalizeChecklistItems(state.checklistItems);
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
                <div class="mini-copy">${escapeHtml(reviewTaskScheduleLabel(item))} / ${escapeHtml(portalDisplayAssignableUserLabel(item.owner))}</div>
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

    try {
      await runAsyncOperation(
        (message, tone) => {
          setUploadStatus(els.reviewTasksStatus, message, tone);
        },
        {
          pending: "Removing checklist item...",
          success: "Checklist item removed from the shared database.",
          error: "Checklist item could not be removed.",
        },
        async () => {
          await apiRequest(`/checklist/${encodeURIComponent(normalizedId)}/`, {
            method: "DELETE",
          });

          const previousReviewState = normalizeReviewStateValue(state.reviewState);
          state.checklistItems = reviewTaskItems().filter((item) => item.id !== normalizedId);
          clearReviewTaskState(normalizedId);
          try {
            await saveReviewState();
            if (typeof setReviewPersistenceStatus === "function") {
              setReviewPersistenceStatus("Review tracking saved.", "success");
            }
          } catch (error) {
            state.reviewState = previousReviewState;
            const detail = error instanceof Error && error.message
              ? error.message
              : "Review tracking state could not be updated.";
            if (typeof setReviewPersistenceStatus === "function") {
              setReviewPersistenceStatus(detail, "error");
            }
            renderReviewTasksPage();
            throw new Error(`Checklist item was removed, but review tracking did not sync: ${detail}`);
          }

          renderReviewTasksPage();
        }
      );
    } catch (error) {
      // The shared helper already set the error status.
    }
  }
