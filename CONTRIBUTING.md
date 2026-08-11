# SynapCap에 기여하기

버그 제보와 개선 제안을 환영합니다. 기능 변경은 먼저 GitHub Issue에서 사용 사례를 설명해 주세요.

## 개발 환경

Python 3.12를 권장합니다.

```bash
python -m venv .venv
pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python main.py
```

## 변경 원칙

- 구독 사용량은 공식 로컬 앱 또는 CLI가 제공하는 값만 사용합니다.
- API 연결 성공 여부를 사용량처럼 표시하지 않습니다.
- 사용자 토큰, 설정 파일, CLI 출력 원문을 커밋하지 않습니다.
- Windows 자식 프로세스에는 창 숨김 처리를 유지합니다.
- 기능 변경에는 가능한 범위의 단위 테스트를 추가합니다.

## Pull Request

PR에는 변경 이유, 사용자에게 보이는 차이, 확인한 운영체제와 테스트 결과를 적어 주세요. 버전 변경과 태그 생성은 릴리스 담당자가 처리합니다.
