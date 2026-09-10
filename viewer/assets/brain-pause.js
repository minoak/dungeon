// 런처와 관전 화면이 같은 정지 사유·재시도 버튼을 보여준다. 모델 원문은 HTML로 해석하지 않는다.
export function createBrainPause() {
  const style = document.createElement('style');
  style.textContent = `
.wl-brain-pause { position:fixed; z-index:10000; right:20px; bottom:20px; box-sizing:border-box;
  width:min(440px,calc(100vw - 40px)); max-height:60vh; overflow:auto; padding:22px;
  background:#211e29; color:#f3eee7; border:1px solid #d4aa69; border-radius:12px;
  box-shadow:0 12px 45px #0009; font:14px/1.65 system-ui,sans-serif; text-align:left; overflow-wrap:anywhere; }
.wl-brain-pause[hidden] { display:none; }
.wl-brain-pause h2 { font-size:20px; margin:0 0 10px; color:#f1ca87; }
.wl-brain-pause p { margin:8px 0; white-space:pre-wrap; }
.wl-brain-pause button { background:#efd39e; color:#241d18; border:0; border-radius:6px;
  padding:10px 18px; font:inherit; font-weight:700; cursor:pointer; margin-top:8px; }
.wl-brain-pause button:disabled { opacity:.6; cursor:wait; }
.wl-brain-pause .retry-error { color:#ffb2a3; }
`;
  document.head.appendChild(style);
  const panel = document.createElement('section');
  panel.className = 'wl-brain-pause'; panel.id = 'brainPause'; panel.hidden = true;
  panel.setAttribute('role', 'alert'); panel.setAttribute('aria-labelledby', 'brainPauseTitle');
  panel.innerHTML = '<h2 id="brainPauseTitle"></h2><p data-summary></p><p data-reasons></p>'
    + '<button type="button" id="brainRetry">판단 재시도</button><p class="retry-error" role="status"></p>';
  document.body.appendChild(panel);
  const title = panel.querySelector('h2'), summary = panel.querySelector('[data-summary]');
  const reasons = panel.querySelector('[data-reasons]'), button = panel.querySelector('button');
  const error = panel.querySelector('.retry-error');
  const labels = { invalid_target: '현재 관측에 없는 대상을 선택했어요.',
    missing_target: '행동할 대상을 지정하지 못했어요.', invalid_item: '현재 소지품에 없는 물건을 선택했어요.',
    invalid_type: '처리할 수 없는 행동을 선택했어요.', missing_item: '사용할 물건을 지정하지 못했어요.',
    unexpected_item: '이 행동에 물건을 지정할 수 없어요.', unexpected_target: '이 행동의 대상 입력을 확인해야 해요.' };
  let paused = null, pendingId = null;
  const update = status => {
    const next = status?.running ? status.brain_pause : null;
    if (next?.id !== paused?.id) { error.textContent = ''; pendingId = null; }
    paused = next;
    panel.hidden = !paused;
    if (!paused) return;
    const busy = paused.retrying || pendingId === paused.id;
    title.textContent = busy ? '다시 판단하고 있어요' : '원정이 일시정지됐어요';
    summary.textContent = `${paused.turn}틱의 판단을 기다리고 있어요. 이동과 전투를 포함한 게임 시간이 멈춰 있어요.`;
    reasons.textContent = (paused.errors || []).map(e => `${e.name || e.char} · ${labels[e.input_error] || '모델의 응답을 처리하지 못했어요.'}`
      + (e.input_error === 'invalid_response' ? ` (${e.reason || '응답 오류'})` : '')).join('\n');
    button.disabled = !!busy; button.textContent = busy ? '판단 중…' : '판단 재시도';
  };
  button.onclick = async () => {
    if (!paused || button.disabled) return;
    const id = paused.id;
    pendingId = id; error.textContent = ''; update({ running: true, brain_pause: paused });
    try {
      const response = await fetch('/api/retry', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pause_id: id }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    } catch (e) {
      if (paused?.id === id) { pendingId = null; update({ running: true, brain_pause: paused }); error.textContent = e.message; }
    }
  };
  return { update };
}
