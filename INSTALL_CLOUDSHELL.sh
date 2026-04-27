#!/usr/bin/env bash
# =============================================================================
# INSTALL_CLOUDSHELL.sh — ONE-CLICK GCP CLOUD SHELL INSTALLER
# Run this in Google Cloud Shell (https://shell.cloud.google.com/):
#
#   curl -sL https://raw.githubusercontent.com/adamhoang20062006/new/main/INSTALL_CLOUDSHELL.sh | bash
#
# =============================================================================
# What this does:
#   1. Creates the pipeline directory structure
#   2. Downloads all scripts from this repo (or extracts from archive / git clone)
#   3. Runs 00_bootstrap.sh to install all deps
#   4. Guides you through YouTube API credential setup
# =============================================================================

set -euo pipefail

PIPELINE_DIR="$HOME/yt-pipeline"
REPO_URL="https://github.com/adamhoang20062006/new"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   YouTube Video Pipeline — GCP Cloud Shell       ║"
echo "║   FFmpeg + Whisper.cpp + YouTube API v3         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Verify we're in Cloud Shell ───────────────────────────────────────
if [ -z "${DEVSHELL_PROJECT_ID:-}" ]; then
  echo "⚠  This looks like it might not be Cloud Shell."
  echo "   For best results, run in: https://shell.cloud.google.com/"
fi

# ── Step 2: Check GCP project ─────────────────────────────────────────────────
PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$PROJECT" ]; then
  echo "❌ No GCP project set."
  echo "   Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi
echo "✓ Project: $PROJECT"

# ── Step 3: Enable required APIs ──────────────────────────────────────────────
echo ""
echo "[1/4] Enabling required GCP APIs..."
gcloud services enable youtube.googleapis.com --quiet 2>/dev/null || true
echo "✓ YouTube Data API v3 enabled"

# ── Step 4: Create directory structure ────────────────────────────────────────
echo ""
echo "[2/4] Creating pipeline directory structure..."
mkdir -p "$PIPELINE_DIR"/{input,output,thumbnails,subtitles,logs,final,scripts}
echo "✓ Directories created at $PIPELINE_DIR"

# ── Step 5: Obtain / set up scripts ───────────────────────────────────────────
echo ""
echo "[3/4] Setting up scripts..."

# Determine where the installer lives (empty when piped via curl | bash)
if [ -n "${BASH_SOURCE[0]:-}" ] && [ "${BASH_SOURCE[0]}" != "bash" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || SCRIPT_DIR=""
else
  SCRIPT_DIR=""
fi

# Case A: scripts are available next to this installer (archive extracted)
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/00_bootstrap.sh" ]; then
  echo "   Detected local scripts next to installer, copying into $PIPELINE_DIR..."
  for SCRIPT in 00_bootstrap.sh 01_process_videos.sh 02_transcribe.sh \
                03_upload_youtube.py 04_burn_subtitles.sh 05_watch_and_process.sh; do
    if [ -f "$SCRIPT_DIR/$SCRIPT" ]; then
      cp "$SCRIPT_DIR/$SCRIPT" "$PIPELINE_DIR/$SCRIPT"
      chmod +x "$PIPELINE_DIR/$SCRIPT" 2>/dev/null || true
      echo "    ✓ $SCRIPT"
    else
      echo "    ⚠ Missing: $SCRIPT (copy manually to $PIPELINE_DIR/)"
    fi
  done
else
  # Case B: no local scripts → try git clone
  echo "   No local scripts found; cloning from repo..."
  if [ -d "$PIPELINE_DIR/.git" ] || [ -f "$PIPELINE_DIR/00_bootstrap.sh" ]; then
    echo "   ✓ Existing checkout found in $PIPELINE_DIR"
  else
    if echo "$REPO_URL" | grep -q 'YOUR_USERNAME'; then
      echo "❌ REPO_URL is still the placeholder."
      echo "   Update REPO_URL in INSTALL_CLOUDSHELL.sh to your real GitHub repo URL."
      exit 1
    fi
    git clone "$REPO_URL" "$PIPELINE_DIR"
  fi

  # Make sure expected scripts are executable
  for SCRIPT in 00_bootstrap.sh 01_process_videos.sh 02_transcribe.sh \
                03_upload_youtube.py 04_burn_subtitles.sh 05_watch_and_process.sh; do
    if [ -f "$PIPELINE_DIR/$SCRIPT" ]; then
      chmod +x "$PIPELINE_DIR/$SCRIPT" 2>/dev/null || true
      echo "    ✓ $SCRIPT"
    else
      echo "    ⚠ Missing after clone: $SCRIPT (check your repo)."
    fi
  done
fi

# ── Step 6: Run bootstrap ─────────────────────────────────────────────────────
echo ""
echo "[4/4] Running bootstrap (installs FFmpeg, whisper.cpp, Python deps)..."
echo "      This will take 5-10 minutes on first run..."
echo ""

if [ ! -f "$PIPELINE_DIR/00_bootstrap.sh" ]; then
  echo "❌ 00_bootstrap.sh not found in $PIPELINE_DIR"
  exit 1
fi

bash "$PIPELINE_DIR/00_bootstrap.sh"

# ── Step 7: YouTube OAuth setup instructions ──────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  FINAL STEP: YouTube OAuth Credentials Setup             ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║                                                          ║"
echo "║  1. Open: https://console.cloud.google.com/apis/         ║"
echo "║     credentials?project=$PROJECT                         ║"
echo "║                                                          ║"
echo "║  2. Click 'CREATE CREDENTIALS' → 'OAuth client ID'       ║"
echo "║                                                          ║"
echo "║  3. Application type: Desktop app                        ║"
echo "║     Name: YouTube Pipeline                               ║"
echo "║                                                          ║"
echo "║  4. Click CREATE → Download JSON                         ║"
echo "║                                                          ║"
echo "║  5. In Cloud Shell, click the ⋮ menu → Upload file       ║"
echo "║     Upload the JSON as: ~/yt-pipeline/client_secrets.json║"
echo "║                                                          ║"
echo "║  6. Also add OAuth consent screen → Test users → add     ║"
echo "║     your YouTube channel's Google account                ║"
echo "║                                                          ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  READY TO RUN:                                           ║"
echo "║   Place videos in: ~/yt-pipeline/input/                  ║"
echo "║   bash ~/yt-pipeline/01_process_videos.sh                ║"
echo "║   bash ~/yt-pipeline/02_transcribe.sh                    ║"
echo "║   python3 ~/yt-pipeline/03_upload_youtube.py             ║"
echo "╚══════════════════════════════════════════════════════════╝"