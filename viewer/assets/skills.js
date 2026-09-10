// 런처와 두 관전 화면이 같은 기록을 같은 말로 보여준다. 엔진 판정은 하지 않는다.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));
const ability = key => ({ str: '힘', dex: '민첩' }[key] || key);

function amount(dice, trpg) {
  const m = /^(\d+)d(\d+)([+-]\d+)?$/.exec(dice || '');
  if (!m) return String(dice || '');
  const n = +m[1], sides = +m[2], bonus = +(m[3] || 0);
  if (!trpg) return String(Math.max(0, Math.floor(n * (sides + 1) / 2 + bonus + 0.5)));
  return `${Math.max(0, n + bonus)}–${Math.max(0, n * sides + bonus)} (${dice})`;
}

export function describeSkill(skill, trpg = true) {
  const effects = (skill.effects || []).map(e => {
    const key = e.type;
    let text = key === 'damage' ? `피해 ${amount(e.dice, trpg)}` : key === 'heal' ? `HP 회복 ${amount(e.dice, trpg)}`
      : key === 'push' ? '1칸 밀침' : '출혈 · 걸을 때 HP 감소';
    if (e.save && trpg) text += ` (${ability(e.save)}으로 저항 가능)`;
    return text;
  });
  effects.push(skill.target === 'self' ? '자신에게 사용' : `사거리 ${skill.range}칸`);
  const penalties = (skill.penalties || []).map(p => p.type === 'cooldown' ? `재사용 대기 ${p.turns}행동`
    : p.type === 'hp_cost' ? `HP ${p.value} 소모` : p.type === 'self_status' ? '사용 후 자신 둔화' : '출혈 대상만');
  if (skill.conditions?.includes('target_bleeding') && !penalties.includes('출혈 대상만')) penalties.push('출혈 대상만');
  if (skill.roll?.type !== 'none') effects.push(`${ability(skill.roll?.ability)} ${skill.roll?.type === 'save' && trpg ? '대상 저항 판정' : '명중 판정'}`);
  return { effects: effects.join(' · '), penalties: penalties.join(' · ') };
}

export function skillsHtml(alpha, bot) {
  if (!alpha?.skills || !bot?.skills) return '';
  return bot.skills.map(id => {
    const generated = bot.generated_skills?.[id];
    const skill = generated || alpha.presets?.[id];
    if (!skill) return `<article class="wl-skill"><strong>${esc(id)}</strong><p>설명이 기록되지 않은 스킬</p></article>`;
    const desc = describeSkill(skill, alpha.trpg_combat);
    const cooldown = bot.skill_cooldowns?.[id] || 0;
    const hpCost = (skill.penalties || []).find(p => p.type === 'hp_cost')?.value || 0;
    // '준비됨'은 비용·대기 기준이다. 실제 표적의 거리·시야·조건은 실행할 때 판정한다.
    const state = bot.alive === false ? '전사' : bot.won ? '이동 완료' : cooldown > 0 ? `${cooldown}행동 후 재사용`
      : hpCost && bot.hp <= hpCost ? 'HP 부족' : '준비됨';
    return `<article class="wl-skill${cooldown ? ' cooling' : ''}" data-skill="${esc(id)}">` +
      `<div class="wl-skill-head"><strong>${esc(skill.name)}</strong><span class="wl-skill-state">${esc(state)}</span></div>` +
      (generated ? '<span class="wl-skill-new">3층 획득</span>' : '') +
      `<p>${esc(desc.effects)}</p><small>${esc(desc.penalties)}</small></article>`;
  }).join('');
}

export function alphaLabel(meta) {
  const a = meta?.alpha;
  if (!a) return '';
  return [meta.ruleset === 'skills-v1' ? '스킬 원정' : '스킬 알파', a.skills ? '스킬 ON' : '스킬 OFF', a.trpg_combat ? '주사위 전투' : '기본 전투',
    a.random_skill_effective ? '3층 랜덤 획득' : '랜덤 획득 OFF'].join(' · ');
}

export function acquisitionHtml(records, names) {
  return (records || []).map(r => `<div class="wl-acquisition">✦ ${esc(names[r.char] || r.char)} — ` +
    `<b>${esc(r.skill?.name || r.generated_skill_id)}</b> 획득</div>`).join('');
}

export function skillRollHtml(event) {
  const r = event.skill_roll;
  const parts = [];
  if (r && typeof r.total === 'number') {
    const dice = r.mode === 'normal' ? r.roll : `${(r.rolls || []).join(', ')} → ${r.roll}`;
    const mod = r.modifier ?? r.mod ?? 0;
    const mode = r.mode === 'advantage' ? ' · 유리' : r.mode === 'disadvantage' ? ' · 불리' : '';
    parts.push(`${r.kind === 'save' ? '대상 저항' : '명중'}${mode}: 주사위 ${dice} ${mod >= 0 ? '+' : '−'} ${Math.abs(mod)} = ${r.total} / 기준 ${r.dc}`);
    if (r.critical) parts.push('치명타');
  }
  for (const p of event.penalties || []) {
    if (p.type === 'hp_cost') parts.push(`HP ${p.value} 소모`);
    if (p.type === 'self_status') parts.push('자신 둔화');
  }
  if (event.cooldown_after) parts.push(`재사용 ${event.cooldown_after}행동 후`);
  return parts.length ? `<small class="wl-skill-roll">${esc(parts.join(' · '))}</small>` : '';
}

export function skillEffectText(effect) {
  const name = { damage: '피해', heal: '회복', push: '밀침', bleed: '출혈' }[effect.type] || effect.type;
  if (!effect.applied) return `${name} 변화 없음 (${({ saved: '대상이 저항함', blocked: '뒤가 막힘', no_change: '변화 없음' })[effect.reason] || '이미 적용됨 / 대상 상태 확인'})`;
  return effect.type === 'damage' ? `${effect.value} 피해${effect.killed ? '·처치' : ''}`
    : effect.type === 'heal' ? `HP +${effect.heal}` : effect.type === 'push' ? '1칸 밀침' : '출혈';
}
