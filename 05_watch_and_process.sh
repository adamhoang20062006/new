#!/usr/bin/env bash
# =============================================================================
# 05_watch_and_process.sh — Auto-watch input folder and trigger pipeline
# Runs as a background daemon. New files dropped in input/ auto-process.
# Uses inotifywait (or polling fallback if not available).
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
INPUT_DIR="$PIPELINE_DIR/input"
LOG="$PIPELINE_DIR/logs/watcher.log"
PID_FILE="$PIPELINE_DIR/watcher.pid"

mkdir -p "$PIPELINE_DIR/logs"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# ── Check if already running ───────────────────────────────────────────────────
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "⚠ Watcher already running (PID $(cat "$PID_FILE"))"
    echo "  Stop it: kill $(cat "$PID_FILE")"
    exit 1
fi

echo $$ > "$PID_FILE"
log "Watcher started (PID $$)"
log "Watching: $INPUT_DIR"

# ── Trigger pipeline for a new file ───────────────────────────────────────────
process_new_file() {
    local FILE="$1"
    log "New file detected: $FILE"
    log "Starting pipeline..."
    bash "$PIPELINE_DIR/01_process_videos.sh" >> "$LOG" 2>&1
    bash "$PIPELINE_DIR/02_transcribe.sh" >> "$LOG" 2>&1
    log "Pipeline complete for: $FILE"
}

# ── Use inotifywait if available (better) ─────────────────────────────────────
if command -v inotifywait &>/dev/null; then
    log "Using inotifywait for file watching"
    inotifywait -m -e close_write,moved_to --format '%f' "$INPUT_DIR" 2>>"$LOG" | \
    while IFS= read -r FILENAME; do
        # Only process video files
        EXT="${FILENAME##*.}"
        EXT_LOWER=$(echo "$EXT" | tr '[:upper:]' '[:lower:]')
        case "$EXT_LOWER" in
            mp4|mkv|mov|avi|webm|m4v|flv|wmv|ts|mxf)
                process_new_file "$FILENAME"
                ;;
            *)
                log "Ignoring non-video file: $FILENAME"
                ;;
        esac
    done
else
    # Polling fallback (check every 30s)
    log "inotifywait not found — using polling (30s interval)"
    log "Install for better performance: sudo apt-get install -y inotify-tools"

    SEEN_FILES=""
    while true; do
        CURRENT=$(find "$INPUT_DIR" -maxdepth 1 -type f \
            \( -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.mov" \
               -o -iname "*.avi" -o -iname "*.webm" -o -iname "*.m4v" \) \
            -printf "%f\n" | sort | tr '\n' '|')

        if [ "$CURRENT" != "$SEEN_FILES" ]; then
            NEW=$(comm -13 \
                <(echo "$SEEN_FILES" | tr '|' '\n' | sort) \
                <(echo "$CURRENT" | tr '|' '\n' | sort))
            if [ -n "$NEW" ]; then
                process_new_file "$NEW"
            fi
            SEEN_FILES="$CURRENT"
        fi
        sleep 30
    done
fi
