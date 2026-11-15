#!/usr/bin/env python3
"""백엔드 표의 ERD를 스키마에서 그린다.

일회용 Postgres 컨테이너에 백엔드 마이그레이션을 적용하고, 카탈로그에서 컬럼 · 키 · 제약을
읽어 Graphviz로 그린다. 표를 손으로 옮겨 적지 않으므로 다시 돌리면 스키마와 같아진다.

필요한 것: Docker, Graphviz(dot), Python 3 표준 라이브러리

실행:
    # back-end 레포의 db 폴더(migration · external이 든 곳)를 넘긴다
    python3 erd.py --db-dir ../../../../back-end/src/main/resources/db

    # 특정 커밋 기준으로 그리려면 그 커밋의 db 폴더를 꺼내서 넘긴다
    git -C <back-end> archive origin/main src/main/resources/db | tar -x -C /tmp/be
    python3 erd.py --db-dir /tmp/be/src/main/resources/db

출력: ../erd/<번호>-<이름>.svg · .png · .dot

손으로 고치는 곳은 아래 GROUPS와 LOGICAL_REFS 둘뿐이다.
- 새 표가 생겨 GROUPS에 없으면 실패한다. 어느 그림에 넣을지 정해 GROUPS에 더한다.
- LOGICAL_REFS는 FK 없이 값으로만 가리키는 관계다. 카탈로그에 나오지 않아 직접 적는다.
"""

import argparse
import json
import os
import subprocess
import sys
import time

# ── 손으로 정하는 것 ─────────────────────────────────────────────

# 그림마다 넣을 백엔드 표. 다른 그림의 표를 가리키는 FK는 이름만 있는 상자로 그린다.
GROUPS = [
    ("1-portfolio", "포트폴리오", [
        "account", "position_line", "position_build", "snapshot_run",
        "position_basis", "basis_build", "realized_pnl_line",
        "manual_cashflow", "sync_run", "sync_run_account",
    ]),
    ("2-alert", "알림", [
        "alert", "alert_state", "alert_event", "alert_delivery",
        "push_device", "alert_watchlist",
    ]),
    ("3-auth", "로그인", [
        "app_user", "auth_session",
    ]),
]

# FK 없이 값으로만 가리키는 관계: (표, 컬럼, 가리키는 표, 가리키는 컬럼).
# data. 으로 시작하면 데이터팀 표다. 데이터팀 표와 FK를 걸지 않는 것은 두 팀의 배포 순서를 묶지 않으려고다.
LOGICAL_REFS = [
    ("position_line", "instrument_id", "data.instrument", "instrument_id"),
    ("position_basis", "instrument_id", "data.instrument", "instrument_id"),
    ("realized_pnl_line", "instrument_id", "data.instrument", "instrument_id"),
    ("realized_pnl_line", "trade_id", "data.cln_trade", "trade_id"),
    ("position_build", "run_id", "data.collection_run", "run_id"),
    ("sync_run_account", "collection_run_id", "data.collection_run", "run_id"),
    ("data.collection_run", "account_ref", "account", "account_ref"),
    ("alert", "instrument_id", "data.instrument", "instrument_id"),
    ("alert_watchlist", "instrument_id", "data.instrument", "instrument_id"),
]

# ── 모양 ─────────────────────────────────────────────────────────

FONT = "Apple SD Gothic Neo"
MONO = "Menlo"
C_HEAD = "#3B5BDB"
C_HEAD_TX = "#FFFFFF"
C_STUB = "#ECEEF1"
C_STUB_TX = "#3A4048"
C_DATA = "#FDF3D6"
C_DATA_ST = "#C7B98F"
C_BORDER = "#AAB2C0"
C_PK = "#B7791F"
C_FK = "#1F6FE5"
C_UQ = "#2E7D52"
C_MUTED = "#8A93A0"
C_EDGE = "#6B7280"

CONTAINER = "pf-erd-db"
NETWORK = "pf-erd-net"

SCHEMA_SQL = r"""
with cols as (
  select c.relname as tbl, a.attnum as pos, a.attname as col,
         format_type(a.atttypid, a.atttypmod) as typ, a.attnotnull as notnull
  from pg_attribute a
  join pg_class c on c.oid = a.attrelid
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'app' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped
    and c.relname <> 'flyway_schema_history'
),
cons as (
  select c.conrelid::regclass::text as tbl, c.contype as kind,
         array(select a.attname from unnest(c.conkey) with ordinality k(n, o)
               join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k.n order by k.o) as cols,
         c.confrelid::regclass::text as ref_tbl,
         array(select a.attname from unnest(c.confkey) with ordinality k(n, o)
               join pg_attribute a on a.attrelid = c.confrelid and a.attnum = k.n order by k.o) as ref_cols,
         c.confdeltype as on_delete
  from pg_constraint c
  where c.connamespace = 'app'::regnamespace and c.contype in ('p', 'f', 'u')
),
uidx as (
  select t.relname as tbl,
         array(select a.attname from unnest(i.indkey::int2[]) k(n)
               join pg_attribute a on a.attrelid = i.indrelid and a.attnum = k.n) as cols,
         pg_get_expr(i.indpred, i.indrelid) as pred
  from pg_index i
  join pg_class t on t.oid = i.indrelid
  join pg_namespace n on n.oid = t.relnamespace
  where n.nspname = 'app' and i.indisunique and not i.indisprimary
    and not exists (select 1 from pg_constraint c where c.conindid = i.indexrelid)
)
select json_build_object(
  'columns', (select json_agg(cols order by tbl, pos) from cols),
  'constraints', (select json_agg(cons) from cons),
  'unique_indexes', (select coalesce(json_agg(uidx), '[]'::json) from uidx),
  'data_columns', (select json_object_agg(table_name, cols) from (
      select table_name, json_agg(column_name order by ordinal_position) as cols
      from information_schema.columns where table_schema = 'data' group by table_name) d)
)
"""


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)


def load_schema(db_dir):
    mig = os.path.abspath(os.path.join(db_dir, "migration"))
    ext = os.path.abspath(os.path.join(db_dir, "external"))
    for d in (mig, ext):
        if not os.path.isdir(d):
            sys.exit(f"폴더가 없다: {d}")
    subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
    subprocess.run(["docker", "network", "create", NETWORK], capture_output=True)
    try:
        run(["docker", "run", "-d", "--rm", "--name", CONTAINER, "--network", NETWORK,
             "-e", "POSTGRES_USER=portfolio", "-e", "POSTGRES_PASSWORD=portfolio",
             "-e", "POSTGRES_DB=portfolio", "postgres:16"])
        for _ in range(60):
            if subprocess.run(["docker", "exec", CONTAINER, "pg_isready", "-U", "portfolio", "-q"]).returncode == 0:
                break
            time.sleep(1)
        # 서버와 같은 탐색 경로(app, data)로 적용해야 app 마이그레이션이 data 표를 찾는다.
        # 데이터팀 표 미러(external)를 함께 적용해 app 마이그레이션이 참조하는 표를 만든다.
        run(["docker", "run", "--rm", "--network", NETWORK,
             "-v", f"{mig}:/m1:ro", "-v", f"{ext}:/m2:ro", "flyway/flyway:10",
             f"-url=jdbc:postgresql://{CONTAINER}:5432/portfolio?currentSchema=app,data",
             "-user=portfolio", "-password=portfolio", "-schemas=app",
             "-locations=filesystem:/m1,filesystem:/m2", "migrate"])
        out = run(["docker", "exec", CONTAINER, "psql", "-U", "portfolio", "-At", "-c", SCHEMA_SQL])
        return json.loads(out.stdout)
    finally:
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        subprocess.run(["docker", "network", "rm", NETWORK], capture_output=True)


def short_type(t):
    return (t.replace("timestamp with time zone", "timestamptz")
             .replace("timestamp without time zone", "timestamp")
             .replace("character varying", "varchar")
             .replace("boolean", "bool")
             .replace("integer", "int"))


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Schema:
    def __init__(self, raw):
        self.columns = {}
        for c in raw["columns"]:
            self.columns.setdefault(c["tbl"], []).append(c)
        self.pk, self.fks, self.uniques = {}, [], {}
        for c in raw["constraints"]:
            tbl = c["tbl"].removeprefix("app.")
            if c["kind"] == "p":
                self.pk[tbl] = c["cols"]
            elif c["kind"] == "u":
                self.uniques.setdefault(tbl, []).append((c["cols"], None))
            else:
                self.fks.append(dict(tbl=tbl, cols=c["cols"], ref=c["ref_tbl"].removeprefix("app."),
                                     ref_cols=c["ref_cols"], cascade=c["on_delete"] == "c"))
        for u in raw["unique_indexes"]:
            self.uniques.setdefault(u["tbl"], []).append((u["cols"], u["pred"]))
        self.data_columns = raw["data_columns"] or {}

    def check(self):
        listed = [t for _, _, ts in GROUPS for t in ts]
        missing = sorted(set(self.columns) - set(listed))
        gone = sorted(set(listed) - set(self.columns))
        if missing or gone:
            sys.exit(f"GROUPS를 스키마에 맞춰야 한다. 없는 표: {missing}, 사라진 표: {gone}")
        for tbl, col, ref, ref_col in LOGICAL_REFS:
            for t, c in ((tbl, col), (ref, ref_col)):
                if t.startswith("data."):
                    ok = c in self.data_columns.get(t[5:], [])
                else:
                    ok = any(x["col"] == c for x in self.columns.get(t, []))
                if not ok:
                    sys.exit(f"LOGICAL_REFS의 {t}.{c}가 스키마에 없다")


def table_node(s, tbl):
    pk = set(s.pk.get(tbl, []))
    fk_cols = {c for f in s.fks if f["tbl"] == tbl for c in f["cols"]}
    fk_cols |= {col for t, col, _, _ in LOGICAL_REFS if t == tbl}
    single_uq = {u[0][0] for u in s.uniques.get(tbl, []) if len(u[0]) == 1 and u[1] is None}
    multi_uq = [u for u in s.uniques.get(tbl, []) if len(u[0]) > 1 or u[1] is not None]

    rows = [f'<TR><TD COLSPAN="3" BGCOLOR="{C_HEAD}" ALIGN="LEFT" CELLPADDING="6">'
            f'<FONT FACE="{MONO}" COLOR="{C_HEAD_TX}" POINT-SIZE="13"><B>{esc(tbl)}</B></FONT></TD></TR>']
    for c in s.columns[tbl]:
        marks = []
        if c["col"] in pk:
            marks.append(f'<FONT COLOR="{C_PK}"><B>PK</B></FONT>')
        if c["col"] in fk_cols:
            marks.append(f'<FONT COLOR="{C_FK}"><B>FK</B></FONT>')
        if c["col"] in single_uq:
            marks.append(f'<FONT COLOR="{C_UQ}"><B>UQ</B></FONT>')
        mark = " ".join(marks) or " "
        typ = esc(short_type(c["typ"]))
        null = "" if c["notnull"] else f' <FONT COLOR="{C_MUTED}">null</FONT>'
        rows.append(
            f'<TR><TD ALIGN="LEFT" PORT="{c["col"]}_l"><FONT FACE="{MONO}" POINT-SIZE="9">{mark}</FONT></TD>'
            f'<TD ALIGN="LEFT"><FONT FACE="{MONO}">{esc(c["col"])}</FONT></TD>'
            f'<TD ALIGN="LEFT" PORT="{c["col"]}_r"><FONT FACE="{MONO}" COLOR="{C_MUTED}">{typ}</FONT>{null}</TD></TR>')
    for cols, pred in multi_uq:
        txt = "UQ (" + ", ".join(cols) + ")" + (f" WHERE {pred}" if pred else "")
        rows.append(f'<TR><TD COLSPAN="3" ALIGN="LEFT"><FONT FACE="{MONO}" COLOR="{C_UQ}" POINT-SIZE="9">'
                    f'{esc(txt)}</FONT></TD></TR>')
    label = (f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="{C_BORDER}">'
             + "".join(rows) + "</TABLE>>")
    return f'  "{tbl}" [label={label}];'


def stub_node(name, data=False):
    if data:
        return (f'  "{name}" [label=<<TABLE BORDER="1" STYLE="dashed" CELLBORDER="0" CELLPADDING="6" '
                f'COLOR="{C_DATA_ST}" BGCOLOR="{C_DATA}"><TR><TD><FONT FACE="{MONO}" COLOR="{C_STUB_TX}">'
                f'{esc(name)}</FONT></TD></TR><TR><TD><FONT POINT-SIZE="9" COLOR="{C_MUTED}">데이터팀 표</FONT>'
                f'</TD></TR></TABLE>>];')
    return (f'  "{name}" [label=<<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="6" COLOR="{C_BORDER}" '
            f'BGCOLOR="{C_STUB}"><TR><TD><FONT FACE="{MONO}" COLOR="{C_STUB_TX}">{esc(name)}</FONT></TD></TR>'
            f'<TR><TD><FONT POINT-SIZE="9" COLOR="{C_MUTED}">다른 그림</FONT></TD></TR></TABLE>>];')


def port(s, tbl, col, side, shown):
    # 선은 표끼리 잇는다. 컬럼 칸에 붙이면 같은 그림 안의 선이 표 옆을 돌아 고리가 된다.
    # 어느 컬럼인지는 선의 라벨과 표 안의 FK 표시가 보인다.
    return f'"{tbl}"'


def diagram(s, title, tables):
    shown = set(tables)
    lines = [
        "digraph erd {",
        '  graph [rankdir=LR, splines=spline, nodesep=0.5, ranksep=1.1, pad=0.4, bgcolor="white",',
        f'         fontname="{FONT}", fontsize=20, labelloc=t, labeljust=l,',
        f'         label=<<B>{esc(title)}</B>  <FONT POINT-SIZE="11" COLOR="{C_MUTED}">'
        f'PK 기본키 · FK 다른 표를 가리킴 · UQ 유일 · null 비워 둘 수 있음 · 실선 FK · 점선 FK 없이 값으로만 가리킴</FONT>>];',
        f'  node [shape=plain, fontname="{FONT}", fontsize=10];',
        f'  edge [color="{C_EDGE}", fontname="{FONT}", fontsize=9, fontcolor="{C_MUTED}", arrowsize=0.8];',
    ]
    for t in tables:
        lines.append(table_node(s, t))
    stubs, data_stubs = set(), set()
    edges = []
    for f in s.fks:
        a, b = f["tbl"], f["ref"]
        if a not in shown and b not in shown:
            continue
        for x in (a, b):
            if x not in shown:
                stubs.add(x)
        one_to_one = sorted(f["cols"]) == sorted(s.pk.get(a, []))
        tail = "tee" if one_to_one else "crow"
        text = ", ".join(f["cols"]) + ("\\n삭제 시 함께 삭제" if f["cascade"] else "")
        label = f' label="{text}"' 
        edges.append(f'  {port(s, a, f["cols"][0], "l", shown)} -> {port(s, b, f["ref_cols"][0], "r", shown)} '
                     f'[dir=both, arrowtail={tail}, arrowhead=tee{label}];')
    for a, col, b, ref_col in LOGICAL_REFS:
        if a not in shown and b not in shown:
            continue
        for x in (a, b):
            if x.startswith("data."):
                data_stubs.add(x)
            elif x not in shown:
                stubs.add(x)
        edges.append(f'  {port(s, a, col, "l", shown)} -> {port(s, b, ref_col, "r", shown)} '
                     f'[style=dashed, dir=both, arrowtail=crow, arrowhead=none, color="{C_DATA_ST}", label="{col}"];')
    for x in sorted(stubs):
        lines.append(stub_node(x))
    for x in sorted(data_stubs):
        lines.append(stub_node(x, data=True))
    lines += edges
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db-dir", required=True, help="back-end의 src/main/resources/db 경로")
    p.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "erd"))
    a = p.parse_args()

    s = Schema(load_schema(a.db_dir))
    s.check()
    os.makedirs(a.out, exist_ok=True)
    for name, title, tables in GROUPS:
        dot = os.path.join(a.out, f"{name}.dot")
        with open(dot, "w") as fh:
            fh.write(diagram(s, f"ERD — {title}", tables))
        for fmt in ("svg", "png"):
            extra = ["-Gdpi=144"] if fmt == "png" else []
            run(["dot", f"-T{fmt}", *extra, dot, "-o", os.path.join(a.out, f"{name}.{fmt}")])
        print(f"{name}: 표 {len(tables)}개")


if __name__ == "__main__":
    main()
