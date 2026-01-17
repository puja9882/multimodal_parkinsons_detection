const CACHE_NAME = 'pd-screening-cache-v3';

const urlsToCache = [
  '/',              // home
  '/screening',
  '/report',
  '/offline',

  // static files
  '/static/style.css',
  '/static/script.js',

  // icons
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

/* INSTALL */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
  self.skipWaiting();
});

/* ACTIVATE */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      )
    )
  );
  self.clients.claim();
});

/* FETCH */
self.addEventListener('fetch', (event) => {

  // ❗ DO NOT CACHE POST REQUESTS (predict, upload, etc.)
  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        const responseClone = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseClone);
        });
        return networkResponse;
      })
      .catch(() => {
        return caches.match(event.request).then((cachedResponse) => {
          if (cachedResponse) return cachedResponse;

          // offline fallback
          if (event.request.destination === 'document') {
            return caches.match('/offline');
          }
        });
      })
  );
});
