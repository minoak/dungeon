// 작은 타입드 이벤트 버스 — 재생 클록·초점·앱 이벤트가 같은 모양으로 쓴다(외부 의존 0).
export type Listener<T> = (payload: T) => void;

export class Emitter<E extends Record<string, unknown>> {
  private readonly map = new Map<keyof E, Set<Listener<never>>>();

  /** 구독 — 반환값을 부르면 해제된다. */
  on<K extends keyof E>(kind: K, fn: Listener<E[K]>): () => void {
    let set = this.map.get(kind);
    if (!set) { set = new Set(); this.map.set(kind, set); }
    set.add(fn as Listener<never>);
    return () => this.off(kind, fn);
  }

  off<K extends keyof E>(kind: K, fn: Listener<E[K]>): void {
    this.map.get(kind)?.delete(fn as Listener<never>);
  }

  /** 한 리스너의 예외가 다른 리스너를 막지 않는다(콘솔에만 남긴다). */
  emit<K extends keyof E>(kind: K, payload: E[K]): void {
    const set = this.map.get(kind);
    if (!set) return;
    for (const fn of [...set]) {
      try { (fn as Listener<E[K]>)(payload); }
      catch (e) { console.error(`[emit ${String(kind)}]`, e); }
    }
  }
}
