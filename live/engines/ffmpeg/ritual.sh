#!/usr/bin/env bash
set -euo pipefail

out=${1:-out/ritual.mkv}
dur=${2:-20}
size=${_II_SIZE:-1280x720}
fps=${_II_FPS:-30}

mkdir -p "$(dirname "$out")"

video="nullsrc=s=${size}:r=${fps}:d=${dur},format=rgb24,geq=r='128+72*sin(X/31+N/5)+44*sin((X+Y)/83+N/11)':g='118+62*sin(Y/27+N/7)+55*sin((X-Y)/71-N/13)':b='150+82*sin(sqrt((X-W/2)*(X-W/2)+(Y-H/2)*(Y-H/2))/29-N/6)',format=yuv420p"
audio="aevalsrc=0.15*sin(2*PI*55*t)+0.10*sin(2*PI*(110+22*sin(0.17*t))*t)+0.05*sin(2*PI*880*t)*lt(mod(t\,0.5)\,0.025):d=${dur}:s=48000"

ffmpeg -hide_banner -y \
    -f lavfi -i "$video" \
    -f lavfi -i "$audio" \
    -shortest \
    -c:v libx264 -preset veryfast -crf 18 \
    -c:a aac -b:a 160k \
    "$out"

