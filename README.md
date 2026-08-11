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
- 리셋까지 남은 시간을 표시하고, 마우스를 올리면 `8/12 15:09 초기화` 형식으로 정확한 시각 제공
- 항상 위에 고정, 크기·너비·갱신 주기·사용량 글꼴 굵기 설정
- 프로바이더별 5시간·주간 한도 표시 여부 설정
- 시스템 트레이에서 표시, 새로고침, 설정, 종료
- 상단 버전 배지와 새 GitHub Release 업데이트 안내
- 작업 표시줄/Dock 최소화와 종료 확인창
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

### Windows 다운로드 경고

Edge의 `일반적으로 다운로드되지 않습니다` 표시는 악성 파일 판정이 아니라 아직 코드 서명과 다운로드 평판이 없는 새 설치 파일이라는 의미입니다. 공식 GitHub Release가 아닌 곳에서 받은 파일은 실행하지 마세요.

공식 Release에서 설치 파일과 `SHA256SUMS.txt`를 받은 다음 PowerShell에서 해시를 확인할 수 있습니다.

```powershell
Get-FileHash .\SynapCap-Windows-x64-Setup.exe -Algorithm SHA256
Get-Content .\SHA256SUMS.txt
```

두 SHA-256 값이 일치하는지 확인합니다. `v0.1.4` 이상은 GitHub CLI로 빌드 출처도 검증할 수 있습니다.

```powershell
gh attestation verify .\SynapCap-Windows-x64-Setup.exe -R kimNarr/SynapCap
```

출처와 해시가 모두 맞을 때만 Edge 다운로드 패널에서 파일의 `…` 메뉴를 열어 `유지` → `더 보기` → `그래도 계속`을 선택하세요. 출처나 해시가 다르면 파일을 삭제합니다. 경고 자체를 근본적으로 제거하려면 Microsoft Store 배포 또는 신원 확인을 거친 코드 서명이 필요합니다.

### macOS 첫 실행에서 차단되는 경우

현재 macOS 설치본은 Apple 개발자 서명과 공증 전이므로 처음 실행할 때 확인되지 않은 개발자 경고가 나타날 수 있습니다. 공식 GitHub Release에서 받은 파일이고 SHA-256이 일치할 때만 다음 절차를 진행하세요.

1. DMG를 열고 `SynapCap`을 **응용 프로그램** 폴더로 옮깁니다.
2. 응용 프로그램 폴더에서 `SynapCap`을 한 번 실행합니다. 보안 경고가 나오면 `확인` 또는 `완료`를 눌러 닫습니다.
3. Apple 메뉴 → **시스템 설정** → **개인정보 보호 및 보안**으로 이동해 아래쪽 **보안** 영역까지 스크롤합니다.
4. SynapCap 차단 안내 옆의 **그래도 열기**를 누르고 로그인 암호 또는 Touch ID로 승인한 다음, 다시 표시되는 창에서 **열기**를 선택합니다.

`그래도 열기` 버튼은 앱 실행을 시도한 뒤 약 1시간 동안 표시됩니다. 승인 후에는 다시 설치할 필요 없이 응용 프로그램 폴더에서 SynapCap을 열면 됩니다. 이 절차는 macOS 보안 기능 전체를 끄지 않고 SynapCap만 예외로 등록합니다. 자세한 내용은 [Apple의 공식 안내](https://support.apple.com/ko-kr/102445)를 참고하세요.

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
4. 톱니바퀴 버튼에서 프로바이더, 표시할 한도, 갱신 주기, 크기, 사용량 글꼴 굵기와 업데이트 확인 여부를 설정합니다.
5. 최소화 버튼은 위젯을 작업 표시줄 또는 Dock으로 보내며 `×` 버튼은 프로그램을 완전히 종료합니다. 트레이 메뉴에서도 표시·숨기기와 종료를 제어할 수 있습니다.

`Cx`, `G`, `Cl` 배지는 각각 Codex, Gemini, Claude를 의미합니다. 조회에 실패하면 카드에 `설치 필요`, `로그인 필요`, `시간 초과` 또는 `조회 오류`가 표시되며 마우스를 올려 상세 원인을 확인할 수 있습니다. macOS 설치본은 Finder에서 실행해도 Homebrew와 사용자 로컬 CLI 경로를 자동 탐색합니다. 사용량 막대와 리셋 정보의 툴팁은 마우스를 올리는 즉시 해당 요소 바로 아래에 표시됩니다. 리셋 툴팁은 `8/12 15:09 초기화` 형식을 사용합니다.

## 오류 해결

| 앱 표시 | 의미 | 확인 및 조치 |
| --- | --- | --- |
| `설치 필요` | 해당 로컬 CLI 실행 파일을 찾지 못함 | 아래 설치 명령을 실행하고 `--version`으로 확인한 뒤 CLI를 한 번 실행해 로그인합니다. 사용하지 않는 서비스는 설정에서 비활성화할 수 있습니다. |
| `로그인 필요` | CLI는 있지만 구독 계정 인증이 없거나 만료됨 | 터미널에서 `codex`, `agy` 또는 `claude`를 직접 실행하고 브라우저 로그인 절차를 완료합니다. Antigravity가 인증 코드를 보여 주면 복사한 뒤 `agy`가 기다리는 터미널 입력란에 붙여 넣고 Enter를 누릅니다. |
| `시간 초과` | CLI가 제한 시간 안에 응답하지 않음 | 네트워크를 확인하고 실행 중인 CLI를 종료한 뒤 SynapCap에서 다시 새로고침합니다. 반복되면 해당 CLI를 직접 실행해 표시되는 오류를 확인합니다. |
| `조회 오류` | 출력 형식 변경 등 그 밖의 오류 | 상태 배지에 마우스를 올려 상세 메시지를 확인하고 SynapCap과 CLI를 최신 버전으로 업데이트합니다. 계속되면 상세 메시지와 운영체제를 GitHub Issue에 남깁니다. |

> [!IMPORTANT]
> SynapCap은 Apple Music, 다른 앱의 데이터, 네트워크 볼륨 또는 외장 볼륨 접근 권한이 필요하지 않습니다. macOS에서 이런 권한 요청이 나타나면 **허용하지 않음**을 선택해도 됩니다. 앱을 완전히 종료한 뒤 MCP 격리 기능이 포함된 최신 버전으로 업데이트하세요.

macOS에서 세 서비스가 모두 `설치 필요`로 표시되면 터미널에서 필요한 CLI만 설치합니다. Codex 앱과 웹 채팅 로그인만으로는 macOS 사용량을 조회할 수 없습니다.

```bash
# Codex CLI
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# Antigravity CLI
curl -fsSL https://antigravity.google/cli/install.sh | bash

# Claude Code CLI
curl -fsSL https://claude.ai/install.sh | bash
```

설치 후 경로와 버전을 확인하고 각 CLI를 한 번 실행해 로그인합니다.

```bash
codex --version
agy --version
claude --version

codex
agy
claude
```

로그인을 마치면 SynapCap을 완전히 종료했다가 다시 실행하고 새로고침합니다. 로그인 후에도 Antigravity만 실패하면 macOS의 **키체인 접근** 앱에서 `Antigravity CLI` 항목의 접근 제어 목록에 `agy`가 허용되어 있는지 확인합니다. `v0.1.1` 이상은 macOS Finder에서 실행해도 Homebrew, `~/.local/bin`, npm·pnpm·Bun·Volta·asdf·nvm 경로를 자동 탐색합니다. 자세한 설치 방법은 [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), [Antigravity CLI](https://antigravity.google/docs/cli-install), [Claude Code](https://code.claude.com/docs/en/getting-started) 공식 문서를 참고하세요.

## 데이터와 개인정보

- API 키를 입력하거나 SynapCap 서버로 전송하지 않습니다.
- 구독 사용량은 설치된 로컬 CLI 프로세스에서 읽습니다.
- 설정은 사용자 컴퓨터에만 저장됩니다.
- 업데이트 확인은 시작 시 GitHub의 최신 Release 정보만 조회하며 설정에서 끌 수 있습니다. 새 버전은 상단 버전 배지, 운영체제 알림과 트레이 메뉴에 표시됩니다.
- SynapCap은 사용자의 MCP 설정을 삭제하거나 일괄 비활성화하지 않습니다. Claude 조회는 빈 MCP 구성으로, Antigravity 조회는 기존 CLI 로그인 상태를 유지하면서 MCP 실행 도구가 제외된 제한 경로와 샌드박스로 실행합니다.

Windows에서 일반 CLI 콘솔은 숨김 처리합니다. Claude는 공식 엄격 MCP 설정으로 실행하며 Antigravity는 macOS Keychain을 포함한 기존 사용자 인증을 그대로 사용합니다. macOS에서는 CLI 탐색 중 Music 같은 보호 폴더나 네트워크·외장 볼륨도 조회하지 않습니다.

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
.\scripts\build_windows.ps1 -Version 0.1.1 -SkipInstaller
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
