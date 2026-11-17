#!/usr/bin/env bash
# 캡처용 로컬 DB를 새로 만든다: 일회용 Postgres(127.0.0.1:5510)에 마이그레이션 · 샘플 · 캡처용 덧씌움을 넣는다.
# 사용: ./setup.sh <back-end 레포 경로>
set -euo pipefail
be="${1:?back-end 레포 경로를 넘긴다}"
db="$be/src/main/resources/db"
here="$(cd "$(dirname "$0")" && pwd)"

docker rm -f pf-tour >/dev/null 2>&1 || true
docker network create pf-tour-net >/dev/null 2>&1 || true
docker run -d --name pf-tour --network pf-tour-net -p 127.0.0.1:5510:5432 \
  -e POSTGRES_USER=portfolio -e POSTGRES_PASSWORD=portfolio -e POSTGRES_DB=portfolio postgres:16 >/dev/null
until docker exec pf-tour pg_isready -U portfolio -q; do sleep 1; done

# 서버와 같은 탐색 경로(app, data)로, 데이터팀 표 미러(external)까지 적용한다(로컬 프로필과 같다).
docker run --rm --network pf-tour-net -v "$db/migration:/m1:ro" -v "$db/external:/m2:ro" flyway/flyway:10 \
  "-url=jdbc:postgresql://pf-tour:5432/portfolio?currentSchema=app,data" -user=portfolio -password=portfolio \
  -schemas=app -locations=filesystem:/m1,filesystem:/m2 migrate >/dev/null

# 샘플 순서는 각 파일 머리말을 따른다: 렌즈 덧씌움이 마지막이다. 캡처용 덧씌움은 그 뒤.
for f in "$db/sample/sample_portfolio.sql" "$db/sample/sample_alert_market.sql" "$db/sample/sample_split.sql" \
         "$db/sample/sample_lookthrough.sql" "$here/extra.sql"; do
  docker cp "$f" pf-tour:/tmp/x.sql
  docker exec pf-tour psql -U portfolio -d portfolio -q -v ON_ERROR_STOP=1 -f /tmp/x.sql >/dev/null
  echo "적용: $(basename "$f")"
done
