/* node --test worker/test : 암호화한 알림을 받는 쪽(휴대폰) 방식으로 다시 풀어서 원문과 같은지 확인 */
import test from "node:test";
import assert from "node:assert/strict";
import { encrypt, makeVapid, vapidHeader, unb64u, b64u, enc, cat, sendPush } from "../src/push.js";

async function hmac(key, data) {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, data));
}

async function fakeBrowser() {
  const kp = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveBits"]);
  const pub = new Uint8Array(await crypto.subtle.exportKey("raw", kp.publicKey)), auth = crypto.getRandomValues(new Uint8Array(16));
  return { kp, sub: { endpoint: "https://push.example.com/abc", keys: { p256dh: b64u(pub), auth: b64u(auth) } }, pub, auth };
}

async function decrypt(body, b) {
  const salt = body.slice(0, 16), rs = new DataView(body.buffer, body.byteOffset).getUint32(16), idlen = body[20], asPub = body.slice(21, 21 + idlen), ct = body.slice(21 + idlen);
  assert.equal(rs, 4096); assert.equal(idlen, 65);
  const asKey = await crypto.subtle.importKey("raw", asPub, { name: "ECDH", namedCurve: "P-256" }, false, []);
  const ecdh = new Uint8Array(await crypto.subtle.deriveBits({ name: "ECDH", public: asKey }, b.kp.privateKey, 256));
  const ikm = await hmac(await hmac(b.auth, ecdh), cat(enc("WebPush: info\0"), b.pub, asPub, [1]));
  const prk = await hmac(salt, ikm);
  const cek = (await hmac(prk, cat(enc("Content-Encoding: aes128gcm\0"), [1]))).slice(0, 16);
  const nonce = (await hmac(prk, cat(enc("Content-Encoding: nonce\0"), [1]))).slice(0, 12);
  const key = await crypto.subtle.importKey("raw", cek, "AES-GCM", false, ["decrypt"]);
  const pt = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, key, ct));
  assert.equal(pt[pt.length - 1], 2); // 마지막 레코드 표시
  return new TextDecoder().decode(pt.slice(0, -1));
}

test("encrypt → decrypt round trip (RFC 8291)", async () => {
  const b = await fakeBrowser();
  const msg = JSON.stringify({ title: "본부장이 브리핑을 가져왔습니다", body: "테스트", url: "./#home" });
  assert.equal(await decrypt(await encrypt(b.sub, msg), b), msg);
});

test("VAPID JWT verifies with the public key", async () => {
  const v = await makeVapid();
  const h = await vapidHeader("https://fcm.googleapis.com/fcm/send/xyz", v, "mailto:a@b.c");
  const [, t, k] = h.match(/^vapid t=([^,]+), k=(.+)$/);
  assert.equal(k, v.pub);
  const [hd, bd, sig] = t.split(".");
  const claims = JSON.parse(new TextDecoder().decode(unb64u(bd)));
  assert.equal(claims.aud, "https://fcm.googleapis.com");
  const pk = await crypto.subtle.importKey("raw", unb64u(v.pub), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  assert.ok(await crypto.subtle.verify({ name: "ECDSA", hash: "SHA-256" }, pk, unb64u(sig), enc(`${hd}.${bd}`)));
});

test("sendPush posts encrypted body with the right headers", async () => {
  const b = await fakeBrowser(), v = await makeVapid(); let seen;
  const st = await sendPush(b.sub, { title: "x" }, v, "mailto:a@b.c", async (url, init) => { seen = { url, init }; return { status: 201 }; });
  assert.equal(st, 201); assert.equal(seen.url, b.sub.endpoint);
  assert.equal(seen.init.headers["Content-Encoding"], "aes128gcm");
  assert.match(seen.init.headers.Authorization, /^vapid t=/);
  assert.equal(JSON.parse(await decrypt(seen.init.body, b)).title, "x");
});
