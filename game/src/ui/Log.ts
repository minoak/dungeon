// 하단 로그 — 대사·지문·사건을 시간순으로(viewer/index.html buildFeedGroups/renderFeed 의 이식, 문장 사전은 text/evline.ts).
// 입력: app.playback('frame') · frame.decisions(say/to/say_kind/reason/src) · frame.events · frame.descend · run.end · app.focus.
// 산출: app.dom.log 안 <div class="grp" data-turn="N"> 묶음 — .say(발화, 제안이면 .kind, 지목이면 .to) · .rsn(속내)
//       · .ev {dim|notable|gold|combat|fb|give|dir} · 층 전이 · 마지막에 .grp.fin(결말). 초점 캐릭터가 얽힌 줄엔 .focus.
// 갱신 규율: step/play 는 그룹 하나 증분 append(창 = 최근 LOG_WINDOW 그룹), seek·새 판은 재구축, 초점 전환은 .focus 만
// 다시 칠한다(재구축 없음 — 스크롤 위치 보존). 자동 스크롤은 사용자가 맨 아래를 보고 있을 때만 붙잡는다.
import type { App } from '../app';
import type { Char } from '../stream/types';
import { endGroupHtml, groupHtml } from '../text/evline';

export const LOG_WINDOW = 90;                    // 로그에 유지할 최근 그룹 수(결말 그룹 포함)

const STYLE = `
#log .grp { border-left: 2px solid var(--line); padding: 3px 0 3px 8px; margin: 4px 0; }
#log .gt { color: var(--dim); font-size: 11px; margin-bottom: 1px; }
#log .say { margin: 2px 0; }
#log .say .bub { color: #e6e9f0; }
#log .say .kind { color: #f0c674; font-size: .85em; margin-left: 5px; border: 1px solid #b08a2e; border-radius: 3px; padding: 0 4px; }
#log .say .to { color: var(--dim); font-size: .85em; margin-left: 5px; }
#log .rsn { color: #767c89; font-size: 11.5px; margin: 1px 0 2px 10px; }
#log .ev { margin: 1px 0; color: #aab0bc; }
#log .ev.dim { color: #5b606c; font-size: 11.5px; }
#log .ev.combat { color: #e88b7d; font-weight: 600; }
#log .ev.gold { color: #e8c268; font-weight: 600; }
#log .ev.notable { color: #9ecbff; font-weight: 600; }
#log .ev.fb { color: #8a8f9c; font-style: italic; }
#log .ev.give { color: #e8c268; font-weight: 600; }
#log .ev.dir { color: #cdbdf0; font-style: italic; }
#log .grp.lvl { color: #b9a06a; font-weight: bold; border-top: 2px solid #2c303c; padding: 8px 0 8px 8px; }
#log .grp.fin { color: #e8c268; font-weight: bold; font-size: 13.5px; }
#log .grp > .focus { background: rgba(255, 209, 102, .09); box-shadow: inset 3px 0 0 var(--accent);
  margin-left: -8px; padding-left: 8px; border-radius: 0 3px 3px 0; }
`;

export function installLog(app: App): void {
  if (!document.getElementById('style-log')) {
    const st = document.createElement('style');
    st.id = 'style-log'; st.textContent = STYLE;
    document.head.appendChild(st);
  }
  const root = app.dom.log;
  root.innerHTML = '';
  // 표시만 거른다. 원본 사건·속내는 모든 기록에서 그대로 볼 수 있다.
  document.querySelectorAll<HTMLButtonElement>('[data-log-view]').forEach(button => {
    button.onclick = () => {
      const stick = atBottom();
      root.dataset.view = button.dataset.logView;
      document.querySelectorAll<HTMLButtonElement>('[data-log-view]').forEach(b => {
        const on = b === button;
        b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on));
      });
      const hint = document.querySelector('.journal-hint');
      if (hint) hint.textContent = root.dataset.view === 'story' ? '대화와 주요 사건' : '이동 · 속내 · 모든 사건';
      if (stick) scrollBottom();
    };
  });
  let lastIdx = -1;                              // 마지막으로 반영한 프레임 번호(-1 = 비어 있음)

  const atBottom = (): boolean => root.scrollTop + root.clientHeight >= root.scrollHeight - 12;
  const scrollBottom = (): void => { root.scrollTop = root.scrollHeight; };
  const showEnd = (idx: number): boolean => !!app.run?.end && idx === app.playback.last;

  /** 초점 강조만 다시 칠한다(data-c=" 1 2 " 에 초점 번호가 들어 있는 줄). */
  function remark(focus: Char | null): void {
    const key = focus ? ` ${focus} ` : null;
    for (const n of root.querySelectorAll<HTMLElement>('[data-c]')) n.classList.toggle('focus', !!key && (n.dataset.c || '').includes(key));
  }

  /** 재구축 — idx 에서 거슬러 올라가며 비지 않은 그룹을 창 크기만큼 모은다. */
  function rebuild(idx: number): void {
    const run = app.run;
    if (!run) { root.innerHTML = ''; lastIdx = -1; return; }
    const focus = app.focus.char;
    const end = showEnd(idx) ? endGroupHtml(run) : '';
    const need = LOG_WINDOW - (end ? 1 : 0);
    const parts: string[] = [];
    for (let i = idx; i >= 0 && parts.length < need; i--) {
      const h = groupHtml(run.frames[i], run, focus);
      if (h) parts.push(h);
    }
    parts.reverse();
    if (end) parts.push(end);
    root.innerHTML = parts.join('');
    lastIdx = idx;
    scrollBottom();
  }

  /** 증분 — 그룹 하나를 뒤에 붙이고 창을 넘는 앞 그룹을 떼어 낸다. */
  function append(idx: number): void {
    const run = app.run;
    if (!run) return;
    const stick = atBottom();
    root.querySelector('.grp.fin')?.remove();    // 결말은 항상 마지막
    const h = groupHtml(run.frames[idx], run, app.focus.char);
    if (h) root.insertAdjacentHTML('beforeend', h);
    if (showEnd(idx)) root.insertAdjacentHTML('beforeend', endGroupHtml(run));
    while (root.children.length > LOG_WINDOW && root.firstChild) root.removeChild(root.firstChild);
    lastIdx = idx;
    if (stick) scrollBottom();
  }

  app.playback.on('frame', ({ idx, mode }) => {
    if (mode !== 'seek' && idx === lastIdx + 1) append(idx);
    else rebuild(idx);
  });
  app.bus.on('run', () => { root.innerHTML = ''; lastIdx = -1; });
  app.focus.on('change', ({ char }) => remark(char));
  // 라이브: end 라인만 뒤늦게 붙는 경우(프레임 성장 없음) — 결말 그룹을 보이게 한다
  app.bus.on('live', on => { if (!on && lastIdx >= 0 && showEnd(lastIdx) && !root.querySelector('.grp.fin')) append(lastIdx); });
}
