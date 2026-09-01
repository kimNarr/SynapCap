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

> `assets/synapcap-logo-source.png`, `assets/synapcap-wordmark.png`(기존 3D 로고)는 교체 대상.

## 색 토큰

로고 accent는 `#5B8DEF`. 앱 UI accent(`#89B4FA`)와 통일 여부는 미결(→ `docs/DESIGN.md`).
통일 시 `logo.svg`의 `#5B8DEF`를 앱 accent로 맞추면 됨.

## 아이콘 파이프라인 (배포 시)

1. `logo-icon.svg` → `synapcap.ico`(16·24·32·48·64·128·256), `synapcap.icns`(16~1024), `synapcap.png`(512).
   - 도구: `cairosvg` / `rsvg-convert` / Inkscape CLI + `png2icns`·ImageMagick. `scripts/build_icons.py`로 묶으면 좋음.
2. `packaging/`, `SynapCap.spec`의 아이콘 경로 확인.
3. 홈페이지(`docs/assets`), README 이미지 교체.

## 앱 코드 연동

- `ui/icon.py` `create_app_pixmap` / `create_app_icon` — 지금은 `synapcap-logo-source.png`를
  크롭·스케일. `logo.svg`/`logo-mono.svg`를 `QSvgRenderer`로 래스터라이즈하도록 교체.
  트레이는 `logo-mono.svg` + 테마색.
- 16px 트레이는 스트로크가 얇으므로, 필요하면 16px 전용으로 굵기를 키운 변형을 추가.

## 워드마크

`Synap`(ink) + `Cap`(accent 단색). **Noto Sans KR Bold**를 아웃라인(패스로 변환)한 자산 —
SIL OFL이라 재배포 문제 없음. viewBox `0 0 223.8 52`, 자간 -1%.

| 파일 | 색 |
| --- | --- |
| `wordmark.svg` | Synap `#EAEEF7` · Cap `#5B8DEF` (어두운 바탕) |
| `wordmark-light.svg` | Synap `#1B1D26` · Cap `#3B6FD4` |
| `wordmark-mono.svg` | 전체 `currentColor` |
| `wordmark-lockup.svg` | 마크 + 워드마크 가로 조합 (README·홈페이지 헤더) |

- 앱 타이틀바는 Segoe UI로 라이브 렌더 중(`create_wordmark_pixmap`) — 자산은 Noto라 미세하게 다르나
  타이틀바 크기에선 구분 불가. 완전 일치를 원하면 앱에서도 `wordmark.svg`를 래스터라이즈.
- Segoe UI 아웃라인 버전이 필요하면 재생성 가능(단, Segoe UI는 Windows 번들 폰트라 아웃라인
  재배포는 EULA 회색지대 — OSS 배포엔 Noto 권장).
