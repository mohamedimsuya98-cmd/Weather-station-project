self.addEventListener('install', (e) => {
  console.log('[Service Worker] Installed');
});

self.addEventListener('fetch', (e) => {
  // Inaruhusu app kuendelea kufanya kazi vizuri mtandaoni
  e.respondWith(fetch(e.request));
});