<p align="center">
  <img src="docs/assets/logo.svg" width="88" alt="SynapCap logo">
</p>

<h1 align="center">SynapCap</h1>

<p align="center">
  Codex, Gemini, Claude의 구독 사용량을 한눈에 보는 가벼운 데스크톱 위젯
</p>

<p align="center">
  <a href="https://github.com/kimNarr/SynapCap/actions/workflows/ci.yml"><img src="https://github.com/kimNarr/SynapCap/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/kimNarr/SynapCap/releases/latest"><img src="https://img.shields.io/github/v/release/kimNarr/SynapCap?display_name=tag" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/kimNarr/SynapCap" alt="MIT License"></a>
</p>

SynapCap은 로컬에 로그인된 AI 도구의 구독 한도와 리셋 시각을 표시합니다. 개발자 API의 과금액을 계산하는 앱이 아니며 API 키도 요구하지 않습니다.

## 주요 기능

- Codex, Gemini, Claude 사용량을 동일한 `사용량 %` 기준으로 표시
- 서비스가 제공하는 5시간 한도와 주간 한도를 각각 표시
- 막대형·링형 그래프 전환
- 리셋까지 남은 시간과 정확한 리셋 시각 제공
- 항상 위에 고정, 크기·너비·갱신 주기·사용량 글꼴 굵기 설정
- 시스템 트레이에서 표시, 새로고침, 설정, 종료
- 새 GitHub Release가 있으면 트레이에서 업데이트 안내
- Windows CLI 콘솔 숨김 및 시간 초과 프로세스 정리

## 다운로드

- [SynapCap 다운로드 페이지](https://kimNarr.github.io/SynapCap/)
- [최신 GitHub Release](https://github.com/kimNarr/SynapCap/releases/latest)

| 운영체제 | 설치 파일 |
| --- | --- |
| Windows 10/11 64비트 | `SynapCap-Windows-x64-Setup.exe` |
| macOS Apple Silicon | `SynapCap-macOS-arm64.dmg` |
| macOS Intel | `SynapCap-macOS-x64.dmg` |

초기 버전은 코드 서명 전이므로 Windows SmartScreen 또는 macOS Gatekeeper 경고가 표시될 수 있습니다. 설치 파일과 함께 제공되는 `SHA256SUMS.txt`로 파일 무결성을 확인할 수 있습니다.

## 연동 조건

SynapCap은 웹 채팅 페이지를 읽지 않습니다. 각 서비스의 로컬 도구가 설치되고 같은 사용자 계정으로 로그인돼 있어야 합니다.

| 표시 이름 | 필요한 로컬 도구 | 조회 방식 |
| --- | --- | --- |
| Codex | Codex CLI, 또는 Windows Codex 앱 | Codex App Server의 구독 rate limit |
| Gemini | Antigravity CLI (`agy`) | `agy --print /usage` |
| Claude | Claude Code CLI (`claude`) | `claude -p /usage` |

웹 ChatGPT, Gemini, Claude만 사용하는 계정은 대상이 아닙니다. SynapCap이 사용량 조회를 위해 별도의 유료 API를 호출하지는 않지만, 각 서비스의 구독 정책과 로컬 CLI 동작은 해당 서비스에 따릅니다.

## 사용 방법

1. 필요한 로컬 AI 도구를 설치하고 로그인합니다.
2. SynapCap을 실행합니다.
3. 위젯의 새로고침 버튼으로 즉시 조회하거나 자동 갱신을 기다립니다.
4. 톱니바퀴 버튼에서 프로바이더, 갱신 주기, 크기, 사용량 글꼴 굵기와 업데이트 확인 여부를 설정합니다.
5. 닫기 버튼은 위젯만 숨기며 프로그램은 트레이에서 계속 실행됩니다. 완전 종료는 전원 버튼이나 트레이 메뉴를 사용합니다.

초록 점은 최신 데이터를 정상 조회했다는 의미입니다. 조회 오류에 마우스를 올리면 CLI 미설치, 로그인 필요, 시간 초과 등의 원인을 볼 수 있습니다.

## 데이터와 개인정보

- API 키를 입력하거나 SynapCap 서버로 전송하지 않습니다.
- 구독 사용량은 설치된 로컬 CLI 프로세스에서 읽습니다.
- 설정은 사용자 컴퓨터에만 저장됩니다.
- 업데이트 확인은 시작 시 GitHub의 최신 Release 정보만 조회하며 설정에서 끌 수 있습니다.
- SynapCap은 사용자의 MCP 설정을 삭제하거나 일괄 비활성화하지 않습니다.

Windows에서 일반 CLI 콘솔은 숨김 처리합니다. Serena MCP의 웹 대시보드와 GUI 로그 창은 별도로 차단하지만, 사용자가 추가한 다른 MCP가 독립 브라우저나 GUI를 여는 경우에는 해당 MCP 설정을 확인해야 합니다.

## 소스에서 실행

Python 3.12를 권장합니다.

```bash
git clone https://github.com/kimNarr/SynapCap.git
cd SynapCap
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## 설정 파일

설정 파일 위치는 설치 방식에 따라 달라집니다.

| 환경 | 위치 |
| --- | --- |
| Windows 설치본 | `%APPDATA%\SynapCap\synapcap.json` |
| macOS 설치본 | `~/Library/Application Support/SynapCap/synapcap.json` |
| 소스 실행 | 저장소 루트의 `synapcap.json` |

전체 형식은 [synapcap.example.json](synapcap.example.json)을 참고하세요. 실제 설정 파일은 토큰이나 로컬 정보가 섞일 가능성에 대비해 Git에서 제외됩니다.

## 개발과 테스트

```bash
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python scripts/manage_version.py current
```

Windows 실행 번들:

```powershell
.\scripts\build_windows.ps1 -Version 0.1.0 -SkipInstaller
```

저장소의 주요 구성은 다음과 같습니다.

```text
SynapCap/
├─ main.py                 # 앱 시작과 구성 연결
├─ subscription_usage.py   # 로컬 CLI 사용량 어댑터
├─ providers.py            # 프로바이더와 사용량 모델
├─ ui/                     # 위젯, 설정, 트레이, 아이콘
├─ workers/                # 백그라운드 갱신 스레드
├─ scripts/                # 빌드와 버전 관리
├─ packaging/              # 운영체제별 설치 패키지 정의
├─ docs/                   # 다운로드 페이지와 릴리스 문서
└─ tests/                  # 단위·UI 테스트
```

## 패치와 릴리스

버전은 `MAJOR.MINOR.PATCH`로 관리합니다. 오류 수정은 `0.1.0 → 0.1.1`처럼 패치 버전을 올립니다.

```bash
python scripts/manage_version.py bump patch
python scripts/manage_version.py check v0.1.1
```

`v*` 태그가 푸시되면 GitHub Actions가 앱 버전과 태그를 검증하고 Windows 설치 파일, 두 종류의 macOS DMG, 체크섬과 CHANGELOG 기반 릴리스 노트를 게시합니다. 자세한 절차는 [릴리스와 패치 관리 문서](docs/RELEASING.md)를 참고하세요.

의존성 업데이트는 Dependabot이 월별 PR로 제안하며 `dev`와 `main`의 변경은 Windows·Linux 테스트를 거칩니다.

## 기여와 보안

- [기여 가이드](CONTRIBUTING.md)
- [변경 기록](CHANGELOG.md)
- [보안 정책](SECURITY.md)

## 라이선스

[MIT License](LICENSE) © 2026 kimNarr
