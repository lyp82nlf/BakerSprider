#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
LABEL="com.youfeng.barker-spider"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
TEMPLATE="$PROJECT_DIR/launchd/$LABEL.plist.template"

mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/logs" "$PROJECT_DIR/state"

python3 - "$TEMPLATE" "$TARGET" "$PROJECT_DIR" "$PYTHON_BIN" <<'PY'
from pathlib import Path
import sys

template, target, project_dir, python_bin = map(Path, sys.argv[1:])
content = template.read_text(encoding="utf-8")
content = content.replace("__PROJECT_DIR__", str(project_dir))
content = content.replace("__PYTHON__", str(python_bin))
target.write_text(content, encoding="utf-8")
PY

launchctl bootout "gui/$(id -u)" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
launchctl enable "gui/$(id -u)/$LABEL"

echo "Installed $LABEL"
echo "Plist: $TARGET"
echo "Logs: $PROJECT_DIR/logs/stdout.log and $PROJECT_DIR/logs/stderr.log"
