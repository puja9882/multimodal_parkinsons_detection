const CACHE_NAME = 'pd-screening-cache-v3';

const urlsToCache = [
  '/',                     // app shell
  '/screening.html',
  '/about.html',
  '/report.html',

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
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

/* FETCH → APP SHELL */
self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(
      caches.match('/').then((response) => {
        return response || fetch(event.request);
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});
