-- 캡처용 덧씌움. back-end 샘플(sample_portfolio · sample_alert_market · sample_split · sample_lookthrough) 뒤에 적용한다.
-- 여정 5의 인증 실패 안내를 보이려고, '국내주식' 계좌의 마지막 수집을 데이터팀이 인증 실패로 끝낸 것처럼 둔다.
SET search_path = app, data;
INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at, failure_reason)
VALUES ('90000000-0000-0000-0000-000000000001', 'ar_2b8e05da', 'SCHEDULE', DATE '2026-07-27',
        TIMESTAMPTZ '2026-07-27 23:00:00+09', 'FAILED', TIMESTAMPTZ '2026-07-27 23:05:00+09', 'SOURCE_CREDENTIAL_INVALID')
ON CONFLICT (run_id) DO NOTHING;
