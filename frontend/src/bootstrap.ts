export interface BootstrapDependencies {
  hash: string;
  replaceState: (state: unknown, unused: string, url?: string | URL | null) => void;
  pathname: string;
  search: string;
  fetch: typeof fetch;
  replace: (url: string) => void;
  renderStatus: (message: string) => void;
}

export async function runBootstrap(deps: BootstrapDependencies): Promise<void> {
  const match = deps.hash.match(/^#token=([A-Za-z0-9_-]+)$/);
  if (!match) {
    deps.renderStatus("Invalid or missing token. Please launch the application again.");
    return;
  }
  
  const token = match[1];
  deps.replaceState(null, "", deps.pathname + deps.search);

  try {
    const response = await deps.fetch("/bootstrap/exchange", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ token }),
      credentials: "same-origin"
    });

    if (response.status === 204) {
      deps.replace("/");
    } else if (response.status === 401 || response.status === 403) {
      deps.renderStatus("Session expired or invalid origin. Please launch the application again.");
    } else {
      deps.renderStatus("Unexpected response from server. Please launch the application again.");
    }
  } catch {
    deps.renderStatus("Network failure. Please launch the application again.");
  }
}

export function init(): void {
  const statusEl = document.getElementById("status");
  runBootstrap({
    hash: window.location.hash,
    replaceState: (state, title, url) => window.history.replaceState(state, title, url),
    pathname: window.location.pathname,
    search: window.location.search,
    fetch: window.fetch.bind(window),
    replace: (url) => window.location.replace(url),
    renderStatus: (msg) => {
      if (statusEl) statusEl.textContent = msg;
    }
  });
}

// Ensure it only auto-runs in a real browser, not in node tests
if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}
