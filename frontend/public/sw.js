const CACHE = "ecoute-shell-v1";
self.addEventListener("install", (event) =>
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) =>
        cache.addAll([
          "/",
          "/index.html",
          "/icon.svg",
          "/manifest.webmanifest",
        ]),
      )
      .then(() => self.skipWaiting()),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  ),
);
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api") ||
    url.pathname.startsWith("/webhooks")
  )
    return;
  // Only static app shell assets: never cache API responses or authenticated records.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/index.html")),
    );
    return;
  }
  if (
    url.pathname.startsWith("/assets/") ||
    ["/icon.svg", "/manifest.webmanifest"].includes(url.pathname)
  )
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const found = await cache.match(event.request);
        if (found) return found;
        const response = await fetch(event.request);
        if (response.ok) await cache.put(event.request, response.clone());
        return response;
      }),
    );
});
