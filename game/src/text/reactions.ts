// 관전 전용 반응 표현. 엔진이 검증·집계한 현재 프레임의 값만 사용한다.
import type { Char, Reaction, ReactionSummary, Run, SocialEvent } from '../stream/types';
import { esc } from '../ui/dom';

export function socialDescription(e: SocialEvent): string {
  if (e.skill_id) return `${e.skill_name || e.skill_id}: HP +${e.heal || 0}`;
  if (e.type === 'say') return `${e.say_kind || '잡담'}: 「${e.text || ''}」`;
  if (e.type === 'bond') return `친목: ${e.form || '몸짓'}`;
  if (e.type === 'give') return `건네기: ${e.what || e.item || '물건'}`;
  return `물약 사용: HP +${e.heal || 0}`;
}

export function reactionHtml(r: Reaction, run: Run): string {
  const who = esc(run.names[r.actor] || r.actor), to = esc(run.names[r.to] || r.to);
  const label = r.value === 'like' ? '좋아함 (like)' : '싫어함 (dislike)';
  return `<b>${who} → ${to}</b> · ${label} — ${esc(socialDescription(r.source))}` +
         ` <span class="t">(t${esc(r.source.turn)} · ${esc(r.reaction_to)})</span>`;
}

export function reactionSummaryHtml(summary: ReactionSummary | undefined, run: Run, char?: Char): string {
  if (!summary) return '반응 기록이 없는 이전 판';
  const total = char ? (summary.by_actor[char] || { like: 0, dislike: 0 }) : summary.total;
  const lines = [`좋아함(like) ${esc(total.like)} · 싫어함(dislike) ${esc(total.dislike)}`];
  for (const pair of summary.pairs.filter(p => !char || p.from === char)) {
    lines.push(`${esc(run.names[pair.from] || pair.from)} → ${esc(run.names[pair.to] || pair.to)}: ` +
               `like ${esc(pair.like)} / dislike ${esc(pair.dislike)}`);
  }
  if (!char) lines.push(`평가가 기록되지 않은 수신 ${esc(summary.unrated)}건`);
  return lines.join('<br>');
}
