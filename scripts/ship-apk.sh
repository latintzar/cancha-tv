#!/usr/bin/env bash
# Ship the Cancha APK + update the self-update manifest atomically.
# Usage: ship-apk.sh   (run after `./gradlew :app:assembleRelease`)
#
# Builds nothing — it signs the already-built release APK, pushes it to the prod
# static dir, then writes ${CANCHA_DEPLOY_DIR:?Set the recipient static directory}/app-version.json with the EXACT
# versionCode/versionName from the APK so the in-app updater advertises the truth.
# Forgetting the manifest is the one footgun that silently breaks auto-update — this
# derives it from the APK so they can never drift.
set -euo pipefail

SDK="${ANDROID_HOME:?Set the recipient Android SDK path}"
BT=$SDK/build-tools/34.0.0
ANALYZER=$SDK/cmdline-tools/latest/bin/apkanalyzer
APK="${CANCHA_APK_PATH:?Set the built APK path}"
KS="${CANCHA_ANDROID_KEYSTORE:?Set the recipient keystore path}"
SIGNED=${TMPDIR:-/tmp}/cancha-shipped-$$.apk
PROD="${CANCHA_DEPLOY_HOST:?Set the recipient deployment host}"
APK_URL="${CANCHA_APK_PUBLIC_URL:?Set the recipient HTTPS APK URL}"

[ -f "$APK" ] || { echo "No release APK — run ./gradlew :app:assembleRelease first"; exit 1; }

echo "Signing (v1+v2+v3)…"
"$BT/apksigner" sign --ks "$KS" --ks-key-alias "${CANCHA_ANDROID_KEY_ALIAS:?Set the recipient signing alias}" \
  --ks-pass env:CANCHA_ANDROID_STORE_PASSWORD --key-pass env:CANCHA_ANDROID_KEY_PASSWORD \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --in "$APK" --out "$SIGNED"
"$BT/apksigner" verify "$SIGNED" >/dev/null

VCODE=$("$ANALYZER" manifest version-code "$SIGNED")
VNAME=$("$ANALYZER" manifest version-name "$SIGNED")
echo "Shipping versionCode=$VCODE versionName=$VNAME"

cat > ${TMPDIR:-/tmp}/cancha-version-$$.json <<EOF
{"version_code": $VCODE, "version_name": "$VNAME", "url": "$APK_URL", "notes": "Cancha $VNAME"}
EOF

sudo rsync -avz -e ssh "$SIGNED" "$PROD:${CANCHA_DEPLOY_DIR:?Set the recipient static directory}/cancha-latest.apk"
sudo rsync -avz -e ssh ${TMPDIR:-/tmp}/cancha-version-$$.json "$PROD:${CANCHA_DEPLOY_DIR:?Set the recipient static directory}/app-version.json"

echo "Verifying…"
sleep 2
curl -sk --max-time 10 "https://5-161-178-146-cancha.sslip.io/v1/app/latest"; echo
echo "Done — installed apps < $VCODE will auto-update."
rm -f "$SIGNED"
