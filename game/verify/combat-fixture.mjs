// 파서가 허용하더라도 실제 장면 생성에 필요한 필드는 픽스처에서 생략할 수 없다.
import assert from 'node:assert/strict';

export function validateFixture(text) {
  const rows = text.trimEnd().split('\n').map(JSON.parse);
  for (const level of rows.filter(r => r.kind === 'level')) {
    assert.ok(Array.isArray(level.exit) && level.exit.length === 2 && level.exit.every(Number.isInteger),
      `층 ${level.depth}: 장면 생성에 필요한 exit=[x,y] 누락`);
    const [x, y] = level.exit;
    assert.ok(x >= 0 && x < level.w && y >= 0 && y < level.h && level.grid[y][x] === '.', '출구는 층 안 바닥 칸이어야 함');
    assert.ok(level.grid.length === level.h && level.grid.every(row => row.length === level.w), '지형 크기 불일치');
    for (const field of ['party', 'monsters', 'features', 'traps', 'rooms']) assert.ok(Array.isArray(level[field]), `층 스냅샷 배열 누락: ${field}`);
  }
  return rows;
}
