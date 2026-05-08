#!/usr/bin/env bash
set -u

fps=${_II_FPS:-20}
frame=0

cleanup() {
    printf '\033[0m\033[?25h\n'
}

trap 'cleanup; exit 0' INT TERM
trap cleanup EXIT

printf '\033[2J\033[?25l'

while :; do
    if read -r rows cols < <(stty size 2>/dev/null); then
        :
    else
        rows=40
        cols=120
    fi

    if [ "${rows:-0}" -lt 4 ]; then rows=40; fi
    if [ "${cols:-0}" -lt 20 ]; then cols=120; fi

    height=$((rows - 1))

    awk -v W="$cols" -v H="$height" -v N="$frame" '
    BEGIN {
        esc = sprintf("%c", 27)
        chars = " .:-=+*#%@"
        split("16 17 18 19 20 21 27 33 39 45 51 87 159 231", palette, " ")

        for (y = 1; y <= H; y++) {
            row = ""
            last = -1
            for (x = 1; x <= W; x++) {
                cx = (x - W * 0.5) / (W * 0.5)
                cy = (y - H * 0.5) / (H * 0.5)
                r = sqrt(cx * cx + cy * cy)
                a = atan2(cy, cx)
                v = sin(10.0 * r - N * 0.13) + sin(5.0 * a + N * 0.09) + sin((x + y) * 0.045 + N * 0.07)
                v = (v + 3.0) / 6.0
                glyph = int(v * 9.0) + 1
                if (glyph < 1) glyph = 1
                if (glyph > 10) glyph = 10
                ci = int(v * 13.0) + 1
                if (ci < 1) ci = 1
                if (ci > 14) ci = 14
                color = palette[ci]
                if (color != last) {
                    row = row esc "[38;5;" color "m"
                    last = color
                }
                row = row substr(chars, glyph, 1)
            }
            printf "%s[%d;1H%s", esc, y, row
        }
        printf "%s[0m", esc
    }'

    printf '\033[%d;1H\033[38;5;250m_ii ansi field | frame %06d | Ctrl-C stop\033[0m' "$rows" "$frame"
    sleep "$(awk -v fps="$fps" 'BEGIN { if (fps < 1) fps = 1; printf "%.4f", 1.0 / fps }')"
    frame=$((frame + 1))
done

