//@name wonderland-spike
//@api 3.0
//@display-name 원더랜드 스파이크
//@version 0.1.0
//@arg gemini_key string Gemini API 키 (aistudio.google.com에서 발급)
//@link https://github.com/minoak/dungeon 원더랜드

/* 원더랜드 → RisuAI 플러그인 이주의 스파이크(실측용 최소판, 2026-07-29).
   목적: 문서로 확인한 세 관문이 실물에서 여는지 — 게임이 아니라 계측기다.
     ① 컨테이너: registerButton(chat) → showContainer('fullscreen') → iframe 안 자유 렌더
     ② 두뇌 콜: //@arg 키 + nativeFetch → Gemini(brains.py _call_gemini 와 동일 형태)
     ③ 저장: getLocalPluginStorage 저장·재로드(재진입 후에도 남는가)
   전부 화면 로그에 찍는다 — 샌드박스 콘솔은 보기 어려울 수 있다. */

(async () => {
    // 관문 0: 전역 API 이름 실측(문서가 risuai/Risuai 두 표기 혼용 — 스파이크 확인 항목)
    const api = globalThis.risuai || globalThis.Risuai;
    if (!api) {
        const pre = document.createElement('pre');
        pre.textContent = '전역 API 없음: risuai/Risuai 둘 다 undefined';
        document.body.appendChild(pre);
        return;
    }
    const API_NAME = globalThis.risuai ? 'risuai' : 'Risuai';

    // ── 미니 방(하드코딩 5×5 — 엔진 아님, 렌더 확인용) ──
    const GRID = [
        '#####',
        '#...#',
        '#.@.#',
        '#..+#',
        '#####',
    ];

    // ── UI: 전부 iframe 자기 document — SafeElement 제약은 부모 DOM 얘기(문서 §3), 여기는 자유 ──
    function render() {
        document.body.innerHTML = '';
        const style = document.createElement('style');
        style.textContent = `
            body { background:#111; color:#ddd; font-family:monospace; padding:16px; }
            pre { font-size:20px; line-height:1.1; letter-spacing:2px; }
            button { font-family:monospace; font-size:14px; margin:4px 8px 4px 0;
                     padding:6px 14px; background:#333; color:#ddd;
                     border:1px solid #666; cursor:pointer; }
            button:hover { background:#444; }
            #log { white-space:pre-wrap; font-size:13px; color:#9c9;
                   border-top:1px solid #444; margin-top:12px; padding-top:8px; }
            .err { color:#e77; }
        `;
        document.head.appendChild(style);

        const h = document.createElement('div');
        h.innerHTML = `<h3>원더랜드 스파이크 — 관문 계측</h3>
            <div>전역 API = <b>${API_NAME}</b> (관문 0 통과)</div>
            <pre>${GRID.join('\n')}</pre>
            <div>@ = 두란 · + = 문 (하드코딩 — 관문 ① 렌더 확인용)</div>`;
        document.body.appendChild(h);

        const mkBtn = (label, fn) => {
            const b = document.createElement('button');
            b.textContent = label;
            b.addEventListener('click', fn);   // 자기 iframe 이벤트 — 제한 무관 확인 항목
            document.body.appendChild(b);
        };
        mkBtn('② 두뇌 콜 테스트', testBrain);
        mkBtn('③ 저장 테스트', testStorage);
        mkBtn('닫기', async () => { await api.hideContainer(); });

        const log = document.createElement('div');
        log.id = 'log';
        document.body.appendChild(log);
    }

    function log(msg, isErr) {
        const el = document.getElementById('log');
        const line = document.createElement('div');
        if (isErr) line.className = 'err';
        line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        el.appendChild(line);
    }

    // ── 관문 ②: 두뇌 콜 — brains.py _call_gemini 와 동일 형태(같은 헤더·같은 thinking 규율) ──
    async function testBrain() {
        log('② 두뇌 콜 시작…');
        let key;
        try {
            key = await api.getArgument('gemini_key');
        } catch (e) {
            log('getArgument 실패: ' + e, true);
            return;
        }
        if (!key) { log('키 없음 — 플러그인 설정에서 gemini_key 입력', true); return; }
        log(`키 확인(지문): 길이 ${key.length} · 끝 4자 ${key.slice(-4)}`);

        const body = {
            contents: [{ parts: [{ text:
                '너는 던전을 탐험하는 전사 두란이다. 5×5 방의 중앙에 서 있고 남동쪽에 문(+)이 있다. ' +
                '다음 행동을 {"type":"move","dir":"SE","say":"한 마디"} 형식의 JSON 한 줄로만 답하라.' }] }],
            generationConfig: {
                maxOutputTokens: 256,
                thinkingConfig: { thinkingLevel: 'minimal' },  // 3.x 규율(안 끄면 사고가 예산 소진)
            },
        };
        const url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent';
        // nativeFetch 우선, 실패 시 risuFetch — 두 fetch 의 차이도 이 스파이크의 확인 항목
        for (const [name, fn] of [['nativeFetch', api.nativeFetch], ['risuFetch', api.risuFetch]]) {
            if (!fn) { log(`${name}: API 없음`, true); continue; }
            try {
                const t0 = Date.now();
                const res = await fn(url, {
                    method: 'POST',
                    headers: { 'x-goog-api-key': key, 'content-type': 'application/json' },
                    body: JSON.stringify(body),
                });
                // 반환형 실측: Response 객체인가 이미 파싱된 값인가
                let obj;
                if (res && typeof res.json === 'function') obj = await res.json();
                else if (typeof res === 'string') obj = JSON.parse(res);
                else obj = res;
                const dt = ((Date.now() - t0) / 1000).toFixed(2);
                const txt = (((obj || {}).candidates || [])[0]?.content?.parts || [])
                    .map(p => p.text || '').join('').trim();
                if (txt) {
                    log(`${name} 성공 (${dt}s): ${txt}`);
                    try {
                        const m = txt.match(/\{[^]*\}/);
                        const dec = JSON.parse(m[0]);
                        log(`  → 파싱: type=${dec.type} dir=${dec.dir} say=${dec.say}`);
                    } catch (e) { log('  → JSON 파싱 실패(원문 위 참조)', true); }
                    return;   // 하나 성공하면 충분
                }
                log(`${name}: 응답은 왔으나 텍스트 없음 — ${JSON.stringify(obj).slice(0, 300)}`, true);
            } catch (e) {
                log(`${name} 실패: ${e}`, true);
            }
        }
    }

    // ── 관문 ③: 저장 — 재진입 카운터(리로드 후에도 남으면 통과) ──
    async function testStorage() {
        log('③ 저장 테스트 시작…');
        try {
            const store = await api.getLocalPluginStorage();
            const prev = (await store.getItem('spike')) || { visits: 0 };
            const next = { visits: (prev.visits || 0) + 1, last: new Date().toISOString() };
            await store.setItem('spike', next);
            const back = await store.getItem('spike');
            log(`저장 OK — 이번이 ${back.visits}번째 (직전 기록: ${prev.last || '없음'})`);
            log('  → RisuAI 재시작 후 다시 누르면 숫자가 이어져야 통과');
        } catch (e) {
            log('getLocalPluginStorage 실패: ' + e, true);
            // 폴백 실측: pluginStorage(문자열)
            try {
                await api.pluginStorage.setItem('spike_fallback', 'ok');
                log('폴백 pluginStorage 는 동작: ' + await api.pluginStorage.getItem('spike_fallback'));
            } catch (e2) { log('pluginStorage 도 실패: ' + e2, true); }
        }
    }

    // ── 관문 ①: 채팅 화면 버튼 → 풀스크린 컨테이너 ──
    try {
        await api.registerButton(
            { name: '원더랜드', location: 'chat' },
            async () => { render(); await api.showContainer('fullscreen'); });
    } catch (e) {
        // registerButton 이 없거나 시그니처가 다르면 — 설정 메뉴 폴백
        try {
            await api.registerSetting('원더랜드 스파이크',
                async () => { render(); await api.showContainer('fullscreen'); });
        } catch (e2) {
            const pre = document.createElement('pre');   // 예외 문자열=외부 텍스트 취급(textContent)
            pre.textContent = '버튼 등록 실패: ' + e + ' / ' + e2;
            document.body.appendChild(pre);
        }
    }
})();
