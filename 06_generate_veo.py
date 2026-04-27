#!/usr/bin/env python3
import os
import sys
import time
import argparse
from pathlib import Path

try:
    import vertexai
    from vertexai.preview.vision_models import VideoGenerationModel
except ImportError:
    print("❌ Missing dependency. Run: pip install google-cloud-aiplatform")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
INPUT_DIR    = PIPELINE_DIR / "input"
OUTPUT_DIR   = PIPELINE_DIR / "output"
STORYBOARD   = PIPELINE_DIR / "storyboard.txt"

# Create directories
for d in [INPUT_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def generate_segments(prompts, project_id, location="us-central1", fast_mode=True):
    vertexai.init(project=project_id, location=location)
    model = VideoGenerationModel.from_pretrained("veo-001")
    
    segment_paths = []
    
    print(f"\n🎬 [FAST MODE] Starting Veo generation for {len(prompts)} segments...")
    
    for i, prompt in enumerate(prompts):
        if not prompt.strip(): continue
        
        filename = f"segment_{i:03d}.mp4"
        filepath = OUTPUT_DIR / filename
        
        print(f"  [{i+1}/{len(prompts)}] Generating: \"{prompt[:50]}...\"")
        
        try:
            # Optimized for speed: 5 seconds, 24 fps
            video = model.generate_video(
                prompt=prompt,
                aspect_ratio="16:9",
                # Note: Some regions/versions support duration and fps parameters
                # duration=5 if fast_mode else 10,
                # fps=24 if fast_mode else 30
            )
            video.save(str(filepath))
            print(f"    ✓ Saved to {filename}")
            segment_paths.append(filepath)
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            
    return segment_paths

def join_videos(segment_paths, output_file):
    if not segment_paths:
        print("❌ No segments to join.")
        return

    print(f"\n拼接 [Stitching] {len(segment_paths)} segments into {output_file}...")
    
    # Create a concat list for FFmpeg
    list_path = OUTPUT_DIR / "concat_list.txt"
    with open(list_path, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p.absolute()}'\n")
            
    # Run FFmpeg concat
    os.system(f"ffmpeg -y -f concat -safe 0 -i {list_path} -c copy {output_file}")
    print(f"✅ Final video ready: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Veo 3 Video Generation & Stitching")
    parser.add_argument("--project", help="GCP Project ID (optional if gcloud is configured)")
    parser.add_argument("--location", default="us-central1", help="Vertex AI location (default: us-central1)")
    args = parser.parse_args()

    # Get project ID
    project_id = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not project_id:
        print("❌ Error: GCP Project ID not found. Use --project YOUR_PROJECT_ID")
        sys.exit(1)

    # Load storyboard
    if not STORYBOARD.exists():
        print(f"❌ storyboard.txt not found. Create it at {STORYBOARD}")
        print("   Each line in the file will be a separate video segment.")
        # Create a sample one
        with open(STORYBOARD, "w") as f:
            f.write("A cinematic shot of a futuristic city at sunset.\n")
            f.write("Close up of a robot hand picking up a glowing crystal.\n")
        print(f"   ✓ Created a sample storyboard at {STORYBOARD}")
        sys.exit(0)

    with open(STORYBOARD, "r") as f:
        prompts = [line.strip() for line in f.readlines() if line.strip()]

    if not prompts:
        print("❌ storyboard.txt is empty.")
        sys.exit(1)

    segments = generate_segments(prompts, project_id, args.location)
    
    if segments:
        final_video = OUTPUT_DIR / "veo_final_video.mp4"
        join_videos(segments, final_video)

if __name__ == "__main__":
    main()
