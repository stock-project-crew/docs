// 사용자 여정 캡처. 샘플 데이터를 막 넣은 로컬 환경에서 처음부터 한 번 돈다(알림 · 연동을 실제로 만든다).
// 실행법은 ../../journeys.md의 "다시 찍기"에 있다. 결과는 OUT(기본 ../../screens)에 화면 이름으로 쓴다.
const path = require('path');
process.env.OUT = process.env.OUT || path.join(__dirname, '..', '..', 'screens');
const { start, settle, shot, tap, tab, back } = require('./lib');
const btn = async (p, name, wait = 2000) => { await p.getByRole('button', { name }).filter({ visible: true }).first().click(); await settle(p, wait); };
const sw = async p => { await p.getByRole('switch').filter({ visible: true }).first().click(); await settle(p); };

async function linkFlow() {
  const { b, p } = await start(null);
  await shot(p, 'login');
  const inputs = p.locator('input');
  await inputs.nth(0).fill('test_empty@a.com'); await inputs.nth(1).fill('local-dev-password');
  await p.getByText('로그인', { exact: true }).last().click(); await settle(p);
  await shot(p, 'summary-empty');
  await tab(p, '계좌'); await shot(p, 'accounts-empty');
  await tap(p, '계좌 연동 관리'); await shot(p, 'account-link-empty');
  await p.getByText('＋ 계좌 연동', { exact: true }).last().click(); await settle(p);
  const f = n => p.locator(`input[aria-label="${n}"]`).filter({ visible: true }).first();
  await f('앱키').fill('PSa1B2c3D4e5F6g7H8i9J0kLmNoPqRsTuV');
  await f('앱 시크릿').fill('example-app-secret-for-screenshot-only-0123456789');
  await f('계좌번호').fill('1234567801');
  await f('라벨').fill('한국투자 위탁');
  await settle(p, 800); await shot(p, 'kis-link-form');
  await btn(p, '연동하기', 2500); await shot(p, 'account-link-connecting');
  await back(p);
  await tap(p, '지금 동기화'); await settle(p, 2500); await shot(p, 'accounts-sync-requested');
  await tap(p, '계좌 연동 관리');
  await p.getByText('갱신', { exact: true }).last().click(); await settle(p); await shot(p, 'credential-refresh');
  await b.close();
}

async function portfolio() {
  const { b, p } = await start();
  await shot(p, 'summary');
  await p.locator('[aria-label*="계정"]').filter({ visible: true }).first().click(); await settle(p); await shot(p, 'account-sheet');
  await tap(p, '취소');
  await tab(p, '종목'); await shot(p, 'positions');
  await sw(p); await shot(p, 'positions-etf');
  await tab(p, '비중'); await shot(p, 'allocation');
  await sw(p); await shot(p, 'allocation-etf'); await sw(p);
  await tab(p, '종목'); await sw(p);
  await tap(p, '삼성전자'); await shot(p, 'instrument-detail');
  await back(p);
  await tab(p, '계좌'); await shot(p, 'accounts-notices');
  await tab(p, '손익'); await tap(p, '올해'); await shot(p, 'realized-pnl');
  await tap(p, '전체 투자손익 보기', { exact: false }); await shot(p, 'asset-change');
  await tap(p, '넣은 돈 입력', { exact: false }); await shot(p, 'cashflows');
  await b.close();
}

async function createAlerts() {
  let { b, p } = await start();
  await tab(p, '종목'); await tap(p, '삼성전자');
  await tap(p, '알림 걸기'); await shot(p, 'alert-pick-condition');
  await tap(p, '가격 도달');
  await p.getByRole('tab', { name: '종가' }).filter({ visible: true }).first().click(); await settle(p);
  await p.locator('input').filter({ visible: true }).first().fill('60000'); await settle(p, 2000);
  await shot(p, 'alert-preset-input');
  await btn(p, '다음'); await shot(p, 'alert-common-settings');
  await btn(p, '저장', 2500); await shot(p, 'alert-detail');
  await b.close();
  ({ b, p } = await start());
  await tab(p, '종목'); await tap(p, 'SK하이닉스'); await tap(p, '알림 걸기');
  await tap(p, 'RSI 과매수·과매도'); await btn(p, '다음'); await btn(p, '저장');
  await b.close();
}

async function fired() {
  const { b, p } = await start();
  await tab(p, '알림'); await shot(p, 'alerts-tab');
  await tap(p, '울린 알림 전체'); await shot(p, 'fired-list');
  await p.getByText('삼성전자 · 가격 도달', { exact: true }).last().click(); await settle(p); await shot(p, 'fired-detail');
  await b.close();
  const s = await start();
  await tab(s.p, '알림');
  await s.p.getByText('SK하이닉스 RSI 과매수·과매도', { exact: true }).last().click(); await settle(s.p);
  await shot(s.p, 'alert-detail-unknown');
  await s.b.close();
}

(async () => {
  await linkFlow();
  await portfolio();
  await createAlerts();
  // 알림 평가는 1분 주기다. 첫 평가에서 울리도록 충족 중인 조건을 걸었다.
  console.log('평가 주기를 기다린다(75초)'); await new Promise(r => setTimeout(r, 75000));
  await fired();
})().catch(e => { console.error('ERR', e.message.split('\n')[0]); process.exit(1); });
