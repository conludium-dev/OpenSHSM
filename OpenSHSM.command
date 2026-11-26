#!/bin/zsh
cd "$(dirname "$0")" || exit 1
python3 -B experiments/wii-static-recomp/build_and_play_current.py "$@"
result=$?
if (( result != 0 )); then
    printf '\nНе удалось завершить сборку или запуск. Нажмите Enter для закрытия.\n'
    read -r
fi
exit "$result"
