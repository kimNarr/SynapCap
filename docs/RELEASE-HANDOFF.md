# 릴리스 절차 & 현황

> 마지막 갱신: 2026-09-04. **v0.3.0은 배포 완료됨.** 아래 1번은 현황, 2번은 다음 릴리스용 절차.

---

## 1. 현재 상태 — v0.3.0 배포 끝

| 항목 | 상태 |
| --- | --- |
| `version.py` | `0.3.0` |
| 태그 `v0.3.0` | `fefca20`, **push 됨** |
| `origin/main` = `origin/dev` | `dd01cd5` (태그보다 2커밋 뒤 — `d3c0d9e`·`dd01cd5`는 릴리스 후 홈페이지 정리) |
| 로컬 `dev` | `origin/dev`와 동일, 작업 트리 클린 |
| 로컬 `main` | `fefca20`에 멈춰 있음(stale). `git checkout main && git reset --hard origin/main`으로 맞추면 됨 |
| CI `release.yml` (`v0.3.0`) | ✅ success — Windows Setup.exe + macOS arm64/x64 dmg + `SHA256SUMS.txt` + provenance |
| GitHub 릴리스 `v0.3.0` | ✅ 게시됨 (assets 4개 첨부, `github-actions[bot]` 작성) |
| CI `pages.yml` (홈페이지) | ✅ `dd01cd5` 배포 성공 |
| CI `ci.yml` (테스트) | ✅ `main` green |

**남은 배포 작업 없음.** 다음 기능 작업은 `dev`에서 계속하면 된다.

- 로컬 `assets/synapcap.ico`/`.icns`/`.png`는 gitignore 대상이라 저장소·릴리스와 무관.
  릴리스는 CI가 `generate_icons.py`로 매번 새로 만든다. 로컬에서 새 아이콘을 보고 싶으면
  `python scripts/generate_icons.py`.

---

## 2. 다음 릴리스 절차

빌드·GitHub 릴리스는 **CI가 태그 push에 반응해서 자동으로 한다.** 사람이 하는 건 버전 범프 + 머지 + 태그 push뿐.

### 2-1. 사람이 하는 것

```bash
cd C:/project/personal/SynapCap
git checkout dev && git pull && git status        # 클린 확인
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests   # green 확인
python -m ruff check ui/ tests/                    # 기존 에러 6건 외 없음 확인

# 버전 범프 (version.py + CHANGELOG [Unreleased] -> [X.Y.Z] - <오늘>)
python scripts/manage_version.py bump minor        # 또는 patch / major / 1.2.3
# CHANGELOG.md의 새 [X.Y.Z] 섹션 문구 검토·정리

git commit -am "chore: release vX.Y.Z"

# main으로 fast-forward 머지
git checkout main && git reset --hard origin/main
git merge --ff-only dev

# 태그 + push  (dev도 같이 올려 origin/dev 동기화)
python scripts/manage_version.py check vX.Y.Z      # 태그 == APP_VERSION 확인
git tag vX.Y.Z
git push origin main dev --tags
```

### 2-2. CI가 자동으로 하는 것 (`.github/workflows/`)

| 트리거 | 워크플로 | 하는 일 |
| --- | --- | --- |
| `v*` 태그 push | `release.yml` | Ubuntu에서 소스 준비 → Windows/macOS(arm64·x64) 러너에서 `build_windows.ps1`/`build_macos.sh` (각각 `generate_icons.py` 먼저) → `SHA256SUMS.txt` + provenance → `manage_version.py notes vX.Y.Z`로 릴리스 노트 → `gh release create vX.Y.Z artifacts/* --verify-tag` |
| `main` push (`docs/**`) | `pages.yml` | 홈페이지 배포 |
| push / PR | `ci.yml` | 테스트 (Win/mac/Linux · Py 3.12) |

### 2-3. 확인

```bash
gh run list --workflow=release.yml --limit 1       # completed / success
gh release view vX.Y.Z --json assets --jq '.assets[].name'
# → SHA256SUMS.txt, SynapCap-macOS-arm64.dmg, SynapCap-macOS-x64.dmg, SynapCap-Windows-x64-Setup.exe
```

### 주의
- 릴리스 노트는 `CHANGELOG.md`의 해당 `## [X.Y.Z]` 섹션에서 뽑힌다. 범프 후 그 섹션을 꼭 다듬을 것.
- `--verify-tag` 때문에 태그가 remote에 있어야 릴리스가 만들어진다 (`git push --tags` 먼저).
- 로컬 `main`은 자주 stale해진다. 항상 `reset --hard origin/main` 후 머지.
- Claude Code 세션은 `dev` 커밋까지만 (push/tag/배포 금지). 이 절차는 오너/Codex가 실행.
