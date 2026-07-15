#!/usr/bin/env bash
set -euo pipefail

ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
TMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TMP_ROOT"' EXIT

PROJECT="$TMP_ROOT/project"
VIDEO_FOLDER="$PROJECT/videos/example"
FAKE_PYTHON="$TMP_ROOT/fake-python"

mkdir -p "$PROJECT/.auth-wechat-channels" "$VIDEO_FOLDER"
printf '{}\n' > "$PROJECT/.cheat-state.json"
printf 'stale report\n' > "$VIDEO_FOLDER/report.md"

cat > "$FAKE_PYTHON" <<'FAKE'
#!/usr/bin/env bash
if [[ "${1:-}" == "-c" ]]; then
  exit "${FAKE_IMPORT_STATUS:-0}"
fi
exit 7
FAKE
chmod +x "$FAKE_PYTHON"

set +e
CHEAT_PYTHON="$FAKE_PYTHON" bash "$ADAPTER_DIR/run.sh" example "$VIDEO_FOLDER" >/dev/null 2>&1
status=$?
set -e

if [[ "$status" -ne 7 ]]; then
  echo "expected crawler exit 7, got $status" >&2
  exit 1
fi
if [[ -e "$VIDEO_FOLDER/report.md" ]]; then
  echo "stale report survived a failed crawler run" >&2
  exit 1
fi

printf 'stale report\n' > "$VIDEO_FOLDER/report.md"
set +e
FAKE_IMPORT_STATUS=9 CHEAT_PYTHON="$FAKE_PYTHON" bash "$ADAPTER_DIR/run.sh" example "$VIDEO_FOLDER" >/dev/null 2>&1
status=$?
set -e

if [[ "$status" -ne 2 ]]; then
  echo "expected dependency exit 2, got $status" >&2
  exit 1
fi
if [[ -e "$VIDEO_FOLDER/report.md" ]]; then
  echo "stale report survived dependency validation failure" >&2
  exit 1
fi

echo "run.sh failure contract: ok"
