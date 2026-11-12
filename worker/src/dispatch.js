/* 정확한 시각에 GitHub 작업을 깨우는 타이머 (2026-11-03 사용자: GitHub 예약이 이틀 연속 빠져서 장마감 릴스가 늦었음).
   GitHub 예약(cron)은 한가한 시간에 건너뛰는 일이 있어, 시각이 정확한 Cloudflare 타이머가 GitHub Actions 를 직접 시킨다.
   필요한 것: Worker 비밀값 GH_DISPATCH_TOKEN (juski1004/ai-trading 에 'Actions: 읽기·쓰기' 권한만 있는 세분화된 토큰).
   인스타 게시(ig_publish)는 이미 올렸으면 건너뛰므로(중복 방지) 같은 작업을 여러 번 시켜도 두 번 올라가지 않는다. */
const REPO = "juski1004/ai-trading", SITE = "https://juski1004.github.io/ai-trading";

/** 한국시간 (요일 0=일, 시, 분) */
export function kstParts(ms) {
  const d = new Date(ms + 9 * 3600e3);
  return { dow: d.getUTCDay(), h: d.getUTCHours(), m: d.getUTCMinutes(), date: d.toISOString().slice(0, 10) };
}

/** 이 시각에 해야 할 일 목록. kind: data(장마감 데이터 확인·실행) | ig(인스타 게시 실행) */
export function plan(ms) {
  const { dow, h, m } = kstParts(ms), at = h * 60 + m, out = [];
  const weekday = dow >= 1 && dow <= 5;
  if (weekday) {
    if (at === 16 * 60 + 10 || at === 16 * 60 + 50) out.push({ kind: "data" });   // 데이터가 오늘 것이 아니면 실행 (금요일 실행은 토요일 퀴즈 준비도 겸함)
    if (dow === 4 && (at === 17 * 60 + 30 || at === 17 * 60 + 40)) out.push({ kind: "ig", what: "reel" }); // 목 앱 홍보 릴스 (주 1회, 17:30 업로드)
  } else if (dow === 6) {
    if (at === 12 * 60 || at === 12 * 60 + 40) out.push({ kind: "ig", what: "quiz" }); // 토 차트 퀴즈 릴스 (정답은 다음 퀴즈 릴스에서)
  }
  return out;
}

const gh = (env, method, path, body) => fetch(`https://api.github.com/repos/${REPO}/${path}`, {
  method,
  headers: { Authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "ai-lab-timer", "X-GitHub-Api-Version": "2022-11-28", ...(body ? { "Content-Type": "application/json" } : {}) },
  body: body ? JSON.stringify(body) : undefined,
});

/** 장마감 데이터: 사이트 cards.json 날짜가 오늘이 아니고 지금 도는 데이터 실행이 없으면 실행 */
async function ensureData(env, date) {
  const c = await fetch(`${SITE}/data/cards/cards.json?t=${Date.now()}`, { cf: { cacheTtl: 0 } }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (c && c.date === date) return "카드가 이미 오늘 것";
  const runs = await gh(env, "GET", "actions/workflows/trade.yml/runs?per_page=5").then(r => r.json()).catch(() => ({}));
  if ((runs.workflow_runs || []).some(r => ["queued", "in_progress", "waiting", "pending"].includes(r.status))) return "데이터 실행이 이미 도는 중";
  const r = await gh(env, "POST", "actions/workflows/trade.yml/dispatches", { ref: "main", inputs: { command: "data" } });
  return r.status === 204 ? "데이터 실행 시킴" : `데이터 실행 실패 ${r.status}`;
}

export async function runPlan(ms, env, log = console.log) {
  if (!env.GH_DISPATCH_TOKEN) return [];
  const { date } = kstParts(ms), res = [];
  for (const a of plan(ms)) {
    try {
      if (a.kind === "data") res.push(await ensureData(env, date));
      else {
        const r = await gh(env, "POST", "actions/workflows/ig-post.yml/dispatches", { ref: "main", inputs: { what: a.what } });
        res.push(r.status === 204 ? `${a.what} 게시 실행 시킴` : `${a.what} 게시 실행 실패 ${r.status}`);
      }
    } catch (e) { res.push(`오류 ${String(e).slice(0, 80)}`); }
  }
  res.forEach(x => log("[타이머]", x));
  return res;
}
