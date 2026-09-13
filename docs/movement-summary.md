# 이동·대기 결산

2026-09-12. `run_summary.Collector`가 `movement_summary.MovementSummary`에도 같은 스트림을 전달한다.
새 결과는 `end.summary.movement`와 결산 표에 추가된다. 엔진·두뇌·러너의 행동 처리는 바꾸지 않았다.
LLM 호출은 없다. 옛 판도 `python run_summary.py <로그>`로 같은 방식으로 집계한다.

## 세는 정보

- 캐릭터별 이동 틱: 같은 층의 연속 스냅샷에서 좌표가 달라진 횟수. 걸은 칸 수와 다르다.
- 제자리 최장: 같은 층에서 좌표가 연속으로 유지된 틱 수. 전투·휴식·대기를 모두 포함하므로 정체 판정이 아니다.
- 대기: `wait → waiting` 성공으로 시작. 종료 이유별 횟수와 종료된 구간의 평균·최장 시간.
- `wait_met`는 새 동료 인지, `wait_bored`는 대기 상한. `order_cleared`는 스냅샷에서 대기 해제만 확인된 경우로 이유를 추측하지 않는다.
- `new_decision`, `inactive`, `level_change`는 각각 새 판단, 사망/퇴장, 층 전이를 확인한 종료다.
- 끝까지 기다리는 구간은 `open_since`로 남기며 종료된 구간의 평균에 섞지 않는다.
- 대기 종료 뒤 첫 행동의 종류. 또 wait인지, goto인지 등을 따로 센다.
- 아군 goto: 작정을 포함한 요청을 action_id와 결과로 연결해 종료 이유와 그 다음 행동을 집계한다.
  `same_ally`는 같은 동료를 다시 선택, `other_ally`는 다른 동료 선택이다. 기존 `actions.goto_ally`는 실판단만 센다는 차이가 있다.
- 두 명 이상 동시에 `order=wait`인 틱. 서로 볼 수 있었는지·누구를 기다렸는지는 이 수치로 알 수 없다.

세계 시간이 멈춘 `brain_pause`는 대기 시간에 더하지 않는다. 층 전이를 보행으로 세지 않는다.
요청 id/명시 결과가 부족한 옛 로그는 `new_decision` 등 관측 가능한 사실로만 종료를 표시한다.
숫자만으로 서로 기다리는 교착이나 이동 실패의 원인을 판정하지 않는다.

옛 `end.summary`와 비교할 때 당시 저장된 갈래만 대조하므로 새 `movement` 필드 때문에 불일치를 만들지 않는다.
검증: `python verify_movement_summary.py`, `python verify_summary.py`.
