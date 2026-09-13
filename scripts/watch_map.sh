#!/usr/bin/env bash
# 깜빡임 없는 GM 맵 뷰어
# 핵심: clear 루프(빈 프레임=깜빡임) 대신, 파일이 바뀔 때만 '제자리' 덮어쓰기.
F="$HOME/dungeon/state/gm_map.txt"

tput civis 2>/dev/null                                  # 커서 숨김 (커서 깜빡임 제거)
trap 'tput cnorm 2>/dev/null; printf "\033[2J\033[H"' EXIT
printf '\033[2J'                                        # 시작 때 1회만 전체 클리어

last=""
while :; do
  cur=$(stat -c %y "$F" 2>/dev/null)                   # 파일 수정시각
  if [ "$cur" != "$last" ]; then                       # 바뀌었을 때만 그림
    last="$cur"
    printf '\033[H'                                     # 커서 홈으로 (클리어 X = 안 깜빡)
    cat "$F" 2>/dev/null
    printf '\033[0J'                                    # 새 내용 아래 잔여물만 정리
  fi
  sleep 0.2
done
