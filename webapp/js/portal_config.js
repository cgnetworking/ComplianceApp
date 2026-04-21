function requirePortalDataAttribute(name) {
  if (!document.body || !document.body.dataset) {
    throw new Error("Portal configuration data attributes are unavailable.");
  }

  const value = document.body.dataset[name];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Portal configuration data attribute '${name}' is required.`);
  }
  return value.trim();
}

function requirePortalBooleanDataAttribute(name) {
  const value = requirePortalDataAttribute(name).toLowerCase();
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  throw new Error(`Portal configuration data attribute '${name}' must be true or false.`);
}

window.ISMS_PORTAL_CONFIG = {
  apiBaseUrl: requirePortalDataAttribute("apiBaseUrl"),
  loginUrl: requirePortalDataAttribute("loginUrl"),
  currentUser: {
    username: requirePortalDataAttribute("currentUsername"),
    isStaff: requirePortalBooleanDataAttribute("currentIsStaff"),
    isPolicyReader: requirePortalBooleanDataAttribute("currentIsPolicyReader"),
  },
};
