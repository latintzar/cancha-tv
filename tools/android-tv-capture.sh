#!/usr/bin/env bash
set -euo pipefail
mkdir -p capture/frames
python3 tools/first-signal.py --serve --port 8765 > capture/backend.log 2>&1 &
backend=$!
trap 'kill "$backend" 2>/dev/null || true' EXIT
for i in $(seq 1 90); do curl -fsS http://127.0.0.1:8765/v1/status >/dev/null 2>&1 && break; sleep 1; done
curl -fsS http://127.0.0.1:8765/v1/status >/dev/null
adb install android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n casa.leo.cancha.debug/casa.leo.cancha.MainActivity
sleep 12
adb shell pidof casa.leo.cancha.debug
adb exec-out screencap -p > capture/tv-guide.png
# Render the same native TV layout at a 3200px viewport; do not enlarge captured pixels.
adb shell wm size 3200x1800
adb shell wm density 533
sleep 4
adb exec-out screencap -p > capture/tv-guide-3200.png
adb shell wm size reset
adb shell wm density reset
sleep 3
adb shell input keyevent KEYCODE_DPAD_DOWN
sleep 1
adb shell input keyevent KEYCODE_DPAD_DOWN
sleep 1
adb exec-out screencap -p > capture/tv-focused.png
# Capture actual TV pixels across guide -> stream -> guide. Screenrecord on this emulator
# produced a truncated file, so bounded ADB frames are the evidence instead.
for i in $(seq 0 19); do
  if [ "$i" -eq 3 ]; then adb shell input keyevent KEYCODE_DPAD_CENTER; sleep 8; fi
  if [ "$i" -eq 14 ]; then adb shell input keyevent KEYCODE_BACK; sleep 2; fi
  printf -v frame '%03d' "$i"
  adb exec-out screencap -p > "capture/frames/$frame.png"
  sleep 0.3
done
ffmpeg -y -hide_banner -loglevel error -framerate 2 -i capture/frames/%03d.png -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -movflags +faststart capture/tv-loop.mp4
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml capture/window.xml
