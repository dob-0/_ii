#!/usr/bin/env bash
set -u

fps=${_II_FPS:-24}
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
        chars = " .,:;ox%#@"
        srand(N + 1)
        beam = 1 + (N * 2 % H)

        for (y = 1; y <= H; y++) {
            row = ""
            last = -1
            dy = y - beam
            if (dy < 0) dy = -dy

            for (x = 1; x <= W; x++) {
                v = rand() * 0.35
                v += 0.45 * exp(-dy * 0.23)
                v += 0.18 * sin((x * 0.21) + (N * 0.19))
                v += 0.10 * sin((x + y) * 0.07 - N * 0.11)
                if (x % 17 == (N + y) % 17) v += 0.45
                if (v < 0.0) v = 0.0
                if (v > 1.0) v = 1.0

                glyph = int(v * 9.0) + 1
                if (glyph < 1) glyph = 1
                if (glyph > 10) glyph = 10

                if (dy < 2) color = 231
                else if (v > 0.74) color = 51
                else if (v > 0.50) color = 45
                else if (v > 0.30) color = 27
                else color = 18

                if (color != last) {
                    row = row esc "[38;5;" color "m"
                    last = color
                }
                row = row substr(chars, glyph, 1)
            }
            printf "%s[%d;1H%s", esc, y, row
        }

        tag = "  II / SCAN " sprintf("%06d", N) "  "
        x0 = int((W - length(tag)) * 0.5)
        if (x0 < 1) x0 = 1
        y0 = int(H * 0.5)
        printf "%s[%d;%dH%s[1;37m%s%s[0m", esc, y0, x0, esc, tag, esc
    }'

    printf '\033[%d;1H\033[38;5;250m_ii ansi scan | frame %06d | Ctrl-C stop\033[0m' "$rows" "$frame"
    sleep "$(awk -v fps="$fps" 'BEGIN { if (fps < 1) fps = 1; printf "%.4f", 1.0 / fps }')"
    frame=$((frame + 1))
done

