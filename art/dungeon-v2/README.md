# Wonderland dungeon architecture lab

Updated 2026-09-20. The approved `concept.png` is the material and composition reference.
The comparison runs the actual Phaser client on deterministic engine snapshots.

## Run

```powershell
node art/dungeon-v2/build-runtime.mjs
node art/dungeon-v2/build-architecture.mjs
npm --prefix game run build
python art/dungeon-v2/preview_server.py --port 4228
```

Open http://127.0.0.1:4228/art/dungeon-v2/compare.html?seed=322274042&profile=concept

- **시안 스타일 · 무작위 구조**: a 42×34 layout with 5–8 rooms packed without
  fixed sectors or a required central hall. Sizes, positions and connections vary
  by seed. Large halls can be open or contain four solid columns; galleries,
  chambers and occasional two-column rooms supply the other room types.
  A randomized spanning tree and 0–2 extra connections use 2–3-cell passages.
- **기존 생성기**: the existing 56×20 production generator, for comparison.
- **입체 재구축 / 직전 구현**: projected architecture or the previous flat painter,
  using exactly the same level, entities, camera and visibility state.
- **살펴볼 곳** selects an overview or an enlarged room. The minimap pans both views.
  **캐릭터 시야** uses the first fixture character's normal client sight calculation.

The local server listens on 127.0.0.1, generates fixtures in memory, and imports
no brain backend. It does not run an autonomous playthrough or write run/state files.
The new room grammar is implemented in `concept_dungeon.py`, a Dungeon subclass;
production generator defaults and character decisions have not been changed.

## Implemented architecture

`game/src/scene/dungeonArchitecture.ts` plans exposed wall fronts, side walls,
ends, corners, pillars, oriented doors and torch positions directly from the grid.
`dungeonPrototype.ts` renders 80px wall faces and 96px column artwork over a 48px
movement grid. Walls, furnishings and actors sort by their floor contact point.
Architecture fades to 28% when a visible character is behind it, and returns to
normal when the character steps in front. Unknown elevated objects are hidden;
remembered objects are dimmed independently of the ground fog.

Floor and stone materials are sampled directly from the approved concept.
The floor uses a mirrored continuous pattern at 0.85 scale; walls have projecting
capstones, foot courses and piers. Torch falloff follows world coordinates across
wall seams. Floor lights are clipped by grid sight. Moss, ivy, stone chips,
exterior boulders, banners and storage clusters provide secondary detail.
Attached piers require at least nine cells of uninterrupted wall face, with four
plain cells at either end and eight-cell support spacing. Short walls stay plain;
corners and freestanding columns retain their structural silhouettes.

`dungeonDecor.ts` clusters furniture around opposite room corners. Small rooms
have up to four pieces; large rooms have at most twelve and about 10% occupancy.
Door approaches, passage mouths, features, exit, initial actors and traps are
reserved. The planner verifies that all remaining floor stays connected if every
furniture footprint were blocked. Columns are real engine wall cells. Barrels,
crates, jars and rubble are currently static visual furnishings: they are not yet
interactive or collision objects, and movement can cross them in a live run.

The renderer is opt-in with `dungeonArt=prototype`; `dungeonArt=flat` selects the
previous painter. Normal game URLs and town maps keep their existing renderer.

## Asset provenance and rebuilding

Built-in imagegen produced the isolated parts using the approved concept as a
reference. Exact prompts and generated source images are kept beside the lab:

| Parts | Prompt | Source | Runtime |
| --- | --- | --- | --- |
| Initial terrain | `terrain-prompt.txt` | `source/terrain.png` | `runtime/terrain.png` |
| Torch, pier, chest, stairs | `props-prompt.txt` | `source/props.png` | `runtime/props.png` |
| Previous floor | `floor-prompt.txt` | `source/floor.png` | `runtime/floor.png` |
| Furnishings, webs, banners | `decor-prompt.txt` | `source/decor.png` | `runtime/decor.png` |
| Previous wall set | `walls-prompt.txt` | `source/walls.png` | `runtime/walls.png` |
| Front/side doors, ruins, storage | `architecture-prompt.txt` | `source/architecture.png` | `runtime/architecture.png` |
| Exterior rocks, ivy, moss | `weathering-prompt.txt` | `source/weathering.png` | `runtime/weathering.png` |

`build-runtime.mjs` packs the earlier sets. `build-architecture.mjs` crops the
reference materials, packs the new 128px sprites with foot anchor 120, and checks
real alpha, nonempty bounds and crop margins. The five `runtime/concept-*.png`
files are literal material samples, not newly generated substitutes. Crop and
packing coordinates are recorded in `architecture-build.json`.

## Verification

```powershell
python art/dungeon-v2/verify-architecture.py
node art/dungeon-v2/verify-decor.mjs
npm --prefix game run build
```

`verification/architecture.json`: 100 original and 1,000 concept seeds; deterministic,
connected, distinct grids; valid actor/entity cells; real column collision;
nonoverlapping rooms, connected room graphs, varied room counts and no unplanned
isolated columns. Connection graph diversity counts labeled room graphs.

`verification/decor.json`: the actual TypeScript architecture and furnishing
planners on the same 200 maps. Checks deterministic output, unchanged input,
wall/door ownership, no duplicate props, protected approaches, and connected
floor with furnished footprints removed, and minimum wall support spacing.
Zero LLM gameplay calls.

`verification/browser.json`: browser observations for the earlier projected
pass, including repeated layout/seed changes, camera agreement, asset cleanup,
unknown/remembered visibility, and controlled actor placement on both sides of a
column. This is renderer QA, not an autonomous gameplay regression suite.

## Handoff

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for the composition rules,
rendering contracts, production integration order and remaining gameplay work.
The concept guides materials and architectural scale; it does not fix the room
graph or require a central hall. Exact object shapes and texture repetition still
differ from the single authored illustration.
