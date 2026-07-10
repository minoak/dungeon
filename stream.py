# -*- coding: utf-8 -*-
"""
구조화 스트림(JSONL) 라이터 — 엔진 진실의 기계 판본 (LLM 0콜).
─────────────────────────────────────────────
엔진 → stream.jsonl → [맵뷰어 | 기계 크로니클 | GM(옵션) | 웹뷰어] 형제 구조의 관.
한 실행 = 한 파일(열 때 truncate). 라인 = compact JSON + '\n', 공통 필드 'kind'.
라인마다 flush — tail -F 라이브 관전 가능, 크래시가 나도 유효한 prefix 가 남는다.
데이터 계약(필드 전수·소비 규칙·리플레이 레시피) = STREAM_FORMAT.md.
"""
import json


class StreamWriter:
    def __init__(self, path):
        # newline='\n' — Windows 쪽 소비자가 열어도 라인 계약(\n)이 흔들리지 않게 고정
        self.f = open(path, 'w', encoding='utf-8', newline='\n')

    def emit(self, kind, **fields):
        """한 라인 기록. kind 가 항상 첫 키 — 사람이 tail 로 봐도 종류가 눈에 먼저 잡힌다."""
        self.f.write(json.dumps({'kind': kind, **fields},
                                ensure_ascii=False, separators=(',', ':')) + '\n')
        self.f.flush()

    def close(self):
        self.f.close()
