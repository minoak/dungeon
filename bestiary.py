#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
도감(bestiary) 발급기 — 스트림 소비자. 획득 규칙은 전부 여기(엔진 무수정 — D9/D5).
─────────────────────────────────────────────
지식 스키마 3분리(D9):
  · 획득 = 이 파일 — 조건은 **스트림 어휘로 닫힌다**(say/reason 해석 금지, 결정론).
  · 주입 = dungeon_gm.view() 의 obs 조인(bot['known'] set + Dungeon.lore).
  · 본문 = entities/*/*.json 의 knowledge.brief/deep(D50, 옛 lore.json) — 본문 수정은 원장 불침.
원장 = bestiary.json {캐릭터이름: {종키: {turn, depth, n, deep?}}} — **죽어도 남는 성장 재산**
(D4: 시트·태그 원장은 죽음으로 소멸하지 않는다. 캐릭터 식별=시트 name).
  D53(09-12, 파트너 "5번 조우하면 심층 정보 — 프리셋을 공통으로, 일단 몬스터만"): 등재(turn·depth = 처음 안 순간)
  뒤에도 조우를 센다(n). 정의의 knowledge.unlock{event:"encounter", count} 를 채우면 deep={turn, depth} 가 붙고
  그때부터 obs 에 심층 본문이 주입된다(그 전엔 brief 한 줄 + 진행도). 옛 원장의 항목(n 없음)은 n=1 로 읽는다
  (⚠️임시 가정: 등재 = 조우 1회. 파트너 미답).

획득 규칙(전부 스트림 어휘 — 오프라인 재적용 = 결정론 투영, 태그 발급기와 거울 구조):
  · 몬스터: tick.bots[].aware_of 에 몹 id 가 *새로* 오른 순간 그 종 획득 — 시야·수색 발각·
    피격을 엔진이 이미 aware_of 하나로 수렴해 둔 덕에 규칙이 한 줄이다. concealed 매복자는
    발각/물린 뒤에야 오르므로 "도감에 있어도 매복은 당한다, 당한 뒤에 아는 것"(D9)이 공짜 성립.
    같은 순간이 조우(encounter) 1회다 — 개체 하나를 새로 인지할 때마다 1(층이 바뀌면 id 공간이
    새로 열리므로 새 층의 개체는 또 1). 같은 개체를 시야에서 놓쳤다 다시 봐도 안 센다.
  · 함정: 밟은(walk.trap) / 간파한(found[] kind=trap) 캐릭터가 획득.
  · 상자·샘: 상호작용 결과를 몸으로 겪은 캐릭터가 획득(멀리서 본 것만으론 습성을 모른다).

사용(오프라인 소급): python3 bestiary.py <run_dir|stream.jsonl> ...   # 획득 내역 stdout
"""
import json
import os
import sys
import time

UNKNOWN_BEAST = '낯선 짐승'

# found[](함정 간파)는 name 만 싣는다 — name→종키 역해석. 엔진 표가 정본, 실패 시 고정 폴백.
try:
    from dungeon_gm import TRAP_KINDS
    _TRAP_BY_NAME = {v['name']: k for k, v in TRAP_KINDS.items()}
except Exception:
    _TRAP_BY_NAME = {'가시 함정': 'spike', '독침 함정': 'dart', '경보 함정': 'alarm'}


def _default_rules():
    """정의(entities)의 심층 해금 조건 — 저장소를 못 읽는 자리(옛 도구)에선 빈 규칙(=옛 2층 동작)."""
    try:
        import entities
        return entities.unlock_rules()
    except Exception:
        return {}


def load_lore(path):
    """(구형) lore.json 꼴 파일 → {종키: {name, lore}}. 본문의 정본은 entities.lore()(D50) — 옛 파일을 읽는 호출자 호환용."""
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        return {k: v for k, v in raw.items()
                if not k.startswith('_') and isinstance(v, dict)}
    except Exception:
        return {}


def label(key, lore=None):
    """종키 → 표시 이름(로어 name 우선, 없으면 키 꼬리)."""
    if lore and key in lore and lore[key].get('name'):
        return lore[key]['name']
    return key.split(':', 1)[-1]


class Issuer:
    """스트림 레코드를 순서대로 consume() 하면 캐릭터별 지식 set(book)이 자란다.
    라이브: 러너가 tick emit 직후 같은 dict 를 먹인다 + bot['known']에 book 의 set 을 *공유*로
    꽂아 획득이 다음 obs 에 즉시 반영된다. 오프라인: 같은 코드로 소급(결정론 투영 검증 가능)."""

    def __init__(self, names=None, rules=None):
        self.names = dict(names or {})   # char -> 캐릭터이름(원장 키). 오프라인은 run_meta 에서 유도
        self.book = {}                   # 이름 -> set(종키)  (bot['known'] 과 같은 객체를 공유)
        self.meta = {}                   # 이름 -> {종키: {turn, depth, n, deep?}}  (원장 파일 몸통 — bot['book'] 과 공유)
        self.rules = dict(rules) if rules is not None else _default_rules()   # 종키 -> {event, count} (심층 해금 조건, 정의에서)
        self.dirty = False               # 마지막 save 뒤 원장이 바뀌었나(조우 수만 올라도 참 — 러너 저장 신호)
        self._idkind = {}                # 이번 층 몹 id(int) -> kind
        self._aware = {}                 # char -> 직전 스냅샷 aware_of set
        self.depth = 1

    def known(self, name):
        """이 캐릭터의 지식 set — 없으면 빈 set 생성. 반환 객체를 bot['known']에 그대로 꽂는다."""
        return self.book.setdefault(name, set())

    def record(self, name):
        """이 캐릭터의 원장 기록 {종키: {turn, depth, n, deep?}} — 반환 객체를 bot['book']에 그대로 꽂는다(D53).
        엔진 view() 는 여기서 n(조우 수)·deep(심층 해금 여부)만 읽는다."""
        return self.meta.setdefault(name, {})

    def snapshot(self):
        """{이름: sorted(종키)} — run_meta 기록용(판 시작 시점 지식 = 리플레이·비교의 전제)."""
        return {n: sorted(s) for n, s in sorted(self.book.items()) if s}

    def progress(self):
        """{이름: {종키: {n, deep?}}} — 판 시작 시점 진행도(run_meta.bestiary_progress, D53 additive).
        deep 는 해금된 종에만 True. 오프라인 소급이 이걸로 시드해야 심층 해금 시점이 라이브와 같다."""
        out = {}
        for name in sorted(self.meta):
            m = {k: {'n': int(r.get('n', 1)), **({'deep': True} if r.get('deep') else {})}
                 for k, r in sorted(self.meta[name].items()) if k in self.known(name)}
            if m:
                out[name] = m
        return out

    def load(self, path):
        """원장 파일 → book/meta 병합. 없으면 첫 원정(조용히 빈 채).
        **깨졌으면 대피+경고** — 조용히 빈 원장으로 시작하면 이번 판 첫 save 가 원본을 덮어써
        '죽어도 남는 재산'(D4)이 무경고 전소된다(07-05 공유상태 소실 사고와 같은 비용 계열)."""
        try:
            with open(path, encoding='utf-8') as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError('최상위가 객체가 아님')
        except FileNotFoundError:
            return self
        except Exception as e:
            bak = path + '.corrupt'
            try:
                os.replace(path, bak)                  # 원본 대피 — 이번 판 save 가 덮어쓰지 못하게
            except OSError:
                bak = '(대피 실패)'
            print('[경고] 도감 원장(%s) 읽기 실패: %s — 원본은 %s 보존, 이번 판은 빈 도감으로 시작'
                  % (path, e, bak), file=sys.stderr)
            return self
        for name, entries in raw.items():
            if name.startswith('_') or not isinstance(entries, dict):
                continue
            for key, rec in entries.items():
                if not isinstance(rec, dict):
                    continue
                rec.setdefault('n', 1)                 # 옛 원장(D53 이전) = 등재만 있음 → 조우 1회로 읽는다(⚠️임시 가정)
                self.record(name)[key] = rec
            self.known(name).update(k for k, r in entries.items() if isinstance(r, dict))
        return self

    def save(self, path):
        """원자적 저장(tmp+rename) — 판 도중 크래시에도 원장이 반쪽으로 깨지지 않는다."""
        body = {'_readme': '도감 원장 — 캐릭터의 죽어도 남는 지식(D4·D9). '
                           '획득 규칙=bestiary.py(스트림 소비자), 본문=entities/*/*.json knowledge.brief/deep(D50 — 수정해도 여기 불침). '
                           'turn·depth=처음 안 순간, n=조우 수, deep={turn, depth}=심층 해금 순간(D53 — 정의의 knowledge.unlock 을 채운 때).'}
        for name in sorted(self.meta):
            body[name] = {k: self.meta[name][k] for k in sorted(self.meta[name])}
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(body, f, ensure_ascii=False, indent=1)
        for i in range(20):                       # Windows: 방금 쓴 파일을 색인기·백신이 잠깐 잡으면 rename 이 WinError 5 —
            try:                                  #   D53 뒤 조우마다 저장해 빈도가 늘자 게이트에서 1회 재현(09-12). 짧게 물러섰다 재시도.
                os.replace(tmp, path)
                break
            except PermissionError:
                if i == 19:
                    raise
                time.sleep(0.05 * (i + 1))
        self.dirty = False

    def _acquire(self, char, key, turn, out):
        """조우 1회 — 처음이면 등재(brief 층, out 에 'brief'), 이어지는 조우는 n 만 올린다.
        정의의 해금 조건(rules[key] = {event:'encounter', count})을 채우는 순간 deep 이 붙는다(out 에 'deep')."""
        if char is None:
            return
        name = self.names.get(char) or ('봇%s' % char)
        book, recs = self.known(name), self.record(name)
        rec = recs.get(key)
        if rec is None:
            book.add(key)
            rec = recs[key] = {'turn': turn, 'depth': self.depth, 'n': 1}
            out.append((name, key, 'brief'))
        else:
            book.add(key)                              # 원장엔 있는데 set 에 없던 경우(시드 불일치) 정합
            rec['n'] = int(rec.get('n', 1)) + 1
        self.dirty = True
        rule = self.rules.get(key)
        if rule and rule.get('event') == 'encounter' and not rec.get('deep') and rec['n'] >= int(rule.get('count', 0)):
            rec['deep'] = {'turn': turn, 'depth': self.depth}
            out.append((name, key, 'deep'))

    def consume(self, kind, rec):
        """스트림 레코드 1개 소비 → 새 사건 [(이름, 종키, 'brief'|'deep')] 반환(발급 순서 = 결정론).
        'brief' = 처음 등재(한 줄 지식 켜짐), 'deep' = 심층 해금(D53). 조우 수만 오른 틱은 빈 리스트(dirty 만 참)."""
        out = []
        if kind == 'run_meta':
            for p in rec.get('party') or []:           # 오프라인 이름 유도 — 라이브가 준 names 우선.
                self.names.setdefault(p.get('char'),   # 폴백은 러너(show_runner)와 같은 규칙('봇N') —
                                      p.get('name') or ('봇%s' % p.get('char')))  # 투영 일치 조건
            prog = rec.get('bestiary_progress') or {}  # D53: 시작 진행도(조우 수·심층 여부)도 시드 — 없으면(옛 판) 조우 1
            for name, keys in (rec.get('bestiary') or {}).items():
                self.known(name).update(keys)          # 판 시작 지식 시드(리뷰 3렌즈 합치 픽스) —
                                                       #   이월 판의 오프라인 소급이 라이브와 같은 증분을
                                                       #   내야 '같은 스트림→같은 원장'(순수 투영)이 성립
                recs = self.record(name)
                for k in keys:
                    pr = (prog.get(name) or {}).get(k) or {}
                    r = recs.setdefault(k, {'turn': 0, 'depth': 0, 'n': int(pr.get('n', 1))})
                    if pr.get('deep') and not r.get('deep'):
                        r['deep'] = {'turn': 0, 'depth': 0}   # 해금 시점은 지난 판의 것(원장 파일에만) — 여기선 여부만
        elif kind == 'level':
            self.depth = rec.get('depth', self.depth)
            self._idkind = {m['id']: m['kind'] for m in rec.get('monsters') or []}
            self._aware = {}                           # 새 층 = 새 몹 id 공간(스폰 봇 aware_of 도 초기화)
        elif kind == 'tick':
            turn = rec.get('turn', 0)
            for m in rec.get('monsters') or []:
                self._idkind[m['id']] = m['kind']
            for b in rec.get('bots') or []:            # ① 몬스터: aware_of 증분 = 인지의 순간
                cur = set(b.get('aware_of') or [])
                for mid in sorted(cur - self._aware.get(b['char'], set())):
                    mk = self._idkind.get(mid)
                    if mk:
                        self._acquire(b['char'], 'monster:' + mk, turn, out)
                self._aware[b['char']] = cur
            for e in rec.get('events') or []:          # ② 함정·상자·샘: 겪은/간파한 캐릭터
                t, ch = e.get('type'), e.get('char')
                if t == 'walk' and (e.get('trap') or {}).get('kind'):
                    self._acquire(ch, 'trap:' + e['trap']['kind'], turn, out)
                if t in ('walk', 'search'):
                    for f in e.get('found') or []:
                        if f.get('kind') == 'trap':
                            tk = _TRAP_BY_NAME.get(f.get('name'))
                            if tk:
                                self._acquire(ch, 'trap:' + tk, turn, out)
                elif t == 'interact':
                    r = e.get('result')
                    if r in ('chest_loot', 'chest_trap'):
                        self._acquire(ch, 'feature:chest', turn, out)
                    elif r in ('fountain_heal', 'fountain_harm'):
                        self._acquire(ch, 'feature:fountain', turn, out)
        return out


def replay(stream_path, names=None):
    """스트림 파일 전체를 소급 발급 — (Issuer, [(turn, 이름, 종키)]). 유효 prefix 규칙(깨진 꼬리 무시)."""
    iss = Issuer(names)
    acq = []
    with open(stream_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for name, key, tier in iss.consume(rec.get('kind'), rec):
                acq.append((rec.get('turn', 0), name, key, tier))
    return iss, acq


def main(argv):
    paths = [a for a in argv if not a.startswith('--')]
    if not paths:
        print(__doc__)
        return 1
    import entities
    lore = entities.lore()                    # D50: 본문은 엔티티 저장소에서
    for p in paths:
        sp = os.path.join(p, 'stream.jsonl') if os.path.isdir(p) else p
        if not os.path.exists(sp):
            print('건너뜀(스트림 없음): %s' % p, file=sys.stderr)
            continue
        iss, acq = replay(sp)
        print('== %s — 획득 %d건 ==' % (p, len(acq)))
        for turn, name, key, tier in acq:
            print('  t%03d  %-6s %s (%s)%s' % (turn, name, label(key, lore), key, '  ← 심층 해금' if tier == 'deep' else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
