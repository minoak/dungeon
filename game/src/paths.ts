// 배포 경로 한 곳(2026-09-12, 챔피언십 제출 — 메모 §3-2 "관전 페이지 정적 빌드").
// - 론처 배포: vite base '/game/'. 에셋·판 파일은 론처(launcher.py)가 리포 루트를 '/' 로 서빙한다(/viewer /runs /state /api).
// - 정적 배포: `vite build --mode static` → base './', 론처 없음. scripts/static-bundle.mjs 가 viewer 에셋·첨부 판·runs/index.json 을
//   dist-static/ 안에 복사한다. 그래서 접두가 BASE_URL('./')이고, /api/status 와 /runs/ 색인은 존재하지 않는다.
export const STATIC: boolean = import.meta.env.MODE === 'static';
export const ROOT: string = STATIC ? import.meta.env.BASE_URL : '/';

/** 정적 배포의 판 목록 — static-bundle.mjs 가 만든다. 첫 항목이 기본으로 열린다. */
export const RUN_INDEX = 'runs/index.json';
export interface RunIndexEntry { path: string; label: string; seed?: number | null; party?: string[] }
export interface RunIndex { runs: RunIndexEntry[] }

export async function fetchRunIndex(): Promise<RunIndex | null> {
  try {
    const r = await fetch(ROOT + RUN_INDEX, { cache: 'no-store' });
    if (!r.ok) return null;
    return (await r.json()) as RunIndex;
  } catch { return null; }
}
