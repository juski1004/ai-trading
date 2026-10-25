// 앱 화면·데이터 모두 항상 새로 받고(고친 화면이 바로 보이게), 인터넷이 안 될 때만 저장본을 씀.
const SHELL = "shell-v25";
const FILES = ["./", "./index.html", "./team.js", "./game.js", "./report.js", "./deck.js", "./advise.js", "./vs.js", "./push.js", "./bgm.js", "./chart.js", "./vendor/lightweight-charts.js", "./daily.js", "./tour.js", "./terms.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== SHELL && k !== "data").map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.endsWith(".mp3")) return; // 음악은 브라우저가 직접 (부분 요청이라 캐시에 넣지 않음)
  if (url.pathname.includes("/data/")) {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open("data").then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
  } else {
    e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return r; })
      .catch(() => caches.match(e.request)));
  }
});

// 앱 밖 알림 (Cloudflare 서버가 보냄): 받으면 표시, 누르면 앱의 해당 화면 열기
self.addEventListener("push", e => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "AI 투자연구소", {
    body: d.body || "", icon: "icon-192.png", badge: "icon-192.png", tag: d.tag || "ai-lab", data: { url: d.url || "./#home" } }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./#home", self.registration.scope).href;
  e.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => {
    for (const w of ws) if (w.url.startsWith(self.registration.scope)) { w.navigate(url); return w.focus(); }
    return clients.openWindow(url);
  }));
});
