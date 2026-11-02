#!/bin/sh
# Builds the 3-minute demo video from the real studio. Needs: API on :8000 and studio on :3000 (recorded runs in
# artifacts/runs, live Meta calls allowed = 0), macOS `say`, ffmpeg, Playwright with Chrome (frontend/node_modules).
#   sh demo/video/build.sh <work_dir>        -> <work_dir>/eventproof_demo.mp4
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
W=${1:?work dir}
mkdir -p "$W"
VOICE=${VOICE:-Samantha}
RATE=${RATE:-172}
GAP=0.6   # silence between scenes

# 1. narration, one file per scene (docs/DEMO_SCRIPT.md -> narration.txt)
i=1
while IFS= read -r line; do
  say -v "$VOICE" -r "$RATE" -o "$W/n$i.aiff" "$line"
  i=$((i + 1))
done < "$HERE/narration.txt"
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
python3 - "$W" <<'EOF'
import json, subprocess, sys
w = sys.argv[1]
d = {str(i): float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                            "csv=p=0", f"{w}/n{i}.aiff"]).decode()) for i in range(1, 8)}
json.dump(d, open(f"{w}/durations.json", "w"), indent=1)
EOF

# 2. studio scenes (2-5) and cards (1, 6a, 6b, 7)
node "$HERE/record.mjs" "$W" "$W/durations.json"
node "$HERE/cards.mjs" "$W"

# 3. one MP4 per scene: picture + its narration + a short gap
V="-c:v libx264 -pix_fmt yuv420p -preset medium -crf 20 -r 30"
A="-c:a aac -b:a 160k -ar 48000 -ac 2"
seg() {  # seg <n> <video input args...>: picture for the narration length + gap
  n=$1; shift
  len=$(python3 -c "print(round($(dur "$W/n$n.aiff") + $GAP + 0.6, 2))")
  ffmpeg -loglevel error -y "$@" -i "$W/n$n.aiff" -filter_complex "[1:a]apad[a]" -map 0:v -map "[a]" -t "$len" $V $A "$W/seg$n.mp4"
}
card() { echo "-loop 1 -framerate 30 -i $W/$1.png"; }
# shellcheck disable=SC2046
seg 1 $(card card_1)
for n in 2 3 4 5; do
  f=$(python3 -c "import json;print(json.load(open('$W/scenes.json'))['$n']['file'])")
  lead=$(python3 -c "import json;print(json.load(open('$W/scenes.json'))['$n']['lead'])")
  seg "$n" -ss "$lead" -i "$f"
done
# scene 6: the figure, then the pooled table (split at 55 % of the narration)
L6=$(dur "$W/n6.aiff")
S6=$(python3 -c "print(round($L6 * 0.55, 2))")
T6=$(python3 -c "print(round($L6 + $GAP + 0.6, 2))")
ffmpeg -loglevel error -y -loop 1 -framerate 30 -t "$S6" -i "$W/card_6a.png" -loop 1 -framerate 30 -i "$W/card_6b.png" \
  -i "$W/n6.aiff" -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0,trim=duration=$T6[v];[2:a]apad[a]" \
  -map "[v]" -map "[a]" -t "$T6" $V $A "$W/seg6.mp4"
# shellcheck disable=SC2046
seg 7 $(card card_7)

# 4. concatenate
: > "$W/list.txt"
for n in 1 2 3 4 5 6 7; do echo "file '$W/seg$n.mp4'" >> "$W/list.txt"; done
ffmpeg -loglevel error -y -f concat -safe 0 -i "$W/list.txt" -c copy -movflags +faststart "$W/eventproof_demo.mp4"
echo "$W/eventproof_demo.mp4 $(dur "$W/eventproof_demo.mp4") s"
