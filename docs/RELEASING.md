# 릴리스와 패치 관리

SynapCap은 `MAJOR.MINOR.PATCH` 형식으로 버전을 관리합니다.

- `PATCH`: 오류·보안 수정 (`0.1.0 → 0.1.1`)
- `MINOR`: 하위 호환 기능 추가 (`0.1.1 → 0.2.0`)
- `MAJOR`: 호환되지 않는 변경 (`0.2.0 → 1.0.0`)

## 패치 릴리스 절차

1. `CHANGELOG.md`의 `[Unreleased]` 아래에 변경 내용을 작성합니다.
2. 아래 수동 테스트 목록을 확인합니다.
3. 자동 테스트를 실행합니다.
4. 버전을 올립니다.

```bash
python scripts/manage_version.py bump patch
python -m unittest discover -s tests -v
```

5. 변경을 `dev`에 커밋하고 `main`으로 병합합니다.
6. 병합된 커밋에 버전 태그를 생성해 푸시합니다.

```bash
git tag v0.1.1
git push origin v0.1.1
```

GitHub Actions는 태그와 `APP_VERSION`이 같은지 확인한 후 Windows 설치 파일, Apple Silicon 및 Intel macOS DMG, SHA-256 체크섬을 게시합니다. Release 설명은 해당 버전의 `CHANGELOG.md`에서 가져옵니다.

## 배포 전 수동 테스트

- Codex, Gemini, Claude가 로그인 상태에서 사용량을 정상 조회하는지 확인
- Codex, Gemini, Claude의 5시간·주간 표시 옵션 및 둘 다 끄기 방지가 동작하는지 확인
- 384px 고정 폭의 가로 한 모델 집중 링 보기가 펼침·컴팩트 전환 후에도 유지되는지 확인
- 기간·리셋 시간에는 툴팁이 나타나지 않고, 제공자 탭·새로고침·설정 등 동작 요소의 툴팁만 대상 가까이에 표시되는지 확인
- 화면 설정 저장 시 CLI를 다시 실행하거나 `대기 중`으로 돌아가지 않는지 확인
- 최소화 후 작업 표시줄/Dock과 트레이에서 정상 복원되는지 확인
- `×`, 작업 표시줄 닫기, 트레이 종료에서 확인창의 취소·종료가 각각 동작하는지 확인
- 새 버전이 있을 때 상단 배지, 운영체제 알림과 트레이 메뉴가 표시되는지 확인
- 트레이의 업데이트 확인과 재시작이 동작하고 자동 확인이 중복 실행되지 않는지 확인
- 이전 버전에서 업데이트를 선택했을 때 다운로드 진행률, SHA-256 검증, Windows UAC·자동 재실행 또는 macOS DMG 열기가 동작하는지 확인
- 체크섬이나 Release 자산 주소가 잘못된 경우 설치를 시작하지 않고 기존 버전을 유지하는지 확인
- Windows에서 CLI 또는 MCP 콘솔 창이 순간적으로 나타나지 않는지 확인
- 프로바이더를 제거하고 저장했을 때 위젯 높이가 즉시 줄고 빈 테두리가 남지 않는지 확인
- Codex·Gemini·Claude가 모두 등록된 상태에서 Add 버튼이 비활성화되고, 하나를 제거하면 누락된 타입만 추가되는지 확인
- Release 파일의 SHA-256 체크섬과 GitHub 빌드 출처 증명이 생성되는지 확인
- 앱 재시작 후 설정과 프로바이더 순서가 유지되는지 확인

## 로컬 확인 명령

```bash
python scripts/manage_version.py current
python scripts/manage_version.py check v0.1.1
python scripts/manage_version.py notes v0.1.1
```

Windows 로컬 번들 확인:

```powershell
.\scripts\build_windows.ps1 -Version 0.1.1 -SkipInstaller
```

앱은 사용자 확인 없이 백그라운드에서 업데이트하지 않습니다. 상단 업데이트 배지나 트레이 메뉴에서 시작하면 공식 GitHub Release 자산과 `SHA256SUMS.txt`를 검증합니다. Windows는 UAC 승인 후 무인 설치하고 다시 실행하며, Apple 서명·공증 전 macOS 버전은 검증된 DMG를 열어 사용자가 응용 프로그램의 기존 앱을 교체합니다.
