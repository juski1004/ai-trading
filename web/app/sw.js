// 앱 화면·데이터 모두 항상 새로 받고(고친 화면이 바로 보이게), 인터넷이 안 될 때만 저장본을 씀.
const SHELL = "shell-v11";
const FILES = ["./", "./index.html", "./team.js", "./game.js", "./report.js", "./deck.js", "./advise.js", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== "data").map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/data/")) {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open("data").then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
  } else {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
  }
});
