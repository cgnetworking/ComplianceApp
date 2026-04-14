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
