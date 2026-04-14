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

    const topPolicies = getPolicyLibraryRows().slice(0, 6);
    if (!topPolicies.length) {
      els.homePolicies.innerHTML = '<div class="empty-state">No policy documents are available yet.</div>';
      return;
    }

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
