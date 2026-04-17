function isRowActivationKey(event) {
  return event.key === "Enter" || event.key === " " || event.key === "Spacebar";
}

function isInteractiveTarget(target) {
  return Boolean(target && target.closest && target.closest("a, button, input, select, textarea, [data-policy-link]"));
}

function decorateSelectableRows(container, rowSelector, activeSelector) {
  if (!container) {
    return;
  }
  container.querySelectorAll(rowSelector).forEach((row) => {
    row.setAttribute("tabindex", "0");
    row.setAttribute("role", "button");
    row.setAttribute("aria-pressed", row.matches(activeSelector) ? "true" : "false");
  });
}

function observeSelectableRows(container, rowSelector, activeSelector, observedFlagName) {
  if (!container || container.dataset[observedFlagName] === "true") {
    return;
  }
  container.dataset[observedFlagName] = "true";
  const observer = new MutationObserver(() => {
    decorateSelectableRows(container, rowSelector, activeSelector);
  });
  observer.observe(container, { childList: true, subtree: true });
}

function applyRowSelectionAccessibility() {
  decorateSelectableRows(els.controlsBody, "[data-control-row]", ".is-selected");
  decorateSelectableRows(els.riskList, "[data-risk-row]", ".is-selected");
}

function bindFilePicker(trigger, input, onFilesSelected) {
  if (!trigger || !input) {
    return;
  }
  trigger.addEventListener("click", () => {
    input.click();
  });
  input.addEventListener("change", async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    await onFilesSelected(files);
  });
}
