# 추가 프로바이더 검증

검증일: 2026-10-07. 기존 Claude 수정과 별개로 수행한 읽기 전용 사용량 조회 검증이다. 아래 결과는 앱 지원 추가나 출시 완료를 의미하지 않는다.

## GitHub Copilot

- 공식 Python SDK `github-copilot-sdk==1.0.16`, SDK가 체크섬을 검증한 런타임 `1.0.90`을 사용했다.
- 2026-10-18부터 SDK 1.0.16(MIT)을 별도 `SynapCapCopilotProbe` 실행 파일로 빌드해 Windows·macOS 앱 번들에 포함한다. 소스 실행은 같은 버전의 빌드 의존성을 사용한다.
- 런타임은 첫 조회 시 공식 GitHub Release에서 내려받고 SDK가 `SHA256SUMS.txt`로 검증한다. `COPILOT_CLI_EXTRACT_DIR`은 사용자 로컬 SynapCap 데이터 폴더를 가리키며 이후 조회에서 재사용한다.
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

소스 실행 환경에서는 `requirements-build.txt`를 설치해야 한다. 설치본은 SDK 프로브를 포함하며 런타임만 첫 조회 때 자동 준비한다. Windows `dist/SynapCap` 번들의 프로브 의존성 자체 검사는 성공했지만, 깨끗한 설치본과 실제 Copilot 계정의 쿼터 대조는 아직 검증 대기다.

공식 자료:

- [계정 한도 조회](https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing)
- [Python SDK와 런타임 설치](https://github.com/github/copilot-sdk/blob/main/python/README.md)

## Cursor


표준 설치 경로에 일부 리소스는 남아 있으나 `Cursor.exe`가 없었다. 로컬 상태 DB의 Cursor 액세스 토큰은 만료돼 있었다. 토큰 값·이메일은 출력하거나 문서에 저장하지 않았다. 현재 상태로는 인증된 실제 사용량을 검증할 수 없다. 실행 가능한 앱 설치와 새 로그인이 필요하다.

## xAI API Rate Limit

- 앱의 `grok` 프로바이더 ID는 기존 설정 호환성을 위해 유지하지만 제품 표시는 `xAI API`로 사용한다.
- xAI API 키 정보 엔드포인트의 rate-limit 헤더가 있을 때만 요청 사용률을 표시한다.
- rate-limit 헤더가 없으면 `연결됨 · 구독 사용량 미지원`으로 표시하며 가상 0%·100% 한도를 만들지 않는다.
- 설정에 입력한 API 키는 로컬 설정 파일에 저장한다. 환경변수 `XAI_API_KEY`를 사용하면 설정 입력을 비워 둘 수 있다.
- 이 연동은 SuperGrok·Grok 웹 구독 잔여량을 조회하지 않는다.

## Grok Bot / Windsurf / Devin Desktop

확인한 표준 설치 경로와 관련 로컬 데이터 경로에서 검증 가능한 설치를 찾지 못했다. 다른 경로에 설치된 가능성까지 배제한 결과는 아니다. 앱·계정이 준비되기 전에는 실제 연동 성공 여부를 판단할 수 없다.

## Antigravity 모델별 한도 — 2026-10-19 추가 확인

사용자는 Antigravity 데스크톱 앱의 Pro 플랜에서 Flash·Argon 사용량을 따로 확인했다고 제보했다. 현재 PC의 CLI `1.1.12`로 기존 `/usage` 조회를 실행하면 `Gemini Models`와 `Claude and GPT models`의 5시간·주간 그룹만 반환한다. 이 응답으로 Flash·Argon의 개별 수치를 확인할 수는 없다.

초기 파서는 합성된 두 Gemini 모델 그룹을 입력하면 모델 구분 없이 `5시간` 두 행을 만들었다. 이후 `quota_group`과 기간을 분리해 보존하고, 기본 Gemini 그룹 선택에서 별도 Gemini 한도를 제외하지 않도록 수정했다. 실제 앱·CLI의 계정 일치와 모델별 한도 출처 검증은 [SC-016](TASKS.md)에서 추적한다.

이후 제공된 Google AI Pro 앱 화면에서 `Gemini Models`의 5시간·주간 잔여량과 `Gemini 4 Argon`의 별도 주간 한도를 확인했다. 일반 Gemini 그룹이 Flash 전용인지는 확인되지 않았다. 합성 응답으로 기본 필터의 Argon 누락을 재현하고 수정했다. 수정본은 `Remaining` 또는 `Used`가 명시된 CLI 행만 변환한다. Argon이 없거나 `Weekly Limit`처럼 값의 의미가 불명확하면 숫자를 추정하지 않고 `Argon 조회 미지원`을 툴팁에 표시한다.

그룹·기간을 카드·툴팁·알림에 보존하고, 다중 그룹의 탭·막대는 합계가 아닌 최대 사용률을 요약한다. 세 한도 라이트·다크 렌더링과 합성 응답 회귀 검증을 수행했으며 전체 테스트 268개가 통과했다. 실제 Argon 응답 필드·잔여/사용률 의미·앱과 CLI 계정 일치는 미검증이므로 SC-016 상태는 `확인 필요`다. 이번 구현은 실제 Argon 조회 성공이나 배포 완료를 뜻하지 않는다.
