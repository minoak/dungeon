# 심사용 서버 — GCP 서울 VM 배포 (2026-09-13)

챔피언십 심사(9/21~10/5) 동안 심사위원이 **자기 Gemini·Anthropic·OpenAI 호환 키(BYOK)** 로 로그인하고 플레이하는 서버.
키 지문 기반 계정·저장 캐릭터·이어가기를 제공한다. 결제 기능은 없다. 관전만 하려면 Pages(https://minoak.github.io/dungeon/)가 있다.

## 현재 배포
- 주소: https://botpicdun.duckdns.org/ (도메인은 `botpicdun`, GCP 리소스 이름은 `botpikdun`).
- 프로젝트/VM: `botpikdun`, `asia-northeast3-a`, e2-small, Ubuntu 24.04, 표준 디스크 20GB.
- 고정 IP: `34.47.94.178` (`botpikdun-ip`). 전용 VPC `botpikdun-network` / 서브넷 `botpikdun-seoul`.
- 웹 TCP 80·443만 전체 공개. SSH TCP 22는 IAP의 `35.235.240.0/20`만 허용. VM 서비스 계정 없음.
- 첫 설치 성공: Caddy 설정 검증, HTTPS 200, gzip, Secure/HttpOnly 쿠키, `.env` 404 확인.
- VM의 Python 3.12.3에서도 `verify_public.py`와 `verify_api_call_limit.py` 통과(실 API 0콜).
- 시험용 예산 통지로 실제 VM `TERMINATED` 확인 후 재시작. 앱/Caddy 자동 시작과 로컬 상태·화면 200 확인.
- 첫 실판: 진짜 Gemini 키로 27턴에 `outcome=returned`, API 전송 시도 정확히 50회. 인증 오류·서버 예외 없음(2026-09-13 14:36 UTC 확인).
- 2026-09-17: `3734b15` 배포. 로그인·다회사 모델 선택·예상 가격 표시를 공개 서버에 반영했다.
- 운영 한도는 사용자 선택에 따라 `DUNGEON_API_CALL_LIMIT=500`으로 변경했다(기존 시험 한도 50).
  **09-20: 1,200 으로 올리기로 했다**(파트너 결정). 같은 날 저녁 기본 원정의 틱 상한이 1800 이 되면서
  이 수와 나란해졌다. ⚠️다만 틱당 콜은 하나의 수가 아니다(09-20 저녁 실판: 마을 0.33 · 1층 1.07 결정/틱) —
  던전에 오래 있는 판이면 1,800틱이 약 1,780콜이라 한도 1200 이 대략 t1256 에서 먼저 닿는다.
  유닛 템플릿 `botpikdun.service` 에 적어 두었으나 **`deploy.sh` 는 유닛 파일을 갱신하지 않는다** —
  이미 도는 서버는 `sudo systemctl edit botpikdun` 으로 `[Service]` / `Environment=DUNGEON_API_CALL_LIMIT=1200`
  을 넣고 `sudo systemctl restart botpikdun`. 확인은 `systemctl show botpikdun -p Environment`.
  비용은 방문자의 키가 낸다(BYOK). 자리를 오래 쥐는 문제는 이 한도가 아니라 자동 멈춤(D91)이 막는다. 재시도·실패를 포함한 러너 프로세스별 API 전송 시도 수이며 금액 한도가 아니다. 중지 후 이어가기는 새 러너이므로 다시 집계한다.
  설정 파일: `/etc/systemd/system/botpikdun.service.d/smoke-test.conf`.
- Cloud Shell 로그: `~/botpikdun-first-install.log`, `~/botpikdun-smoke-setup.log`, `~/botpikdun-recovery.log`.
- 갱신 전후 데이터 백업: VM의 `/var/backups/botpikdun/pre-login-20260917.tgz`, `login-ready-20260917.tgz`(root 전용). 이후 생성된 계정·캐릭터는 해당 시점 백업에 포함되지 않는다. 지속 운영 시 별도 정기 백업이 필요하다.

## 접속과 로그인

1. https://botpicdun.duckdns.org/ 에 접속한다. Windows에서는 `wonderland.bat`의 `[2] ONLINE SERVER`로 바로 연다. `[1]`은 계정 없는 로컬 론처다.
2. 상단 계정 카드에서 회사를 선택하고 해당 API 키를 넣은 뒤 **이 키로 들어오기**를 누른다. 이메일/비밀번호 가입 방식이 아니다.
3. 같은 키로 다른 브라우저에서 로그인해도 같은 계정의 저장 캐릭터·기록을 읽는다. 모델 실행용 키를 바꾸는 것만으로 계정이 바뀌지는 않는다. 로그인 키를 교체할 때는 기존 계정에서 새 열쇠를 연결한다.
4. 로컬 론처의 기존 캐릭터·판 기록은 서버로 자동 업로드되지 않는다. 로컬 파일은 그대로 남는다.

배포 확인: `/healthz` 200, `/api/me` 200, `/api/presets`의 `model_ui_version=2`, `/game/` 200, `/.env`와 `/server.py` 404. 쿠키는 HTTPS에서 Secure·HttpOnly·SameSite=Lax다.

9/17 VM 검증: 운영 데이터와 분리한 `/tmp/wl-deploy-verify.FEIlCz`에서 `verify_public`, `verify_account`, `verify_resume`, `verify_model_wiring`, `verify_api_call_limit` 모두 통과(실 API 0콜). 브라우저 자동화 도구의 URL 정책으로 공개 화면 직접 조작은 차단되어, 실제 사용자 키의 로그인 확인은 별도다.

## BYOK 키의 신뢰 경계
키는 브라우저에서 HTTPS로 봇픽던 서버에 전달되고, 로그인 때 선택한 회사의 모델 목록으로 유효성을 확인하며 플레이 때 러너 환경변수로 해당 회사 호출에 사용된다.
파일·로그에 의도적으로 저장하지 않는 구조와 가짜 키 미기록 검사는 갖췄지만, 실행 중 메모리는 서버 관리자 또는 서버를 침해한 공격자가 접근할 수 있다.
첫 시험에는 별도 키를 사용하고 Gemini API 제한 및 서버 IP `34.47.94.178` 제한을 적용하는 것을 권한다.
러너당 500회 제한은 이 서버의 정상 코드에만 적용되며, 유출된 키의 외부 사용이나 키 프로젝트의 총비용을 제한하지 않는다.
키 제한 방법: https://ai.google.dev/gemini-api/docs/api-key#restricting-and-securing-your-keys

## D98 운영자 키 판 (2026-09-21 — 키 없이 한 판)
키를 비우고 출발하면 **서버의 Gemini 키**로 돈다. 조건은 서버가 정하고 화면이 그대로 말한다(`/api/presets.house`):
모델 `gemini-3.8-flash` 고정 · 한 판 최대 600틱 · 판당 모델 호출 400회 · 서버 전체 하루 10판 · 주소당 하루 2판 · **이어가기 없음**
(⚠️값 임시 — 파트너 확정 전). 하루는 한국 시간 자정에 바뀐다. 쓴 판 수는 `<BOTPIKDUN_DATA>/house_usage.json`(주소는 지문만).
최악 비용 = 하루 판 수 × 판당 호출 수 × 콜 단가. 이어가기를 막는 까닭은 이어간 판이 새 러너라 호출 한도를 0부터 다시 세기 때문이다(D96).
자기 키를 넣은 판은 옛날 그대로다(1800틱 · `DUNGEON_API_CALL_LIMIT` · 이어가기).

**⚠️켜기 전에 — 키와 5만 원 가드.** 누적 5만 원 가드(`budget-guard/`)는 **프로젝트 `botpikdun` 의 모든 서비스·크레딧 차감 전 금액**을 센다.
운영자 키를 `botpikdun` 프로젝트에서 만들면(2026-09-21 파트너가 이렇게 만들었다) 심사위원들이 쓴 Gemini 비용이 그 5만 원에 합쳐져
**심사 도중 VM 이 꺼질 수 있다.** 그래서:
1. 예산 `botpikdun-total-50000-krw` 의 **'서비스' 범위에서 Gemini(Generative Language API)만 뺀다.** 이름·금액은 그대로 둔다 —
   가드 코드(`budget-guard/main.py` `should_stop`)는 예산 이름·통화(KRW)·**예산 금액이 정확히 50000** 인지만 보므로 범위를 바꿔도 그대로 작동한다.
   ⚠️**예산 금액만 올리면 가드가 조용히 멈춘다**(`budgetAmount == 50000` 이 아니면 VM 을 끄지 않는다 — 메일만 온다). 올리려면 함수 코드도 같이.
2. Gemini 만 보는 **알림 예산**(메일만)을 따로 하나 건다. Gemini 비용의 자동 상한은 서버의 하루 판 수(D98)다.
3. 키 제한 — 콘솔 **API 및 서비스 → 사용자 인증 정보**(`https://console.cloud.google.com/apis/credentials?project=botpikdun`) → 키 이름 →
   **애플리케이션 제한사항 = IP 주소 `34.47.94.178`** · **API 제한사항 = 키 제한 → Generative Language API** → 저장(적용까지 최대 5분).
   새어 나가도 이 서버 밖에서는 못 쓴다. 한도(RPM 등)는 키가 아니라 **프로젝트 단위**라(구글 문서) 같은 프로젝트의 다른 Gemini 사용과 나눠 쓴다 —
   `botpikdun` 에는 다른 Gemini 사용처가 없다.

켜기(콘솔 SSH 창 — 키는 명령줄·셸 기록에 남기지 않는다):
```bash
sudo install -d -m 700 /etc/botpikdun
sudo install -m 600 /dev/null /etc/botpikdun/house.env
read -rsp 'Gemini key: ' K; echo
printf 'BOTPIKDUN_HOUSE_KEY=%s\n' "$K" | sudo tee /etc/botpikdun/house.env >/dev/null; unset K
printf '[Service]\nEnvironmentFile=/etc/botpikdun/house.env\n' | sudo tee /etc/systemd/system/botpikdun.service.d/house.conf >/dev/null
sudo systemctl daemon-reload && sudo systemctl restart botpikdun
sudo journalctl -u botpikdun -n 20 --no-pager | grep D98
```
마지막 줄에 `운영자 키 판(D98): 켜짐 / 모델 gemini-3.8-flash / 최대 600틱 / …` 이 보이면 켜진 것이다(키 문자열은 어디에도 찍지 않는다).
`systemctl show -p Environment` 에는 **안 보이는 게 정상**이다 — EnvironmentFile 은 파일 경로만 남긴다(그래서 이 방식을 쓴다).
값을 바꾸려면 같은 파일에 줄을 더한다: `BOTPIKDUN_HOUSE_PER_DAY=10` · `BOTPIKDUN_HOUSE_PER_IP_DAY=2` · `BOTPIKDUN_HOUSE_CALL_LIMIT=400` ·
`BOTPIKDUN_HOUSE_TURNS=600` (`sudo nano /etc/botpikdun/house.env` → 재시작). 끄기: `BOTPIKDUN_HOUSE_PER_DAY=0` 을 넣고 재시작하거나
`house.conf` 를 `house.conf.disabled` 로 바꾸고 `daemon-reload` + 재시작. 밖에서 확인:
```bash
curl -s -c /tmp/c -o /dev/null https://botpicdun.duckdns.org/launcher/
curl -s -b /tmp/c https://botpicdun.duckdns.org/api/presets | python3 -c 'import sys,json; print(json.load(sys.stdin)["house"])'
```
VM 에서 키가 통하는지(IP 제한 포함 — 모델 목록 한 번, 생성 호출·과금 없음, 키는 파일에서 읽어 명령줄에 안 남는다):
```bash
sudo bash -c 'source /etc/botpikdun/house.env; curl -s -o /dev/null -w "%{http_code}\n" -H "x-goog-api-key: $BOTPIKDUN_HOUSE_KEY" "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"'
```
`200` = 통한다 · `403` = IP 제한이 VM 주소와 안 맞거나 API 제한에 Gemini 가 빠졌다.
게이트: `verify_house.py`(실 API 0콜 — 모델 고정·틱 상한·판당 호출·하루 판 수·이어가기 거절·키 미기록).

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
3. **BYOK**: 판 시작 요청에 `key` 필수(20~1024자·공백 없음) → 선택한 회사의 키 환경변수로만 러너에 전달한다(`launcher.Runner.start`의 `extra_env`). 서버의 다른 회사 키·대체 두뇌는 비워서 물려준다. 로그·디스크·응답에 안 남긴다(게이트가 세션 폴더 전체와 서버 로그를 검사). Gemini·Anthropic·OpenAI 호환 모델을 선택할 수 있다.
4. **상한**: 서버 전체 동시 `BOTPIKDUN_MAX_RUNS`(기본 3)판 → 429 · 세션당 1판 → 409 · IP 당 시간당 시작 `BOTPIKDUN_START_PER_HOUR`(기본 12) → 429 · 메모리 세션 500 · 판당 600틱(러너 기본).
   **자리 지키기**(09-18): 판을 시작할 때도 로그인과 같은 키 생존 확인을 한다(죽은 키 400 · 회사 불통 503 — 어느 쪽도 자리를 안 준다. 확인은 IP 시간당 시작 상한 뒤라 죽은 키의 시도도 시작 횟수를 쓴다).
   판단 정지(모델 호출 실패로 게임 시간이 멈추고 재시도를 기다리는 상태)가 `BOTPIKDUN_PAUSE_LIMIT_SEC`(기본 600초 — ⚠️값 임시, 0 = 끝없이) 동안 재시도 없이 이어지면 러너가 스스로 닫는다 —
   사용자가 멈춘 것과 같은 길이라 스냅샷이 남고 론처에 '판단 정지가 오래 이어져 멈춤 · 이어가기'로 뜬다. 재시도가 또 실패하면 시간을 새로 센다. 로컬 `launcher.py` 는 제한이 없다(러너 기본 `DUNGEON_PAUSE_LIMIT_SEC=0`).
5. **계정**(D77, 09-16): 키의 지문(HMAC-SHA256, 서버 비밀 섞음)이 계정이다. `POST /api/login` 이 선택한 회사에 키 생존을 묻고(모델 목록 GET, 생성 호출 없음) 지문으로 계정을 찾거나 만든 뒤 번호표를 묶는다 — 그 뒤 그 번호표의 `state/`·`runs/`·캐릭터는 `<BOTPIKDUN_DATA>/accounts/<id>/`. 키는 저장·기록되지 않는다(지문·별명만). 열쇠 여러 개(키 교체는 로그인 상태에서 새 키 연결), 마지막 열쇠 해제 불가, 로그인 IP 시간당 `BOTPIKDUN_LOGIN_PER_HOUR`(기본 30) → 429. **서버 비밀**은 `BOTPIKDUN_SECRET` 환경변수, 없으면 `<BOTPIKDUN_DATA>/secret` 을 첫 기동 때 만든다(0600) — 이 파일이 바뀌면 지문이 전부 바뀌어 모든 계정이 고아가 되므로 데이터 폴더와 함께 백업한다. 계정 판의 도감 원장(`accounts/<id>/bestiary.json`, 저장 캐릭터만)과 원정 기록(`campaign.json`, D78)도 같은 폴더에 쌓인다.
5. `/` → 론처 화면 · `/healthz` → `{running, max_runs}` · `--host 127.0.0.1` 고정(외부에서는 Caddy 를 거쳐서만) · `.jsonl` 은 `text/plain`(Caddy 압축 매치).
6. **이어가기**(D79, 09-16): 러너가 틱마다 `state/snapshot.pkl`(+`snapshot.json`)에 판의 몸을 얼린다. `systemctl restart`·배포로 러너가 죽어도 그 번호표(계정이면 `accounts/<id>/state/`)의
   론처 타이틀에 '이어가기'가 뜨고, 같은 판을 마지막 기록에서 계속 쓴다(키는 다시 넣는다 — 저장 안 함). 엔진이 바뀌어 피클이 안 맞으면 러너가 옛 기록을 `runs/` 로 대피시키고
   새 판을 연다(`run_meta.resume_failed`). 익명 번호표는 TTL 뒤 폴더가 지워지므로 스냅샷도 함께 사라진다(계정은 남는다).

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
   첫 실판에는 systemd 서비스 환경에 `DUNGEON_API_CALL_LIMIT=50`을 넣고 재시작한다.
   `brains._http_post`가 러너 프로세스별 HTTP 전송 시도를 센다(동시 캐릭터·재시도·실패 포함, 리다이렉트는 따라가지 않음).
   한도 이후 추가 전송을 거부하고 기존 판단 보류 흐름으로 들어간다. 그 판을 중지하면 된다.
   기본값 `0`은 제한 없음. 이 배포는 시험 한도 50을 사용자 승인한 운영 한도 500으로 변경했다. 설정 변경 후에는 서비스를 재시작한다.
   검증: `python verify_api_call_limit.py`(실 API 0콜). 이 제한은 GCP 비용 가드와 별개이며 틱 수와도 다르다.

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

## 다중 접속 연습(0콜, 2026-09-17)
`python3 scripts/vm/loadtest_public.py [사용자 수=12] [초=30] [동시 판 상한=3]` — 임시 폴더·임시 포트에 공개 서버(두뇌 dummy)를 띄우고 가짜 사용자를 붙인다. 사용자마다 번호표 하나로 론처 열기 → 설정 읽기 → 판 시작 시도(상한까지만 성공, 나머지는 '자리 없음') → 실제 화면처럼 1.5초 폴링. `LT_BIGSTREAM=<판 기록 파일>` 을 주면 끝난 판의 기록을 실제 크기 사본으로 바꿔 폴링 부담을 현실에 맞춘다. 운영 서버·운영 데이터·Caddy 는 거치지 않는다.

- 개발 노트북 기준선(09-17): 12명·동시 3판 = 실패 0, 응답 중앙값 2~9ms · 40명·동시 8판·판 파일 4.8MB = 론처·시작·판 파일 요청 실패 0, 상태 조회 95%가 127ms 안(최대 529ms), 서버 40~76MB·러너 하나 34MB.
- 같은 조건에서 상태 조회 800회 중 53회 실패 — 쓰는 중인 판 파일을 읽다 난 글자 해독 오류를 상태 조회가 안 잡는다(연습의 4.8MB 통째 덮어쓰기가 과장한 수치, 실판에선 드물고 다음 폴링에 회복). 수선 예정.
- **VM(e2-small) 값은 미측정.** 노트북 값으로 VM 을 말하지 않는다 — VM 에서 같은 명령으로 잰다(psutil 이 없으면 메모리 줄만 빠진다). 메모리만 보면 동시 3판을 늘릴 여지가 있으나 CPU·압축 부담은 재 봐야 안다.
- 이 연습이 재는 것은 '여러 사람이 각자 자기 판을 돌리는' 지금 구조다. 사용자들이 한 마을에 같이 서는 구조는 아직 없다(`docs/town_plaza_2026-09-17.md` 5절).

## 아직 안 된 것
- 판 파일 폴링을 Range 요청(추가분만)으로 바꾸는 것 — 클라이언트 변경이라 뒤로. 지금은 Caddy 압축으로 버틴다.
- 500회 운영 한도로 심사용 긴 판을 검증하는 것(9/13의 짧은 첫 실판은 성공). 9/17 배포 검증에는 유료 생성 호출을 사용하지 않는다.

## D80 다회사 BYOK (2026-09-17)

화면에서 Gemini·Anthropic·OpenAI 호환 회사를 고르고 자기 키를 넣는다. 서버에 운영자 생성 키를 넣을 필요는 없다. 로그인/열쇠 연결도 회사 선택을 받는다. `BOTPIKDUN_BRAIN`은 provider를 생략한 이전 요청의 기본값이고, `dummy`는 0콜 검증 전용이다.

OpenAI 호환 서비스 목적지를 바꾸려면 `sudo systemctl edit botpikdun`의 `[Service]` 아래 `Environment="OPENAI_BASE_URL=https://openrouter.ai/api/v1"`처럼 설정하고, 진행 중인 판이 없을 때 서비스를 재시작한다. 사용자에게 목적지 회사와 사용할 모델 ID를 알린다. 이 값은 생성 호출과 로그인 모델 목록 GET 양쪽에 쓰이며 브라우저가 임의 주소로 바꿀 수 없다. `/models` 인증을 제공하지 않는 서비스는 계정 로그인에 사용할 수 없다. 인증 없는 로컬 vLLM/Ollama는 단독 로컬 론처용이다.

기본 모델은 `brain_config.py`, 문서와 한계는 `docs/model_wiring_2026-09-17.md`. 새 기본 모델로 바뀌므로 배포 전 기록을 확인한다.
