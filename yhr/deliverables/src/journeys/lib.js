// 캡처 도우미. 폰 크기(390×844, 3배) 창에서 앱을 열고 로그인 · 탭 이동 · 캡처를 한다.
const { chromium } = require('playwright-core');
const OUT = process.env.OUT;
async function start(email = 'yhr@a.com') {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
  const p = await ctx.newPage();
  await p.goto('http://localhost:8191', { waitUntil: 'networkidle' });
  if (email) {
    const inputs = p.locator('input');
    await inputs.nth(0).fill(email);
    await inputs.nth(1).fill('local-dev-password');
    await p.getByText('로그인', { exact: true }).last().click();
    await settle(p);
  }
  return { b, p };
}
async function settle(p, ms = 1500) { try { await p.waitForLoadState('networkidle', { timeout: 8000 }); } catch {} await p.waitForTimeout(ms); }
async function fixTabBar(p) {
  // 웹에는 홈 인디케이터 여백이 없어 탭 이름이 잘린다. 아이폰처럼 아래 여백을 준다(캡처 전용).
  await p.evaluate(() => {
    const tl = document.querySelector('[role=tablist]');
    if (!tl || tl.dataset.fixed) return;
    tl.dataset.fixed = '1';
    // 아이폰 탭 막대 높이(49 + 홈 인디케이터 34)에 맞추고, 4px로 눌린 이름 칸을 편다.
    tl.parentElement.style.height = '83px';
    tl.style.height = '83px';
    tl.style.alignItems = 'flex-start';
    tl.querySelectorAll('[role=tab]').forEach(t => { t.style.height = '56px'; });
    tl.querySelectorAll('div').forEach(e => {
      if (!e.childElementCount && e.textContent && getComputedStyle(e).overflow === 'hidden') {
        e.style.height = 'auto'; e.style.overflow = 'visible';
      }
    });
  });

}
async function shot(p, name) { await fixTabBar(p); await p.waitForTimeout(200); await p.screenshot({ path: `${OUT}/${name}.png` }); console.log('shot', name); }
async function tap(p, text, opts = {}) {
  const loc = opts.exact === false ? p.getByText(text) : p.getByText(text, { exact: true });
  await loc.filter({ visible: true }).nth(opts.nth ?? 0).click({ timeout: 6000 }); await settle(p, opts.wait ?? 1500);
}
async function tab(p, name) {
  // 하단 탭은 a[role=tab]이다. 비중 화면의 축 선택도 tab 역할이라 a로 좁힌다.
  await p.locator('a[role=tab]').filter({ hasText: name }).first().click({ timeout: 6000 }); await settle(p);
}
async function texts(p, label) {
  const t = await p.evaluate(() => [...document.querySelectorAll('div,span,a')].filter(e => !e.childElementCount && e.textContent.trim() && e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().y < innerHeight && e.checkVisibility({ visibilityProperty: true, opacityProperty: true })).map(e => e.textContent.trim()).filter(x => x.length < 40));
  console.log(`[${label}]`, [...new Set(t)].join(' | '));
}
async function back(p) { await p.locator('[aria-label$="back"]').filter({ visible: true }).first().click({ timeout: 6000 }); await settle(p); }
async function reveal(p, text) { await p.getByText(text, { exact: false }).filter({ visible: true }).first().scrollIntoViewIfNeeded(); await p.waitForTimeout(600); }
module.exports = { back, reveal, texts, start, settle, shot, tap, tab };
