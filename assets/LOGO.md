# SynapCap 로고 자산

컨셉 **A · 게이지** — 용량 게이지 아크 안에 `S`. 플랫, 광택·그라디언트 없음, 16px 생존.

기하: `viewBox 0 0 32 32`, 중심 `(16,16)`. 게이지 아크 반경 11, 굵기 2.8, 하단 90° 공백.
채움 ~66%. `S`는 스트로크(굵기 2.6, 라운드 캡). 선단 노드는 채움 끝의 작은 점.

## 파일

| 파일 | 용도 | 색 |
| --- | --- | --- |
| `logo.svg` | 마스터 · 어두운 바탕 | glyph `#EAEEF7` · fill `#5B8DEF` · track `#363B4D` |
| `logo-light.svg` | 밝은 바탕 | glyph `#1B1D26` · fill `#3B6FD4` · track `#D5D9E4` |
| `logo-mono.svg` | 단색 (트레이) | `currentColor`, track `stroke-opacity 0.32` — 부모에 `color` 지정 |
| `logo-icon.svg` | 앱 아이콘 빌드 소스 | 근접흑 라운드 타일 + 마스터 마크(78% 인셋) |

## 색 토큰

로고 accent는 `#5B8DEF`. 앱 UI accent(`#89B4FA`)와 통일 여부는 미결(→ `docs/DESIGN.md`).
통일 시 `logo.svg`의 `#5B8DEF`를 앱 accent로 맞추면 됨.

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

## 남은 것

- **홈페이지·README**: `docs/assets/logo.png`, `docs/assets/synapcap-wordmark.png`,
  `docs/index.html`의 위젯 미리보기 목업 — 아직 기존 3D 로고. SVG → PNG 래스터라이즈 후 교체 필요.
- 라이트 테마 도입 시 `create_wordmark_pixmap`이 `wordmark-light.svg`를 고르도록 분기.
- 로고/앱 accent 통일 결정.

## 워드마크

`Synap`(ink) + `Cap`(accent 단색). **Noto Sans KR Bold**를 아웃라인(패스로 변환)한 자산 —
SIL OFL이라 재배포 문제 없음. viewBox `0 0 223.8 52`, 자간 -1%.

| 파일 | 색 |
| --- | --- |
| `wordmark.svg` | Synap `#EAEEF7` · Cap `#5B8DEF` (어두운 바탕) |
| `wordmark-light.svg` | Synap `#1B1D26` · Cap `#3B6FD4` |
| `wordmark-mono.svg` | 전체 `currentColor` |
| `wordmark-lockup.svg` | 마크 + 워드마크 가로 조합 (README·홈페이지 헤더) |
