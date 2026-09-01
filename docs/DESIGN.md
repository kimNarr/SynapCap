# SynapCap 디자인 가이드 & UI 개선 backlog

이 문서는 두 부분이다.

- **Part 1 — 디자인 언어**: 색·타이포·컴포넌트 규칙의 단일 출처(reference).
- **Part 2 — 개선 backlog**: 다른 세션에서 바로 구현할 수 있도록 정리한 작업 목록.

값의 원본은 코드다. 구현 전 `ui/widget.py`, `ui/icon.py`, `ui/settings_dialog.py`, `config.py`의
현재 상태를 확인할 것. 이 문서는 `v0.1.17` + 진행 중인 `dev` 작업 기준이며, 수치가
조금 달라졌을 수 있다.

관련 시각 자료 (Artifact): `SynapCap 디자인 가이드`(이 문서의 HTML판),
`SynapCap UI 시안`(로고·테마·통합 뷰 재설계 목업).

---

## Part 1 — 디자인 언어

### 원칙

1. **한눈에** — 2초 안에 "얼마나 썼는지" 읽혀야 한다. 큰 숫자, 의미 있는 색, 한 줄 한 지표.
2. **방해하지 않기** — 트레이 전용. 작업표시줄·Alt+Tab·Dock 미표시. 항상 작고, 데이터 변경 시 조용히 갱신.
3. **정직하게** — CLI가 준 값 그대로. 보정·추정 없음. 조회 시각과 `CLI 기준` 배지로 출처를 밝힌다.
4. **로컬·프라이빗** — API 키 없음. 진단 보고서에 토큰 미포함. 설정은 로컬에만.
5. **두 OS 한 얼굴** — Windows·macOS가 같은 타이틀바·체크박스·여백. 네이티브 컨트롤 대신 `QPainter`로 직접 그림.
6. **설정을 따른다** — 글꼴 크기(또는 `widget_scale`) 하나가 제목·이름·수치·막대 높이·위젯 폭을 비례로 끌고 간다.

### 브랜드 · 로고

**확정 — 컨셉 A "게이지 S"**: 속도계형 270° 아크(하단 90° 공백) 안에 스트로크 `S`.
아크의 채움 부분이 용량, 남은 부분(딤)이 여유. 채움 끝에 작은 선단 노드.
플랫, 광택·그라디언트 없음, 16px 생존. 이전 3D 시안→퍼플 그라디언트 로고는 폐기.

**마스터 자산** (제작 완료, `assets/`):

| 파일 | 용도 |
| --- | --- |
| `logo.svg` | 마크 마스터 · 어두운 바탕 |
| `logo-light.svg` | 밝은 바탕 |
| `logo-mono.svg` | 단색 (`currentColor`, track opacity 0.32) — 트레이용 |
| `logo-icon.svg` | 앱 아이콘 빌드 소스 (근접흑 라운드 타일 + 마크 78%) |
| `wordmark.svg` / `-light` / `-mono` | `Synap`(ink) + `Cap`(accent 단색). Noto Sans KR Bold 아웃라인(OFL) |
| `wordmark-lockup.svg` | 마크 + 워드마크 가로 조합 |

기하: viewBox `0 0 32 32`, 중심 `(16,16)`, 아크 반경 11 · 굵기 2.8 · 채움 66%, `S` 스트로크 굵기 2.6.
자세한 스펙·파이프라인은 [`assets/LOGO.md`](../assets/LOGO.md).

**로고 팔레트**:

| 토큰 | 값 | 위치 |
| --- | --- | --- |
| `mark-glyph` | `#EAEEF7` (라이트 `#1B1D26`) | `S` |
| `mark-fill` | `#5B8DEF` (라이트 `#3B6FD4`) | 채움 아크 · 선단 노드 |
| `mark-track` | `#363B4D` (라이트 `#D5D9E4`) | 빈 아크 |

**미결정**: 로고 accent(`#5B8DEF`)와 앱 UI accent(`#89B4FA`)의 통일 여부.
통일 시 `logo.svg`의 `#5B8DEF`를 앱 accent에 맞춘다.

**연동 완료**: `ui/icon.py`가 `logo.svg`/`logo-icon.svg`/`wordmark.svg`를 런타임 래스터라이즈,
`scripts/generate_icons.py`가 빌드 시 `synapcap.ico`/`.icns`/`.png` 생성. 홈페이지(`docs/`)와
README도 새 SVG/PNG로 교체. 기존 3D 래스터 자산 제거.
**남은 것**: 홈페이지 위젯 미리보기 목업을 현재 앱 디자인에 맞추기(별도), 로고/앱 accent 통일 결정.

### 색 (Catppuccin Mocha 기반, 배경은 더 어둡게)

| 토큰 | 값 | 용도 |
| --- | --- | --- |
| `ground` | `#050608` | 위젯 프레임 바탕 |
| `ground · compact` | `#020304` | 컴팩트 바 / 컴팩트 프레임 |
| `providers frame` | `#090A0D` | 내부 프로바이더 프레임 |
| `metric row` | `#0D0E12` | 링뷰 메트릭 행 배경 |
| `line` | `#272C38` | 기본 테두리 |
| `line · separator` | `#20242D` | 카드 사이 구분선 |
| `frame border` | `#4A5266` (compact `#596176`) | 위젯 프레임 2px 테두리 |
| `ink` | `#CDD6F4` | 본문·제목·이름·리셋 텍스트 |
| `ink-mid` | `#A6ADC8` | 보조 설명 |
| `ink-dim` | `#8087A0` | 링뷰 리셋 텍스트 |
| `compact value` | `#F8FAFC` | 컴팩트 기본 수치(경고 전) |
| `accent` | `#89B4FA` | 링크·포커스·진행막대 기본·`CLI 기준` 배지 (로고 accent는 별도 `#5B8DEF`) |
| `marker` | `#8FB6E8` on `#141A28` | `5h`/`7d` 표식 (딤, 뒤로 물러남) |

**진행 막대** (`UsageBar`, `QWidget` + `paintEvent`): 트랙 배경 `#1C2130`, 테두리 `1px #3A4152`.
`used > 0`이면 채움 폭을 `max(3px, 비율)`로 clamp, `used = 0`이면 채움 없음.
`objectName="usageBar"`, `usage_used`, `fill_width` 노출.

### 사용량 스케일 — 색이 곧 경고 단계

`_usage_color(used)` — `ui/widget.py`

| 범위 | 색 | 의미 |
| --- | --- | --- |
| `< 60` | `#89B4FA` | 여유 |
| `60–79` | `#FAB387` (peach) | 경고 |
| `>= 80` | `#F38BA8` | 위험 |

진행 막대 채움 색과 `%` 글자 색 둘 다 이 함수로 결정된다.

**컴팩트 바 예외** (`_compact_usage_color`): `< 60`이면 흰색 `#F8FAFC`, 이상이면 위 스케일.

### 상태 배지

`_set_status_badge(label, state, preset)` — `ui/widget.py`

| state | 글자 | 배경 | 쓰임 |
| --- | --- | --- | --- |
| `source` | `#89B4FA` | `#252B3F` | `CLI 기준` |
| `waiting` | `#F9E2AF` | `#323040` | `한도 정보 없음`, 조회 대기 |
| `error` | `#F38BA8` | `#3B2735` | `설치 필요` · `로그인 필요` · `시간 초과` · `조회 오류` |
| (기본) | `#A6E3A1` | `#26372F` | 정상 완료 |

배지 공통: padding `3px 7px`, radius `5`, weight `700`, size `max(9, val_size − 1)`.

### 프로바이더 칩

`ui/icon.py` — 실제로는 공식 브랜드 SVG. 색 조합:

| 프로바이더 | 글자(아이콘) | 배경 |
| --- | --- | --- |
| GPT / Codex | `#B4BEFE` | `#252B3F` |
| Gemini | `#4285F4` | `#FFFFFF` (흰 바탕 — 브랜드 star가 뜨도록) |
| Claude | `#FAB387` | `#3A2B2B` |

> Gemini 칩만 흰 바탕이다. 어두운 프로바이더 프레임(`#090A0D`) 위에서 밝게 튀는 것이 의도.
> 값 위치: `ui/icon.py` — `_PROVIDER_BRANDS`.
>
> **제안 (미적용)**: 세 칩을 "단색 글리프 + 브랜드 톤 배경"으로 통일(Gemini만 원색 유지),
> Claude 아이콘은 현재 "Claude Code" 격자 → **Anthropic 선버스트**(방사형 별, 코럴 `#D97757`)로
> 교체. 시안 `SynapCap UI 시안` 참고.

### 타이포그래피

- 폰트: Windows `Segoe UI`, macOS `-apple-system`, fallback `sans-serif`.
- 파생 스케일 (`_expanded_preset`, `ui/widget.py`) — 기준값은 `expanded_font_size`(10–18, 기본 13)
  또는 `widget_scale` 프리셋(`small`/`medium`/`large`).

| 역할 | 공식 | 13px 기준 |
| --- | --- | --- |
| 타이틀 | `font + 2` | 15 |
| 프로바이더 이름 | `font + 1` | 14 |
| 사용량 `%` | `font` | 13 |
| 배지 | `max(9, font − 1)` | 12 |
| 리셋·표식 | `max(9, font − 2)` | 11 |
| 진행 막대 높이 | `max(8, round(font × 0.72))` | 9 |

- **굵기 위계** (`_set_label_font`은 `400 / 600 / 700` 세 단계):

  | 요소 | 굵기 | 이유 |
  | --- | --- | --- |
  | 프로바이더 이름 | `700` Bold | 카드 앵커 |
  | 사용량 `%` (< 60) | `600` DemiBold | 데이터지만 조용히 |
  | 사용량 `%` (≥ 60, 경고·위험) | `700` Bold + `▲`(≥80) | 굵기 자체가 "높아지는 중" 신호 |
  | `5h` / `7d` 표식 | `400` Regular | 라벨이지 데이터 아님 |
  | 리셋 카운트다운 | `400` Regular · `#8087A0` · `val_size − 2` | 보조 정보 |

  → 볼드는 "여기 봐"(카드 이름 + 높아진 값)에만. 나머지는 차분하게.
- 수치는 항상 `tabular-nums` 의도.

### 레이아웃

| 요소 | 반경 | 테두리 |
| --- | --- | --- |
| 위젯 프레임 | 6 | 2px `#4A5266` |
| 내부 프로바이더 프레임 | 6 | 1px `#272C38` |
| 배지·표식·메트릭 행 | 5 | none |
| 진행 막대·컴팩트 바 | 4 | 1px `#3A4152` (막대) |

- 프레임 여백 `12 / 14 / 12 / 12`, 요소 간격 `10`.
- 막대 행 내부 간격 `max(7, val_size × 0.55)`.
- 위젯 폭: `min(480, max(300, provider_header_width, content_width))`
  - 막대뷰 `content_width = max(268, val_size × 16 + 52)`
  - 링뷰 `content_width = max(300, 2 × max(116, val_size × 9))`
- 엣지 스냅 거리 `EDGE_SNAP_DISTANCE = 48`.
- `dock_above_taskbar` (선택): 하단 근처에 놓으면 작업표시줄 위 park, 다른 곳에 놓으면 유지.
  `_docked_to_bottom` 플래그로 관리. park 상태에서 높이가 커지면 위로 자란다.

### 사용량 행 — 막대뷰 순서

`_render_usage_rows` bar 분기 (`ui/widget.py` ~1471)

```
[표식 20px] [리셋 텍스트] [진행 막대 · Expanding · 텍스트 없음] [% · 고정폭 우측정렬 · 스케일 색]
```

- 표식: `_usage_window_marker(label)` → `"5h"`(5시간) / `"7d"`(주간) / `"•"`. 딤 블루 필(`#8FB6E8 on #141A28`), Regular.
- 리셋: `_condensed_reset(relative)` → 현재 영어 축약 `"3h 44m"` / `"6d 22h"`. 고정폭 열(`~48px`).
- `%`: `value_label`, `objectName="usageValue"`, `setFixedWidth(max(38, val_size × 3 + 6))`
- 툴팁: 진행 막대와 `%` 둘 다 `usage_tooltip` (`"49% 사용 · 51% 남음"` [+ CLI 출처])

### 모션

- 상태 전달용으로만. 데이터 변경 시 전환 애니메이션 없음.
- 로딩: 회전 아크 스피너 (`LoadingSpinner`, `#89B4FA` / 트랙 `#2B303D`).
- 엣지 스냅·park: 즉시 이동(부드러운 보간 없음).
- 툴팁: 지연 0, 페이드 없음, 대상 바로 아래(하단이면 위).
- `prefers-reduced-motion` 존중.

### 보이스

- 한국어, 짧고 사실적. 사과·모호함 없음.
- 지표는 사용자 언어로("구독 사용량 %"), 내부 구현 용어 노출 금지.
- 오류 = 원인 + 조치. 툴팁에 "클릭하여 진단 정보 보기".
- 버튼은 결과를 말함: `적용` → `적용됨 ✓`.
- 과장 금지("실시간" X) → "CLI 기준", "마지막 조회 시각".

---

## Part 2 — 개선 backlog

우선순위: **P1** 읽기를 방해함 · **P2** 완성도 · **P3** 다듬기.

각 항목은 독립적으로 구현 가능. 하나의 PR에 P1 3개를 묶는 것을 권장.

### 공통 작업 규칙

- 브랜치: `dev`에서 작업.
- 테스트: `python -m unittest discover -s tests` (offscreen Qt). 변경 시 관련 테스트 갱신/추가.
- 린트: `python -m ruff check ui/ tests/` (CI엔 없지만 유지).
- 시각 확인: `python main.py` 실행 후 스크린샷. 실 CLI 로그인 상태면 실데이터로 렌더됨.
- `CHANGELOG.md` `[Unreleased]`에 항목 추가.

### 진행 상황 (2026-08-31 기준)

| 항목 | 상태 |
| --- | --- |
| I-01 낮은 사용률 막대 | ✅ `UsageBar` 커스텀 위젯, 최소 3px 채움 |
| I-02 행 내 위계 | ✅ 리셋을 `#8087A0` · `val_size−2` · 고정폭으로 강등 + 굵기 위계(아래) |
| I-03 색각 대비 | ✅ 경고·위험 `%`에 굵기 가중, 위험에 `▲` |
| I-04 표식 `5`/`W` | ✅ `5h` / `7d` 로 교체, Regular 굵기 + 딤 필 |
| I-05 리셋 열 정렬 | ✅ `setFixedWidth` |
| I-06 트랙 대비 | ✅ `UsageBar` 트랙 `#1C2130` / `#3A4152` |
| I-17 리셋 상태 문구 잘림 | ✅ `확인 중`·`미상`으로 축약 + 툴팁에 원문 |
| I-08 카드 여백 | ✅ `card_gap` 추가, 이름→행 축소·행 사이 확대·수직 패딩 축소 |
| I-09 경고색 대비 | ✅ 60–79 색 `#F9E2AF` → `#FAB387`(peach) |
| I-07 언어(리셋 영어) | 영어 축약 유지로 결정됨 — Part 1에 규칙 명시 |

**굵기 위계** (`_set_label_font`이 `400/600/700` 지원): 이름 `700` · 일반 `%` `600` ·
경고·위험 `%` `700`+`▲` · `5h`/`7d` 표식 `400` · 리셋 `400`.

---

### P1 — 읽기를 방해하는 문제

#### I-01 · 낮은 사용률 막대가 안 보임 — 적용됨

**현상**: `6d 22h ▏3%` 처럼 사용률이 낮으면 `QProgressBar::chunk`가 실선 한 가닥이라
"빈 막대 / 렌더 깨짐"으로 읽힌다.

**적용**: `QProgressBar` → `UsageBar`(`QWidget` + `paintEvent`)로 교체.
`used > 0`이면 채움 폭 `max(3px, 비율)`, `used = 0`이면 채움 없음.
위젯에 `objectName="usageBar"`, `usage_used`, `fill_width` 노출(테스트가 조회).
`findChild(QProgressBar)`를 쓰던 테스트 다수 갱신 완료.

---

#### I-02 · 한 행에 숫자 두 개가 경쟁 — 적용됨

**현상**: `3h 44m`(리셋까지 남은 시간)과 `16%`(사용량)이 비슷한 크기·색 무게로 나란히 있어
한눈에 무엇이 헤드라인인지 불명확하다.

**적용**: `reset_label`을 `#8087A0` · `max(9, val_size − 2)` · `00d 00h` 기준 고정폭으로 강등.
`%`는 오른쪽 고정 열에서 스케일 색 + 굵기 위계로 가장 먼저 읽히게. (아래 굵기 위계 참고)

---

#### I-03 · 경고 단계가 색으로만 구분됨 (접근성) — 적용됨

**현상**: 60/80 경계가 파랑→노랑→빨강 색 변화로만 표현된다. 색각 이상 사용자는 구분이 어렵다.

**적용**: `60–79`는 `value_label` 굵게(`700`), `>= 80`은 `▲ 88%`처럼 삼각형 프리픽스 + 굵게.
이 신호는 펼침 글꼴 굵기 설정과 무관하게 유지. `test_warning_and_critical_values_have_non_color_signals`로 고정.
남은 아이디어: 막대 채움 `>= 80` 상단 하이라이트, 세그먼트 스트라이프(시안 참고).

---

### P2 — 완성도

#### I-04 · 표식 `5` / `W` 의미 불명 — 적용됨

**적용**: `_usage_window_marker` → `"5h"`(5시간) / `"7d"`(주간) / `"•"`.
Regular 굵기, 딤 블루 필(`#8FB6E8 on #141A28`), 폭은 2글자 맞게 확장.
관련 테스트(`test_condensed_reset_drops_the_relative_suffix`, `test_bar_and_ring_views_can_be_toggled`,
`test_missing_reset_is_shown_explicitly`) 갱신 완료.

---

#### I-05 · 행 간 정렬 어긋남 — 적용됨 (단 I-17)

**적용**: `reset_label`에 `QFontMetrics(font).horizontalAdvance("00d 00h") + 4` 기준 고정폭(`~48px`),
좌측 정렬. 같은 카드 내 막대 시작선이 한 세로선에서 시작한다.
부작용: 한국어 상태 문구가 잘림 → **I-17**.

---

#### I-06 · 트랙 대비 부족 — 적용됨

**적용**: `UsageBar` 트랙 배경 `#1C2130`, 안쪽 테두리 `1px #3A4152`. 사용률 0%에서도 막대 영역이 보인다.

---

#### I-07 · 언어 혼용 (리셋만 영어) — 결정됨(B)

리셋 표기는 **영어 축약 유지**(`3h 44m` / `6d 22h`)로 결정. `_condensed_reset`이
`_reset_presentation` 출력을 `Nd Nh Nm` 형태로 변환. 링뷰·툴팁·컴팩트도 같은 규칙.
남은 것: 상태 문구 잘림 → I-17.

---

#### I-08 · 카드 여백 불균형 — 적용됨

**적용**: 프리셋에 `card_gap`(카드 사이, 4/5·5/7·7/9) 추가 → `cards_layout.setSpacing`.
`card_spacing`(이름→행)은 줄이고 `window_spacing`(행 사이)은 늘림.
카드 상/하 패딩은 `card_padding × 0.72`로 좌우와 분리(수직만 축소).
결과: 카드 내부 간격(이름→행 ~7px, 행 사이 ~9px)보다 카드 사이 간격(~29px)이
훨씬 커서 각 프로바이더가 한 덩어리로 읽힌다. 배지 높이에 따른 이름 "halo"는 유지(의도).

---

#### I-09 · 경고색 대비 약함 — 적용됨

**적용**: `_usage_color`의 60–79 색을 `#F9E2AF`(파스텔 옐로) → `#FAB387`(peach)로.
파랑 → peach → 핑크의 자연스러운 램프가 되고, 어두운 바탕에서 확실히 뜬다.
`waiting` 배지(`한도 정보 없음`)는 다른 의미(경고 아님, 정보)라 옐로 유지.
`test_usage_scale_uses_blue_peach_red`로 고정.

---

#### I-17 · 리셋 열 고정폭이 한국어 상태 문구를 자름 (I-05의 부작용) — 적용됨

**적용**: `_condensed_reset`이 상태 문구를 짧게 매핑 — `초기화 확인 중` → `확인 중`,
`리셋 시각 미상`/`""` → `미상` (`_RESET_STATUS_SHORT`). 전체 내용은 `_reset_hint`로 툴팁에 유지
(빈 값이면 `"리셋 시각을 알 수 없습니다."`). 카운트다운 표기·열 폭은 그대로.
`test_stale_reset_shows_short_label_with_full_tooltip`, `test_missing_reset_is_shown_explicitly`로 고정.

---

### P3 — 다듬기

| ID | 영역 | 문제 | 제안 | 대상 |
| --- | --- | --- | --- | --- |
| I-10 | 헤더 아이콘 | 300px 폭에 모노 아이콘 5개 + 버전 배지. 뷰 전환(원형) 아이콘 의미 불명 | 뷰 전환에 막대/도넛 미니 아이콘, 또는 `···` 오버플로로 새로고침·설정 묶기 | `ui/widget.py` 헤더, `ui/icon.py` `create_*_icon` |
| I-11 | `CLI 기준` 배지 | 파랑 채움 pill이 프로바이더 이름과 주목도 경쟁. 메타 정보인데 강함 | 아웃라인만(배경 제거, 테두리 `#252B3F`), 또는 작은 `ⓘ` 아이콘 + 툴팁으로 강등 | `_set_status_badge` `source` state |
| I-12 | 내부 프레임 테두리 | `#272C38` on `#090A0D` — 거의 안 보임 | 대비를 올려 살리거나(`#3A4152`) 아예 제거. 어중간한 상태 해소 | `frame.setStyleSheet` `QFrame#providersFrame` |
| I-13 | 로딩 스피너 | 수치 영역 전체를 스피너로 교체 → 레이아웃 순간 흔들림 | 막대 모양 스켈레톤/시머로 자리 유지 | `set_loading`, `LoadingSpinner`, `_render_usage_rows` |
| I-14 | 링뷰 `%` 크기 | 작은 링 안 `%` 텍스트가 글꼴 10px에서 읽기 힘듦 | 링 최소 크기 ↑ (`max(116, val_size × 9)` 상향), 또는 `%`를 링 옆으로 | `UsageRing`, 링뷰 `content_width` |
| I-15 | 컴팩트 바 단일 색 | `90%/20%` 전체가 한 색 → 어느 창이 위험한지 안 보임 | 위험한 쪽 값만 강조(rich text), 또는 아이콘 옆 작은 점 | `_build_compact_items` / `_refresh_compact_values`, `_compact_usage_color` |
| I-16 | 버전 배지 대비 | 업데이트 없을 때 `#7F849C on #252538` — 거의 안 보임 | 클릭 가능함을 알리려면 살짝 대비 ↑. 의도된 저강도면 유지 | `_set_version_badge_style(False)` |

---

## 권장 실행 순서

1. ~~**PR 1 (P1)**: I-01 → I-03 → I-02~~ — **완료**. `UsageBar` 기준으로 저사용률·색각 신호·
   리셋 위계를 회귀 테스트로 고정. I-04·I-05·I-06·I-07도 함께 처리됨.
2. **다음**: P3(I-10~I-16), 그리고 로고 자산 연동.
3. **큰 재설계** (시안 `SynapCap UI 시안` 참고, 오너 확인 필요):
   - 통합 타일 — 막대/링이 같은 상단 줄 공유, 그래프 줄만 교체(링 정렬 자동 해결)
   - 그래프 4종 — 막대 / 세그먼트 / 링 / 숫자만, 환경설정에서 선택
   - **테마** — 다크/라이트/자동. 선행: `theme.py` 토큰 추출(색 하드코딩 전부 이관, 시각 변화 0)
   - 배경 — 순수 검정 `#000000` vs 근접흑 `#0B0B0E`
   - 위험 표식 — `▲` vs 타일 왼쪽 severity 스트라이프
   - 헤더 간소화 — 버전 필·최소화 버튼 정리

각 PR: `CHANGELOG.md` 갱신, `python -m unittest discover -s tests` 통과, `python main.py` 스크린샷 첨부.
