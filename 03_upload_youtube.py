#!/usr/bin/env python3
"""
03_upload_youtube.py — YouTube Data API v3 Batch Uploader
Uploads processed MP4s from output/ to YouTube with:
  - Title, description, tags from metadata JSON or interactive prompt
  - Custom thumbnail upload
  - SRT subtitle track upload
  - Resumable upload (survives network interruptions)
  - Rate-limit safe (respects YouTube API quota)

SETUP (one-time):
  1. Go to https://console.cloud.google.com/
  2. Enable "YouTube Data API v3"
  3. Create OAuth 2.0 credentials → Desktop App
  4. Download JSON → save as ~/yt-pipeline/client_secrets.json
  5. Run: python3 03_upload_youtube.py
  6. First run opens a browser to authorise — token saved for future runs.
"""

import os
import sys
import json
import time
import glob
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError:
    print("❌ Missing dependencies. Run: pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR    = Path.home() / "yt-pipeline"
OUTPUT_DIR      = PIPELINE_DIR / "output"
THUMB_DIR       = PIPELINE_DIR / "thumbnails"
SUB_DIR         = PIPELINE_DIR / "subtitles"
LOG_DIR         = PIPELINE_DIR / "logs"
SECRETS_FILE    = PIPELINE_DIR / "client_secrets.json"
TOKEN_FILE      = PIPELINE_DIR / "youtube_token.json"
UPLOADED_LOG    = PIPELINE_DIR / "uploaded.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# YouTube API quota: 10,000 units/day
# video.insert = 1,600 units
# thumbnail.set = 50 units
# captions.insert = 400 units
# Safe daily limit: ~5 uploads/day (8,000 units)

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# ── Auth ───────────────────────────────────────────────────────────────────────
def get_authenticated_service():
    creds = None

    if not SECRETS_FILE.exists():
        log.error(f"❌ client_secrets.json not found at {SECRETS_FILE}")
        log.error("   Download from: GCP Console → APIs & Services → Credentials → OAuth 2.0 Client IDs")
        sys.exit(1)

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            log.info("Refreshing access token...")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
            
            # Special handling for Google Cloud Shell
            if os.environ.get('DEVSHELL_PROJECT_ID'):
                log.info("Detected Cloud Shell environment.")
                log.info("1. Click the link below to authorize.")
                log.info("2. After authorizing, you will see a 'Site can't be reached' error on localhost.")
                log.info("3. Copy the ENTIRE URL from your browser's address bar (the one starting with http://localhost...)")
                log.info("4. Paste that URL here:")
                creds = flow.run_local_server(host='localhost', port=8080, open_browser=False)
            else:
                log.info("Opening browser for YouTube authorisation...")
                creds = flow.run_local_server(port=0)

        # Save token for next run
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        log.info(f"✓ Token saved to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


# ── Resumable video upload ─────────────────────────────────────────────────────
def upload_video(youtube, video_path: Path, title: str, description: str,
                 tags: list, category_id: str = "22",
                 privacy: str = "private") -> str | None:
    """
    Upload a video. Returns YouTube video ID on success.
    Retries up to 5 times on transient errors.
    privacy: 'private' | 'unlisted' | 'public'
    category_id: 22 = People & Blogs, 28 = Science & Tech, 24 = Entertainment
    """
    body = {
        "snippet": {
            "title": title[:100],         # YouTube max title length
            "description": description[:5000],
            "tags": tags[:500],           # YouTube max tag string
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        }
    }

    file_size = video_path.stat().st_size
    log.info(f"  Uploading: {video_path.name} ({file_size / 1e9:.2f} GB)")

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024   # 10 MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    retry = 0
    max_retries = 5
    retry_exceptions = (HttpError,)

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"\r  Progress: {pct}% ({pct * file_size // 100 / 1e6:.0f} MB)", end="", flush=True)
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504] and retry < max_retries:
                retry += 1
                wait = 2 ** retry
                log.warning(f"  Retry {retry}/{max_retries} after {wait}s (HTTP {e.resp.status})")
                time.sleep(wait)
            elif e.resp.status == 403:
                log.error(f"  ❌ 403 Forbidden — check OAuth scopes or quota")
                return None
            elif e.resp.status == 400:
                log.error(f"  ❌ 400 Bad Request: {e}")
                return None
            else:
                raise

    print()  # newline after progress
    video_id = response.get("id")
    log.info(f"  ✓ Uploaded! Video ID: {video_id}")
    log.info(f"  🔗 https://studio.youtube.com/video/{video_id}/edit")
    return video_id


# ── Thumbnail upload ───────────────────────────────────────────────────────────
def upload_thumbnail(youtube, video_id: str, thumb_path: Path):
    log.info(f"  Setting thumbnail: {thumb_path.name}")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(str(thumb_path), mimetype="image/jpeg")
    ).execute()
    log.info(f"  ✓ Thumbnail set")


# ── Caption upload ─────────────────────────────────────────────────────────────
def upload_captions(youtube, video_id: str, srt_path: Path):
    log.info(f"  Uploading captions: {srt_path.name}")
    body = {
        "snippet": {
            "videoId": video_id,
            "language": "en",
            "name": "English (Auto-generated by Whisper)",
            "isDraft": False,
        }
    }
    youtube.captions().insert(
        part="snippet",
        body=body,
        media_body=MediaFileUpload(str(srt_path), mimetype="application/octet-stream")
    ).execute()
    log.info(f"  ✓ Captions uploaded")


# ── Load / save uploaded log ───────────────────────────────────────────────────
def load_uploaded() -> dict:
    if UPLOADED_LOG.exists():
        with open(UPLOADED_LOG) as f:
            return json.load(f)
    return {}

def save_uploaded(data: dict):
    with open(UPLOADED_LOG, "w") as f:
        json.dump(data, f, indent=2)


# ── Interactive metadata prompt ────────────────────────────────────────────────
def prompt_metadata(name: str, meta: dict) -> dict:
    print(f"\n{'═'*50}")
    print(f"Video: {name}")
    print(f"{'═'*50}")

    default_title = meta.get("title") or name.replace("_", " ").replace("-", " ").title()
    title = input(f"Title [{default_title}]: ").strip() or default_title

    default_desc = meta.get("description") or f"Video processed with YouTube pipeline. {datetime.now().strftime('%B %Y')}"
    print(f"Description [{default_desc[:60]}...]: ", end="")
    description = input().strip() or default_desc

    default_tags = meta.get("tags") or ""
    tags_input = input(f"Tags (comma-separated) [{default_tags}]: ").strip() or default_tags
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    privacy_options = {"1": "private", "2": "unlisted", "3": "public"}
    privacy_input = input("Privacy [1=private, 2=unlisted, 3=public] (default: 1): ").strip() or "1"
    privacy = privacy_options.get(privacy_input, "private")

    return {"title": title, "description": description, "tags": tags, "privacy": privacy}


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Upload videos to YouTube")
    parser.add_argument("--auto", action="store_true", help="Non-interactive: use .meta.json files for all metadata")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--video", help="Upload a single specific video file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without actually uploading")
    args = parser.parse_args()

    # Find videos to upload
    if args.video:
        mp4_files = [Path(args.video)]
    else:
        mp4_files = sorted(OUTPUT_DIR.glob("*.mp4"))

    if not mp4_files:
        log.error(f"❌ No MP4 files found in {OUTPUT_DIR}")
        sys.exit(1)

    log.info(f"Found {len(mp4_files)} video(s) to upload")

    uploaded = load_uploaded()
    youtube = None if args.dry_run else get_authenticated_service()

    results = {"success": [], "skipped": [], "failed": []}

    for mp4 in mp4_files:
        name = mp4.stem

        if name in uploaded:
            log.info(f"SKIP: {name} already uploaded → {uploaded[name]['video_id']}")
            results["skipped"].append(name)
            continue

        # Load metadata
        meta_file = OUTPUT_DIR / f"{name}.meta.json"
        meta = {}
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)

        # Get upload metadata
        if args.auto:
            title = meta.get("title") or name.replace("_", " ").replace("-", " ").title()
            description = meta.get("description") or f"Processed by YouTube pipeline on {datetime.now().strftime('%Y-%m-%d')}"
            tags = meta.get("tags") or []
            privacy = args.privacy
        else:
            m = prompt_metadata(name, meta)
            title, description, tags, privacy = m["title"], m["description"], m["tags"], m["privacy"]

        # Find thumbnail
        thumb_candidates = [
            THUMB_DIR / f"{name}_main.jpg",
            THUMB_DIR / f"{name}_candidate_1.jpg",
        ]
        thumb_path = next((t for t in thumb_candidates if t.exists()), None)

        # Find SRT subtitle
        srt_path = SUB_DIR / f"{name}.srt"

        # ── Upload ──────────────────────────────────────────────────────────────
        if args.dry_run:
            log.info(f"[DRY RUN] Would upload: {mp4.name}")
            log.info(f"  Title: {title}")
            log.info(f"  Privacy: {privacy}")
            log.info(f"  Thumbnail: {thumb_path}")
            log.info(f"  Subtitles: {srt_path if srt_path.exists() else 'not found'}")
            continue

        try:
            video_id = upload_video(youtube, mp4, title, description, tags, privacy=privacy)
            if not video_id:
                results["failed"].append(name)
                continue

            # Upload thumbnail
            if thumb_path:
                try:
                    upload_thumbnail(youtube, video_id, thumb_path)
                except Exception as e:
                    log.warning(f"  ⚠ Thumbnail upload failed: {e}")

            # Upload subtitles
            if srt_path.exists():
                try:
                    upload_captions(youtube, video_id, srt_path)
                except Exception as e:
                    log.warning(f"  ⚠ Captions upload failed: {e}")

            # Log success
            uploaded[name] = {
                "video_id": video_id,
                "title": title,
                "uploaded_at": datetime.utcnow().isoformat() + "Z",
                "url": f"https://youtu.be/{video_id}",
            }
            save_uploaded(uploaded)
            results["success"].append(name)

            # Rate limit: pause 5s between uploads to be safe
            if len(mp4_files) > 1:
                log.info("  Pausing 5s before next upload...")
                time.sleep(5)

        except HttpError as e:
            log.error(f"  ❌ Upload failed: {e}")
            results["failed"].append(name)
        except KeyboardInterrupt:
            log.info("\nInterrupted. Progress saved to uploaded.json")
            sys.exit(0)

    # ── Summary ─────────────────────────────────────────────────────────────────
    print(f"\n{'═'*50}")
    print(f" UPLOAD SUMMARY")
    print(f"  Uploaded : {len(results['success'])}")
    print(f"  Skipped  : {len(results['skipped'])} (already done)")
    print(f"  Failed   : {len(results['failed'])}")
    if results["success"]:
        print(f"\n Uploaded videos:")
        for name in results["success"]:
            info = uploaded.get(name, {})
            print(f"  ✓ {info.get('title', name)}")
            print(f"    → {info.get('url')}")
    print(f"{'═'*50}")


if __name__ == "__main__":
    main()
