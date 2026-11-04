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
GAP=${GAP:-0.6}   # silence between scenes

# 1. narration, one file per scene (narration.txt). With AUDIO_DIR set, use recorded voice files instead
#    (n1..n8 as .wav/.mp3/.m4a, e.g. from Gemini TTS in AI Studio); otherwise the macOS voice is used.
i=1
while IFS= read -r line; do
  src=""
  if [ -n "${AUDIO_DIR:-}" ]; then for ext in wav mp3 m4a aiff; do [ -f "$AUDIO_DIR/n$i.$ext" ] && src="$AUDIO_DIR/n$i.$ext" && break; done; fi
  if [ -n "$src" ]; then ffmpeg -loglevel error -y -i "$src" -ar 48000 -ac 2 "$W/n$i.aiff"
  else say -v "$VOICE" -r "$RATE" -o "$W/n$i.aiff" "$line"; fi
  i=$((i + 1))
done < "$HERE/narration.txt"
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
python3 - "$W" <<'EOF'
import json, subprocess, sys
w = sys.argv[1]
d = {str(i): float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                            "csv=p=0", f"{w}/n{i}.aiff"]).decode()) for i in range(1, 9)}
json.dump(d, open(f"{w}/durations.json", "w"), indent=1)
EOF

# 2. studio scenes (2-6) and cards (1, 7, 8)
node "$HERE/record.mjs" "$W" "$W/durations.json"
node "$HERE/cards.mjs" "$W"

# 3. one MP4 per scene: picture + its narration + a short gap
V="-c:v libx264 -pix_fmt yuv420p -preset medium -crf 20 -r 30"
A="-c:a aac -b:a 160k -ar 48000 -ac 2"
seg() {  # seg <n> <video input args...>: picture for the narration length + gap
  n=$1; shift
  len=$(python3 -c "print(round($(dur "$W/n$n.aiff") + $GAP + ${PAD:-0.6}, 2))")
  ffmpeg -loglevel error -y "$@" -i "$W/n$n.aiff" -filter_complex "[1:a]apad[a]" -map 0:v -map "[a]" -t "$len" $V $A "$W/seg$n.mp4"
}
card() { echo "-loop 1 -framerate 30 -i $W/$1.png"; }
# shellcheck disable=SC2046
seg 1 $(card card_1)
for n in 2 3 4 5 6; do
  f=$(python3 -c "import json;print(json.load(open('$W/scenes.json'))['$n']['file'])")
  lead=$(python3 -c "import json;print(json.load(open('$W/scenes.json'))['$n']['lead'])")
  seg "$n" -ss "$lead" -i "$f"
done
# shellcheck disable=SC2046
seg 7 $(card card_7)
# shellcheck disable=SC2046
seg 8 $(card card_8)

# 4. concatenate
: > "$W/list.txt"
for n in 1 2 3 4 5 6 7 8; do echo "file '$W/seg$n.mp4'" >> "$W/list.txt"; done
ffmpeg -loglevel error -y -f concat -safe 0 -i "$W/list.txt" -c copy -movflags +faststart "$W/eventproof_demo.mp4"
echo "$W/eventproof_demo.mp4 $(dur "$W/eventproof_demo.mp4") s"
