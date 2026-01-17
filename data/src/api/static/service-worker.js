const CACHE_NAME = 'pd-screening-cache-v2';

const urlsToCache = [
  '/',                       // home
  '/screening.html',
  '/report.html',
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
  console.log('[ServiceWorker] Install');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Caching app shell');
      return cache.addAll(urlsToCache);
    })
  );
  self.skipWaiting();
});

/* ACTIVATE */
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Removing old cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

/* FETCH */
self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // cache new requests
        const responseClone = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseClone);
        });
        return networkResponse;
      })
      .catch(() => {
        // offline → return cached version
        return caches.match(event.request).then((response) => {
          if (response) return response;

          // offline page for HTML
          if (event.request.destination === 'document') {
            return caches.match('/offline');
          }
        });
      })
  );
});
