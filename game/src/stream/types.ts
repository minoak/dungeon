// STREAM_FORMAT.md 의 미러 — 클라이언트가 읽는 필드만 적는다. 모르는 필드는 인덱스 시그니처로
// 조용히 허용한다(additive 계약: 필드 삭제·의미 변경 없음, 소비자는 모르는 것을 무시).
// 뒤쪽 Frame/Run 은 스트림에 없는 파생물(뷰어의 frames 와 같은 뼈대 + 시야·본 곳).

export type Char = string;                       // 봇 번호 문자열 '1' '2' …
export type Dir = 'front' | 'right' | 'back' | 'left';

export interface Look {
  sprite?: string;                               // SD 외형 id (atlas.presets 키) — 없으면 옛 판(파츠 합성)
  hairstyle?: string;
  head?: string; body?: string; colors?: Record<string, string>;
  [k: string]: unknown;
}

export interface PartyMember {
  char: Char; name?: string; job?: string; sex?: string; maxhp?: number;
  persona?: string; goal?: string; look?: Look;
  [k: string]: unknown;
}

/** 도감 원장 한 칸(run_meta.bestiary_progress — D53·D55): 조우 수·심층 여부·캐릭터가 남긴 인식 한 줄(지난 판). */
export interface BestiaryNote { text: string; n?: number; turn?: number; depth?: number }
export interface BestiaryEntry { n: number; deep?: boolean; deep_n?: number; asked_n?: number; due?: string; note?: BestiaryNote }
/** 지식 본문 정의(run_meta.bestiary_defs — D63 additive, entities.lore()): 등재 한 줄(brief)·심층 본문(lore)·해금 조건. */
export interface BestiaryDef { name: string; lore: string; brief?: string; unlock?: { event: string; count: number }; review?: { event: string; count: number } }

export interface RunMeta {
  kind: 'run_meta'; v: number; started: string; seed: number; w: number; h: number; depths: number;
  sight?: number; town?: boolean; max_turns?: number; backend?: string;
  party: PartyMember[];
  give?: boolean; bond?: boolean; say_kind?: boolean; sayto?: boolean; relations?: boolean; status?: boolean;
  ally_sight?: boolean; events?: boolean; graves?: boolean;
  notebook?: boolean;                                                  // D59 수첩 판 여부
  bestiary?: Record<string, string[]>;                                 // 판 시작 때 이름별 아는 종키
  bestiary_progress?: Record<string, Record<string, BestiaryEntry>>;   // 판 시작 때 이름별 진행도(note 본문까지)
  bestiary_defs?: Record<string, BestiaryDef>;                         // D63 지식 본문 정의(옛 판은 없음)
  [k: string]: unknown;
}

export interface Gear { name: string; bonus?: number; [k: string]: unknown }

export interface Bot {
  char: Char; job?: string; sex?: string;
  x: number; y: number; hp: number; maxhp: number; bag?: number;
  alive: boolean; won: boolean; potions?: number;
  weapon?: Gear | null; armor?: Gear | null;
  order?: string | null;                         // 'm0' 'b1' 'f2' 'exit' '@x,y' 'follow:b1' 'rest' …
  status?: string[] | null;                      // 상태 태그(둔화·출혈·중독 …)
  relations?: Record<Char, Record<string, number>>;   // 관계 뼈 {other: {talk: n, gave: n, bond: n …}}
  aware_of?: unknown[];
  [k: string]: unknown;
}

export interface Monster {
  id: number; kind: string; x: number; y: number; hp: number; maxhp: number;
  alive: boolean; state: 'SLEEPING' | 'HUNTING' | 'FLEEING' | string;
  concealed: boolean; target?: Char | null; desperate?: boolean;
  [k: string]: unknown;
}

export interface Feature {
  id: number; type: string;                      // exit/treasure/chest/fountain/potion/weapon/armor/grave/npc/stairs_up …
  name: string; x: number; y: number; room_id?: number | null;
  concealed?: boolean; perception_gate?: number;
  [k: string]: unknown;
}

export interface Trap {
  x: number; y: number; kind: string; name: string; dc?: number; dmg?: number;
  hidden: boolean; sprung: boolean;
  [k: string]: unknown;
}

export interface Room { id: number; x: number; y: number; w: number; h: number; type: string; neighbours?: number[] }

/** 마을 v1(2026-09-11) 시각 레이어 — 엔진은 무시하고 클라이언트만 그린다(art/town-v1/layout.json 유래, 좌표는 오프셋 전). */
export interface TownVisual {
  schema: string; tileSize: number; offset: [number, number];
  ground: { tile: string; rect: [number, number, number, number] }[];
  buildings: { id: string; name?: string; texture: string; x: number; footY: number; width: number }[];
  spaces?: { id: string; name: string; regions: { id: string; name: string; role: string; rects: [number, number, number, number][] }[] };
  props: { frame: number; x: number; y: number }[];
  npcs: { id: string; row: number; cell: [number, number] }[];
}

export interface LevelLine {
  skill_acquisitions?: unknown[];
  reaction_stats?: ReactionStats;
  kind: 'level'; turn: number; depth: number; w: number; h: number;
  master_seed?: number; level_seed?: number;
  grid: string[];                                // h 개의 w 폭 문자열: '#' 벽 · '.' 바닥 · '+' 문(빛을 막고 지나감)
  exit: [number, number];
  rooms: Room[]; features: Feature[]; traps: Trap[]; monsters: Monster[];
  party: Bot[];                                  // 이 층 개시 스냅샷(스폰 칸)
  visual?: TownVisual;                           // 마을 v1 시각 레이어(마을 층만)
}

export interface Then { type: string; target?: string }

export interface Decision {
  reaction?: 'like' | 'dislike'; reaction_to?: string;
  type: string; target?: string; item?: string; form?: string; choice?: number; then?: Then[];
  note?: string; say?: string; to?: string; say_kind?: string; reason?: string; src?: string;
  skipped?: boolean;
  relation?: { to: Char; line: string };
  floor_line?: string;
  brain_degraded?: { what: string; key?: string; sticky?: boolean };   // D62(09-13) 안전 차단 → 몸짓 서술 접고 한 판단(접었음을 남긴다)
  book_line?: { key: string; text: string };                           // D55 도감평 — 해금 순간·N번 조우 뒤 캐릭터가 남긴 인식 한 줄
  [k: string]: unknown;
}

/** 이벤트는 type 별로 필드가 다르다(STREAM_FORMAT '이벤트 어휘 전수'). 소비자가 type/result 로 좁힌다. */
export interface StreamEvent {
  type: string; char?: Char; result?: string; target?: string; target_id?: string;
  to?: unknown;                                  // walk: [x,y] / give·bond: 받는 봇 char
  reason?: string; job?: string;
  id?: string; monster?: string;                 // 몹 이벤트
  [k: string]: unknown;
}

export interface InboxMsg { from: Char; text: string; turn?: number; to?: string; kind?: string; social_event_id?: string }
export interface Reply { from: Char; to: Char; kind: string; how: string }

export interface SocialEvent {
  skill_id?: string; skill_name?: string;
  id: string; type: 'say' | 'give' | 'bond' | 'use' | 'skill'; actor: Char; recipients: Char[];
  turn: number; depth: number; floor_id: string; source_action_id?: string;
  text?: string; say_kind?: string; addressed_to?: string; what?: string; item?: string; form?: string; heal?: number;
}
export interface Reaction {
  id: string; actor: Char; to: Char; value: 'like' | 'dislike'; reaction_to: string;
  turn: number; depth: number; floor_id: string; source: SocialEvent;
}
export interface ReactionCounts { like: number; dislike: number }
export interface ReactionSummary {
  total: ReactionCounts; by_actor: Record<Char, ReactionCounts>;
  pairs: ({ from: Char; to: Char } & ReactionCounts)[];
  events: number; opportunities: number; unrated: number;
}
export interface ReactionFloor extends ReactionSummary { id: string; depth: number; since: number; until?: number }
export interface ReactionStats { run: ReactionSummary; floor: ReactionFloor }

export interface TickLine {
  social_events?: SocialEvent[]; reactions?: Reaction[]; reaction_stats?: ReactionStats;
  kind: 'tick'; turn: number;
  inbox?: Record<Char, InboxMsg[]>;
  decisions?: Record<Char, Decision>;
  hails?: Record<Char, Char[]>;
  answers?: Record<Char, Record<Char, boolean>>;
  replies?: Reply[];
  events: StreamEvent[];
  bots: Bot[]; monsters: Monster[]; features: Feature[]; traps: Trap[];
  [k: string]: unknown;
}

export interface DescendLine {
  reaction_summary?: ReactionFloor;
  kind: 'descend' | 'ascend'; turn: number; to_depth: number;
  party: { char: Char; hp: number; bag: number; potions?: number }[]; fallen: Char[];
  pages?: Record<Char, string>;                                        // D59 수첩 — 층을 떠나는 순간 캐릭터가 쓴 한 장(실패한 캐릭터는 키 없음)
}

export interface EndLine {
  reaction_summary?: ReactionSummary; reaction_floors?: ReactionFloor[];
  kind: 'end'; turn: number; outcome: 'escaped' | 'wiped' | 'timeout' | string; depth: number;
  survivors: Char[]; fallen: Char[]; remaining?: Char[]; bots: Bot[];
}

export type StreamLine = RunMeta | LevelLine | TickLine | DescendLine | EndLine | { kind: string; [k: string]: unknown };

/* ───────────── 파생(스트림에 없는 것 = 계산으로 얻는 것) ───────────── */

/** 한 층의 누적 장부 — 프레임은 '이 프레임까지의 길이'만 들고, 리스트는 층이 공유한다(임의 틱 시킹 공짜). */
export interface LevelState {
  idx: number;                                   // 몇 번째 level 라인인가(프레임의 levelIdx 와 조인)
  line: LevelLine;
  town: boolean;                                 // 마을 층(전체 시야)
  visitedList: [number, number][];               // 발자국(파티 공용) — 파생 규칙: 스폰 칸 + 이후 틱 봇 좌표 누적
  seenList: Record<Char, [number, number][]>;    // 캐릭터별 '본 적 있는 칸'(시야 누적, 관전 근사)
}

export interface Frame {
  social_events?: SocialEvent[]; reactions?: Reaction[]; reaction_stats?: ReactionStats;
  kind: 'level' | 'tick';
  idx: number;                                   // run.frames 안 번호
  turn: number;
  levelIdx: number;                              // 층 전이 감지 = 값 변화 (파일 순서 조인 — turn 으로 조인 금지)
  level: LevelLine;
  bots: Bot[]; monsters: Monster[]; features: Feature[]; traps: Trap[];
  events: StreamEvent[];
  decisions: Record<Char, Decision>;
  inbox: Record<Char, InboxMsg[]>;
  hails?: Record<Char, Char[]>;
  answers?: Record<Char, Record<Char, boolean>>;
  replies?: Reply[];
  descend?: DescendLine;                         // 이 틱 뒤에 층 전이(다음 프레임이 level)
  facing: Record<Char, Dir>;                     // 직전 프레임과의 좌표 차(안 움직이면 유지, 처음은 front)
  moved: Record<Char, boolean>;                  // 이 프레임에서 걸었나(트윈·걷기 애니의 방아쇠)
  vis: Record<Char, Set<string>>;                // 이 프레임에서 그 봇이 보는 칸 "x,y"(죽음·하강=빈 집합, 마을=전부)
  seen: Record<Char, number>;                    // levelState.seenList[char] 의 이 프레임까지 길이
  visited: number;                               // levelState.visitedList 의 이 프레임까지 길이
}

export interface Run {
  meta: RunMeta | null;
  end: EndLine | null;
  party: PartyMember[];
  frames: Frame[];
  levels: LevelState[];
  names: Record<Char, string>;
  jobs: Record<Char, string>;
  colors: Record<Char, string>;
  looks: Record<Char, Look>;
  deathTurn: Record<Char, number>;
  sight: number;
  town: boolean;
}
