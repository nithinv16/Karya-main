// Karya service worker — network-first for everything, safe fallbacks.
// Bumping CACHE name invalidates the old buggy SW that could return undefined
// from respondWith (which caused: "Failed to convert value to 'Response'").
const CACHE = "karya-v3";

const OFFLINE_HTML = `<!doctype html><html><head><meta charset="utf-8"><title>Karya offline</title>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>body{font-family:-apple-system,system-ui,sans-serif;padding:40px;color:#09090b;background:#fafafa}
h1{font-size:20px;margin:0 0 8px}p{color:#71717a;font-size:14px}</style></head>
<body><h1>You're offline</h1><p>Karya couldn't reach the server. Reconnect and refresh.</p></body></html>`;

const offlineResponse = () => new Response(OFFLINE_HTML, {
  status: 200,
  headers: { "Content-Type": "text/html; charset=utf-8" },
});

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  let url;
  try { url = new URL(req.url); } catch { return; }

  // Never intercept non-GET or API calls — let the browser handle them normally.
  if (req.method !== "GET") return;
  if (url.pathname.startsWith("/api")) return;
  if (url.origin !== location.origin) return;

  // Navigation requests: try network, fall back to cached index, then offline HTML.
  // CRITICAL: we must always resolve to a real Response object — never undefined.
  if (req.mode === "navigate") {
    e.respondWith((async () => {
      try {
        const net = await fetch(req);
        if (net && net.ok) return net;
        // 5xx / 4xx from network — try cache before falling back
        const cached = await caches.match("/index.html") || await caches.match("/");
        return cached || net || offlineResponse();
      } catch {
        const cached = await caches.match("/index.html") || await caches.match("/");
        return cached || offlineResponse();
      }
    })());
    return;
  }

  // Static assets: cache-first with network refresh, always return a Response.
  e.respondWith((async () => {
    try {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(req);
      if (cached) {
        // Refresh in background, don't block response
        fetch(req).then((res) => { if (res && res.ok) cache.put(req, res.clone()); }).catch(() => {});
        return cached;
      }
      const net = await fetch(req);
      if (net && net.ok) cache.put(req, net.clone());
      return net;
    } catch {
      // Absolute last resort — return a benign empty response instead of undefined
      return new Response("", { status: 504, statusText: "Offline" });
    }
  })());
});
