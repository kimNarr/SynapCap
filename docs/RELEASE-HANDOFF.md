# 릴리스 절차 & 현황

> 마지막 갱신: 2026-11-20. **v0.4.0 배포 진행.** 사용자가 보류를 해제하고 커밋·배포를 요청했다. 아래 0번이 현재 상태이며 1번은 v0.3.0 당시 기록이다.

## 0. 현재 릴리스 — v0.4.0 준비

- SC-020 비모달 업데이트 안내와 SC-021 구독 전용 Windows 간단 보기·Mac 노치/메뉴바 표시를 묶는다. 로컬 테스트 313개 중 311개 통과·macOS 전용 2개 건너뛰기다.
- 새 설치는 간단 보기로 시작하고 기존 사용자 모드·좌표·API 설정은 보존한다. Mac에서 새 UI를 보려면 설정의 `미니 (노치·메뉴바)`를 선택한다.
- 사용자가 Mac 실기기 확인을 이어갈 예정이다. 실제 노치·Spaces·전체화면·외장 모니터와 설치본 네이티브 창 순서는 배포 성공과 별개로 검증 대기다.
- 다음 작업은 v0.4.0 커밋·태그 push, 세 운영체제 CI·Windows 및 Mac arm64/x64 빌드, 공개 자산·업데이트 감지·홈페이지 배포 확인이다. 개발 기록과 로컬 배치 파일은 커밋하지 않는다.

### 직전 릴리스 — v0.3.3

- SC-019 Claude 세션 대기 표시를 사용자의 요청으로 배포했다. 앱 버전·태그는 `0.3.3` / `v0.3.3` → `6809dc36b26e8bdfbde61babf51b4507c35b8a0b`다. 홈페이지 Windows·macOS CLI 설치 안내는 별도 `767eef5` 커밋으로 포함했다.
- Claude의 정확한 세션 0%·리셋 시각 없음만 `세션 대기`로 구분하고, 사용 중 시간 누락·잘못된 시각·주간·다른 서비스는 기존 표시를 유지한다. 실제 응답의 세션 0%·리셋 시각 없음·주간 7%를 확인했다.
- Windows 로컬 테스트 289개 중 287개 통과·macOS 전용 2개 건너뛰기. 두 테마·실제 Windows 글꼴·150% 배율 렌더링을 확인했다. `ui/ tests/` 기존 Ruff 경고 6건과 `subscription_usage.py` 기존 경고 외 추가 없음.
- [공개 릴리스](https://github.com/kimNarr/SynapCap/releases/tag/v0.3.3), [릴리스 CI](https://github.com/kimNarr/SynapCap/actions/runs/44435892896), [세 운영체제 CI](https://github.com/kimNarr/SynapCap/actions/runs/44435893104), [홈페이지 배포](https://github.com/kimNarr/SynapCap/actions/runs/44435892876) 성공을 확인했다.
- Windows 설치 파일·macOS arm64/x64 DMG·번들 검증 보고서 3개·체크섬 등 공개 자산 7개를 확인했다. 보고서의 실제 버전 `0.3.3`·프로브 `ready`, 다운로드한 보고서의 SHA-256과 모든 설치 파일의 GitHub digest를 체크섬과 대조했다.
- 실제 앱 업데이트 함수가 `0.3.2`에서 `0.3.3` Windows 설치 파일과 원클릭 가능 상태를 반환했다. 해당 함수로 설치 파일을 내려받아 SHA-256 검증까지 완료했고, 현재 `0.3.3`에는 다시 업데이트를 제안하지 않는 것을 확인했다. 설치 파일은 실행하지 않았다.
- SC-019는 배포 완료다. 실제 Claude 메시지를 보내 세션을 시작하거나 사용자 PC 설치본을 교체하지 않았다. 기존 SC-003·006·018의 전체 검증은 이 문구 패치와 별도로 남긴다. 개발 기록·로컬 실행 파일은 커밋하지 않았다.

### 미출시 수정 — SC-020 (2026-11-19)

- v0.3.3 업데이트 안내가 가려진 채 입력을 막는 제보를 받아 비모달·항상 위 설정 연동·전면 표시·테마·수명 정리를 수정했다. Windows 자동 테스트 293개 중 291개 통과·macOS 전용 2개 건너뛰기이며 설치본 네이티브 창 순서는 추가 검증이 필요하다.
- 2026-11-19 사용자의 수정만·배포 대기 요청으로 보류했다. 2026-11-20 커밋·배포 요청으로 보류가 해제됐으며 SC-021과 함께 v0.4.0에 포함한다.

### 미출시 기능 — SC-021 (2026-11-20)

- 사용자가 구독 사용량만 표시하는 Windows 모델별 한 줄과 Mac 노치·메뉴바 방향을 승인해 구현했다. 기존 API 설정과 상세 카드는 보존하되 간단 보기·트레이 숫자에서는 제외한다. 새 설치만 간단 보기로 시작하고 기존 설정은 보존한다.
- Windows 실제 글꼴·150% 렌더링, 전체 313개 테스트 중 311개 통과·macOS 전용 2개 건너뛰기를 확인했다. Mac 노치 좌표·노치 없는 화면 대체·메뉴바 이미지·클릭 경로는 합성 검증이며 실제 Mac·Spaces·전체화면·외장 모니터·Cocoa 패키징 검증은 남아 있다.
- Cocoa 브리지는 `pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"` 조건부 의존성이다. 다음 Mac 빌드에서 포함·실행을 확인해야 한다. 화면 정보는 공개 API로 읽으며 화면 녹화나 손쉬운 사용 권한은 요청하지 않는다.
- 2026-11-20 사용자 요청에 따라 v0.4.0(SC-020·021)으로 커밋·배포를 진행한다. 이전 배포 보류는 해제됐고, Mac 실기기 확인은 사용자가 이어서 수행한다.

### 직전 릴리스 — v0.3.2

- SC-018 UI 회귀 수정을 사용자의 요청으로 배포했다. 앱 버전·태그는 `0.3.2` / `v0.3.2` → `c6f0517d3289a009b4494ae2c38e15d885b1611b`다.
- 로컬 Windows 테스트는 281개 중 279개 통과·macOS 전용 2개 건너뛰기이며 기존 Ruff 경고 6건 외 추가 없음.
- 설정창 우선순위·미리보기, 중복 제목·CLI 배지·탭 채움·지연 툴팁 수정이 대상이다. 설치본의 실제 네이티브 창 순서 확인은 남아 있으며 릴리스 안내에도 명시한다.
- [공개 릴리스](https://github.com/kimNarr/SynapCap/releases/tag/v0.3.2), [릴리스 CI](https://github.com/kimNarr/SynapCap/actions/runs/42567134310), [Windows·macOS·Linux CI](https://github.com/kimNarr/SynapCap/actions/runs/42567134074), [홈페이지 배포](https://github.com/kimNarr/SynapCap/actions/runs/42567134065) 성공을 확인했다.
- Windows Setup.exe와 macOS arm64·x64 DMG, 검증 JSON 3개, 체크섬 목록 등 공개 자산 7개를 확인했다. 세 보고서 모두 실제 버전 `0.3.2`·프로브 `ready`이며 보고서 다운로드 해시와 설치 파일 GitHub digest를 체크섬과 대조했다.
- 실제 앱 업데이트 함수가 `0.3.1`에서 `0.3.2` Windows 설치 파일과 원클릭 업데이트 가능 상태를 반환했고, 현재 버전 `0.3.2`에는 새 업데이트를 반환하지 않았다. 사용자 PC에 설치·실행하지는 않았다.
- 개발 기록과 로컬 실행용 배치 파일은 커밋하지 않는다. SC-018의 코드 배포와 실제 네이티브 창 순서 확인은 별개로 관리한다.

### 이전 릴리스 — v0.3.1

- 앱 버전·태그: `0.3.1` / `v0.3.1` → `f108f2c6f0c4fa5cd518fc418e90442f6df592f1`.
- [공개 릴리스](https://github.com/kimNarr/SynapCap/releases/tag/v0.3.1)와 [릴리스 CI](https://github.com/kimNarr/SynapCap/actions/runs/42543053890) 성공을 확인했다. Windows Setup.exe, macOS arm64·x64 DMG, 검증 JSON 3개, SHA256SUMS.txt 등 자산 7개를 공개했고 provenance 생성도 성공했다.
- [Windows·macOS·Linux CI](https://github.com/kimNarr/SynapCap/actions/runs/42543054097)가 성공했다. 테스트는 플랫폼별 271개이며 플랫폼 전용 건너뛰기를 포함한다. 로컬 Windows는 269개 통과·macOS 링크 테스트 2개 건너뛰기다. Ruff는 기존 경고 6건 외 추가 없음.
- 각 공개 번들 보고서에서 실제 앱 버전 `0.3.1`과 Copilot 프로브 `ready`를 확인했다. 보고서 다운로드 SHA-256 및 공개 설치 파일의 GitHub digest를 체크섬 목록과 대조했다.
- 기존 버전 `0.3.0`을 전달한 실제 앱 업데이트 조회가 `0.3.1` Windows 설치 파일과 원클릭 업데이트 가능 상태를 반환했다. 사용자 PC에 설치하거나 실행 중인 앱을 교체하지는 않았다.
- Claude·Copilot 실계정 대조, 실제 Argon 응답 확인, macOS 메뉴바 클릭 종료 재현은 미완료다. 빌드 성공만으로 해결 완료로 바꾸지 않는다.
- 개발 기록(`journal/`)과 로컬 실행용 배치 파일은 릴리스 커밋에서 제외한다.
- 첫 시도는 경로·운영체제 가정을 보완한 `eb622c5`, 두 번째는 macOS 헬퍼 링크 중복을 보완한 `f108f2c`로 재시도했다. 공개 릴리스가 없는 상태에서만 기존 SHA를 명시한 lease로 태그를 갱신했다. 게시된 v0.3.1 태그는 더 이상 이동하지 않는다.

---

## 1. 이전 기록 — v0.3.0 배포 끝 (2026-09-04 당시)

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
git switch main
git merge --ff-only origin/main
git merge --ff-only dev

# 태그 + push  (dev도 같이 올려 origin/dev 동기화)
python scripts/manage_version.py check vX.Y.Z      # 태그 == APP_VERSION 확인
git tag vX.Y.Z
git push --atomic origin main dev refs/tags/vX.Y.Z
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
- 로컬 `main`이 뒤처져 있으면 `merge --ff-only origin/main`으로 갱신한다. fast-forward가 불가능하면 중단하고 차이를 확인하며, 기존 변경을 강제로 초기화하지 않는다.
- Claude Code 세션은 `dev` 커밋까지만 (push/tag/배포 금지). 이 절차는 오너/Codex가 실행.
