/* /api/docs: Scalar API Reference (1.75.0) in Team Foundry colors (docs/console-polish; colors in api-docs.css). Dark only, no telemetry,
   no AI agent or MCP extras; "try it" requests go to this console (same origin), so no proxy is needed. */
(() => {
  "use strict";

  Scalar.createApiReference("#foundry-api", {
    url: "/openapi.json",
    theme: "none",  // colors: /static/api-docs.css (not `customCss`, which misbehaves in 1.75.0)
    forceDarkModeState: "dark",
    hideDarkModeToggle: true,
    withDefaultFonts: false,
    telemetry: false,
    showDeveloperTools: "never",
    agent: { disabled: true },
    mcp: { disabled: true },
    defaultOpenAllTags: true,
    metaData: { title: "Team Foundry console API" },
  });

  // 1.75.0 still shows its "Ask AI" button on localhost despite `agent: { disabled: true }`, and the button has no
  // stable class, so hide it by its label whenever Scalar renders or re-renders the sidebar.
  // Observe the body: Scalar replaces its mount element, so an observer on it would go deaf.
  const root = document.body;
  const hideAskAi = () => root.querySelectorAll(".scalar-app button").forEach((b) => {
    if (b.textContent.trim() === "Ask AI") b.style.setProperty("display", "none", "important");  // its flex class beats [hidden]
  });
  new MutationObserver(hideAskAi).observe(root, { childList: true, subtree: true });
})();
