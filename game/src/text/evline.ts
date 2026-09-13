// 사건 문장 사전 — viewer/index.html 의 nameSpan/resolveTarget/iga/evLine/buildFeedGroups/endGroupHtml 을 순수 함수로 이식.
// DOM 무접촉: HTML 문자열만 만든다. 이름·대사·문구·몹 종류는 LLM/사용자 입력이므로 전부 esc() 를 거친다.
// 뷰어에 없던 어휘(follow·rest·wait·walk 의 동행/대기/휴식/정지 결과·give·bond·마을 NPC·장비 장착)는
// STREAM_FORMAT '이벤트 어휘 전수' 를 따라 짧은 한글 한 줄로 보탠다. monster_move 는 null(지도가 보여준다).
// 색 등급(cls): dim(소음) · notable(정지·발견) · gold(획득·하강) · combat(전투) · fb(규칙 두뇌) · give(건네기) · dir(지문).
import type { Char, Decision, Frame, Run, StreamEvent } from '../stream/types';
import { esc } from '../ui/dom';
import { reactionHtml, reactionSummaryHtml } from './reactions';
import { acquisitionHtml, skillRollHtml, skillEffectText } from '../../../viewer/assets/skills.js';

export interface EvLine { cls: string; html: string }

/* ───────────── 원시값 도우미(스트림 필드는 unknown — additive 계약) ───────────── */
const str = (v: unknown, d = ''): string => (v == null ? d : String(v));
const num = (v: unknown, d = 0): number => (typeof v === 'number' ? v : (v == null || v === '' ? d : (Number(v) || d)));
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const obj = (v: unknown): Record<string, unknown> | null =>
  (v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const isBotChar = (run: Run, v: unknown): boolean => typeof v === 'string' && v in run.names;

/** 이름(색 없음, 평문). */
export function nameOf(run: Run, c: unknown): string { const k = str(c); return run.names[k] || k; }
/** 캐릭터 색 이름 span. */
export function nameSpan(run: Run, c: unknown): string {
  const k = str(c);
  return `<b style="color:${esc(run.colors[k] || '#fff')}">${esc(run.names[k] || k)}</b>`;
}

/** 조사 이/가 — 받침 유무로 선택("고블린이" / "그림자거미가"). 태그가 섞여 있으면 벗기고 본다. */
export function iga(word: string): string {
  const s = String(word).replace(/<[^>]*>/g, '').trim();
  const ch = s.charCodeAt(s.length - 1);
  if (ch >= 0xAC00 && ch <= 0xD7A3) return (ch - 0xAC00) % 28 ? '이' : '가';
  return '이(가)';
}
/** 조사 을/를. */
export function eul(word: string): string {
  const s = String(word).replace(/<[^>]*>/g, '').trim();
  const ch = s.charCodeAt(s.length - 1);
  if (ch >= 0xAC00 && ch <= 0xD7A3) return (ch - 0xAC00) % 28 ? '을' : '를';
  return '을(를)';
}

/** order/target 원시값('m2'/'b1'/'follow:b1'/'f3'/'d4'/'exit'/'wait'/'rest'/'@x,y') → 사람 말(평문 — 호출자가 esc). */
export function resolveTarget(t: unknown, f: Frame, run: Run): string {
  if (t == null) return '';
  const s = String(t);
  if (s === 'exit') return '출구(계단)';
  if (s === 'wait') return '기다림';
  if (s === 'rest') return '휴식';
  let m: RegExpExecArray | null;
  if ((m = /^(?:follow:|chase:)?b(.+)$/.exec(s))) return run.names[m[1]] || s;
  if ((m = /^m(\d+)$/.exec(s))) { const mob = f.monsters.find(x => x.id === +m![1]); return mob ? mob.kind : '적'; }
  if ((m = /^f(\d+)$/.exec(s))) { const ft = f.features.find(x => x.id === +m![1]); return ft ? ft.name : '무언가'; }
  if (/^d\d+$/.test(s)) return '문';
  if ((m = /^@(-?\d+),(-?\d+)$/.exec(s))) return `(${m[1]},${m[2]}) 지점`;
  return s;
}

/** 명단([{char,name}] | [char] | [{name}]) → 이름 나열(·). */
function listNames(v: unknown, run: Run): string {
  return arr(v).map(x => {
    const o = obj(x);
    if (o) return o.char != null ? nameSpan(run, o.char) : esc(str(o.name ?? o.kind, '?'));
    return isBotChar(run, x) ? nameSpan(run, x) : esc(str(x));
  }).join('·');
}

/** 이 사건에 얽힌 봇들(행위자·받는 이·대상) — 초점 강조용. */
export function evChars(e: StreamEvent, run: Run): Char[] {
  const out: Char[] = [];
  const add = (v: unknown) => { if (isBotChar(run, v) && !out.includes(v as string)) out.push(v as string); };
  add(e.char);
  add(e.to);                                     // give·bond 의 받는 봇(walk 의 to 는 [x,y] 라 걸러진다)
  let m: RegExpExecArray | null;
  if (typeof e.target === 'string' && (m = /^(?:follow:|chase:)?b(.+)$/.exec(e.target))) add(m[1]);
  if (e.type.startsWith('monster_')) add(e.target);   // 몹의 표적은 봇 번호
  const swap = obj(e.swap); if (swap) add(swap.char);
  add(e.paced);
  return out;
}

/* ───────────── 이벤트 → 한 줄(show_runner.act_summary / mon_summary 계승) ───────────── */

export function evLine(e: StreamEvent, f: Frame, run: Run): EvLine | null {
  const t = e.type;
  const who = e.char ? nameSpan(run, e.char) + ' ' : '';
  const L = (cls: string, h: string): EvLine => ({ cls, html: who + h });
  const tgt = (): string => resolveTarget(e.target, f, run);

  if (e.skill_id) {
    const effects = arr(e.effects).map(obj).filter(x => x !== null).map(skillEffectText);
    const why: Record<string, string> = { cooldown: '재사용 대기 중', insufficient_hp: 'HP 부족',
      invalid_skill: '보유하지 않은 스킬', target_not_bleeding: '출혈 조건 미충족', lost: '대상 소실',
      not_living: '살아있는 대상이 아님', too_far: '범위 밖', self_only: '자신에게만 가능', hostile_self: '자해 불가' };
    const detail = e.result === 'skill_failed' ? (why[str(e.reason_code)] || str(e.reason_code))
      : e.hit === false ? '빗나감/저항' : effects.join(', ');
    return L('combat', `✦ ${esc(e.skill_name || e.skill_id)} → ${esc(tgt())}: ${esc(detail)}` + skillRollHtml(e));
  }
  if (t === 'monster_status') return L('combat', `${esc(e.monster)} — ${esc(e.status)} ${num(e.dmg)} 피해${e.killed ? '·쓰러짐' : ''}`);

  if (e.result === 'approaching') return L('dim', `↗ ${esc(tgt())} — 실행 거리까지 접근한다`);
  if (e.result === 'no_path' && e.parent_action_id) return L('dim', `${esc(tgt())} — 접근할 길이 없다`);
  if (e.result === 'no_effect') return L('dim', `${esc(tgt())} — ${esc(t)} 시도, 변화 없음`);
  if (t === 'use' && e.result === 'healed') return L('gold', `${esc(tgt())}에게 물약 사용 — HP +${num(e.heal)} (HP ${num(e.hp)})`);
  if (t === 'use' && (e.effect_type === 'interact' || e.effect_type === 'goto')) return evLine({ ...e, type: e.effect_type }, f, run);
  if (t === 'use') return L('dim', `${esc(tgt())} 사용 실패 — ${esc(e.result)}`);

  if (t === 'goto') {
    if (e.result === 'blocked') return L('notable', `⚑ ${esc(tgt())} — 길 막힘(${listNames(e.allies, run) || '동료'}가 길목에)`);
    if (e.result === 'already_beside') return L('dim', `⚑ ${esc(tgt())} — 이미 곁에 멈춰 있어 갈 곳 없음`);   // D48 개정 goto<아군>
    return L('dim', `⚑ ${esc(tgt())}${e.result === 'arrived' ? ' — 이미 곁에' : '에게 핑'}`);
  }
  if (t === 'explore') {
    if (e.result === 'pathed') {
      if (e.to_exit) return L('dim', e.remembered ? '⚑ 더 볼 곳 없음 — 기억의 계단으로 향한다' : '⚑ 더 볼 곳 없음 — 출구로 향한다');
      if (e.door) return L('dim', '⚑ 더 볼 곳 없음 — 안 가 본 문 너머로');
      if (e.frontier) return L('dim', '⚑ 더 볼 곳 없음 — 안 본 가장자리로');
      return L('dim', `⚑ ${esc(str(e.bearing, '?'))} 방향 탐색`);
    }
    return L('dim', e.exhausted ? '⚑ 탐색 — 더 볼 곳이 없다' : '⚑ 탐색 — 갈 곳이 없다');
  }
  if (t === 'follow') {                          // 동행(D18 A-5)
    const n = esc(tgt());
    if (e.result === 'pathed') return L('dim', `⇢ ${n} 곁으로 — 동행 시작`);
    if (e.result === 'following') return L('dim', `${n} 곁에 붙는다 — 동행`);
    if (e.result === 'blocked') return L('notable', `⇢ ${n} 곁으로 — 길 막힘(${listNames(e.allies, run) || '동료'}가 길목에)`);
    return L('dim', `⇢ ${n} — 동행 ${esc(str(e.result))}`);
  }
  if (t === 'wait') return L('dim', '기다리기 시작');
  if (t === 'rest') return L('dim', `휴식 (HP ${num(e.hp)})`);
  if (t === 'walk') {
    const line = walkLine(e, f, run);
    if (!line) return null;
    const bleed = obj(e.bleed);                  // D34 출혈 — 어떤 걸음에도 병기
    if (bleed && !bleed.down) line.html += ` · 출혈 −1 (HP ${num(bleed.hp)})`;
    return { cls: line.cls, html: who + line.html };
  }
  if (t === 'give') {                            // 건네기(D47 ②) — 파트너 문장 그대로 "{준 이름} → {받은 이름}: {what}"
    const M: Record<string, string> = { too_far: '곁에 없다', nothing: '줄 것이 없다', no_target: '대상 없음', no_room: '놓을 자리 없음' };
    if (e.result === 'given')
      return { cls: 'give', html: `${nameSpan(run, e.char)} → ${nameSpan(run, e.to)}: ${esc(str(e.what, '?'))}${e.placed ? ' (발밑에 놓임)' : ''}` };
    return L('dim', '건네기 — ' + (M[str(e.result)] || esc(str(e.result))));
  }
  if (t === 'bond') {                            // 친목(D47 ②) — 지문 "{이름}: *{form}*"
    if (e.result === 'done') return { cls: 'dir', html: `${nameSpan(run, e.char)}: *${esc(str(e.form, '몸짓'))}*` };
    return L('dim', '친목 — ' + (e.result === 'too_far' ? '곁에 없다' : e.result === 'nothing' ? '할 것이 없다' : '대상 없음'));
  }
  if (t === 'interact') {
    const r = str(e.result);
    if (r === 'exit') return L('gold', `▼ 다 모였다 — 함께 하강!! (${listNames(e.party, run)})`);
    if (r === 'locked') return L('notable', '◈ 워프게이트 — 봉인돼 있다(보스가 서 있는 동안 열리지 않는다)');   // D65
    if (r === 'ascend') return L('gold', e.gate ? `◈ 봉인 풀린 워프게이트로 — 마을 귀환!! (${listNames(e.party, run)})`   // D65
                                          : `▲ 마을로 돌아간다 (${listNames(e.party, run)})`);
    if (r === 'wait_allies') {
      const missing = listNames(e.missing, run), busy = listNames(e.busy, run);
      const bits = [missing ? `아직: ${missing}` : '', busy ? `바쁨: ${busy}` : ''].filter(Boolean).join(' · ');
      return L('notable', `계단에서 동료를 기다린다${bits ? ` (${bits})` : ''}`);
    }
    if (r === 'treasure') return L('gold', '◆ 보물 획득');
    if (r === 'chest_loot') return L('gold', `상자를 열었다 — 보물 ${num(e.loot)}개! (d20 ${num(e.total)})`);
    if (r === 'chest_trap') return L('combat', `상자에서 독침이! ${num(e.dmg)}피해 (d20 ${num(e.total)})${e.down ? ' — 쓰러졌다!' : ''}`);
    if (r === 'fountain_heal') return L('gold', `샘물을 마셨다 — HP ${num(e.heal)} 회복`);
    if (r === 'fountain_harm') return L('combat', `샘물이 오염돼 있었다 — ${num(e.dmg)}피해${e.down ? ' — 쓰러졌다!' : ''}`);
    if (r === 'potion') return L('gold', '! 회복 물약을 집어 챙겼다');
    if (r === 'equip') {                         // 장비(D28)
      const item = esc(str(e.item, '장비'));
      return L('gold', `${item} 장착 (+${num(e.bonus)})${e.dropped ? ` — ${esc(str(e.dropped))} 내려놓음` : ''}`);
    }
    if (r === 'npc_talk') return L('notable', `${esc(str(e.npc, 'NPC'))}: 「${esc(str(e.line))}」`);   // 마을 NPC(D29·D32)
    if (r === 'npc_gift') {
      const item = esc(str(e.item, '무언가'));
      return L('gold', `${esc(str(e.npc, 'NPC'))}에게서 ${item}${eul(item)} 받았다 — 「${esc(str(e.line))}」`);
    }
    const tag: Record<string, string> = { too_far: '너무 멀다', nothing: '허탕', no_target: '대상 없음' };
    return L('dim', `상호작용 ${esc(tgt())} — ${esc(tag[r] || r)}`);
  }
  if (t === 'drink') {
    if (e.result === 'drink_heal')
      return L('gold', `회복 물약을 들이켰다 — HP ${num(e.heal)} 회복(전부), 남은 물약 ${num(e.potions)}병`);
    return L('dim', '물약을 마시려 했지만 — 없다');
  }
  if (t === 'attack') {
    if (e.result === 'no_target') return L('dim', '공격 — 인접한 적 없음(허공)');
    if (e.result === 'too_far') return L('dim', '공격 — 지목한 적이 너무 멀다');
    const mod = num(e.mod);
    const roll = ` (d20 ${num(e.roll)}${mod >= 0 ? '+' : ''}${mod}=${num(e.total)} vs AC ${num(e.ac)})`;
    const sneak = e.surprise ? '기습! ' : '';
    const target = esc(str(e.target, '적'));
    if (!e.hit) return L('combat', `⚔ ${sneak}${target} 공격 — 빗나감${roll}`);
    const head = sneak + (e.crit ? '대성공! ' : '');
    const tail = (e.killed ? ' — 처치!' : ` (${e.target_kind === 'bot' ? '대상' : '적'} HP ${Math.max(0, num(e.monster_hp))})`)
      + (e.unsealed ? ' ◈ 워프게이트의 봉인이 풀렸다' : '');   // D65 보스 처치
    return L('combat', `⚔ ${target} 공격 — ${head}${num(e.dmg)}피해${tail}${roll}`);
  }
  if (t === 'search') {
    const found = arr(e.found);
    if (!found.length) return L('dim', `샅샅이 살폈다 (반경 ${num(e.radius, 1)}) — 아무것도 없음`);
    return L('notable', '샅샅이 살폈다 — 발견: ' + listNames(found, run));
  }
  // ── 몹 이벤트 ──
  const mon = esc(str(e.monster));
  if (t === 'monster_notice')
    return { cls: 'notable', html: `${mon}${iga(mon)} ${nameSpan(run, e.target)}를 발견 — 추적 개시!` };
  if (t === 'monster_flee') return { cls: 'ev', html: `${mon} 겁에 질려 달아나기 시작한다!` };
  if (t === 'monster_desperate') return { cls: 'combat', html: `${mon} 더는 도망칠 곳이 없다 — 이빨을 드러낸다!` };
  if (t === 'monster_join') return { cls: 'ev', html: `${mon} ${esc(str(e.ally_kind, '동료'))} 곁에 붙는다 — ${e.state === 'HUNTING' ? '함께 싸운다!' : '숨을 고른다'}` };   // D51
  if (t === 'monster_attack') {
    const sneak = e.from_hiding ? `매복!! 어둠에서 ${mon}${iga(mon)} 튀어나온다 — ` : (e.surprise ? '기습! ' : '');
    const mod = num(e.mod);
    const roll = ` (d20 ${num(e.roll)}${mod >= 0 ? '+' : ''}${mod}=${num(e.total)} vs AC ${num(e.ac)})`;
    if (!e.hit) return { cls: 'combat', html: `${sneak}${mon} ⚔ ${nameSpan(run, e.target)} — 빗나감${roll}` };
    const tail = e.down ? ' — 쓰러졌다!' : ` (HP ${num(e.hp)})`;
    const status = e.status ? ` · ${esc(str(e.status))} 걸림` : '';
    return { cls: 'combat', html: `${sneak}${mon} ⚔ ${nameSpan(run, e.target)} — ${num(e.dmg)}피해${tail}${status}${roll}` };
  }
  if (t === 'monster_move') return null;         // 지도가 보여준다 — 피드 소음 제거
  return { cls: 'dim', html: who + esc(t) };     // 모르는 이벤트: 이름만(additive 관용)
}

/** walk 한 걸음(who 없이) — result 분기. */
function walkLine(e: StreamEvent, f: Frame, run: Run): EvLine | null {
  const r = str(e.result);
  const tgt = (): string => resolveTarget(e.target, f, run);
  if (r === 'encounter') {
    const bits: string[] = [];
    if (e.woke === 'rest') bits.push('쉬다 깼다');
    const mons = arr(e.monsters);
    if (mons.length) bits.push('적 출현: ' + mons.map(m => esc(str(obj(m)?.kind, '?'))).join(', '));
    const tr = obj(e.trap);
    if (tr) {
      const name = esc(str(tr.name, '함정'));
      if (tr.safe) bits.push(`${name} 회피! (d20 ${num(tr.total)} vs DC ${num(tr.dc)})`);
      else if (tr.alarm != null) bits.push(`${name} 발동!! 몹 ${num(tr.alarm)} 각성`);
      else bits.push(`${name}! ${num(tr.dmg)}피해${tr.status ? ` · ${esc(str(tr.status))} 걸림` : ''}${tr.down ? ' — 쓰러졌다!' : ''}`);
    }
    const bleed = obj(e.bleed);
    if (bleed && bleed.down) bits.push('출혈로 쓰러졌다!');
    if (e.treasure) bits.push('보물 획득');
    if (e.potion) bits.push('회복 물약 획득');
    const found = arr(e.found);
    if (found.length) bits.push('발견: ' + listNames(found, run));
    return { cls: bleed && bleed.down || (tr && !tr.safe && tr.down) ? 'combat' : 'notable', html: '보행 정지 — ' + (bits.join(' / ') || '조우') };
  }
  if (r === 'blocked' && arr(e.monsters).length)
    return { cls: 'notable', html: `길 막힘 — ${arr(e.monsters).map(m => esc(str(obj(m)?.kind, '?'))).join(', ')}가 길목을 점거` };
  if (r === 'treasure') return { cls: 'gold', html: '◆ 길에서 보물을 주웠다' };
  if (r === 'potion') return { cls: 'gold', html: '! 길에서 회복 물약을 챙겼다' };
  if (r === 'at_exit') return { cls: 'notable', html: '계단 앞에 섰다' };
  // ── D19 정지·D21 자기 관찰 ──
  if (r === 'sighted') return { cls: 'notable', html: `${listNames(e.seen, run) || '무언가'} 발견 — 멈춰 선다` };
  if (r === 'reunion') return { cls: 'notable', html: `낯익은 곳이다 — ${esc(str(e.name, '아는 곳'))}` };
  if (r === 'wander') return { cls: 'notable', html: `같은 곳을 맴돌았다 (${num(e.steps)}걸음) — 멈춰 선다` };
  // ── D18 동행 ──
  if (r === 'following') return { cls: 'dim', html: 'to' in e ? `⇢ ${esc(tgt())} 뒤를 따라 걷는다 — 동행` : `${esc(tgt())} 곁에 머문다 — 동행` };
  if (r === 'idle') { const n = esc(tgt()); return { cls: 'dim', html: `${n}${iga(n)} 움직이지 않는다 — 동행 끝` }; }
  if (r === 'beside') return { cls: 'dim', html: `${esc(tgt())} 곁에 붙어 있다 — 따라간다` };   // D48 개정 추적(chase:b)
  // ── D25 대기 ──
  if (r === 'waiting') return { cls: 'dim', html: '기다린다' };
  if (r === 'wait_met') { const n = listNames(e.allies, run) || '동료'; return { cls: 'notable', html: `기다리다 ${n}${iga(n)} 보였다` }; }
  if (r === 'wait_bored') return { cls: 'notable', html: `${num(e.ticks)}틱을 기다렸지만 — 아무도 안 온다` };
  if (r === 'wait_left') { const n = listNames(e.allies, run) || '동료'; return { cls: 'notable', html: `기다리는 사이 ${n}${iga(n)} 시야에서 사라졌다` }; }   // D25 개정 3
  // ── D35 휴식 ──
  if (r === 'resting') return { cls: 'dim', html: `휴식 중 (HP ${num(e.hp)})` };
  if (r === 'rested') {
    const cleared = arr(e.cleared).map(x => esc(str(x))).join('·');
    return { cls: 'gold', html: `휴식 끝 — ${num(e.ticks)}틱, HP +${num(e.healed)}${cleared ? `, ${cleared} 풀림` : ''}` };
  }
  if (r === 'rest_met') { const n = listNames(e.allies, run) || '동료'; return { cls: 'notable', html: `쉬다 ${n}${iga(n)} 보여 일어난다` }; }
  // ── 도착·허탕·막힘 ──
  if (r === 'arrived' && !('to' in e)) return { cls: 'dim', html: `${esc(tgt())} 곁에 도착 — 재결정` };
  if (r === 'lost') return { cls: 'notable', html: `${esc(tgt())}를 마지막 본 자리까지 갔지만 — 곁에 없다` };
  if (r === 'arrived') return { cls: 'dim', html: '도착' };
  if (r === 'blocked') return { cls: 'dim', html: '길 막힘' };
  if (e.paced) return { cls: 'dim', html: `동료(${esc(nameOf(run, e.paced))})에게 한 박자 양보 — 일렬 행군` };
  const swap = obj(e.swap);
  if (swap) return { cls: 'dim', html: `${esc(str(swap.name, '동료'))}와 스치듯 자리를 바꾸며 — 이동 중` };
  if (e.slowed) return { cls: 'dim', html: '둔화 — 제자리' };
  const n = tgt();
  return { cls: 'dim', html: `▸ ${esc(n)}${/지점$/.test(n) ? '으로' : '에게'} 이동 중` };
}

/* ───────────── 프레임 → 로그 그룹 HTML(buildFeedGroups 이식) ───────────── */

function lineHtml(cls: string, html: string, chars: Char[], focus: Char | null): string {
  const hit = !!focus && chars.includes(focus);
  const dc = chars.length ? ` data-c=" ${chars.join(' ')} "` : '';
  return `<div class="${cls}${hit ? ' focus' : ''}"${dc}>${html}</div>`;
}

/** 결정 한 건 → 줄들(발화 .say · 속내 .rsn · 규칙 두뇌 .ev.fb). skipped 는 없음. */
/** D62(09-13): 모델의 안전 차단으로 몸짓 서술을 접고 한 판단의 표식 — 접었음을 숨기지 않는다(⚠️문구 임시). */
export function degMark(d: Decision | undefined): string {
  return d?.brain_degraded ? '<span class="deg" title="모델의 안전 차단으로 몸짓 서술을 접고 판단했다">몸짓 접음</span> ' : '';
}

export function decisionLines(c: Char, d: Decision, run: Run, focus: Char | null): string {
  if (d.skipped) return '';
  const chars: Char[] = [c];
  if (isBotChar(run, d.to)) chars.push(d.to as string);
  if (d.src === 'fallback') return lineHtml('ev fb', `${nameSpan(run, c)} ⚙ 규칙 두뇌가 대신 움직였다`, chars, focus);
  let out = '';
  if (d.say) {
    const kind = d.say_kind === '제안' ? '<span class="kind">제안</span>' : '';
    const to = d.to ? `<span class="to">→ ${d.to === 'all' ? '모두' : esc(nameOf(run, d.to))}</span>` : '';
    out += lineHtml('say', `${nameSpan(run, c)} <span class="bub">「${esc(d.say)}」</span>${kind}${to}`, chars, focus);
  }
  if (d.reason) out += lineHtml('rsn', `${degMark(d)}${esc(d.reason)}`, chars, focus);
  return out;
}

/** 층 머리글(level 프레임). */
export function levelHead(f: Frame, run: Run): string {
  const roster = f.bots.map(b => esc(nameOf(run, b.char))).join('·');
  const d = f.level.depth;
  if (d === 0 && run.town) return `⚐ 마을 (${roster})`;
  if (d === 1) return `⚐ 원정 시작 — 지하 1층 (${roster})`;
  return `▼ 지하 ${d}층 진입 (${roster})`;
}

/** 한 프레임의 로그 그룹 — 결정(발화·속내)·사건·층 전이. 비면 ''. */
export function groupHtml(f: Frame, run: Run, focus: Char | null): string {
  if (f.kind === 'level') return `<div class="grp lvl" data-turn="${f.turn}">${levelHead(f, run)}` +
    acquisitionHtml(f.level.skill_acquisitions, run.names) + '</div>';
  const parts: string[] = [];
  if (f.oracle) parts.push(lineHtml('ev gold', `🔮 신의 요청 — 「${esc(f.oracle.text)}」 (요청이지 명령이 아니다)`, [], focus));   // D61 개정(09-13) 어디서나
  for (const c of Object.keys(f.decisions)) parts.push(decisionLines(c, f.decisions[c], run, focus));
  for (const reaction of f.reactions || []) {
    parts.push(lineHtml('ev notable reaction', reactionHtml(reaction, run), [reaction.actor, reaction.to], focus));
  }
  for (const e of f.events) {
    const line = evLine(e, f, run);
    if (!line) continue;
    // 등급이 곧 훅: .ev.give(건네기) · .ev.dir(지문) · .ev.dim/notable/gold/combat(색)
    parts.push(lineHtml(line.cls === 'ev' ? 'ev' : `ev ${line.cls}`, line.html, evChars(e, run), focus));
  }
  if (f.descend) {
    const who = arr(f.descend.party).map(p => esc(nameOf(run, obj(p)?.char))).join('·');
    const chars = arr(f.descend.party).map(p => str(obj(p)?.char)).filter(c => isBotChar(run, c));
    const html = f.descend.kind === 'ascend' ? `▲ ${who} — 마을로 돌아간다` : `▼ ${who} — 지하 ${f.descend.to_depth}층으로 내려간다`;
    parts.push(lineHtml('ev gold', html, chars, focus));
    if (f.descend.reaction_summary) parts.push(lineHtml('ev notable',
      '이 층의 반응 결산<br>' + reactionSummaryHtml(f.descend.reaction_summary, run), chars, focus));
  }
  const body = parts.join('');
  if (!body) return '';
  return `<div class="grp" data-turn="${f.turn}"><div class="gt">t${f.turn}</div>${body}</div>`;
}

/** 결말 그룹(end 라인) — 결말·쓰러진 자·생환·남은 자. */
export function endGroupHtml(run: Run): string {
  const end = run.end;
  if (!end) return '';
  const OC: Record<string, string> = { escaped: '던전 돌파 — 탈출!!', wiped: '전멸', timeout: '시간 종료' };
  const bits = [`▣ 원정 결말 — ${esc(OC[end.outcome] || end.outcome)} (t${end.turn})`];
  if (arr(end.fallen).length) bits.push(`☠ 쓰러진 자: ${arr(end.fallen).map(c => esc(nameOf(run, c))).join(', ')}`);
  if (arr(end.survivors).length) bits.push(`🛡 생환: ${arr(end.survivors).map(c => esc(nameOf(run, c))).join(', ')}`);
  if (arr(end.remaining).length) bits.push(`⏳ 남은 자: ${arr(end.remaining).map(c => esc(nameOf(run, c))).join(', ')}`);
  if (end.reaction_summary) bits.push('원정 반응 결산<br>' + reactionSummaryHtml(end.reaction_summary, run));
  for (const floor of end.reaction_floors || []) bits.push(
    `${floor.depth === 0 ? '마을' : '지하 ' + esc(floor.depth) + '층'} (t${esc(floor.since)}~${esc(floor.until)}): ` +
    `like ${esc(floor.total.like)} / dislike ${esc(floor.total.dislike)}`);
  return `<div class="grp fin" data-turn="${end.turn}">${bits.join('<br>')}</div>`;
}
