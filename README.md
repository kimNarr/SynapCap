# SynapCap - AI Usage HUD Widget

SynapCap은 OpenAI Codex, Google Antigravity, Anthropic Claude 등 다양한 AI 서비스의 사용량, 한도 및 쿼터를 실시간으로 추적하는 경량 크로스 플랫폼 데스크톱 HUD 위젯 및 시스템 트레이 애플리케이션입니다.

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
API 키 설정 및 프로바이더 활성화/비활성화, 갱신 주기 등을 변경할 수 있습니다.

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
      "api_key": "YOUR_API_KEY_HERE",
      "limit": 100,
      "unit": "%"
    }
  ]
}
```
