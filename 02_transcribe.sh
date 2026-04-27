#!/usr/bin/env bash
# =============================================================================
# 02_transcribe.sh — Whisper.cpp Batch Transcription (100% FREE)
# Generates SRT + VTT subtitle files for all processed videos
# Uses local whisper.cpp — no API costs, no internet needed
# =============================================================================
# Models available (larger = more accurate, slower on e2-micro):
#   tiny.en   ~75 MB  — fastest, lower accuracy
#   base.en   ~142 MB — good balance ← DEFAULT
#   small.en  ~466 MB — better accuracy (~3-4x slower)
#   medium.en ~1.5 GB — high accuracy (~8x slower) — may OOM on e2-micro 1GB RAM
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
WHISPER_DIR="$PIPELINE_DIR/whisper.cpp"
OUTPUT_DIR="$PIPELINE_DIR/output"
SUB_DIR="$PIPELINE_DIR/subtitles"
AUDIO_TMP="$PIPELINE_DIR/audio_tmp"
LOG_DIR="$PIPELINE_DIR/logs"
LOG="$LOG_DIR/transcribe_$(date +%Y%m%d_%H%M%S).log"

# ── Config ────────────────────────────────────────────────────────────────────
MODEL="${WHISPER_MODEL:-base.en}"   # Override: WHISPER_MODEL=small.en bash 02_transcribe.sh
THREADS="${WHISPER_THREADS:-2}"     # e2-micro has 2 vCPUs
LANGUAGE="en"                       # Override: WHISPER_LANG=es bash 02_transcribe.sh (or use auto)

mkdir -p "$SUB_DIR" "$AUDIO_TMP" "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# ── Validate whisper.cpp ───────────────────────────────────────────────────────
if [ ! -f "$WHISPER_DIR/main" ] && [ ! -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
    echo "❌ whisper.cpp not found. Run 00_bootstrap.sh first."
    exit 1
fi

# Detect binary location
if [ -f "$WHISPER_DIR/build/bin/whisper-cli" ]; then
    WHISPER_BIN="$WHISPER_DIR/build/bin/whisper-cli"
elif [ -f "$WHISPER_DIR/main" ]; then
    WHISPER_BIN="$WHISPER_DIR/main"
else
    echo "❌ whisper binary not found. Rebuild whisper.cpp."
    exit 1
fi

MODEL_FILE="$WHISPER_DIR/models/ggml-${MODEL}.bin"
if [ ! -f "$MODEL_FILE" ]; then
    log "Downloading model: $MODEL..."
    bash "$WHISPER_DIR/models/download-ggml-model.sh" "$MODEL" 2>&1 | tee -a "$LOG"
fi

log "Whisper binary: $WHISPER_BIN"
log "Model: $MODEL ($MODEL_FILE)"
log "Threads: $THREADS | Language: $LANGUAGE"
echo ""

# ── Find processed MP4 files ───────────────────────────────────────────────────
mapfile -t MP4_FILES < <(find "$OUTPUT_DIR" -maxdepth 1 -name "*.mp4" | sort)
TOTAL=${#MP4_FILES[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "❌ No MP4 files in $OUTPUT_DIR"
    echo "   Run 01_process_videos.sh first."
    exit 1
fi

log "Found $TOTAL video(s) to transcribe"

DONE=0
SKIPPED=0
FAILED=0

for MP4 in "${MP4_FILES[@]}"; do
    BASENAME=$(basename "$MP4")
    NAME="${BASENAME%.mp4}"
    SRT_OUT="$SUB_DIR/${NAME}.srt"
    VTT_OUT="$SUB_DIR/${NAME}.vtt"
    WAV_TMP="$AUDIO_TMP/${NAME}.wav"

    log "─────────────────────────────────────────────────"
    log "Transcribing: $BASENAME"

    if [ -f "$SRT_OUT" ]; then
        log "  SKIP: SRT already exists → $SRT_OUT"
        ((SKIPPED++)) || true
        continue
    fi

    # ── Step 1: Extract 16kHz mono WAV (required by whisper.cpp) ─────────────
    log "  Extracting audio (16kHz mono WAV)..."
    ffmpeg -y -i "$MP4" \
        -vn \
        -acodec pcm_s16le \
        -ar 16000 \
        -ac 1 \
        "$WAV_TMP" \
        2>>"$LOG"

    if [ ! -f "$WAV_TMP" ]; then
        log "  ✗ FAILED: Audio extraction failed for $BASENAME"
        ((FAILED++)) || true
        continue
    fi

    WAV_SIZE=$(du -sh "$WAV_TMP" | cut -f1)
    log "  Audio extracted: $WAV_SIZE"

    # ── Step 2: Run whisper.cpp transcription ──────────────────────────────────
    log "  Running Whisper transcription (this may take a while on e2-micro)..."
    log "  TIP: On e2-micro, expect ~1-2x realtime for base.en model"

    "$WHISPER_BIN" \
        -m "$MODEL_FILE" \
        -f "$WAV_TMP" \
        -l "$LANGUAGE" \
        -t "$THREADS" \
        --output-srt \
        --output-vtt \
        --output-file "$SUB_DIR/${NAME}" \
        --print-progress \
        2>>"$LOG"

    # Cleanup audio tmp
    rm -f "$WAV_TMP"

    if [ -f "$SRT_OUT" ]; then
        SRT_LINES=$(wc -l < "$SRT_OUT")
        log "  ✓ SRT generated: $SRT_OUT ($SRT_LINES lines)"
        log "  ✓ VTT generated: $VTT_OUT"
        ((DONE++)) || true
    else
        log "  ✗ FAILED: No SRT output for $BASENAME"
        ((FAILED++)) || true
    fi
done

echo ""
log "═══════════════════════════════════════════════"
log " TRANSCRIPTION COMPLETE"
log "  Done    : $DONE"
log "  Skipped : $SKIPPED"
log "  Failed  : $FAILED"
log "  SRT/VTT : $SUB_DIR"
log "═══════════════════════════════════════════════"

if [ "$DONE" -gt 0 ]; then
    echo ""
    echo "➜ To burn subtitles into video: bash $PIPELINE_DIR/04_burn_subtitles.sh"
    echo "➜ To upload to YouTube:         bash $PIPELINE_DIR/03_upload_youtube.sh"
fi
