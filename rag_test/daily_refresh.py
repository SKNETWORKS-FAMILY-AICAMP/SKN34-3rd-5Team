"""순위·일정 자동 갱신 — 크롤링 → 로컬 전용 폴더로 복사 → 재적재

git 에 올라간 data/preprocessed 는 건드리지 않는다 (팀원과 충돌 방지).
크롤링 결과는 backend/_data_live 에만 쌓고, build_index 는 RAG_DATA_DIR 로 그 폴더를 본다.

수동 실행: python rag_test\\daily_refresh.py
로그      : rag_test\\results\\refresh.log
"""
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(__file__).resolve().parent / "results" / "refresh.log"
LOG.parent.mkdir(exist_ok=True)

CRAWLERS = ["crawling/kbo_standing.py", "crawling/kbo_schedule.py"]   # 자주 바뀌는 것만
REPO_DATA = ROOT / "data" / "preprocessed"          # git 추적 대상 — 읽기만 한다
CRAWLED = ROOT / "backend" / "data" / "preprocessed"  # 크롤러가 쓰는 곳 (스크립트 위치 기준)
LIVE = ROOT / "backend" / "_data_live"              # build_index 가 읽을 로컬 전용 폴더


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(*args, env=None):
    cmd = ["docker", "compose", "exec", "-T"]
    for k, v in (env or {}).items():
        cmd += ["-e", f"{k}={v}"]
    cmd += ["backend", *args]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        log(f"실패: {' '.join(args)}\n{(p.stderr or p.stdout)[-800:]}")
        sys.exit(1)
    return p.stdout


def guard_gitignore(folder):
    """이 폴더는 통째로 git 에서 무시 (팀 .gitignore 를 건드리지 않으려고 폴더 안에 둔다)"""
    folder.mkdir(parents=True, exist_ok=True)
    ignore = folder / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")


log("=== 갱신 시작 ===")
guard_gitignore(LIVE)
guard_gitignore(ROOT / "backend" / "data")
CRAWLED.mkdir(parents=True, exist_ok=True)   # 크롤러가 저장할 폴더 (컨테이너의 /app/data/preprocessed)

first = not any(LIVE.glob("*.csv"))
if first:                                            # 처음 한 번만 원본 전체를 복사
    for src in REPO_DATA.iterdir():
        if src.is_file():
            shutil.copy2(src, LIVE / src.name)
    log(f"기준 데이터 {len(list(LIVE.glob('*.csv')))}개 복사 (최초 1회)")

for script in CRAWLERS:                              # 1. 크롤링
    run("python", script)
    log(f"크롤링 완료 {script}")

updated = 0                                          # 2. 새로 받은 것만 덮어쓰기
for src in CRAWLED.glob("*.csv"):
    dst = LIVE / src.name
    if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
        shutil.copy2(src, dst)
        updated += 1
        log(f"갱신 {src.name}")
log(f"갱신 {updated}건")

out = run("python", "manage.py", "build_index", env={"RAG_DATA_DIR": "/app/_data_live"})   # 3. 재적재
log(out.strip().splitlines()[-1] if out.strip() else "build_index 완료")
log("=== 갱신 끝 ===")
