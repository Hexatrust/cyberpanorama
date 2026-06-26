/* Service worker du CyberPanorama : cache des images (logos et branding).
   Strategie stale-while-revalidate : on sert tout de suite la version en cache (rendu instantane
   au rechargement et entre les filtres), et on rafraichit le cache en arriere-plan. Seules les
   images same-origin sont mises en cache ; le HTML, le CSS et le JS passent par le reseau (pas de
   risque de servir une app perimee). */
const CACHE = "cyberpanorama-img-v1";
const IMG = /\/assets\/logos\/|\.(svg|png|webp|jpe?g|gif)$/i;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || !IMG.test(url.pathname)) return;

  event.respondWith(
    caches.open(CACHE).then((cache) =>
      cache.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    )
  );
});
