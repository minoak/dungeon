#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
도감(bestiary) 발급기 — 스트림 소비자. 획득 규칙은 전부 여기(엔진 무수정 — D9/D5).
─────────────────────────────────────────────
지식 스키마 3분리(D9):
  · 획득 = 이 파일 — 조건은 **스트림 어휘로 닫힌다**(say/reason 해석 금지, 결정론).
  · 주입 = dungeon_gm.view() 의 obs 조인(bot['known'] set + Dungeon.lore).
  · 본문 = lore.json — 본문 수정은 원장 불침.
원장 = bestiary.json {캐릭터이름: {종키: {turn, depth}}} — **죽어도 남는 성장 재산**
(D4: 시트·태그 원장은 죽음으로 소멸하지 않는다. 캐릭터 식별=시트 name).

획득 규칙(전부 스트림 어휘 — 오프라인 재적용 = 결정론 투영, 태그 발급기와 거울 구조):
  · 몬스터: tick.bots[].aware_of 에 몹 id 가 *새로* 오른 순간 그 종 획득 — 시야·수색 발각·
    피격을 엔진이 이미 aware_of 하나로 수렴해 둔 덕에 규칙이 한 줄이다. concealed 매복자는
    발각/물린 뒤에야 오르므로 "도감에 있어도 매복은 당한다, 당한 뒤에 아는 것"(D9)이 공짜 성립.
  · 함정: 밟은(walk.trap) / 간파한(found[] kind=trap) 캐릭터가 획득.
  · 상자·샘: 상호작용 결과를 몸으로 겪은 캐릭터가 획득(멀리서 본 것만으론 습성을 모른다).

사용(오프라인 소급): python3 bestiary.py <run_dir|stream.jsonl> ...   # 획득 내역 stdout
"""
import json
import os
import sys

UNKNOWN_BEAST = '낯선 짐승'

# found[](함정 간파)는 name 만 싣는다 — name→종키 역해석. 엔진 표가 정본, 실패 시 고정 폴백.
try:
    from dungeon_gm import TRAP_KINDS
    _TRAP_BY_NAME = {v['name']: k for k, v in TRAP_KINDS.items()}
except Exception:
    _TRAP_BY_NAME = {'가시 함정': 'spike', '독침 함정': 'dart', '경보 함정': 'alarm'}


def load_lore(path):
    """lore.json → {종키: {name, lore}}. 없거나 깨져도 게임은 죽지 않는다(빈 로어 = 이름만 등재)."""
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

    def __init__(self, names=None):
        self.names = dict(names or {})   # char -> 캐릭터이름(원장 키). 오프라인은 run_meta 에서 유도
        self.book = {}                   # 이름 -> set(종키)  (bot['known'] 과 같은 객체를 공유)
        self.meta = {}                   # 이름 -> {종키: {turn, depth}}  (원장 파일 몸통)
        self._idkind = {}                # 이번 층 몹 id(int) -> kind
        self._aware = {}                 # char -> 직전 스냅샷 aware_of set
        self.depth = 1

    def known(self, name):
        """이 캐릭터의 지식 set — 없으면 빈 set 생성. 반환 객체를 bot['known']에 그대로 꽂는다."""
        return self.book.setdefault(name, set())

    def snapshot(self):
        """{이름: sorted(종키)} — run_meta 기록용(판 시작 시점 지식 = 리플레이·비교의 전제)."""
        return {n: sorted(s) for n, s in sorted(self.book.items()) if s}

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
            self.meta.setdefault(name, {}).update(entries)
            self.known(name).update(entries)
        return self

    def save(self, path):
        """원자적 저장(tmp+rename) — 판 도중 크래시에도 원장이 반쪽으로 깨지지 않는다."""
        body = {'_readme': '도감 원장 — 캐릭터의 죽어도 남는 지식(D4·D9). '
                           '획득 규칙=bestiary.py(스트림 소비자), 본문=lore.json(수정해도 여기 불침).'}
        for name in sorted(self.meta):
            body[name] = {k: self.meta[name][k] for k in sorted(self.meta[name])}
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(body, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def _acquire(self, char, key, turn, out):
        if char is None:
            return
        name = self.names.get(char) or ('봇%s' % char)
        book = self.known(name)
        if key in book:
            return
        book.add(key)
        self.meta.setdefault(name, {})[key] = {'turn': turn, 'depth': self.depth}
        out.append((name, key))

    def consume(self, kind, rec):
        """스트림 레코드 1개 소비 → 새 획득 [(이름, 종키)] 반환(발급 순서 = 결정론)."""
        out = []
        if kind == 'run_meta':
            for p in rec.get('party') or []:           # 오프라인 이름 유도 — 라이브가 준 names 우선.
                self.names.setdefault(p.get('char'),   # 폴백은 러너(show_runner)와 같은 규칙('봇N') —
                                      p.get('name') or ('봇%s' % p.get('char')))  # 투영 일치 조건
            for name, keys in (rec.get('bestiary') or {}).items():
                self.known(name).update(keys)          # 판 시작 지식 시드(리뷰 3렌즈 합치 픽스) —
                                                       #   이월 판의 오프라인 소급이 라이브와 같은 증분을
                                                       #   내야 '같은 스트림→같은 원장'(순수 투영)이 성립
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
            for name, key in iss.consume(rec.get('kind'), rec):
                acq.append((rec.get('turn', 0), name, key))
    return iss, acq


def main(argv):
    paths = [a for a in argv if not a.startswith('--')]
    if not paths:
        print(__doc__)
        return 1
    lore = load_lore(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lore.json'))
    for p in paths:
        sp = os.path.join(p, 'stream.jsonl') if os.path.isdir(p) else p
        if not os.path.exists(sp):
            print('건너뜀(스트림 없음): %s' % p, file=sys.stderr)
            continue
        iss, acq = replay(sp)
        print('== %s — 획득 %d건 ==' % (p, len(acq)))
        for turn, name, key in acq:
            print('  t%03d  %-6s %s (%s)' % (turn, name, label(key, lore), key))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
