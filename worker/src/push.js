/* 웹 푸시 보내기 (외부 라이브러리 없이 WebCrypto만 사용).
   - VAPID (RFC 8292): ES256 JWT 로 '이 서버가 보낸 알림'임을 증명
   - 내용 암호화 (RFC 8291, aes128gcm): 구독한 휴대폰만 열어 볼 수 있게 */

export const enc = s => new TextEncoder().encode(s);
export const cat = (...parts) => {
  const arrs = parts.map(p => (p instanceof Uint8Array ? p : new Uint8Array(p)));
  const out = new Uint8Array(arrs.reduce((n, a) => n + a.length, 0));
  let o = 0; for (const a of arrs) { out.set(a, o); o += a.length; }
  return out;
};
export const b64u = buf => {
  const b = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = ""; for (const c of b) s += String.fromCharCode(c);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};
export const unb64u = s => {
  const t = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  return Uint8Array.from(atob(t), c => c.charCodeAt(0));
};

async function hmac(key, data) {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}

/* VAPID 열쇠 한 쌍 만들기: { pub: 공개키(b64url, 65바이트), jwk: 비밀키 } */
export async function makeVapid() {
  const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  return { pub: b64u(await crypto.subtle.exportKey("raw", kp.publicKey)), jwk: await crypto.subtle.exportKey("jwk", kp.privateKey) };
}

export async function vapidHeader(endpoint, vapid, subject) {
  const aud = new URL(endpoint).origin, exp = Math.floor(Date.now() / 1000) + 12 * 3600;
  const head = b64u(enc(JSON.stringify({ typ: "JWT", alg: "ES256" }))), body = b64u(enc(JSON.stringify({ aud, exp, sub: subject })));
  const key = await crypto.subtle.importKey("jwk", vapid.jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, enc(`${head}.${body}`));
  return `vapid t=${head}.${body}.${b64u(sig)}, k=${vapid.pub}`;
}

/* RFC 8291 aes128gcm 로 내용 암호화 → 보낼 본문(바이트) */
export async function encrypt(sub, text) {
  const uaPub = unb64u(sub.keys.p256dh), auth = unb64u(sub.keys.auth);
  const as = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const asPub = new Uint8Array(await crypto.subtle.exportKey("raw", as.publicKey));
  const uaKey = await crypto.subtle.importKey("raw", uaPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: uaKey }, as.privateKey, 256));
  const ikm = await hmac(await hmac(auth, ecdh), cat(enc("WebPush: info\0"), uaPub, asPub, [1]));
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc("Content-Encoding: aes128gcm\0"), [1]))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc("Content-Encoding: nonce\0"), [1]))).slice(0, 12);
  const key = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["encrypt"]);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, key, cat(enc(text), [2])));
  const head = new Uint8Array(16 + 4 + 1 + 65);
  head.set(salt, 0); new DataView(head.buffer).setUint32(16, 4096); head[20] = 65; head.set(asPub, 21);
  return cat(head, ct);
}

/* 한 구독자에게 보내기. 반환: HTTP 상태 (404·410 이면 구독이 끝난 것) */
export async function sendPush(sub, payload, vapid, subject = "mailto:juskim1004@gmail.com", fetchFn = fetch) {
  const body = await encrypt(sub, JSON.stringify(payload));
  const r = await fetchFn(sub.endpoint, {
    method: "POST",
    headers: { Authorization: await vapidHeader(sub.endpoint, vapid, subject), "Content-Encoding": "aes128gcm",
      "Content-Type": "application/octet-stream", TTL: "43200", Urgency: "normal" },
    body,
  });
  return r.status;
}
