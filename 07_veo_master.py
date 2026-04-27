#!/usr/bin/env python3
import os
import sys
import time
import argparse
from pathlib import Path

try:
    import vertexai
    from vertexai.preview.vision_models import VideoGenerationModel
    from vertexai.generative_models import GenerativeModel
except ImportError:
    print("❌ Missing dependencies. Run: pip install google-cloud-aiplatform")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
OUTPUT_DIR   = PIPELINE_DIR / "output"
STORYBOARD   = PIPELINE_DIR / "storyboard.txt"
STYLE_FILE   = PIPELINE_DIR / "style_prefix.txt"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def ai_director(vision, project_id, location):
    """Uses Gemini to generate a storyboard and style based on a vision."""
    print(f"🤖 AI Director is planning: \"{vision}\"...")
    
    vertexai.init(project=project_id, location=location)
    model = GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    You are a professional film director. 
    Based on the vision "{vision}", create:
    1. A style prefix (3-5 words describing the overall look, lighting, and camera style).
    2. A storyboard of 4 distinct cinematic scenes (one descriptive sentence per scene).
    
    Format your response EXACTLY like this:
    STYLE: [your style]
    SCENE 1: [description]
    SCENE 2: [description]
    SCENE 3: [description]
    SCENE 4: [description]
    """
    
    response = model.generate_content(prompt)
    lines = response.text.strip().split('\n')
    
    style = ""
    scenes = []
    
    for line in lines:
        if line.startswith("STYLE:"):
            style = line.replace("STYLE:", "").strip()
        elif "SCENE" in line and ":" in line:
            scenes.append(line.split(":", 1)[1].strip())
            
    return style, scenes

def generate_and_stitch(vision, project_id, location):
    # 1. AI Planning
    style, scenes = ai_director(vision, project_id, location)
    
    if not scenes:
        print("❌ AI Director failed to plan scenes.")
        return

    print(f"🎨 Style Chosen: {style}")
    for i, s in enumerate(scenes):
        print(f"🎬 Scene {i+1}: {s}")

    # 2. Setup Veo
    model = VideoGenerationModel.from_pretrained("veo-001")
    segment_paths = []
    seed = 42 # Keep it consistent
    
    print(f"\n🚀 Starting Veo 3 Generation (Fast Mode)...")
    
    for i, scene in enumerate(scenes):
        full_prompt = f"{style}. {scene}".strip()
        filename = f"master_seg_{i:03d}.mp4"
        filepath = OUTPUT_DIR / filename
        
        print(f"  [{i+1}/{len(scenes)}] Generating: \"{full_prompt[:60]}...\"")
        
        try:
            video = model.generate_video(
                prompt=full_prompt,
                aspect_ratio="16:9",
                seed=seed
            )
            video.save(str(filepath))
            segment_paths.append(filepath)
            print(f"    ✓ Done.")
        except Exception as e:
            print(f"    ❌ Failed: {e}")

    # 3. Stitching
    if segment_paths:
        final_video = OUTPUT_DIR / "master_final_video.mp4"
        list_path = OUTPUT_DIR / "master_concat.txt"
        with open(list_path, "w") as f:
            for p in segment_paths:
                f.write(f"file '{p.absolute()}'\n")
        
        os.system(f"ffmpeg -y -f concat -safe 0 -i {list_path} -c copy {final_video}")
        print(f"\n✨ COMPLETE! Final movie: {final_video}")

def main():
    parser = argparse.ArgumentParser(description="Veo 3 All-in-One Director")
    parser.add_argument("vision", help="What is your video about?")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", default="us-central1", help="Vertex AI location")
    args = parser.parse_args()

    project_id = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not project_id:
        print("❌ Error: Project ID missing.")
        sys.exit(1)

    generate_and_stitch(args.vision, project_id, args.location)

if __name__ == "__main__":
    main()
