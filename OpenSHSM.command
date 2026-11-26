#!/bin/zsh
cd "$(dirname "$0")" || exit 1
python3 -B experiments/wii-static-recomp/build_and_play_current.py "$@"
result=$?
if (( result != 0 )); then
    language="${OPENSHSM_LANGUAGE:-${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}}"
    if [[ -z "$OPENSHSM_LANGUAGE" && ( "$language" == C || "$language" == C.* || "$language" == POSIX ) ]]; then
        language=$(/usr/bin/defaults read -g AppleLanguages 2>/dev/null |
            /usr/bin/sed -n '2s/^[[:space:]]*"\([^"_-]*\).*$/\1/p')
    fi
    if [[ "$language" == ru* || "$language" == RU* ]]; then
        printf '\nНе удалось завершить сборку или запуск. Нажмите Enter для закрытия.\n'
    else
        printf '\nBuild or launch did not finish. Press Enter to close.\n'
    fi
    read -r
fi
exit "$result"
