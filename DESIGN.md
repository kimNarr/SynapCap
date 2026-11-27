# SynapCap 랜딩페이지 디자인 원칙

이 문서는 `docs/` 랜딩페이지를 수정할 때 따르는 디자인 기준과 기능 보존 조건이다. 사용자의 명시적인 새 요청이 없으면 이 방향을 유지한다. 확인일: 2026-11-27.

## 프로젝트 구조와 기술

랜딩페이지는 **프레임워크와 빌드 단계가 없는 정적 HTML·CSS·JavaScript**다. Vite, Next.js, React 등을 사용하지 않으며 웹 앱용 `package.json`도 없다. Node.js는 디자인 검사와 JavaScript 테스트에 사용하며, 페이지 실행에 필요한 서버 런타임은 아니다.

| 위치 | 역할 |
|---|---|
| `docs/index.html` | 랜딩페이지 진입점, 다운로드 링크·자산 식별자, 첫 화면의 테마 초기화 |
| `docs/styles.css` | 레이아웃, 컴포넌트, 반응형·접근성 스타일. `docs/tokens.css`를 가져옴 |
| `docs/tokens.css` | 색상·글꼴·모서리 토큰과 다크·라이트 테마 |
| `docs/app.js` | 최신 Release 조회, OS별 다운로드 선택, 테마·탭 전환, 명령어 복사 |
| `docs/assets/` | 기존 로고, 서비스 아이콘, 실제 위젯 캡처 |
| `.github/workflows/pages.yml` | `docs/`를 빌드 없이 GitHub Pages에 배포 |
| `tests/test_homepage.py` | CLI 설치 안내, 내부 링크·ID, 탭 연결과 복사 버튼 구조 검사 |
| `tests/homepage_interactions.test.cjs` | 탭·복사·OS 선택·Release 응답 처리의 JavaScript 회귀 검사 |
| `main.py`, `ui/`, `providers.py`, `workers/` | Python·PySide6 데스크톱 앱과 사용량 조회. 웹 프레임워크 코드가 아님 |
| `updates.py` | 데스크톱 앱 자체의 최신 버전 확인·업데이트 다운로드·검증 |
| `scripts/`, `packaging/`, `.github/workflows/` | 개발·검증·앱 패키징·CI·배포 도구 |

기존 `docs/DESIGN.md`는 데스크톱 앱의 디자인 언어와 UI 개선 기록이다. 앱의 로고·실제 UI를 참조할 때 사용하고, 랜딩페이지의 톤과 보존 조건은 이 루트 문서를 따른다.

## 제품 설명과 검증 범위

최신 제품 사실은 `docs/RELEASE-HANDOFF.md`, 미해결 사항은 `docs/TASKS.md`를 기준으로 한다. 현재 홈페이지 제품 설명 기준은 v0.4.2, 릴리스 소스는 `663e0ef`다. 이 값은 제품 이해를 위한 기록이며 홈페이지의 최신 Release 조회를 고정값으로 대체하지 않는다.

- 핵심 설명: **로컬에 로그인된 AI 도구의 구독 사용량과 리셋 시간을 작게 띄워 확인하는 데스크톱 위젯.** 주요 소개 대상은 Codex·Gemini(Antigravity)·Claude다.
- 기본 구독 조회에는 API 키가 필요 없지만 해당 로컬 도구 설치·로그인이 필요하다. 웹사이트 로그인만으로 조회되거나 API 비용·토큰 사용량을 계산하는 대시보드라고 설명하지 않는다.
- Windows 간단 보기는 서비스별 아이콘과 숫자 하나를 개별 박스 없이 한 줄로 표시한다. 숫자는 해당 서비스의 전체 구독 한도 중 **최대 사용률**이며 평균·합산·남은 비율이 아니다. 펼침 화면의 복수 수치·세션·주간 링·리셋 타이머는 유지한다.
- 막대 목업은 앱 로고 없이 모델 아이콘·사용률·펼치기 버튼으로 구성한다. Windows 트레이는 퍼센트 기호 없는 숫자 배지, Mac 메뉴바는 모델 아이콘과 사용률로 구분한다. 펼침·링 목업의 기간 표기는 SESSION / WEEKLY이며 시간 앞의 ‘리셋까지’ 문구는 화면에 표시하지 않는다.
- Gemini의 Neon·Carbon·Argon·Hydrogen 등은 하나의 Gemini 공유 한도를 사용한다. 모델별 사용량을 합산하지 않으며 별도로 반환되는 그룹·기간은 보존한다. 수치 의미와 검증 범위는 `docs/PROVIDER-VERIFICATION.md`를 따른다.
- `*`는 갱신 실패 후 마지막 정상 값이다. 오류·값 없음·무제한을 임의로 0%로 표현하지 않는다. API 요청 제한은 간단 보기·트레이 집계에서 제외하지만 기존 API 설정·상세 카드는 보존한다.
- **새 설치만 간단 보기로 시작**하며 기존 사용자의 모드·위치는 유지된다.
- Mac 미니 보기는 노치 아래에 배치하며 노치가 없거나 화면 정보를 읽지 못하면 메뉴바로 대체한다. 메뉴바는 아이콘·사용률을 표시하고 클릭하면 상세 위젯을 연다. 트레이·메뉴바만 모드는 위젯을 숨긴다.
- Mac 빌드·자동 테스트 성공과 실기기 확인을 구분한다. 노치 배치·메뉴바 가독성·클릭과 오른쪽 메뉴·Spaces·전체화면·외장 모니터·잠자기 복귀는 실기기 확인 대기다. 완벽 지원·종료 문제 완전 해결·근거 없는 Mac 최소 OS를 기재하지 않는다.
- macOS는 Apple 개발자 서명·공증 전이다. 검증된 DMG를 연 뒤 응용 프로그램 폴더에서 앱을 교체하는 단계가 남으므로 완전 자동 설치라고 설명하지 않는다.
- Grok 웹 구독 지원으로 홍보하지 않는다. 기존 선택적 xAI API 요청 제한은 구독 사용량과 구분한다. Copilot 등의 전체 플랜 지원을 검증 완료로 표현하지 않는다.
- 현재 로고만 사용한다. 새 로고 생성·이전 로고 복원은 제외한다. 다크·라이트 실제 앱 화면과 새 Windows 간단 보기를 소개하되, 캡처는 버전·촬영 출처를 확인한다. 기존 `widget-dark.png`·`widget-light.png`는 현재 로고·버전 일치를 확정하기 전 재사용하지 않는다. 현재 홈페이지는 이 두 PNG를 참조하지 않는다.
- Mac 이미지는 실제 촬영본을 우선하며 목업에는 목업임을 표시한다. 사이트 테마 전환을 앱과 자동 동기화되는 기능으로 설명하지 않는다.
- 홈페이지 작업은 `docs/`와 관련 디자인 문서·검사에 한정한다. 공유 작업 폴더의 다른 변경을 덮어쓰거나 일괄 커밋하지 않는다. `main`의 `docs/**` push는 홈페이지 자동 배포를 유발한다. 앱 코드·버전·태그·릴리스는 별도 요청 없이 변경하지 않는다.

## 디자인 규칙

- **톤:** Raycast, Linear 스타일의 정밀하고 절제된 데스크톱 유틸리티 톤을 유지한다. 명확한 정보 위계, 읽기 쉬운 숫자, 직접 조작할 수 있는 제품 미리보기를 중심으로 구성한다.
- **금지:** 균일한 `01~06` 번호 기능 카드 6개 나열, 과한 그라데이션, 둥근 배지·알약 장식 남발 등 AI 마케팅 템플릿 느낌을 만들지 않는다. 장식용 그림자·상태 점·반복 라벨로 빈 공간을 채우지 않는다.
- **보더와 여백:** 1px 헤어라인 보더, 절제된 여백, 일관된 콘텐츠 정렬을 사용한다. 헤더와 본문은 공통 최대 폭 1320px, 기본 좌우 여백 32px을 사용하며 600px 이하에서는 좌우 20px을 유지한다. 섹션마다 화면 전체 높이를 강제하거나 장식 때문에 페이지를 길게 늘리지 않는다.
- **숫자:** 사용량 퍼센트, 리셋 타이머, 비교하는 숫자 데이터에는 `font-variant-numeric: tabular-nums`를 적용한다. 터미널 명령어는 모노스페이스로 표시한다.
- **토큰과 테마:** 색상과 글꼴은 `docs/tokens.css`에서 관리한다. 다크·라이트 양쪽의 텍스트·보더·포커스 대비와 기존 로고를 유지한다.
- **현재 정보 구조:** 4칸 비대칭 벤토에서 표시 밀도 전환·로컬 우선 보안은 큰 카드로, 세션·주간 링과 리셋 타이머·SHA-256 업데이트는 작은 카드로 구성한다. 수치·상태 배지는 실제 UI처럼 표현하고 장식용 아이콘은 넣지 않는다. OS·서비스별 CLI 탭, 다운로드 아래의 기본 접힘 보안 안내 아코디언, 미설치·로그인 필요·시간 초과·조회 오류의 상태별 해결 탭을 유지한다. 기존 설치·로그인·오류 해결 정보는 삭제하지 않는다.
- **인터랙션:** 펼침·막대·트레이만 미리보기, 명령어 원클릭 복사, 키보드 탭 이동과 즉시 보이는 포커스를 보존한다. 모션 감소 설정과 JavaScript 없이도 안내를 읽을 수 있는 구조를 유지한다.

## 반드시 유지할 GitHub Release 연동

웹페이지의 최신 버전·다운로드 URL 조회는 `docs/app.js`에 있다.

| 코드 | 보존할 동작 |
|---|---|
| `repository`, `releaseBase`, `releasePage`, `assets` | `kimNarr/SynapCap` 저장소, 기본 최신 Release 경로와 플랫폼별 자산 이름 |
| `detectPlatform()` | Windows·macOS·기타 환경 구분 |
| `configurePrimaryDownload()` | 감지한 OS에 맞는 기본 다운로드와 다른 OS 선택 경로 설정. Mac은 Apple Silicon·Intel 선택을 제공 |
| `loadLatestRelease()` | GitHub API로 최신 공개 Release를 조회하고 버전·공개일·다운로드 수와 실제 자산 URL을 반영 |

조회 주소:

```text
https://api.github.com/repos/kimNarr/SynapCap/releases/latest
```

- `fetch()`와 `Accept: application/vnd.github+json` 요청, 응답 상태 확인·오류 처리를 보존한다.
- `tag_name`, `published_at`, `assets[].download_count`로 표시 정보를 구성하는 흐름을 유지한다. 버전이나 다운로드 수를 디자인용 고정값으로 대체하지 않는다.
- `assets[].name`과 `browser_download_url`을 매핑해 HTML의 `[data-asset]` 링크를 갱신하는 흐름을 반드시 유지한다.
- 자산이 없을 때 `release.html_url` 또는 기본 최신 Release 페이지로 연결하는 대체 경로를 유지한다. API 실패 시 실패 안내와 기본 다운로드 경로를 보존한다.
- `#release-status`, `#release-meta`, `#primary-download`, `#primary-download-label`, `#primary-platform`, `#alternate-download`, `[data-asset]`, `[data-platform-card]`와 관련 자산 이름을 스타일 수정 중 삭제하거나 연결 없이 바꾸지 않는다.
- 파일 하단의 초기화 순서를 보존한다. OS별 다운로드를 구성한 뒤 최신 Release 응답으로 해당 자산 URL을 갱신한다.

데스크톱 앱의 별도 조회 위치는 `updates.py`의 `LATEST_RELEASE_API`와 `check_for_update()`다. 랜딩페이지 디자인 작업으로 앱의 업데이트·체크섬 검증 경로를 변경하지 않는다.

## 반드시 유지할 다크·라이트 전환

- `docs/index.html`의 초기화 스크립트: 저장된 `localStorage["synapcap-theme"]`를 우선하고, 값이 없으면 OS 색상 설정을 읽어 첫 렌더링 전에 `html[data-theme]`를 설정한다.
- `docs/app.js`의 `configureThemeToggle()`: `#theme-toggle` 클릭으로 테마를 전환하고, 저장값·`aria-pressed`·접근성 이름·`meta[name="theme-color"]`를 갱신한다.
- `docs/tokens.css`: 기본 다크 토큰과 `html[data-theme="light"]`의 라이트 토큰을 유지한다.
- `docs/styles.css`: 테마별 로고 표시와 숫자의 `tabular-nums` 적용을 유지한다.

테마 저장 키, `data-theme` 속성, 버튼 ID를 임의로 바꾸거나 테마 전환을 외형만 있는 버튼으로 대체하지 않는다.

## 변경 후 확인

- 다크·라이트와 데스크톱·모바일에서 기존 정보, 숫자 정렬, 포커스, 탭·아코디언·복사를 확인한다.
- Release 성공·누락 자산·API 실패 처리와 OS별 다운로드 경로가 유지되는지 확인한다.
- 웹 동작 변경 시 관련 검사를 실행한다.

```text
python -m unittest tests.test_homepage
node --test tests/homepage_interactions.test.cjs
```

디자인 원칙 기록만 변경한 경우에는 문서의 경로와 함수 이름을 실제 코드와 대조하면 된다.
