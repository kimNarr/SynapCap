# 릴리스 인수인계 — v0.2.6 이후 (2026-09-03)

> 이 문서는 **다음 릴리스를 내보내기 위한** 현황 정리다. 디자인/기능 작업은 `dev`에 전부
> 커밋되어 있고, **머지·버전 범프·태그·push·빌드·GitHub 릴리스만 남았다.**
> Claude Code 세션은 push/tag/배포를 못 하므로 여기까지만 준비됨.

---

## 1. 지금 git 상태

| ref | SHA | 의미 |
| --- | --- | --- |
| `origin/main` | `3d81560` | **마지막 릴리스 = 태그 `v0.2.6`** (`origin/main`이 곧 `v0.2.6`) |
| `dev` (로컬) | `25ed88f` | 이번에 낼 것. `origin/main`의 **직계 자손** → 충돌 없이 fast-forward 머지 가능 |
| `origin/dev` | `2a3eb4c` | 오래된 상태. 로컬 `dev`가 훨씬 앞서 있고 **아직 push 안 됨** |
| `main` (로컬) | `d578859` | 오래됨(`v0.2.0` 근처). 무시하고 `origin/main` 기준으로 작업할 것 |

- `dev`는 `origin/main`보다 **27 커밋 앞섬** (`git rev-list --count origin/main..dev`).
- 작업 트리 클린. 단 `assets/logo-concept.png`가 **untracked** — 컨셉 스케치라 커밋 대상 아님. `.gitignore`에 넣거나 그대로 두면 됨.
- `version.py` = `0.2.6` (아직 안 올림). `CHANGELOG.md`에 `[Unreleased]` 항목 가득.
- 테스트 **187개 통과** (`QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests`).
- ruff: 기존 에러 6건만 (`test_subscription_usage.py` FLY002, `test_updates.py` UP012 ×3, `config.py` blind-except ×2) — 이번 변경으로 늘지 않음.

---

## 2. v0.2.6 이후 `dev`의 27 커밋 (릴리스 노트용)

### 새 기능
| 커밋 | 내용 |
| --- | --- |
| `e3daa85` | 펼침·막대·트레이만 **3단계 표시 모드** + 모드별 위치 저장 + 동적 트레이 숫자 아이콘 |
| `8913399` | 컴팩트 막대에 "트레이로 접기" 버튼 (위젯 안에서 펼침→막대→트레이만) |
| `c649a5c` · `56da206` · `f508f7b` | 트레이에 표시할 수치 선택 설정 `tray_metric` (`최고 사용률` / 특정 프로바이더 / `숫자 표시 안 함`) |
| `6a84b99` | 펼침·막대 창 제어를 `[트레이로] [모드 토글] [종료]` 같은 순서·아이콘으로 통일, 펼침에서도 곧장 트레이만 모드로 |
| `25ed88f` | 첫 실행·업데이트 직후 위젯을 화면 중앙 배치, 이후엔 마지막 위치·모드 복원 |
| `034a81b` | 홈페이지 라이트 테마 |

### 디자인 / UX
| 커밋 | 내용 |
| --- | --- |
| `f94848e` · `8e1c4d0` | 집중 링 뷰로 재설계 (단일 `UsageRing` + 프로바이더 탭, 384px 고정) |
| `a63be2a` · `c090850` · `060cb4b` | 펼침 헤더 브랜드 마크, 탭 폭·타이포 정리 |
| `32947a8` | 집중 카드에서 링 안 `%`가 헤드라인이 되도록 라벨 강등 (9-6) |
| `b1da61f` | 버전 칩은 업데이트 시에만 노출 + 세 프로바이더 출처 툴팁 일관 (9-8) |
| `c53ac1d` | 위험 단계에 색 외 신호(집중 링 타일 테두리 2/3px) (Task 3) |
| `0904d3e` · `12898c7` | 로고 마크를 앱 accent로 통일 (`#89B4FA` / 라이트 `#1857C9`) + 자산 재생성 (Task 5) |
| `0098e22` · `85de758` | 프로바이더 칩 테마 틴트 통일, Claude 글리프를 공식 Claude 마크로 (Task 6) |
| `5a2c864` | 홈페이지 위젯 미리보기를 현재 디자인으로 갱신 (Task 7) |
| `9ff9729` | 트레이 글리프 확대(여백↓·자릿수별 폰트) + 설정 푸터 `취소`/`저장` 2버튼(`적용` 제거) |
| `ec8f619` · `89897e4` · `ee57f31` · `e9992f6` · `6f77ff3` | **로고 스피너 오인 해결**: 게이지 270°호→닫힌 원, 트랙 색 대비↑, 인앱 아트 HiDPI 렌더, 헤더 마크 20→26px·`S` 획 굵게, 테마 전환 시 헤더 로고 재도색 |

### 수정
| 커밋 | 내용 |
| --- | --- |
| `3d81560`\* · `b4f8c21` · `dd17729` · `2a3eb4c` | 작업표시줄 위 고정 위젯 Z-order/클릭 안정화 (\* `3d81560`은 이미 `v0.2.6`에 포함) |
| `8e1c4d0` | 막대 펼치기 시 현재 화면 모서리 기준으로 펼치도록 (과거 좌표 이동 버그) |

### 문서
`56dc1dd` · `71bdb5c` · `f9b7c5b` · `7101448` — `docs/HANDOFF.md`(디자인 backlog) 추가·갱신, 프로바이더 아이콘 고지 정정.

> 세부 결정·구현 위치는 `docs/HANDOFF.md`, `docs/DESIGN.md` 참고. `CHANGELOG.md`의 `[Unreleased]` 블록에 사용자용 문구가 이미 정리돼 있음.

---

## 3. 남은 릴리스 절차 (오너/Codex가 직접)

권장 버전: **`0.3.0`** (minor — 3단계 표시 모드·`tray_metric`·창 제어 통일 등 새 기능 다수).

```bash
# 0) dev 최신·클린 확인 (로컬 dev = 25ed88f)
cd C:/project/personal/SynapCap
git checkout dev && git status
python scripts/manage_version.py current            # 0.2.6

# 1) 버전 범프 (version.py + CHANGELOG [Unreleased] -> [0.3.0] - <오늘>)
python scripts/manage_version.py bump minor         # 0.2.6 -> 0.3.0
git commit -am "chore: release v0.3.0"

# 2) origin/main 기준으로 main 맞추고 fast-forward 머지
git checkout main
git reset --hard origin/main
git merge --ff-only dev

# 3) 태그·검증·push
python scripts/manage_version.py check v0.3.0       # 태그↔APP_VERSION 일치 확인
git tag v0.3.0
git push origin main dev --tags                     # dev도 올려 origin/dev 갱신

# 4) 빌드 (스크립트가 generate_icons.py를 먼저 돌려 새 로고 반영)
pwsh scripts/build_windows.ps1
bash scripts/build_macos.sh                         # macOS 러너에서

# 5) GitHub 릴리스
python scripts/manage_version.py notes 0.3.0 > RELEASE_NOTES_v0.3.0.md
gh release create v0.3.0 dist/* --title "SynapCap v0.3.0" --notes-file RELEASE_NOTES_v0.3.0.md
```

### 주의
- 패키지 `synapcap.ico` / `.icns` / `.png`는 `.gitignore` 대상 — 빌드 스크립트가 `scripts/generate_icons.py`로 매번 생성. 이번 로고 변경은 자동 반영됨.
- `docs/assets/logo.png`는 저장소에 커밋돼 있고 이미 새 로고로 재생성됨.
- `manage_version.py bump`은 `version.py`의 `APP_VERSION`과 `CHANGELOG.md`의 `[Unreleased]` 마커만 건드림(태그·push·빌드 안 함). `notes <버전>`으로 릴리스 노트 추출, `check <태그>`로 태그↔버전 일치 확인.
- Windows 체크아웃이라 `git`이 CRLF 경고를 낼 수 있음(정상).
- `dev` 브랜치 규칙: Claude Code 세션은 여기 커밋까지만. 이 문서도 그래서 작성됨.
