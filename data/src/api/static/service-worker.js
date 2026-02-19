const CACHE_NAME = 'pd-screening-cache-v1';
const urlsToCache = [
  '/',  // your homepage
  '/static/style.css',
  '/static/script.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];


// Install event – caching important files
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});


// Activate event – clean up old caches
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


// Fetch event – serve cached files if offline
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          // Return cached file
          return response;
        }
        // Fetch from network and cache it
        return fetch(event.request)
          .then((networkResponse) => {
            if(!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
              return networkResponse;
            }
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseClone);
              });
            return networkResponse;
          });
      })
      .catch(() => {
        // Optional: fallback if offline & file not cached
        if (event.request.destination === 'document') {
          return caches.match('/');
        }
      })
  );
});
