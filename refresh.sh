#!/usr/bin/env bash
# Dependency-light version of the refresh for phones (Termux): needs only curl, awk, sed, grep.
# Reads NAUKRI_USERNAME, NAUKRI_PASSWORD, RESUME_DRIVE_URL, RESUME_NAME from ./.env next to this script.
# One attempt, no retries: any failure prints the reason and exits non-zero.
set -euo pipefail
cd "$(dirname "$0")"

set -a; . ./.env; set +a
: "${NAUKRI_USERNAME:?}" "${NAUKRI_PASSWORD:?}" "${RESUME_DRIVE_URL:?}" "${RESUME_NAME:?}"

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
STATIC_JS_BASE="https://static.naukimg.com/s/5/105/j/"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
JAR="$WORK/cookies"
BODY="$WORK/body"

die() { echo "FAILED: $*" >&2; exit 1; }

# call METHOD URL [curl args...]: sets $BODY, dies unless HTTP 2xx.
call() {
  local method="$1" url="$2" code; shift 2
  code="$(curl -sS --max-time 30 -o "$BODY" -w '%{http_code}' -X "$method" -b "$JAR" -c "$JAR" \
    -H "user-agent: $UA" -H "accept: application/json" -H "appid: 105" -H "clientid: d3skt0p" \
    -H "x-requested-with: XMLHttpRequest" "$@" "$url")" || die "$method $url (network error)"
  [[ "$code" == 2* ]] || die "$method $url -> $code: $(head -c 300 "$BODY")"
}

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

# 1. Resume from Drive
file_id="$(printf '%s' "$RESUME_DRIVE_URL" | sed -nE 's#.*/file/d/([A-Za-z0-9_-]+).*#\1#p; s#.*[?&]id=([A-Za-z0-9_-]+).*#\1#p' | head -n1)"
[[ -n "$file_id" ]] || die "no file id in RESUME_DRIVE_URL"
PDF="$WORK/resume.pdf"
curl -sSfL --max-time 60 -o "$PDF" "https://drive.google.com/uc?export=download&id=$file_id" || die "Drive download failed"
[[ "$(head -c 4 "$PDF")" == "%PDF" ]] || die "Drive file is not a PDF (is the link shared with 'Anyone with the link'?)"
FILENAME="${RESUME_NAME}_$(date -u +%d-%m-%Y).pdf"

# 2. Login
call POST "https://www.naukri.com/central-login-services/v1/login" \
  -H "content-type: application/json" -H "referer: https://www.naukri.com/nlogin/login" \
  -H "systemid: jobseeker" \
  --data "{\"username\":\"$(json_escape "$NAUKRI_USERNAME")\",\"password\":\"$(json_escape "$NAUKRI_PASSWORD")\"}"
TOKEN="$(awk '$6 == "nauk_at" {print $7}' "$JAR" | head -n1)"
[[ -n "$TOKEN" ]] || die "login gave no token (wrong credentials, or Naukri asked for OTP/MFA)"
BEARER="authorization: Bearer $TOKEN"

# 3. Profile id
call GET "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard" \
  -H "$BEARER" -H "systemid: Naukri"
PROFILE_ID="$(sed -nE 's/.*"profileId"[[:space:]]*:[[:space:]]*"?([A-Za-z0-9]+).*/\1/p' "$BODY" | head -n1)"
[[ -n "$PROFILE_ID" ]] || die "profile id not found"

# 4. formKey (lives in Naukri's mnj JS bundle, whose version changes)
# first_value FILE ANCHOR RE: first `d="value"` (RE) after the first ANCHOR; empty ANCHOR = whole file.
first_value() {
  tr -d '\n' < "$1" | awk -v anchor="$2" -v re="$3" '{
    t = $0
    if (anchor != "") { i = index(t, anchor); if (!i) exit; t = substr(t, i + length(anchor)) }
    if (match(t, re)) { v = substr(t, RSTART, RLENGTH); sub(/"$/, "", v); sub(/.*"/, "", v); print v }
  }'
}

call GET "https://www.naukri.com/mnjuser/profile" -H "$BEARER" -H "systemid: Naukri"
app_js="$(grep -oE '(https?:)?//static\.naukimg\.com/s/5/105/j/app_v[0-9]+\.min\.js' "$BODY" | head -n1 || true)"
mnj_urls=()
if [[ -n "$app_js" ]]; then
  [[ "$app_js" == //* ]] && app_js="https:$app_js"
  call GET "$app_js"
  ver="$(grep -oE 'mnj[[:space:]]*:[[:space:]]*"_v[0-9]+"' "$BODY" | head -n1 | sed -E 's/.*"(_v[0-9]+)"/\1/' || true)"
  [[ -n "$ver" ]] && mnj_urls+=("${STATIC_JS_BASE}mnj${ver}.min.js")
fi
mnj_urls+=("${STATIC_JS_BASE}mnj_v323.min.js" "${STATIC_JS_BASE}mnj_v299.min.js")

FORM_KEY=""
for url in "${mnj_urls[@]}"; do
  curl -sSf --max-time 30 -A "$UA" -o "$WORK/mnj.js" "$url" 2>/dev/null || continue
  FORM_KEY="$(first_value "$WORK/mnj.js" 'key:"initUploader"' 'd[[:space:]]*=[[:space:]]*"[A-Za-z0-9]+"' | head -n1)"
  [[ -n "$FORM_KEY" ]] || FORM_KEY="$(first_value "$WORK/mnj.js" '' 'd[[:space:]]*=[[:space:]]*"[A-Za-z0-9]{10,}"' | head -n1)"
  [[ -n "$FORM_KEY" ]] && break
done
[[ -n "$FORM_KEY" ]] || die "formKey not found in Naukri JS bundle"

# 5. Upload the PDF
FILE_KEY="U$(head -c 512 /dev/urandom | LC_ALL=C tr -dc 'A-Za-z0-9' | head -c 13 || true)"
call POST "https://filevalidation.naukri.com/file" \
  -H "origin: https://www.naukri.com" -H "referer: https://www.naukri.com/" -H "systemid: fileupload" \
  -F "file=@$PDF;filename=$FILENAME;type=application/pdf" \
  -F "formKey=$FORM_KEY" -F "fileName=$FILENAME" -F "uploadCallback=true" -F "fileKey=$FILE_KEY"
# Naukri sometimes remaps the key: use the first key of the JSON response.
if grep -qE '^[[:space:]]*\{[[:space:]]*"[^"]+"' "$BODY" && ! grep -q "\"$FILE_KEY\"" "$BODY"; then
  FILE_KEY="$(sed -nE 's/^[[:space:]]*\{[[:space:]]*"([^"]+)".*/\1/p' "$BODY" | head -n1)"
fi

# 6. Attach it as the profile resume
call POST "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/$PROFILE_ID/advResume" \
  -H "$BEARER" -H "systemid: 105" -H "content-type: application/json" \
  -H "origin: https://www.naukri.com" -H "referer: https://www.naukri.com/mnjuser/profile" \
  -H "x-http-method-override: PUT" \
  --data "{\"textCV\":{\"formKey\":\"$FORM_KEY\",\"fileKey\":\"$FILE_KEY\"}}"

echo "OK: profile $PROFILE_ID refreshed as $FILENAME"
