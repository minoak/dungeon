// 재생 버튼은 글꼴 기호 대신 같은 굵기의 벡터 아이콘으로 표시한다.
const paths = {
  play: '<path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
  pause: '<path d="M8 5v14M16 5v14" stroke-width="4"/>',
  back: '<path d="m15 6-6 6 6 6"/>',
  forward: '<path d="m9 6 6 6-6 6"/>',
  start: '<path d="M6 5v14m12-13-7 6 7 6"/>',
  end: '<path d="M18 5v14M6 6l7 6-7 6"/>',
};
export function icon(name: keyof typeof paths): string {
  return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
}
