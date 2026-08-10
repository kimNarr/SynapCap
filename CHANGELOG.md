# 변경 기록

이 프로젝트는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 따르며 버전은 [Semantic Versioning](https://semver.org/lang/ko/)으로 관리합니다.

## [Unreleased]

## [0.1.0] - 2026-08-10

### 추가

- Codex, Gemini, Claude 로컬 구독 사용량 조회
- 5시간 및 주간 한도 동시 표시
- 막대형과 링형 그래프 전환
- Windows 및 macOS 설치 패키지 자동 빌드
- GitHub Pages 다운로드 페이지
- 새 GitHub Release 알림

### 변경

- 서비스별 남은 양과 사용량 표기를 `사용량 %` 기준으로 통일
- 설정 화면에서 실제 지원하는 세 프로바이더만 제공

### 수정

- Windows CLI 콘솔이 순간적으로 표시되는 문제 방지
- Serena MCP 대시보드와 GUI 로그 창 실행 방지
- CLI 시간 초과 시 하위 프로세스 정리
