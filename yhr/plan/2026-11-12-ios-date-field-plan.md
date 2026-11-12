# iOS 날짜 칸 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** iOS에서 날짜 칸을 한 번 누르면 달력이 바로 열리고, 달력이 한국어로 표기된다.

**Architecture:** 공용 컴포넌트 `src/ui/DateField.tsx`의 iOS 분기만 바꾼다. 칸을 누르면 투명 `Modal`을 띄우고, 그 안에 `DateTimePicker`를 `display="inline"` · `locale="ko-KR"`로 그린다. 날짜를 고르면 값을 넘기고 닫는다. 바깥(뒷배경)을 누르면 값을 바꾸지 않고 닫는다. Android(시스템 대화상자)와 웹(글자 입력)은 그대로다.

**Tech Stack:** React Native · Expo SDK 58 · `@react-native-community/datetimepicker` 9.2.1 · TypeScript · jest-expo

**Spec:** [입출금 설계](../specs/portfolio-management/2026-10-16-manual-cashflow-input-design.md) §5.3(입출금 화면). 스펙 문장은 바뀌지 않는다.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호를 넣지 않는다. 실기기에서 확인하지 않은 동작은 주석에 단정하지 않는다.
- 작업 위치: `.worktrees/front-end-push-date-field`(브랜치 `fix/push-reopen-date-field`).
- Expo SDK와 의존성 버전을 바꾸지 않는다. `app.json`도 바꾸지 않는다.
- 오늘 뒤를 막는 `max`, 오늘 앞을 막는 `min`의 동작을 바꾸지 않는다. 웹 날짜 칸을 바꾸지 않는다.
- 끝에 `npx jest` · `npx tsc --noEmit` 통과.

## 확인한 사실 (9.2.1 소스)

- `display`를 주지 않으면 `default`가 되고, iOS 네이티브에서 `UIDatePickerStyleAutomatic`으로 바뀐다. iOS 14 이상의 날짜 모드에서 이것은 compact(칸 옆 버튼 → 한 번 더 눌러야 달력)다.
- `locale`을 주지 않으면 앱 번들의 현지화를 따른다. Expo Go에서 영어로 나온 것은 이 때문으로 본다(추정). README는 `locale` prop이 모드에 따라 월 · 요일 이름이 섞일 수 있다고 경고한다. inline 모드의 한국어 표기는 실기기에서 확인한다(Task 2).

## Review Focus

1. **만료 시트 위의 날짜 칸** — 시트가 이미 `Modal`이라 달력 `Modal`이 그 위에 겹쳐 떠야 한다. → Task 2 실기기 확인(테스트로는 겹침을 볼 수 없다). 기존 `expirySheet.test.tsx`가 시트 안에서 고르기 흐름을 계속 통과해야 한다.
2. **달을 넘기는 동작** — inline 달력에서 달만 넘겨도 `onChange`가 불리면 날짜를 고르기 전에 닫힌다. → Task 2 실기기 확인.
3. **고르지 않고 닫기** — 뒷배경을 누르면 값이 바뀌지 않아야 한다. → Task 1 `바깥을 누르면 값을 바꾸지 않고 닫는다`.
4. **`min` · `max`** — 지금처럼 넘겨야 한다. → Task 1 `고를 수 있는 범위를 그대로 넘긴다`.
5. **값이 빈 칸** — 달력은 `min` 또는 오늘에서 열린다(지금과 같다). → Task 1 `빈 칸은 min에서 연다`.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/ui/DateField.tsx` | iOS 달력 모달 |
| `src/__tests__/dateField.test.tsx` (신규) | iOS · Android 분기 |

---

### Task 1: iOS 날짜 칸을 누르면 한국어 달력이 바로 열린다

**Files:**
- Modify: `src/ui/DateField.tsx`
- Test: `src/__tests__/dateField.test.tsx` (신규)

**Interfaces:**
- `DateField`의 props(`label` · `value` · `min` · `max` · `onChange`)는 바뀌지 않는다. 쓰는 네 곳은 고치지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

피커 대역은 받은 props를 기록하고, `날짜 고르기` 버튼을 누르면 정해 둔 날짜로 `onChange`를 부른다(`expirySheet.test.tsx`의 대역과 같은 모양에 props 기록만 더한다). jest-expo 기본 플랫폼은 iOS다. Android 케이스는 `Object.defineProperty(Platform, 'OS', { get: () => 'android' })`를 그 `describe` 안에서 걸고 되돌린다.

```tsx
describe('iOS 날짜 칸', () => {
  it('칸을 누르면 달력이 inline · 한국어로 바로 열린다', async () => {
    await render(<DateField label="시작일" value="2026-11-10" onChange={jest.fn()} />);
    expect(screen.queryByText('피커')).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: '시작일' }));
    expect(lastPickerProps()).toMatchObject({ mode: 'date', display: 'inline', locale: 'ko-KR' });
  });

  it('날짜를 고르면 값을 넘기고 달력이 닫힌다', async () => {
    const onChange = jest.fn();
    await render(<DateField label="시작일" value="2026-11-10" onChange={onChange} />);
    await fireEvent.press(screen.getByRole('button', { name: '시작일' }));
    await fireEvent.press(screen.getByRole('button', { name: '날짜 고르기' }));
    expect(onChange).toHaveBeenCalledWith('2026-11-05');
    expect(screen.queryByText('피커')).toBeNull();
  });

  it('바깥을 누르면 값을 바꾸지 않고 닫는다', async () => {
    const onChange = jest.fn();
    await render(<DateField label="시작일" value="2026-11-10" onChange={onChange} />);
    await fireEvent.press(screen.getByRole('button', { name: '시작일' }));
    await fireEvent.press(screen.getByLabelText('달력 닫기'));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByText('피커')).toBeNull();
  });

  it('고를 수 있는 범위를 그대로 넘긴다', async () => {
    await render(<DateField label="만료일" value="2026-11-20" min="2026-11-12" max="2026-12-31" onChange={jest.fn()} />);
    await fireEvent.press(screen.getByRole('button', { name: '만료일' }));
    expect(toIso(lastPickerProps().minimumDate)).toBe('2026-11-12');
    expect(toIso(lastPickerProps().maximumDate)).toBe('2026-12-31');
  });

  it('빈 칸은 min에서 연다', async () => {
    await render(<DateField label="만료일" value="" min="2026-11-12" onChange={jest.fn()} />);
    await fireEvent.press(screen.getByRole('button', { name: '만료일' }));
    expect(toIso(lastPickerProps().value)).toBe('2026-11-12');
  });
});

describe('Android 날짜 칸', () => {
  it('시스템 대화상자 그대로다 — display · locale을 주지 않는다', async () => {
    await render(<DateField label="시작일" value="2026-11-10" onChange={jest.fn()} />);
    await fireEvent.press(screen.getByRole('button', { name: '시작일' }));
    expect(lastPickerProps().display).toBeUndefined();
    expect(lastPickerProps().locale).toBeUndefined();
  });
});
```

대역이 고르는 날짜는 `new Date(2026, 10, 5)`다. `toIso`는 `@/ui/period`의 것이다.

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/dateField.test.tsx`
Expected: iOS 케이스 중 inline · 한국어와 `달력 닫기`가 FAIL. Android 케이스는 PASS.

- [ ] **Step 3: `DateField`의 iOS 분기를 구현한다**

- `Platform.OS === 'ios'`이면 `open`일 때 `<Modal visible transparent animationType="fade" onRequestClose={close}>`를 그린다. 안에는 화면 전체를 덮는 뒷배경 `Pressable`(`accessibilityLabel="달력 닫기"`, 색은 `palette.scrim`)과, 그 위 가운데에 `palette.bg` 카드 하나가 있다. 카드 안의 `DateTimePicker`는 `mode="date"` · `display="inline"` · `locale="ko-KR"`이고, `value` · `minimumDate` · `maximumDate`는 지금과 같게 넘긴다.
- iOS의 `onChange`는 고른 날짜가 있으면 `onChange(toIso(picked))` 뒤에 닫는다.
- Android는 지금 코드 그대로다(모달 없이 `open`이면 `DateTimePicker`, `display` · `locale` 없음).
- 컴포넌트 주석: "기기에서는 눌러서 시스템 피커를 연다. iOS는 칸 위에 달력을 바로 띄운다. 피커의 기본 표시는 칸 옆에 버튼을 하나 더 띄우는 compact라 두 번 눌러야 달력이 열리기 때문이다. 표기는 한국어로 고정한다. 바깥을 누르면 고르지 않고 닫는다." 웹 설명은 그대로 둔다.

- [ ] **Step 4: 테스트가 통과하는지 본다**

Run: `npx jest src/__tests__/dateField.test.tsx src/__tests__/expirySheet.test.tsx src/__tests__/realizedPnl.test.tsx src/__tests__/controls.test.tsx src/__tests__/cashflowFlow.test.tsx src/__tests__/alertSettings.test.tsx`
Expected: PASS

- [ ] **Step 5: 전체 테스트와 타입 검사**

Run: `npx jest && npx tsc --noEmit`
Expected: 모두 PASS, 타입 오류 없음

- [ ] **Step 6: 커밋**

```bash
git add src/ui/DateField.tsx src/__tests__/dateField.test.tsx
git commit -m "fix: iOS 날짜 칸을 누르면 한국어 달력이 바로 열린다"
```

### Task 2: 실기기에서 네 곳을 확인한다 (사용자)

Expo Go(iOS)에서 [사람]이 확인하고 결과를 받는다. 로컬 백엔드를 띄워야 하면 띄우기 전에 묻는다.

- [ ] 입출금 화면 폼: 자산 변화 화면의 `넣은 돈 입력 →` → 날짜 칸. 한 번 누르면 달력, 오늘 뒤는 고를 수 없음
- [ ] 기간 직접 고르기(`PeriodControl`): 시작일 · 종료일. 오늘 뒤는 고를 수 없음
- [ ] 알림 공통 설정(`SettingsStep`): 만료일 칸
- [ ] 만료 시트(`ExpirySheet`): 시트 위에 달력이 겹쳐 뜸, 오늘 앞은 고를 수 없음
- [ ] 네 곳 공통: 월 · 요일이 모두 한국어이고 섞이지 않음, 좌우 화살표로 달만 넘겨서는 닫히지 않음, 위쪽 월 · 연도를 눌러 휠로 바꿔도 닫히지 않음, 바깥을 누르면 값이 그대로인 채 닫힘

한국어 표기가 섞이거나 달을 넘길 때 닫히면 멈추고 보고한다(설계를 다시 정한다).
