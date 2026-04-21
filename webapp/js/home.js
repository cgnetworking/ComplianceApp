  function renderHomePage() {
    const controls = getAllControlViews();
    renderGlobalOverview(controls, {
      currentMonthActivities: monthlyActivities(state.monthIndex),
    });
    renderHomeUpcoming();
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
            <div class="mini-copy">${escapeHtml(activity.month)} / ${escapeHtml(activity.frequency)} / ${escapeHtml(portalDisplayAssignableUserLabel(activity.owner))}</div>
            <div class="mini-copy">Evidence: ${escapeHtml(activity.evidence)}</div>
          </article>
        `).join("")}
      </div>
    `;
  }
