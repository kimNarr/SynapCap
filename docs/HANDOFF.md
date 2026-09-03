# SynapCap — 작업 현황 & 남은 일 (최종본)

> `dev` `7101448` 기준. 테스트 **175개 통과**. 이번 라운드의 디자인/UX backlog는
> **딱 하나(자산 의존)만 남기고 전부 완료**. push/tag/배포는 오너가 직접.

---

## 남은 일 (1개)

### 공식 Claude 마크 SVG 교체

현재 Claude 프로바이더 칩의 글리프는 **손으로 그린 방사형 버스트 근사치**다
(`ui/icon.py::_claude_burst_markup` — `<line>` 11개 + 중심 원, 코럴).
라이선스 가능한 공식 Claude 마크를 확보하면:

1. `ui/icon.py` — `_PROVIDER_BRANDS["claude"]`의 `"markup"`(또는 `"path"`) 값만 교체.
   `create_provider_pixmap`는 두 키를 다 처리한다. `"path"`면 `{fg}` 없이 `d="..."`만,
   `"markup"`이면 `{fg}` 플레이스홀더 포함 inner SVG.
2. `docs/assets/provider-claude.svg` — 같은 아트로 교체(`fill="#d97757"` 유지 또는
   `provider_claude_fg`에 맞춤).
3. `assets/PROVIDER_ICONS_NOTICE.md` — Claude 항목을 실제 출처/라이선스로 갱신.
4. `theme.py`의 `provider_claude_fg`(다크 `#D97757` / 라이트 `#A8431C`)는 그대로 두거나
   공식 마크 색에 맞춤. 라이트는 `#F3E3DE` 배경 대비 3:1 이상 유지.

그 외 코드 변경 불필요.

---

## 프로젝트 컨텍스트 (참고)

- **SynapCap**: PySide6(Qt6) Windows/macOS 데스크톱 위젯. Codex/Gemini/Claude 구독 사용량(%).
  API 키 없음 — 각 CLI가 로컬에 남긴 값을 읽는다.
- **표시 모드 3단계** (`settings["window_mode"]`):
  - `expanded` — 384px 고정. 프로바이더 탭 + 선택 카드에 `5h`(SESSION)/`7d`(WEEKLY) 대형 듀얼 링.
  - `bar` — 컴팩트 막대. `아이콘 + 5h / 7d 값` 평면 그룹. `availableGeometry()` 도킹.
  - `none` — 떠 있는 창 없음. 트레이 아이콘만.
  - 트레이 아이콘은 항상 최고 사용률 숫자 + 4단계 색 칩(`create_usage_tray_icon`), 툴팁에 내역.
- 핵심 파일:
  - `theme.py` — 색 토큰 단일 출처. `DARK`/`LIGHT`(키 집합 동일). `test_theme.py`가 정합 검사.
  - `ui/widget.py` — 위젯 본체. `UsageRing`(유일 그래프), `FocusProviderButton`(탭).
    렌더 `_render_focus_ring_rows`(기본) / `_render_usage_rows`(세로 폴백, 현재 미사용).
    `apply_theme()` 라이브 재스타일. 표시 모드 `set_window_mode()`.
  - `ui/tray.py` — 트레이 메뉴 + `create_usage_tray_icon()` + `update_usage()` + `show_tray_pin_guidance()`.
  - `ui/settings_dialog.py` — `theme_combo`·`window_mode_combo`·provider 카드("사용" 체크박스).
  - `ui/icon.py` — 아이콘 런타임 생성. `_PROVIDER_BRANDS` + `create_provider_pixmap`(`path`/`markup`).
  - `config.py` — schema v8. `window_mode`·`last_window_mode`·`window_pos_{expanded,bar}`·
    `tray_pin_guidance_shown`·`theme`.
  - `main.py` — `apply_window_mode()`, hot-reload, `_setting_changed()`.
- 문서: `docs/DESIGN.md` (Part 1 = 단일 출처 / Part 2 backlog).

## 공통 작업 규칙

- 브랜치 `dev`만. 커밋 OK, **push/tag/배포 금지.**
- 테스트 `python -m unittest discover -s tests` (offscreen 자동). **175개 통과 유지.**
- 린트 `python -m ruff check ui/ tests/`. **기존 에러(건드리지 말 것)**:
  `test_subscription_usage.py`(FLY002), `test_updates.py`(UP012 ×3), `config.py:204/216`(blind-except).
- QSS: 리터럴 `{}` 블록 → `%(name)s` 퍼센트 스타일, **모듈 레벨 named constant**로 올려
  `_XXX_QSS % palette()`. (ruff UP031이 리터럴 `% args`만 잡음.)
- 시각 확인 `QT_QPA_PLATFORM=windows python main.py` 스크린샷.
- `CHANGELOG.md` `[Unreleased]` 갱신.

---

## 완료 이력

### 큰 재설계 (병렬 Codex 작업, `dev` 병합됨)

| 항목 | 내용 | 커밋 |
| --- | --- | --- |
| 테마 3모드 | `LIGHT` 팔레트 · `auto`/OS 감지·실시간 전환 · `theme_combo` · `apply_theme()` 라이브 재스타일 | — |
| 배경색 | 근접흑 `#050608`/`#020304` 유지 (순수 검정 X) — 오너 결정 | — |
| 뷰 재설계 | `UsageBar`/`SegmentBar`/`GraphShapePicker` 제거 → 단일 링 + 프로바이더 탭 집중 보기, 384px 고정 | `f94848e` |
| 표시 모드 3단계 | `window_mode ∈ {expanded,bar,none}` · 트레이 메뉴 · `window_mode_combo` · 모드별 위치 저장 · 트레이만→복원 | `e3daa85` |
| 작업표시줄 Z-order | `_available_geometry` → `availableGeometry()` (겹침 없음). 네이티브 topmost 재확인 코드 전부 제거. `WindowStaysOnTopHint`만 유지 | `e3daa85` |
| 트레이 숫자 | `create_usage_tray_icon` — 최고 사용률 + 4단계 색 칩, DPI 멀티사이즈 · 툴팁 내역 · `show_tray_pin_guidance`(최초 1회) | `e3daa85` |

### 외부 리뷰(Gemini·Claude 2개 모델) + backlog 반영

| # | 항목 | 커밋 |
| --- | --- | --- |
| 9-1 | 사용량 색 4단계(`USAGE_NOTICE/WARN/CRIT`=60/75/90) + `<60` 무채색 `usage_calm` | `ac0f499` |
| 9-2 | `리셋까지·사용률` 컬럼 레전드(세로 폴백) + 갱신 캡션. 집중 뷰에선 새로고침 툴팁으로 | `1adb871` |
| 9-3 | `5h`/`7d` 배지 테두리 제거 → `ink_dim` 텍스트. 아웃라인 칩은 `CLI 기준`에만 | `6deb3f3` |
| 9-4 | 라이트 경고색 `#9A5200`(오커) → `#C2410C`(번트 오렌지, AA 4.88:1) | `a913e4c` |
| 9-5 | 헤더 앱동작↔창제어 `header_control_divider` (컴팩트 바 구분선은 재설계로 제거) | `6deb3f3` |
| 9-6 | 집중 링 `SESSION/WEEKLY`·리셋 라벨 흐리게 → 링 안 `%`가 헤드라인 | `32947a8` |
| 9-7 | CLI 미설치 = 회색 `dormant` 배지 `미설치` + 카드 이름 흐리게. `로그인 필요` 등은 `error` 유지 | `4357144` |
| 9-8 | 버전 칩 업데이트 시에만 노출 + 세 프로바이더 출처(어느 CLI·조회 시각) 툴팁 일관 | `b1da61f` |

### 시안 재설계 항목

| Task | 결정 · 내용 | 커밋 |
| --- | --- | --- |
| 3 | 위험 비색 신호 — **E안**: 집중 링 타일 테두리 `<75` 1px / `75–89` 2px / `≥90` 3px severity 색 | `c53ac1d` |
| 4 | 헤더 간소화(I-10) — 설정 그래프 미리보기 + 헤더 뷰 전환 제거 (※ 이후 뷰 재설계로 흡수) | `7706456` |
| 5 | 로고 accent 통일 — **B안**: `logo_mark` = `accent` (`#89B4FA`/`#1857C9`). SVG·아이콘·`docs/` 자산 재생성 | `0904d3e` · `12898c7` |
| 6 | 프로바이더 칩 통일 — **D안**: Gemini 흰 박스 제거(테마 틴트) + Claude 격자 → 방사형 버스트(근사치) | `0098e22` |
| 7 | 홈페이지 위젯 미리보기 — 4단계 색·흐린 라벨·검정 프레임·창제어 구분선·버전 칩 제거 | `5a2c864` |
| — | 프로바이더 아이콘 notice 정정(Claude 플레이스홀더 반영) | `7101448` |
