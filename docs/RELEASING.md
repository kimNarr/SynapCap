# 릴리스와 패치 관리

SynapCap은 `MAJOR.MINOR.PATCH` 형식으로 버전을 관리합니다.

- `PATCH`: 오류·보안 수정 (`0.1.0 → 0.1.1`)
- `MINOR`: 하위 호환 기능 추가 (`0.1.1 → 0.2.0`)
- `MAJOR`: 호환되지 않는 변경 (`0.2.0 → 1.0.0`)

## 패치 릴리스 절차

1. `CHANGELOG.md`의 `[Unreleased]` 아래에 변경 내용을 작성합니다.
2. 테스트를 실행합니다.
3. 버전을 올립니다.

```bash
python scripts/manage_version.py bump patch
python -m unittest discover -s tests -v
```

4. 변경을 `dev`에 커밋하고 `main`으로 병합합니다.
5. 병합된 커밋에 버전 태그를 생성해 푸시합니다.

```bash
git tag v0.1.1
git push origin v0.1.1
```

GitHub Actions는 태그와 `APP_VERSION`이 같은지 확인한 후 Windows 설치 파일, Apple Silicon 및 Intel macOS DMG, SHA-256 체크섬을 게시합니다. Release 설명은 해당 버전의 `CHANGELOG.md`에서 가져옵니다.

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

서명과 공증이 도입되기 전까지 앱은 새 버전을 자동 설치하지 않습니다. 사용자는 트레이의 업데이트 메뉴에서 공식 GitHub Release 페이지로 이동해 설치 파일을 받습니다.
