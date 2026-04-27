#!/usr/bin/env bash
# =============================================================================
# 01_process_videos.sh — FFmpeg Batch Encoder
# Converts raw video files → YouTube-optimised H.264 MP4
# + extracts smart thumbnails
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
INPUT_DIR="$PIPELINE_DIR/input"
OUTPUT_DIR="$PIPELINE_DIR/output"
THUMB_DIR="$PIPELINE_DIR/thumbnails"
LOG_DIR="$PIPELINE_DIR/logs"
LOG="$LOG_DIR/process_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$OUTPUT_DIR" "$THUMB_DIR" "$LOG_DIR"

# ── YouTube-recommended encoding settings ────────────────────────────────────
#  Resolution: preserve source (up to 1080p)
#  Video codec: H.264 (libx264) — universal YouTube compatibility
#  CRF 18 = near-lossless quality (lower = better, 18-23 is sweet spot)
#  Preset: slow = better compression (use 'medium' if CPU is too slow)
#  Audio: AAC 192k stereo — YouTube recommended
#  Profile: high / Level 4.0 — required for 1080p
#  Pixel format: yuv420p — required for compatibility
#  GOP size: half frame rate (30fps → -g 15)
#  B-frames: 2 consecutive — YouTube recommended
#  Colour space: BT.709 — YouTube standard
# ─────────────────────────────────────────────────────────────────────────────

VIDEO_CODEC="libx264"
CRF=18                    # Quality: 18 = high quality, 23 = good balance
PRESET="slow"             # Encoding speed vs compression
AUDIO_CODEC="aac"
AUDIO_BITRATE="192k"
PIXEL_FMT="yuv420p"
MAX_RATE="8M"             # Max bitrate cap for 1080p
BUFSIZE="16M"             # VBV buffer (2x maxrate)

# Thumbnail settings
THUMB_PERCENT=10          # Extract thumbnail at 10% into video
THUMB_COUNT=3             # Also generate 3 candidate thumbnails

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# ── Supported input formats ────────────────────────────────────────────────────
EXTENSIONS=("mp4" "mkv" "mov" "avi" "webm" "m4v" "flv" "wmv" "ts" "mxf")

# ── Find all video files ───────────────────────────────────────────────────────
mapfile -t VIDEO_FILES < <(find "$INPUT_DIR" -maxdepth 2 -type f \( \
    -iname "*.mp4" -o -iname "*.mkv" -o -iname "*.mov" -o -iname "*.avi" \
    -o -iname "*.webm" -o -iname "*.m4v" -o -iname "*.flv" -o -iname "*.wmv" \
    -o -iname "*.ts" -o -iname "*.mxf" \
\) | sort)

TOTAL=${#VIDEO_FILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "❌ No video files found in $INPUT_DIR"
    echo "   Supported formats: ${EXTENSIONS[*]}"
    exit 1
fi

log "Found $TOTAL video file(s) to process"
log "Output directory: $OUTPUT_DIR"
log "CRF: $CRF | Preset: $PRESET | Audio: $AUDIO_CODEC @ $AUDIO_BITRATE"
echo ""

PROCESSED=0
FAILED=0
SKIPPED=0

for VIDEO in "${VIDEO_FILES[@]}"; do
    BASENAME=$(basename "$VIDEO")
    NAME="${BASENAME%.*}"
    OUTPUT="$OUTPUT_DIR/${NAME}.mp4"
    THUMB_BASE="$THUMB_DIR/${NAME}"

    log "─────────────────────────────────────────────────"
    log "Processing: $BASENAME"

    # Skip if already processed
    if [ -f "$OUTPUT" ]; then
        log "  SKIP: Output already exists → $OUTPUT"
        ((SKIPPED++)) || true
        continue
    fi

    # Get video duration and frame rate
    DURATION=$(ffprobe -v quiet -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$VIDEO" 2>/dev/null || echo "0")
    FPS=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=r_frame_rate \
        -of default=noprint_wrappers=1:nokey=1 "$VIDEO" 2>/dev/null | head -1 || echo "30/1")

    # Calculate GOP size (half of FPS)
    GOP=$(python3 -c "
import fractions
fps = fractions.Fraction('$FPS')
print(int(fps / 2))
" 2>/dev/null || echo "15")

    DURATION_H=$(python3 -c "
d = float('${DURATION}')
h,r = divmod(int(d), 3600)
m,s = divmod(r, 60)
print(f'{h:02d}:{m:02d}:{s:02d}')
" 2>/dev/null || echo "unknown")

    log "  Duration: $DURATION_H | FPS: $FPS | GOP: $GOP"

    # ── FFmpeg encode ──────────────────────────────────────────────────────────
    log "  Encoding to YouTube H.264 MP4..."

    ffmpeg -y \
        -i "$VIDEO" \
        -c:v "$VIDEO_CODEC" \
        -crf "$CRF" \
        -preset "$PRESET" \
        -profile:v high \
        -level:v 4.0 \
        -pix_fmt "$PIXEL_FMT" \
        -g "$GOP" \
        -bf 2 \
        -coder 1 \
        -maxrate "$MAX_RATE" \
        -bufsize "$BUFSIZE" \
        -movflags "+faststart" \
        -colorspace bt709 \
        -color_trc bt709 \
        -color_primaries bt709 \
        -c:a "$AUDIO_CODEC" \
        -b:a "$AUDIO_BITRATE" \
        -ar 48000 \
        -ac 2 \
        -metadata:s:a:0 language=eng \
        -map_metadata 0 \
        "$OUTPUT" \
        2>>"$LOG"

    if [ $? -eq 0 ]; then
        OUT_SIZE=$(du -sh "$OUTPUT" 2>/dev/null | cut -f1)
        IN_SIZE=$(du -sh "$VIDEO" 2>/dev/null | cut -f1)
        log "  ✓ Encoded: $IN_SIZE → $OUT_SIZE"
        ((PROCESSED++)) || true
    else
        log "  ✗ FAILED: $BASENAME"
        ((FAILED++)) || true
        continue
    fi

    # ── Thumbnail extraction ───────────────────────────────────────────────────
    log "  Extracting thumbnails..."

    # Primary thumbnail at 10% of duration
    THUMB_TIME=$(python3 -c "print(f'{float(\"$DURATION\") * 0.10:.1f}')" 2>/dev/null || echo "30")
    ffmpeg -y -ss "$THUMB_TIME" -i "$VIDEO" -frames:v 1 \
        -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
        -q:v 2 \
        "${THUMB_BASE}_main.jpg" \
        2>>"$LOG" && log "  ✓ Main thumbnail: ${THUMB_BASE}_main.jpg"

    # 3 candidate thumbnails spread across the video (for YouTube custom thumb)
    for i in 1 2 3; do
        T=$(python3 -c "print(f'{float(\"$DURATION\") * ($i * 0.25):.1f}')" 2>/dev/null || echo "$((i*60))")
        ffmpeg -y -ss "$T" -i "$VIDEO" -frames:v 1 \
            -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
            -q:v 2 \
            "${THUMB_BASE}_candidate_${i}.jpg" \
            2>>"$LOG"
    done
    log "  ✓ 3 candidate thumbnails generated"

    # ── Write video metadata JSON (used by uploader) ───────────────────────────
    META_FILE="$OUTPUT_DIR/${NAME}.meta.json"
    cat > "$META_FILE" <<METAJSON
{
  "source_file": "$BASENAME",
  "output_file": "${NAME}.mp4",
  "duration_seconds": $DURATION,
  "thumbnail": "${NAME}_main.jpg",
  "subtitle_file": "${NAME}.srt",
  "processed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
METAJSON
    log "  ✓ Metadata: $META_FILE"
done

echo ""
log "═══════════════════════════════════════════════"
log " BATCH COMPLETE"
log "  Processed : $PROCESSED"
log "  Skipped   : $SKIPPED (already done)"
log "  Failed    : $FAILED"
log "  Output    : $OUTPUT_DIR"
log "  Thumbnails: $THUMB_DIR"
log "  Log       : $LOG"
log "═══════════════════════════════════════════════"

if [ "$PROCESSED" -gt 0 ]; then
    echo ""
    echo "➜ Next: Run bash $PIPELINE_DIR/02_transcribe.sh to generate subtitles"
fi
