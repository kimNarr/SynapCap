# SynapCap 로고 자산

컨셉 **A · 게이지** — 용량 게이지 안에 `S`. 플랫, 광택·그라디언트 없음, 16px 생존.

기하: `viewBox 0 0 32 32`, 중심 `(16,16)`. 게이지 트랙은 **닫힌 원**(반경 11, 굵기 2.8) —
작은 크기에서 로딩 스피너로 오인되지 않도록. 그 위에 파란 채움 아크 ~66% + 선단 노드(점).
`S`는 스트로크(굵기 3, 라운드 캡).

## 파일

| 파일 | 용도 | 색 |
| --- | --- | --- |
| `logo.svg` | 마스터 · 어두운 바탕 | glyph `#EAEEF7` · fill `#89B4FA` · track `#363B4D` |
| `logo-light.svg` | 밝은 바탕 | glyph `#1B1D26` · fill `#1857C9` · track `#AEB6C6` |
| `logo-mono.svg` | 단색 (트레이) | `currentColor`, track `stroke-opacity 0.32` — 부모에 `color` 지정 |
| `logo-icon.svg` | 앱 아이콘 빌드 소스 | 근접흑 라운드 타일 + 마스터 마크(78% 인셋) |

## 색 토큰

로고 accent = 앱 UI accent로 **통일**: `#89B4FA` (라이트 `#1857C9`). SVG 자산은 이 hex를
직접 쓰고, `theme.py`의 `logo_mark`가 같은 값이라 `ui/icon.py`의 런타임 recolor가 항상 일치한다.
`_themed_brand_asset`의 치환 키도 `b"#89B4FA"`.

## 앱 코드 연동 — 완료

`ui/icon.py`가 `_render_svg` + `QSvgRenderer`로 런타임 래스터라이즈:

| 함수 | 소스 | 쓰임 |
| --- | --- | --- |
| `create_app_pixmap(size)` | `logo.svg` | 컴팩트 바의 작은 로고(투명) |
| `create_app_icon_pixmap(size)` · `create_app_icon` | `logo-icon.svg` | 창·트레이·설치 아이콘 — 타일이 밝은/어두운 시스템 크롬 모두에서 대비 확보 |
| `create_wordmark_pixmap(w, h)` | `wordmark.svg` | 위젯 헤더·설정 타이틀바 (둘 다 어두운 바탕) |

`assets/logo.svg` · `logo-icon.svg` · `wordmark.svg` 3개를 PyInstaller 번들에 포함
(`SynapCap.spec`, `build_windows.ps1`, `build_macos.sh`). SVG 없을 때 대비한 코드 드로잉 fallback 유지.

### `synapcap.ico` / `.icns` / `.png` (gitignore)

빌드 시 `scripts/generate_icons.py`가 `create_app_icon_pixmap`으로 생성 → PyInstaller `--icon`,
Inno Setup이 사용. 두 빌드 스크립트가 PyInstaller 전에 이 스크립트를 실행하므로 로고 교체가
자동 반영됨.

## 홈페이지 · README

`docs/assets/`에 `logo.svg`·`logo-icon.svg`·`wordmark.svg` 사본, `logo.png`는
`logo.svg`의 256px 래스터(README·favicon fallback). `docs/index.html`은 favicon(SVG),
헤더·푸터 워드마크, CTA·미리보기 로고를 새 자산으로 교체. `docs/assets/synapcap-wordmark.png` 제거.

## 남은 것

- 홈페이지 위젯 미리보기 목업이 아직 구버전 UI(막대 전용·구 리셋 표기) — 앱 재설계와 함께 갱신.
- 라이트 테마 도입 시 `create_wordmark_pixmap`이 `wordmark-light.svg`를 고르도록 분기.

## 워드마크

`Synap`(ink) + `Cap`(accent 단색). **Noto Sans KR Bold**를 아웃라인(패스로 변환)한 자산 —
SIL OFL이라 재배포 문제 없음. viewBox `0 0 223.8 52`, 자간 -1%.

| 파일 | 색 |
| --- | --- |
| `wordmark.svg` | Synap `#EAEEF7` · Cap `#89B4FA` (어두운 바탕) |
| `wordmark-light.svg` | Synap `#1B1D26` · Cap `#1857C9` |
| `wordmark-mono.svg` | 전체 `currentColor` |
| `wordmark-lockup.svg` | 마크 + 워드마크 가로 조합 (README·홈페이지 헤더) |
