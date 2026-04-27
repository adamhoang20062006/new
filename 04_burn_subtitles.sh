#!/usr/bin/env bash
# =============================================================================
# 04_burn_subtitles.sh — Burn SRT Subtitles into Video (Hardcoded/Muxed)
# Two modes:
#   HARDCODED (default): Permanently burn subtitles into video pixels
#   SOFTCODED (--soft):  Mux SRT as a separate selectable track (smaller file)
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
OUTPUT_DIR="$PIPELINE_DIR/output"
SUB_DIR="$PIPELINE_DIR/subtitles"
FINAL_DIR="$PIPELINE_DIR/final"
LOG_DIR="$PIPELINE_DIR/logs"
LOG="$LOG_DIR/burn_$(date +%Y%m%d_%H%M%S).log"

SOFT_MODE=false
FONT_NAME="Arial"
FONT_SIZE=28
FONT_COLOR="white"
OUTLINE_COLOR="black"
OUTLINE_WIDTH=2

# ── Args ───────────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --soft) SOFT_MODE=true; shift ;;
        --font) FONT_NAME="$2"; shift 2 ;;
        --size) FONT_SIZE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

mkdir -p "$FINAL_DIR" "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

if $SOFT_MODE; then
    log "Mode: SOFT (muxed subtitle track)"
    log "Note: Soft subtitles won't show on YouTube — use hard for visible subs"
else
    log "Mode: HARD (burned into video pixels)"
fi

# ── Find processed videos ──────────────────────────────────────────────────────
mapfile -t MP4_FILES < <(find "$OUTPUT_DIR" -maxdepth 1 -name "*.mp4" | sort)
TOTAL=${#MP4_FILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "❌ No MP4 files in $OUTPUT_DIR. Run 01_process_videos.sh first."
    exit 1
fi

DONE=0
SKIPPED=0
NOSUB=0

for MP4 in "${MP4_FILES[@]}"; do
    BASENAME=$(basename "$MP4")
    NAME="${BASENAME%.mp4}"
    SRT="$SUB_DIR/${NAME}.srt"
    FINAL="$FINAL_DIR/${NAME}_final.mp4"

    log "─────────────────────────────────────────────────"
    log "Video: $BASENAME"

    if [ -f "$FINAL" ]; then
        log "  SKIP: Final already exists"
        ((SKIPPED++)) || true
        continue
    fi

    if [ ! -f "$SRT" ]; then
        log "  ⚠ No SRT found — copying without subtitles"
        cp "$MP4" "$FINAL"
        ((NOSUB++)) || true
        continue
    fi

    log "  SRT: $SRT"

    if $SOFT_MODE; then
        # Softcode: mux SRT as subtitle stream (no re-encode needed)
        ffmpeg -y \
            -i "$MP4" \
            -i "$SRT" \
            -c:v copy \
            -c:a copy \
            -c:s mov_text \
            -metadata:s:s:0 language=eng \
            -metadata:s:s:0 title="English" \
            "$FINAL" \
            2>>"$LOG"
    else
        # Hardcode: burn subtitles into video stream
        # Escape colon in path for ffmpeg subtitles filter
        SRT_ESCAPED=$(echo "$SRT" | sed 's/:/\\:/g')

        ffmpeg -y \
            -i "$MP4" \
            -vf "subtitles='${SRT_ESCAPED}':force_style='FontName=${FONT_NAME},FontSize=${FONT_SIZE},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=0,Italic=0,Alignment=2,BorderStyle=1,Outline=${OUTLINE_WIDTH},Shadow=1,MarginV=30'" \
            -c:v libx264 \
            -crf 18 \
            -preset slow \
            -profile:v high \
            -level:v 4.0 \
            -pix_fmt yuv420p \
            -movflags "+faststart" \
            -c:a copy \
            "$FINAL" \
            2>>"$LOG"
    fi

    if [ -f "$FINAL" ]; then
        SIZE=$(du -sh "$FINAL" | cut -f1)
        log "  ✓ Final: $FINAL ($SIZE)"
        ((DONE++)) || true
    else
        log "  ✗ FAILED"
    fi
done

echo ""
log "═══════════════════════════════════════════════"
log " SUBTITLE BURN COMPLETE"
log "  Done    : $DONE"
log "  Skipped : $SKIPPED"
log "  No SRT  : $NOSUB (copied as-is)"
log "  Final   : $FINAL_DIR"
log "═══════════════════════════════════════════════"
echo ""
echo "➜ Final videos ready for upload in: $FINAL_DIR"
echo "   Copy them to output/ then run: bash $PIPELINE_DIR/03_upload_youtube.sh"
