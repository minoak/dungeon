# 심사용 서버 — GCP 서울 VM 배포 (2026-09-13 초안)

챔피언십 심사(9/21~10/5) 동안 심사위원이 **자기 Gemini 키(BYOK)** 로 한 판을 돌려 보는 서버.
제품의 접속 층(계정·결제·캐릭터 영속)이 아니다. 관전만 하려면 Pages(https://minoak.github.io/dungeon/)가 있다.

## 구성
- VM 하나(Ubuntu 24.04) · `server.py`(공개용 서버, D68 — 게이트 `verify_public`)가 127.0.0.1:8000 · Caddy 가 443 에서 HTTPS 로 받아 넘긴다.
- 리포는 `/opt/botpikdun` 에 읽기 전용으로, 세션 데이터(심사위원별 `state/`·`runs/`·파티 파일)는 `/var/lib/botpikdun/sessions/<id>/` 에.
- 키 파일(`.env`)은 서버에 두지 않는다. 키는 판 시작 요청에 실려 와 그 판의 러너 프로세스 환경변수에만 머문다.
- Docker 는 쓰지 않는다. Gemini HTTP 호출에 `requests`가 필요하며 Ubuntu의 `python3-requests` 패키지로 설치한다(pip 설치 0). Node 22 는 관전 클라이언트 빌드에만 쓴다.

| 파일 | 역할 |
|---|---|
| `setup.sh` | 첫 설치(한 번, 다시 실행해도 안전). 패키지 → 클론 → 빌드 → systemd → Caddy |
| `deploy.sh` | 갱신. 리포 최신 → 빌드 → 서비스 재시작 |
| `botpikdun.service` | systemd 템플릿(`@APP_DIR@`·`@DATA_DIR@`·`@PORT@`·`@USER@` 를 setup.sh 가 채움) |
| `Caddyfile` | Caddy 템플릿(`@DOMAIN@`·`@PORT@`) — 자동 인증서·압축·역프록시 |

## `server.py` 가 `launcher.py` 와 다른 것(D68, 구현됨 — `verify_public` 게이트가 전부 검사)
`launcher.py` 는 로컬 도구라 리포 루트 전체를 정적으로 서빙하고(`.env` 포함), 판 시작 API 에 인증이 없고, 판이 서버에 하나뿐이다. 공개용 `server.py` 는 그 위에:
1. **정적 허용 목록**: `/game/`(빌드)·`/viewer/`·`/launcher/`·`/art/` 와 자기 세션의 `/state/`·`/runs/` 만. 그 밖(.env·소스·설계 문서·남의 세션)은 404, 디렉터리 목록은 자기 `/runs/` 만, 점 파일·`.py` 는 어디서도 안 준다.
2. **세션**: 쿠키 번호표(`botpikdun_sid`, HttpOnly·SameSite=Lax·HTTPS 뒤에서 Secure) 하나에 `Ctx` 하나 — `state/`·`runs/`·`party_custom.json`·`character_presets.json` 전부 `<BOTPIKDUN_DATA>/sessions/<id>/`. 관전 클라이언트·론처 화면은 무변경(경로가 같다). 24시간 안 오면 메모리에서 내리고 판 기록 없는 폴더만 지운다.
3. **BYOK**: 판 시작 요청에 `key` 필수(20~200자·공백 없음) → 러너 `Popen` env 의 `GEMINI_API_KEY` 로만(`launcher.Runner.start` 의 `extra_env`). 서버의 다른 키·대체 두뇌는 비워서 물려준다. 로그·디스크·응답에 안 남긴다(게이트가 세션 폴더 전체와 서버 로그를 grep). 두뇌는 `gemini_api` 하나, 도감 이월 없음.
4. **상한**: 서버 전체 동시 `BOTPIKDUN_MAX_RUNS`(기본 3)판 → 429 · 세션당 1판 → 409 · IP 당 시간당 시작 `BOTPIKDUN_START_PER_HOUR`(기본 12) → 429 · 메모리 세션 500 · 판당 600틱(러너 기본).
5. `/` → 론처 화면 · `/healthz` → `{running, max_runs}` · `--host 127.0.0.1` 고정(외부에서는 Caddy 를 거쳐서만) · `.jsonl` 은 `text/plain`(Caddy 압축 매치).

로컬 확인: `BOTPIKDUN_BRAIN=dummy python server.py --port 8031` 로 띄우면 LLM 0콜로 화면·세션·키 칸을 볼 수 있다(키 칸엔 아무 20자 이상).

## 콘솔에서 할 일
1. 프로젝트 만들기 → Compute Engine API 사용 설정.
2. VM 인스턴스 만들기 — 이름 `botpikdun`, 리전 `asia-northeast3`(서울), 머신 `e2-small`(2GB), 부팅 디스크 Ubuntu 24.04 LTS · **20GB** 표준, 방화벽 "HTTP 트래픽 허용"·"HTTPS 트래픽 허용" 체크.
   - 네트워크 인터페이스 → 외부 IPv4 → **고정 IP 주소 예약**(임시 IP 는 중지/시작 때 바뀐다).
3. DuckDNS 에서 서브도메인 하나 만들고 그 고정 IP 를 넣는다.
4. 콘솔 "SSH" 버튼으로 브라우저 터미널을 열고:
   ```bash
   sudo apt-get install -y git
   git clone --depth 1 https://github.com/minoak/dungeon.git ~/src
   sudo BOTPIKDUN_DOMAIN=<서브도메인>.duckdns.org bash ~/src/scripts/vm/setup.sh
   ```
   스크립트를 먼저 읽고 싶으면 `less ~/src/scripts/vm/setup.sh`. 갱신은 `sudo bash /opt/botpikdun/scripts/vm/deploy.sh`.
5. 확인: `curl -fsS https://<도메인>/healthz` → `{"ok": true, ...}`. 화면은 `curl -fsSL -o /dev/null -w '%{http_code}\n' https://<도메인>/` → `200`.
   `/`는 `/launcher/`로 302 이동한다. `-I`(HEAD)가 아니라 실제 GET 요청과 `-L`(이동 따라가기)로 확인한다.
   인증서는 DNS 가 VM 을 가리키고 80·443 이 열린 뒤 Caddy 가 자동으로 받는다.
6. 진행 중인 판이 없는 상태에서 [비용 가드](budget-guard/README.md)의 시험 메시지를 보내 VM의 `TERMINATED` 상태를 확인한다.
   VM을 다시 켠 뒤 5번의 상태·화면 확인과 브라우저 접속을 반복한다. VM 이름은 가드 대상과 같은 `botpikdun`이어야 한다.
7. 진짜 키를 사용하는 짧은 판은 브라우저 키 칸에 직접 입력해 시험한다. 보스방 앞 프리셋 자체에는 **50콜 상한이 없다**.
   50콜 이내를 반드시 지키려면 별도의 실제 API 호출 상한을 먼저 구현·검증해야 한다(틱 수와 API 호출 수는 다름).

## 비용(서울, 대략 — 요금표 재확인 전)
| 항목 | 월 |
|---|---|
| e2-small 상시 | 약 ₩20,000 |
| 표준 디스크 20GB | 약 ₩1,200 |
| 고정 외부 IPv4(연결 중에도 과금) | 약 ₩4,000 |
| 트래픽 | 관전 폴링(1.5초마다 판 파일 전체) — 압축 뒤 심사위원 1명 20분에 약 0.4GB, GB 당 ₩160 안팎 |

상시 무료(Always Free) VM 은 미국 일부 리전의 e2-micro 뿐이라 서울 e2-small 은 유료 구성이고, 크레딧(개발자 프로그램 월 ₩13,833 × 5장 + 매달 1장)으로 상쇄한다.

## 디스크 계산
리포 워킹트리 약 260MB(art 85·runs 90) + `.git` 얕은 클론 수십 MB + `game/node_modules` 약 220MB + 빌드 + Ubuntu 약 2GB. 심사위원 판 하나 2~5MB. 10GB 도 되지만 20GB 가 편하다(월 ₩600 차이).

## 아직 안 된 것
- 판 파일 폴링을 Range 요청(추가분만)으로 바꾸는 것 — 클라이언트 변경이라 뒤로. 지금은 Caddy 압축으로 버틴다.
- 새 VM 에서 `setup.sh` 실전 검증(아직 로컬 문법 검사만). Ubuntu 24.04 의 python3 는 3.12 — 로컬(3.13)과 차이가 있는지도 그때 확인.
