# SynapCap - AI Usage HUD Widget

SynapCap은 OpenAI Codex, Google Antigravity, Anthropic Claude Code의 **구독 사용량과 리셋 시각**을 추적하는 경량 데스크톱 HUD 위젯 및 시스템 트레이 애플리케이션입니다. 개발자 API 비용이 아니라 각 로컬 CLI에 로그인된 구독 한도를 표시합니다.

---

## 다운로드

- 다운로드 페이지: <https://kimNarr.github.io/SynapCap/>
- GitHub Releases: <https://github.com/kimNarr/SynapCap/releases/latest>

릴리스가 게시되면 다음 설치 파일이 제공됩니다.

- `SynapCap-Windows-x64-Setup.exe`
- `SynapCap-macOS-arm64.dmg`
- `SynapCap-macOS-x64.dmg`

초기 베타 빌드는 코드 서명 전이므로 Windows SmartScreen 또는 macOS Gatekeeper 경고가 표시될 수 있습니다.

---

## 🛠️ 가상환경 설정 및 실행 방법 (Recommended)

프로젝트 독립성과 패키지 충돌 방지를 위해 **Python 가상환경(venv)** 사용을 강력히 권장합니다.

### 1. 가상환경 생성

프로젝트 루트 디렉토리(`c:\project\SynapCap`)에서 아래 명령어를 실행합니다.

```bash
python -m venv .venv
```

### 2. 가상환경 활성화

- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  *(PowerShell 스크립트 실행 정책 오류 발생 시 `Set-ExecutionPolicy Unrestricted -Scope Process` 실행)*

- **Windows (CMD)**:
  ```cmd
  .\.venv\Scripts\activate.bat
  ```

- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### 3. 의존성 패키지 설치

가상환경이 활성화된 상태에서 `requirements.txt`에 명시된 패키지들을 설치합니다.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. SynapCap 실행

```bash
python main.py
```

---

## ⚙️ 설정 파일 (`synapcap.json`)

최초 실행 시 `synapcap.json` 설정 파일이 자동으로 로드되거나 생성됩니다.
프로바이더 활성화/비활성화, 갱신 주기 등을 변경할 수 있습니다.

구독 사용량 연동을 위해 사용하려는 서비스의 로컬 클라이언트가 설치되고 로그인되어 있어야 합니다.

- Codex: `codex` App Server의 ChatGPT 구독 한도 사용
- Gemini: `agy --print /usage` 사용
- Claude: `claude -p /usage` 사용

서비스가 제공하는 경우 5시간 한도와 주간 한도를 각각 별도 진행바로 표시합니다.
헤더의 그래프 버튼으로 막대형과 링형 보기를 전환할 수 있으며 선택은 다음 실행에도 유지됩니다. 리셋 시각은 남은 시간으로 표시하고 정확한 시각은 툴팁으로 확인할 수 있습니다.

현재 배포 버전은 Codex, Gemini, Claude의 로컬 구독 사용량만 지원하며 API 키는 필요하지 않습니다. 구현되지 않은 프로바이더는 설정 목록에 표시하지 않습니다.

Windows에서는 SynapCap이 실행하는 CLI 콘솔을 숨기고, 조회 시간 초과 시 하위 프로세스도 함께 종료합니다. Antigravity가 불러오는 Serena의 웹 대시보드와 GUI 로그 창도 별도로 비활성화합니다. 단, 사용자가 추가한 다른 MCP가 자체 브라우저나 GUI를 여는 동작은 해당 MCP 설정에 따라 달라질 수 있습니다.

```json
{
  "settings": {
    "refresh_interval_sec": 30,
    "always_on_top": true,
    "widget_width": 280,
    "theme": "dark"
  },
  "providers": [
    {
      "id": "codex",
      "name": "Codex",
      "type": "codex",
      "enabled": true,
      "source": "local_subscription",
      "cache_ttl_sec": 60,
      "limit": 100,
      "unit": "%"
    }
  ]
}
```

---

## 릴리스 만들기

`main` 브랜치의 배포할 커밋에 `v`로 시작하는 태그를 푸시하면 GitHub Actions가 테스트와 운영체제별 빌드를 실행하고 GitHub Release를 생성합니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Pages 다운로드 페이지는 `main` 브랜치의 `docs/` 변경을 자동 배포합니다. 저장소의 **Settings → Pages → Build and deployment**에서 Source를 **GitHub Actions**로 한 번 설정해야 합니다.

macOS를 경고 없이 배포하려면 Apple Developer ID 서명과 공증이 필요합니다. Windows SmartScreen 경고를 줄이려면 별도의 코드 서명 인증서가 필요합니다.
