function resolvePortalDataAttribute(name, fallback) {
  if (!document.body || !document.body.dataset) {
    return fallback;
  }

  const value = document.body.dataset[name];
  if (typeof value === "string" && value.trim() !== "") {
    return value;
  }
  return fallback;
}

function resolvePortalBooleanDataAttribute(name) {
  const value = resolvePortalDataAttribute(name, "false");
  return value.trim().toLowerCase() === "true";
}

window.ISMS_PORTAL_CONFIG = {
  apiBaseUrl: resolvePortalDataAttribute("apiBaseUrl", "/api"),
  loginUrl: resolvePortalDataAttribute("loginUrl", "/login/"),
  currentUser: {
    username: resolvePortalDataAttribute("currentUsername", ""),
    isStaff: resolvePortalBooleanDataAttribute("currentIsStaff"),
    isPolicyReader: resolvePortalBooleanDataAttribute("currentIsPolicyReader"),
  },
};
