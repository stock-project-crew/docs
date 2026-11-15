#!/usr/bin/env bash
# 서버 코드에서 생성한 OpenAPI 명세를 받아 HTML(Redoc)과 Markdown으로 바꾼다.
#
# 필요한 것: Node(npx), Python 3
#
# 1. back-end에서 명세를 생성한다(테스트 DB가 필요하다):
#      ./gradlew test --tests '*OpenApiSpecExportTest'
#    결과: back-end/build/openapi/openapi.json
# 2. 이 스크립트에 그 파일을 넘긴다:
#      ./api.sh <back-end>/build/openapi/openapi.json
#
# 출력: ../api/openapi.json(원본) · ../api/index.html(Redoc) · ../api.md(Markdown)
set -euo pipefail

src="${1:?openapi.json 경로를 넘긴다}"
here="$(cd "$(dirname "$0")" && pwd)"
out="$here/.."

mkdir -p "$out/api"
cp "$src" "$out/api/openapi.json"

npx -y @redocly/cli@1.25.0 build-docs "$out/api/openapi.json" -o "$out/api/index.html"
npx -y widdershins@4.0.1 "$out/api/openapi.json" -o "$out/api.md" \
  --omitHeader --language_tabs --shallowSchemas true --maxDepth 1 >/dev/null

# 제목을 생성기의 메서드 이름(refresh_1 등) 대신 "메서드 경로"로 바꾸고, 내용 없는 안내 줄을 지운다.
python3 - "$out/api/openapi.json" "$out/api.md" <<'EOF'
import json, re, sys
spec = json.load(open(sys.argv[1]))
summary = {op["operationId"]: op["summary"]
           for item in spec["paths"].values() for op in item.values()
           if isinstance(op, dict) and "operationId" in op}
md = open(sys.argv[2]).read()
md = re.sub(r"^## (\S+)$", lambda m: "## " + summary.get(m.group(1), m.group(1)), md, flags=re.M)
md = re.sub(r"^\*(GET|POST|PUT|DELETE|PATCH) [^*]+\*\n\n", "", md, flags=re.M)
for noise in ("> Scroll down for example requests and responses.\n\n", "Base URLs:\n\n", "> Code samples\n\n"):
    md = md.replace(noise, "")
open(sys.argv[2], "w").write(md)
EOF
echo "api: $(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['paths']))" "$out/api/openapi.json")개 경로"
