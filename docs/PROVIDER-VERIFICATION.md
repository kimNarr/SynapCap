# 추가 프로바이더 검증

검증일: 2026-10-07. 기존 Claude 수정과 별개로 수행한 읽기 전용 사용량 조회 검증이다. 아래 결과는 앱 지원 추가나 출시 완료를 의미하지 않는다.

## GitHub Copilot

- 공식 Python SDK `github-copilot-sdk==1.0.16`, SDK가 체크섬을 검증한 런타임 `1.0.90`을 사용했다.
- 의존성과 런타임은 `build/provider-probe/`에 격리했다. 앱의 requirements는 변경하지 않았다.
- 기존 `gh` 로그인 두 계정을 각각 선택해 `account.getQuota`를 호출했다. 활성 계정을 전환하거나 새 로그인을 저장하지 않았다.
- 채팅 세션·모델 요청은 생성하지 않았다. GitHub 토큰은 메모리에서만 전달하고 결과에 포함하지 않았다.

| 구분 | 실제 응답 |
|---|---|
| 계정 A | 인증 성공. `chat`: 한도 200, 사용 0, 잔여 100%. `completions`: 한도 2,000, 사용 0, 잔여 100%. `premium_interactions`: 한도 0, 사용 0, 잔여 0%. |
| 계정 B | 인증 성공. `quotaSnapshots`가 빈 객체. |
| 계정 A 반복 조회 | 같은 한도와 리셋 날짜를 반환. |

결론: 실제 계정의 사용량 조회 경로가 동작한다. 유료 프리미엄 한도가 있는 계정은 검증하지 못했으므로 유료 플랜 전체 지원을 확정하지 않는다. 응답의 리셋 날짜는 서버가 반환한 값이며, 실제 UI와 대조하는 검증은 남아 있다.

앱 통합 시 조건:

- 한도 0 또는 빈 한도 목록은 `한도 없음`/`조회 가능한 한도 없음`으로 처리한다. 사용량 0%나 소진 100%로 바꾸지 않는다.
- `isUnlimitedEntitlement` 또는 한도 -1은 무제한으로 표시한다.
- 런타임이 반환하는 한도 종류를 확인한다. 모든 계정을 프리미엄 요청 기반 플랜으로 가정하지 않는다.
- 리셋 날짜가 없거나 유효하지 않거나 이미 지났으면 카운트다운을 표시하지 않는다.
- SDK 생성 코드에서 이 조회 스키마는 experimental로 표시돼 있다. SDK·런타임 버전을 함께 고정하고 변경 시 재검증한다.

재실행:

```powershell
.\.venv\Scripts\python.exe scripts/probe_copilot_usage.py --account <기존-gh-계정>
```

준비되지 않은 환경에서는 공식 SDK와 런타임을 먼저 설치해야 한다. 검증용 스크립트는 제품의 일반 실행 경로에서 호출하지 않는다.

공식 자료:

- [계정 한도 조회](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing)
- [Python SDK와 런타임 설치](https://github.com/github/copilot-sdk/blob/main/python/README.md)

## Cursor

표준 설치 경로에 일부 리소스는 남아 있으나 `Cursor.exe`가 없었다. 로컬 상태 DB의 Cursor 액세스 토큰은 만료돼 있었다. 토큰 값·이메일은 출력하거나 문서에 저장하지 않았다. 현재 상태로는 인증된 실제 사용량을 검증할 수 없다. 실행 가능한 앱 설치와 새 로그인이 필요하다.

## Grok Bot / Windsurf / Devin Desktop

확인한 표준 설치 경로와 관련 로컬 데이터 경로에서 검증 가능한 설치를 찾지 못했다. 다른 경로에 설치된 가능성까지 배제한 결과는 아니다. 앱·계정이 준비되기 전에는 실제 연동 성공 여부를 판단할 수 없다.
