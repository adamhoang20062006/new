#!/usr/bin/env bash
# =============================================================================
# 00_bootstrap.sh — GCP Cloud Shell Bootstrap
# YouTube Video Pipeline: FFmpeg + Whisper.cpp (FREE) + Auto Upload
# Run this FIRST from Google Cloud Shell.
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
LOG="$PIPELINE_DIR/bootstrap.log"

echo "=============================================="
echo " YouTube Pipeline Bootstrap"
echo " $(date)"
echo "=============================================="

mkdir -p "$PIPELINE_DIR"/{input,output,thumbnails,subtitles,logs,scripts}

# ── 1. Update system & install core deps ──────────────────────────────────────
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    ffmpeg \
    python3-pip \
    python3-venv \
    git \
    cmake \
    build-essential \
    curl \
    wget \
    jq \
    2>&1 | tee -a "$LOG"

echo "✓ FFmpeg version: $(ffmpeg -version 2>&1 | head -1)"

# ── 2. Python venv ─────────────────────────────────────────────────────────────
echo "[2/7] Setting up Python virtual environment..."
python3 -m venv "$PIPELINE_DIR/venv"
source "$PIPELINE_DIR/venv/bin/activate"

pip install --upgrade pip -q
pip install -q \
    google-auth \
    google-auth-oauthlib \
    google-api-python-client \
    tqdm \
    2>&1 | tee -a "$LOG"

echo "✓ Python venv ready"

# ── 3. whisper.cpp (FREE local transcription — no API cost) ───────────────────
echo "[3/7] Building whisper.cpp (local Whisper — 100% free)..."
if [ ! -d "$PIPELINE_DIR/whisper.cpp" ]; then
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$PIPELINE_DIR/whisper.cpp" 2>&1 | tee -a "$LOG"
fi

cd "$PIPELINE_DIR/whisper.cpp"
make -j$(nproc) 2>&1 | tee -a "$LOG"

# Download base.en model (~142 MB) — good accuracy/speed balance on e2-micro
if [ ! -f "models/ggml-base.en.bin" ]; then
    echo "  Downloading Whisper base.en model (~142 MB)..."
    bash models/download-ggml-model.sh base.en 2>&1 | tee -a "$LOG"
fi

cd "$PIPELINE_DIR"
echo "✓ whisper.cpp ready"

# ── 4. Copy pipeline scripts ───────────────────────────────────────────────────
echo "[4/7] Copying pipeline scripts..."
cp "$PIPELINE_DIR/scripts/"*.sh "$PIPELINE_DIR/" 2>/dev/null || true
cp "$PIPELINE_DIR/scripts/"*.py "$PIPELINE_DIR/" 2>/dev/null || true
echo "✓ Scripts in place"

# ── 5. GCP credential check ────────────────────────────────────────────────────
echo "[5/7] Checking GCP authentication..."
if gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q "@"; then
    ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
    echo "✓ Authenticated as: $ACCOUNT"
else
    echo "⚠  Not authenticated. Run: gcloud auth login"
fi

PROJECT=$(gcloud config get-value project 2>/dev/null || echo "NOT SET")
echo "  Active project: $PROJECT"

# ── 6. Budget alert (protect $300 credit) ─────────────────────────────────────
echo "[6/7] Setting up budget alert for $300 credit protection..."
echo "  NOTE: Run 02_setup_budget.sh after setting your billing account ID."

# ── 7. Summary ─────────────────────────────────────────────────────────────────
echo "[7/7] Bootstrap complete!"
echo ""
echo "=============================================="
echo " NEXT STEPS:"
echo " 1. Place raw video files in: $PIPELINE_DIR/input/"
echo " 2. Set YouTube credentials:  $PIPELINE_DIR/client_secrets.json"
echo " 3. Run the pipeline:         bash $PIPELINE_DIR/01_process_videos.sh"
echo " 4. Upload to YouTube:        bash $PIPELINE_DIR/03_upload_youtube.sh"
echo ""
echo " Scripts summary:"
echo "  01_process_videos.sh  — FFmpeg batch encode + thumbnails"
echo "  02_transcribe.sh      — Whisper.cpp subtitles (SRT/VTT)"
echo "  03_upload_youtube.sh  — YouTube Data API v3 upload"
echo "  04_burn_subtitles.sh  — Burn SRT into final MP4 (optional)"
echo "=============================================="
