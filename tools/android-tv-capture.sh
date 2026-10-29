#!/usr/bin/env bash
set -euo pipefail
mkdir -p capture
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
adb shell input keyevent KEYCODE_DPAD_DOWN
sleep 1
adb exec-out screencap -p > capture/focus-down-1.png
adb shell input keyevent KEYCODE_DPAD_DOWN
sleep 1
adb exec-out screencap -p > capture/focus-down-2.png
adb shell input keyevent KEYCODE_DPAD_CENTER
sleep 12
adb exec-out screencap -p > capture/tv-playing.png
adb shell screenrecord --time-limit 8 /sdcard/cancha.mp4 &
recording=$!
sleep 2
adb shell input keyevent KEYCODE_DPAD_DOWN
sleep 2
adb shell input keyevent KEYCODE_DPAD_UP
wait "$recording"
adb pull /sdcard/cancha.mp4 capture/tv-loop.mp4
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb pull /sdcard/window.xml capture/window.xml
