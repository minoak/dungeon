# 브라우저 사이트 안전 정책 차단 — 지원 문의 초안

작성일: 2026-09-10. 아직 전송하지 않은 지원 문의용 자료다. 커뮤니티 게시글에는 포함하지 않는다.

## 문의 내용

Windows 데스크톱 앱에서 사용자가 허용한 개인 게임 개발일지와 게임 화면 PNG 세 장을
아카라이브 AI 채팅 채널에 게시하려고 했습니다. Chrome 확장 연결은 정상적으로 감지되지만,
연결된 탭을 선택하는 단계에서 사이트 안전 정책이 작업을 차단했습니다.

해당 주소가 지원되지 않는 것인지, 오탐 또는 제품 문제인지 확인 부탁드립니다.
정책상 허용되지 않는 작업이라면 그 범위를 안내해 주세요. 보안 제한 해제나 우회 방법을 요청하는 것은 아닙니다.

## 확인한 환경

- 운영체제: Windows
- 데스크톱 앱 패키지: OpenAI.Codex, 버전 26.901.6511.0
- 브라우저: Google Chrome 153.0.8010.37, 확장 프로그램 연결
- 대상 채널: https://arca.live/b/characterai
- 오류에 나온 주소: https://arca.live/b/characterai/write
- 대화 ID: 01a085cd-0d4b-7391-8088-a71f980c113e
- 게시 자료: 개인 식별 정보를 제거한 게임 소개와 실제 플레이 화면 세 장

## 발생 과정

1. 처음에는 브라우저 도구에 앱 내부 브라우저만 표시되어 Chrome 연결을 인식하지 못했습니다.
2. Windows 컴퓨터 사용 도구로는 Chrome 창을 찾았지만, 현재 브라우저 URL을 신뢰성 있게 확인하지 못한다는 오류로 중단됐습니다.
3. 사용자가 컴퓨터 사용 설정에서 허용 상태와 정상 연결을 확인했습니다.
4. 이후 브라우저 도구의 연결 목록에 Chrome과 AI 채팅 채널 탭이 나타났습니다.
5. 그 목록에서 반환된 브라우저 ID와 탭 ID로 탭을 선택하자 다음 오류가 발생했습니다.

```text
Browser Use rejected this action due to browser security policy. Reason: The site-safety policy blocks this action; no user permission prompt or Auto-review was attempted. Browser use is not permitted on https://arca.live/b/characterai/write. The agent must not attempt to achieve the same outcome via workaround, indirect execution, raw CDP or browser commands, alternate browser surfaces, or policy circumvention. Proceed only with a materially safer alternative that does not require this blocked browser action; if none exists, stop and request user input.
```

이 차단 이후 게시, 업로드, 입력, 다른 도구를 통한 동일 작업을 시도하지 않았습니다.
허가 요청 창이나 자동 승인 검토는 실행되지 않았다고 오류에 명시돼 있습니다.
게시 성공 여부를 확인할 URL은 없으며, 에이전트가 글이나 파일을 제출한 사실도 없습니다.

## 확인을 부탁드리는 항목

- 이 주소에 적용된 사이트 안전 정책이 의도된 제한인지 확인할 수 있나요?
- 의도된 제한이 아니라면 지원되는 정상 복구 절차가 있나요?
- 추가 진단이 필요하다면 어떤 제품 로그를 제공해야 하나요?

## 공식 지원 경로

OpenAI의 [브라우저 확장 프로그램 문제 해결 안내](https://learn.chatgpt.com/ko-KR/docs/chrome-extension)는
연결 문제가 계속될 때 앱에서 `/feedback`을 실행하고 대화 ID를 포함해 지원팀에 문의하도록 안내합니다.
이 절차가 위 사이트 정책 차단의 해제를 보장하지는 않습니다.

별도 문의 경로는 [OpenAI 고객센터의 공식 연락 안내](https://help.openai.com/en/articles/6614161-how-can-i-c)에
따라 고객센터 오른쪽 아래 채팅을 여는 것이다. 처음에는 가상 상담원이 응답하며, 필요하면 지원팀으로 이어진다.
이 경로로 보내려는 내용은 위 오류 원문, 앱·브라우저 버전, 대화 ID, 대상 주소와 발생 과정이다.
사용자가 이 별도 수신자에게 문의를 보내도록 명시적으로 요청하기 전에는 전송하지 않는다.

이 문의문에는 쿠키, 비밀번호, 브라우저 프로필 이름, 개인 별칭, 전체 원정 로그를 포함하지 않았습니다.
