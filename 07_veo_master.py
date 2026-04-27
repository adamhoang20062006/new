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
    print(f"🤖 AI Director (War Simulation Elite) is planning: \"{vision}\"...")
    
    vertexai.init(project=project_id, location=location)
    model = GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
You are an elite film director specializing in cinematic war simulations.

Your job is to transform the idea below into a visually stunning, emotionally intense 4-scene storyboard optimized for AI video generation (Veo).

VISION:
"{vision}"

DIRECTING RULES:
- Every scene must feel like a moment from a high-budget film
- Use specific visual language: camera angle, movement, lighting, environment
- Include human elements (soldiers, civilians, command rooms, pilots, etc.)
- Maintain strong continuity (each scene progresses in time)
- Focus on clarity + intensity, not abstract descriptions
- Avoid generic phrases

OUTPUT FORMAT (STRICT):

STYLE: [3–6 words describing cinematic style, lighting, realism, tone]

SCENE 1 (Hour 0 - First Impact):
[A single sentence describing the opening moment, including camera shot, environment, action, and mood]

SCENE 2 (Escalation):
[A single sentence showing reaction and rising tension, different location or perspective, cinematic detail]

SCENE 3 (Turning Point):
[A single sentence showing a critical decision, battle shift, or high-intensity moment]

SCENE 4 (Aftermath / Consequence):
[A single sentence showing large-scale impact, emotional weight, or global consequence]

IMPORTANT:
- Each scene must be ONE sentence only
- Each sentence must be highly visual and concrete
- Do NOT explain — only describe what is seen on screen
"""
    
    response = model.generate_content(prompt)
    lines = response.text.strip().split('\n')
    
    style = ""
    scenes = []
    
    for line in lines:
        line = line.strip()
        if line.startswith("STYLE:"):
            style = line.replace("STYLE:", "").strip()
        elif line.startswith("SCENE") and ":" in line:
            # Handle "SCENE 1 (Description): Actual Content"
            content = line.split(":", 1)[1].strip()
            if not content: continue # Skip if content is on next line
            scenes.append(content)
        elif scenes and line and not line.startswith("SCENE"):
            # If content was on the next line after SCENE X:
            if not scenes[-1]:
                scenes[-1] = line
            
    return style, [s for s in scenes if s]

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
