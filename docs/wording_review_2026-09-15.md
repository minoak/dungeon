# 임시 문장 검토표 (2026-09-15)

> SilenceBreaker 가 D69~D75 에서 임시로 넣은 문장을 한 곳에 모았다. **파트너의 문장이 사양이다** — '교정' 칸을 채우면 그대로 정의 JSON 에 옮긴다
> (비우면 지금 문장 유지, `삭제` 라 쓰면 그 칸을 없앤다). `{name}`·`{monsters}`·`{traps}`·`{quests}`·`{done}`·`{undone}` 은 엔진이 채우는 자리라 남겨 둔다.
> `prompts/npc_prompt.md`(NPC 두뇌 지침)도 임시 — 파일을 직접 고쳐도 된다.

| # | 파일 | 키 | 지금 문장(임시) | 교정 |
|---|---|---|---|---|
| 1 | `entities/npc/apprentice_adventurer.json` | `npc.role` | 파티를 못 구한 견습 모험자 | |
| 2 | `entities/npc/apprentice_adventurer.json` | `npc.persona` | 들뜨고 어설프다. 모험가를 동경하고, 같이 가고 싶어 하지만 대놓고는 못 말한다. | |
| 3 | `entities/npc/apprentice_adventurer.json` | `npc.line` | 저, 저도 곧 던전에 내려갈 거예요! 아직 파티가 없지만요… | |
| 4 | `entities/npc/apprentice_adventurer.json` | `npc.line_again` | 파티… 아직 못 구했어요. 같이 가 주실 순 없죠? | |
| 5 | `entities/npc/apprentice_adventurer.json` | `npc.hail` | {name} 님! 진짜 모험가시죠? 저, 저도 언젠가는… | |
| 6 | `entities/npc/apprentice_adventurer.json` | `story.trait` | 파티를 못 구한 견습. 샛길을 서성인다 | |
| 7 | `entities/npc/apprentice_adventurer.json` | `story.history` | 길드에 등록은 했지만 아직 아무 파티도 받아주지 않았다. 남의 장비를 오래 쳐다보고, 던전 얘기가 나오면 눈이 커진다. | |
| 8 | `entities/npc/guild_receptionist.json` | `npc.role` | 원정 물품 · 의뢰 접수와 귀환 보고 | |
| 9 | `entities/npc/guild_receptionist.json` | `npc.persona` | 친절하고 사무적이다. 모험가를 존중하지만 길드 규정은 지킨다. 살아 돌아온 사람을 제일 반긴다. | |
| 10 | `entities/npc/guild_receptionist.json` | `npc.line` | 모험가 길드예요. 원정 나가는 분께 기본 물품을 드려요 — 물약 하나, 빈손이면 단검도요. | |
| 11 | `entities/npc/guild_receptionist.json` | `npc.line_again` | 아까 왔잖아요. 이번 원정 몫은 이미 드렸어요 — 살아 돌아오면 또 챙겨 드릴게요. | |
| 12 | `entities/npc/guild_receptionist.json` | `npc.hail` | {name} 님, 모험가 길드예요. 원정 나가시면 물품 챙겨 가세요. | |
| 13 | `entities/npc/guild_receptionist.json` | `npc.hail_no_potion` | {name} 님, 물약도 없이 내려가시게요? 원정 물품 받아 가세요. | |
| 14 | `entities/npc/guild_receptionist.json` | `npc.hail_board` | {name} 님, 게시판에 아직 안 맡은 의뢰가 {quests}개 있어요. 보고 가실래요? | |
| 15 | `entities/npc/guild_receptionist.json` | `npc.hail_return` | {name} 님, 돌아오셨군요! 원정 보고하시겠어요? | |
| 16 | `entities/npc/guild_receptionist.json` | `npc.line_report` | 돌아오셨군요. 의뢰 확인했어요 — {done}. 길드가 이름을 기억할게요. | |
| 17 | `entities/npc/guild_receptionist.json` | `npc.line_report_failed` | 돌아오셨군요. 맡으신 의뢰({undone})는 이번엔 못 채우셨네요 — 살아 돌아온 게 제일이에요. | |
| 18 | `entities/npc/guild_receptionist.json` | `npc.line_report_empty` | 돌아오셨군요. 이번 원정엔 맡은 의뢰가 없었네요 — 다음엔 게시판도 봐 주세요. | |
| 19 | `entities/npc/guild_receptionist.json` | `story.trait` | 원정 물품(물약, 빈손이면 단검)을 주고 의뢰 접수와 귀환 보고를 받는다 | |
| 20 | `entities/npc/guild_receptionist.json` | `story.history` | 길드 장부를 혼자 다 쓴다. 규정엔 까다롭지만 살아 돌아온 사람에게는 누구보다 먼저 웃는다. 던전엔 한 번도 내려간 적이 없다. | |
| 21 | `entities/npc/street_vendor.json` | `npc.role` | 노점 · 잡동사니 구경(아직 사고팔 수는 없다) | |
| 22 | `entities/npc/street_vendor.json` | `npc.persona` | 넉살 좋고 시끄럽다. 손님이면 누구든 붙잡는다. | |
| 23 | `entities/npc/street_vendor.json` | `npc.line` | 구경하고 가세요! 던전에서 나온 잡동사니예요. 아직 값은 안 매겼어요. | |
| 24 | `entities/npc/street_vendor.json` | `npc.line_again` | 아까 봤죠? 사고파는 건 아직이에요. 다음에 꼭. | |
| 25 | `entities/npc/street_vendor.json` | `npc.hail` | {name} 님, 구경만 해도 돼요! 던전 잡동사니 있어요~ | |
| 26 | `entities/npc/street_vendor.json` | `story.trait` | 잡동사니 구경만 된다(사고팔기는 아직 없다) | |
| 27 | `entities/npc/street_vendor.json` | `story.history` | 던전에서 나온 물건이라며 파는 것 대부분이 마을에서 만든 것이다. 목소리가 커서 번화가 어디서든 알아볼 수 있다. | |
| 28 | `entities/npc/tavern_keeper.json` | `npc.role` | 소문 · 쉬어 가는 자리 | |
| 29 | `entities/npc/tavern_keeper.json` | `npc.persona` | 말이 많고 정이 많다. 던전에서 올라온 소문을 모으는 게 낙이다. 손님이 뭘 물으면 아는 만큼만 말한다. | |
| 30 | `entities/npc/tavern_keeper.json` | `npc.line` | 주점은 아직 준비 중이야. 자리는 있으니 앉았다 가도 돼. | |
| 31 | `entities/npc/tavern_keeper.json` | `npc.line_again` | 아까 왔잖아. 아직 준비 중이라니까 — 곧 열 거야. | |
| 32 | `entities/npc/tavern_keeper.json` | `npc.hail` | {name}, 잠깐 쉬었다 가. 던전 얘기 좀 들려줘. | |
| 33 | `entities/npc/tavern_keeper.json` | `npc.hail_rumor` | {name}, 던전 내려가기 전에 들어 둬. 요즘 1층엔 {monsters}가 돈대. 함정도 {traps}개쯤 있다더라. | |
| 34 | `entities/npc/tavern_keeper.json` | `story.trait` | 1층 몬스터·함정 수를 소문으로 알려준다 | |
| 35 | `entities/npc/tavern_keeper.json` | `story.history` | 손님 말은 다 기억하고 자기 말은 반쯤 보탠다. 그래도 숫자만은 정확하다 — 틀리면 장사가 안 된다는 걸 안다. | |
| 36 | `entities/npc/temple_attendant.json` | `npc.role` | 기도 · 신의 요청 | |
| 37 | `entities/npc/temple_attendant.json` | `npc.persona` | 조용하고 다정하다. 죽은 이의 이름을 기억하고, 신의 요청이 있으면 그대로 전한다. | |
| 38 | `entities/npc/temple_attendant.json` | `npc.line` | 기도를 들었어요. 신의 축복이 담긴 물약이에요 — 마시면 몸이 한 단계 강해져요. 던전에서 돌아오면 또 들르세요. | |
| 39 | `entities/npc/temple_attendant.json` | `npc.line_again` | 오늘 기도는 이미 드렸어요. 축복은 한 원정에 한 병이에요 — 살아 돌아오면 또 드릴게요. | |
| 40 | `entities/npc/temple_attendant.json` | `npc.hail` | {name} 님, 떠나기 전에 기도하고 가세요. 신의 축복을 받아 갈 수 있어요. | |
| 41 | `entities/npc/temple_attendant.json` | `npc.hail_oracle` | {name} 님, 신께서 하실 말씀이 있어요. 잠깐 들르시겠어요? | |
| 42 | `entities/npc/temple_attendant.json` | `story.trait` | 기도를 받고 축복의 물약을 준다(원정마다 한 병) | |
| 43 | `entities/npc/temple_attendant.json` | `story.history` | 젊은 얼굴인데 마을에서 제일 오래 살았다는 말이 있다. 죽은 이의 이름을 하나도 잊지 않는다. 신의 요청이 있으면 꾸미지 않고 그대로 전한다. | |
| 44 | `entities/npc/wandering_adventurer.json` | `npc.role` | 다른 파티의 모험자 · 던전 소문 | |
| 45 | `entities/npc/wandering_adventurer.json` | `npc.persona` | 말수가 적고 피곤해 보인다. 던전 얘기는 정확하게, 그 밖엔 무심하다. | |
| 46 | `entities/npc/wandering_adventurer.json` | `npc.line` | 던전에서 막 올라온 참이야. 2층 계단 옆에 거미가 매복하더라 — 조심해. | |
| 47 | `entities/npc/wandering_adventurer.json` | `npc.line_again` | 아까 말했잖아, 2층 거미. 그것만 기억해. | |
| 48 | `entities/npc/wandering_adventurer.json` | `npc.hail` | {name}? 처음 보는 얼굴이네. 던전 내려가나? | |
| 49 | `entities/npc/wandering_adventurer.json` | `npc.hail_rumor` | {name}, 내려갈 거면 알아 둬. 1층엔 {monsters}가 있어. 함정은 {traps}개 봤어. | |
| 50 | `entities/npc/wandering_adventurer.json` | `story.trait` | 다른 파티의 모험자. 1층 몬스터·함정 수를 안다 | |
| 51 | `entities/npc/wandering_adventurer.json` | `story.history` | 혼자 다닌다. 어느 파티에 있었는지는 말하지 않고, 던전 얘기만은 정확하게 한다. 피곤해 보이지만 계속 내려간다. | |
| 52 | `entities/building/dungeon_gate.json` | `story.trait` | 계단 아래가 던전. 일행이 3칸 안에 모여야 내려간다 | |
| 53 | `entities/building/dungeon_gate.json` | `story.history` | 마을은 이 구멍 때문에 생겼다. 처음엔 울타리 하나였는데, 내려갔다 올라온 사람들이 술과 잠자리를 찾으면서 길이 나고 지붕이 올라갔다. 계단 옆 돌기둥엔 못 돌아온 이들의 이름이 새겨져 있다. | |
| 54 | `entities/building/guild_hall.json` | `building.role` | 의뢰 게시판 · 원정 물품 · 귀환 보고 | |
| 55 | `entities/building/guild_hall.json` | `story.trait` | 게시판 의뢰를 맡고, 접수원에게 원정 물품을 받고, 돌아오면 보고한다 | |
| 56 | `entities/building/guild_hall.json` | `story.history` | 던전에서 돌아오지 않는 사람이 늘자 마을 사람들이 세운 장부다. 누가 내려갔고 누가 돌아왔는지를 적는 것이 첫 일이었고, 지금도 그 일이 전부다. 의뢰는 마을 사람들이 길드에 맡긴 부탁이다. | |
| 57 | `entities/building/tavern.json` | `building.role` | 소문 · 쉬어 가는 자리 | |
| 58 | `entities/building/tavern.json` | `story.trait` | 주인이 던전 1층 소문을 안다. 쉬어 가는 자리 | |
| 59 | `entities/building/tavern.json` | `story.history` | 던전에서 올라온 사람이 처음 들르는 곳이라 소문이 여기로 모인다. 술값 대신 이야기를 받는다는 말이 있을 만큼 주인이 듣는 걸 좋아한다. 번화가 쪽 정문과 샛길 쪽 뒷문이 있다. | |
| 60 | `entities/building/temple.json` | `building.role` | 기도 · 신의 요청 | |
| 61 | `entities/building/temple.json` | `story.trait` | 성직자에게 기도하면 축복의 물약을 한 병 받는다. 신의 요청이 들리는 곳 | |
| 62 | `entities/building/temple.json` | `story.history` | 마을에서 가장 오래된 건물. 어느 신을 모시는지 묻는 이가 없고, 성직자는 "너희와 계약한 그분"이라고만 답한다. 벽에는 돌아오지 못한 모험가의 이름이 작게 적혀 있다. | |
| 63 | `entities/map/town_alley.json` | `story.trait` | 좁고 꺾이는 길. 견습 모험자가 서성인다 | |
| 64 | `entities/map/town_alley.json` | `story.history` | 주점 뒷문으로 이어지는 골목. 파티를 못 구한 이들이 여기서 나가는 파티를 눈으로 좇는다. | |
| 65 | `entities/map/town_dungeon.json` | `story.trait` | 계단이 있는 구역. 일행이 여기서 모여 내려간다 | |
| 66 | `entities/map/town_dungeon.json` | `story.history` | 돌바닥이 닳아 있다. 내려가기 전에 한 번씩 뒤를 돌아보는 자리. | |
| 67 | `entities/map/town_guild.json` | `story.trait` | 길드 건물과 게시판이 있는 구역 | |
| 68 | `entities/map/town_guild.json` | `story.history` | 던전 입구에서 가장 가까운 지붕. 원정 나가는 사람과 돌아온 사람이 여기서 엇갈린다. | |
| 69 | `entities/map/town_main_street.json` | `story.trait` | 넓고 트인 길. 노점 상인과 떠돌이 모험자가 다닌다 | |
| 70 | `entities/map/town_main_street.json` | `story.history` | 길드·주점·신전을 잇는 큰길. 낮이면 노점이 서고 지나가는 모험자가 많다. | |
| 71 | `entities/map/town_tavern.json` | `story.trait` | 주점이 있는 구역. 번화가와 샛길 양쪽으로 통한다 | |
| 72 | `entities/map/town_tavern.json` | `story.history` | 밤에 제일 시끄럽고 아침에 제일 조용하다. | |
| 73 | `entities/map/town_temple.json` | `story.trait` | 신전과 성직자가 있는 구역 | |
| 74 | `entities/map/town_temple.json` | `story.history` | 마을에서 제일 조용한 자리. 기도하러 오는 사람보다 이름을 읽으러 오는 사람이 많다. | |
| 75 | `entities/map/town_wonderland.json` | `story.trait` | 던전 위에 선 마을. 구역 여섯 | |
| 76 | `entities/map/town_wonderland.json` | `story.history` | 이름은 처음 내려간 사람이 붙였다는 말과 돌아온 사람이 붙였다는 말이 있다. 어느 쪽이든 던전이 먼저였고 마을이 나중이다. | |
| 77 | `entities/quest/goblin_cull.json` | `name` | 고블린 소탕 | |
| 78 | `entities/quest/goblin_cull.json` | `quest.goal` | 던전 1층의 고블린을 셋 처치한다 | |
| 79 | `entities/quest/goblin_cull.json` | `quest.reward` | 길드가 이름을 기억한다 | |
| 80 | `entities/quest/goblin_cull.json` | `quest.client` | 모험가 길드 | |
| 81 | `entities/quest/lost_trinket.json` | `name` | 잃어버린 장신구 | |
| 82 | `entities/quest/lost_trinket.json` | `quest.goal` | 던전에서 보물을 하나 찾아 마을로 가져온다 | |
| 83 | `entities/quest/lost_trinket.json` | `quest.reward` | 주점에서 한 끼 | |
| 84 | `entities/quest/lost_trinket.json` | `quest.client` | 주점 주인 | |
| 85 | `entities/quest/reach_floor_2.json` | `name` | 2층 답사 | |
| 86 | `entities/quest/reach_floor_2.json` | `quest.goal` | 던전 2층까지 내려가 계단을 확인하고 돌아온다 | |
| 87 | `entities/quest/reach_floor_2.json` | `quest.reward` | 길드가 이름을 기억한다 | |
| 88 | `entities/quest/reach_floor_2.json` | `quest.client` | 모험가 길드 | |

항목 88개.
