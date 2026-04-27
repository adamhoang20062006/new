#!/usr/bin/env python3
import os
import random
import argparse
import sys
from pathlib import Path
from typing import List, Tuple

try:
    import vertexai
    from vertexai.preview.vision_models import VideoGenerationModel
    from vertexai.generative_models import GenerativeModel
    from gtts import gTTS
except ImportError:
    print("❌ Missing dependencies. Run: pip install google-cloud-aiplatform gTTS")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
OUTPUT_DIR = PIPELINE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_TEXT = "gemini-1.5-flash"
MODEL_VIDEO = "veo-001"

# ── GLOBAL LOCKS (For extreme consistency) ────────────────────────────────────
CHARACTER_LOCK = "same male soldier, mid-30s, short hair, tactical uniform, consistent face"
ENVIRONMENT_LOCK = "same city, overcast sky, smoky war atmosphere, consistent lighting"
SHOT_TYPES = ["handheld", "drone shot", "tracking shot", "close up"]

# ── AI DIRECTOR MULTI VARIATION ───────────────────────────────────────────────

def generate_variations(vision, project, location, n=3):
    """Generates N variations of the storyboard and picks the best."""
    vertexai.init(project=project, location=location)
    model = GenerativeModel(MODEL_TEXT)
    variations = []

    print(f"🧠 Brainstorming {n} cinematic variations...")
    
    for i in range(n):
        prompt = f"""
You are an elite film director. Create a 4-scene storyboard.

VISION: {vision}

Rules:
- 4 scenes only. One sentence per scene.
- Strong visual detail (lighting, camera, action).
- Continuous timeline.
- Focus on clarity + intensity.

OUTPUT FORMAT:
STYLE: [3-6 words]
SCENE 1: [description]
SCENE 2: [description]
SCENE 3: [description]
SCENE 4: [description]
"""
        try:
            res = model.generate_content(prompt).text.split("\n")
            style, scenes = "", []
            for line in res:
                line = line.strip()
                if line.startswith("STYLE:"):
                    style = line.replace("STYLE:", "").strip()
                elif "SCENE" in line and ":" in line:
                    scenes.append(line.split(":", 1)[1].strip())
            
            if len(scenes) == 4:
                variations.append((style, scenes))
        except Exception as e:
            print(f"  ⚠ Variation {i+1} failed: {e}")

    return variations

def score_story(scenes: List[str]) -> int:
    """Simple scoring engine to pick the most 'cinematic' variation."""
    score = 0
    keywords = ["explosion", "camera", "soldier", "fire", "smoke", "panic", "running", "tracking"]
    for s in scenes:
        s_low = s.lower()
        for k in keywords:
            if k in s_low: score += 2
        if len(s.split()) > 15: score += 1
    return score

def pick_best(variations):
    if not variations: return None, None
    scored = [(score_story(scenes), style, scenes) for style, scenes in variations]
    scored.sort(reverse=True)
    return scored[0][1], scored[0][2]

# ── PROMPT BUILDER ────────────────────────────────────────────────────────────

def build_prompt(style, scene, prev_scene, shot_type):
    continuity = f"Follow the action from: {prev_scene[:100]}." if prev_scene else ""
    return f"""
{style}, cinematic realism, 8k. 
{CHARACTER_LOCK}. {ENVIRONMENT_LOCK}.
{shot_type}.
{continuity}
{scene}
""".strip()

# ── GENERATION & RENDERING ───────────────────────────────────────────────────

def generate_video(style, scenes, project, location):
    model = VideoGenerationModel.from_pretrained(MODEL_VIDEO)
    paths = []
    prev = None

    for i, scene in enumerate(scenes):
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        prompt = build_prompt(style, scene, prev, shot)
        out = OUTPUT_DIR / f"ultra_seg_{i}.mp4"

        print(f"  🎬 Generating Scene {i+1}/{len(scenes)}...")
        try:
            video = model.generate_video(prompt=prompt, aspect_ratio="16:9", seed=42 + i)
            video.save(str(out))
            paths.append(out)
            prev = scene
        except Exception as e:
            print(f"    ❌ Scene {i+1} failed: {e}")

    return paths

def generate_voice(scenes: List[str]) -> Path:
    print("🔊 Generating AI Narration...")
    text = ". ".join(scenes)
    tts = gTTS(text=text, lang="en", slow=False)
    audio_path = OUTPUT_DIR / "voice.mp3"
    tts.save(audio_path)
    return audio_path

def generate_subtitle(scenes: List[str], total_duration=20) -> Path:
    print("📝 Generating Subtitles...")
    srt_path = OUTPUT_DIR / "subtitles.srt"
    per_scene = max(5, total_duration // len(scenes))

    def fmt(t):
        mm = t // 60
        ss = t % 60
        return f"00:{mm:02}:{ss:02},000"

    with open(srt_path, "w") as f:
        for i, scene in enumerate(scenes):
            start = i * per_scene
            end = start + per_scene
            f.write(f"{i+1}\n{fmt(start)} --> {fmt(end)}\n{scene}\n\n")
    return srt_path

def stitch_video(paths: List[Path], audio: Path, subtitle: Path):
    print("🔗 Finalizing Master Render...")
    list_file = OUTPUT_DIR / "ultra_concat.txt"
    final = OUTPUT_DIR / "ULTRA_MOVIE.mp4"
    temp = OUTPUT_DIR / "temp_silent.mp4"

    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p.absolute()}'\n")

    # 1. Join video segments
    os.system(f"ffmpeg -y -f concat -safe 0 -i {list_file} -c copy {temp}")

    # 2. Add Audio + Burn Subtitles
    # Note: subtitles filter requires path to be escaped for ffmpeg
    sub_filter = f"subtitles='{subtitle.absolute()}'"
    os.system(f"ffmpeg -y -i {temp} -i {audio} -vf \"{sub_filter}\" -c:v libx264 -c:a aac -shortest {final}")
    
    return final

def run(vision, project, location):
    variations = generate_variations(vision, project, location, n=3)
    style, scenes = pick_best(variations)
    
    if not scenes:
        print("❌ Could not generate a storyboard.")
        return

    print(f"🏆 Best Storyboard Selected (Style: {style})")
    
    paths = generate_video(style, scenes, project, location)
    if not paths: return

    audio = generate_voice(scenes)
    subs = generate_subtitle(scenes)
    final = stitch_video(paths, audio, subs)

    print(f"\n✅ MISSION COMPLETE: {final}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vision", help="The vision for your war simulation")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", default="us-central1")
    args = parser.parse_args()

    pid = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ Error: Project ID required.")
        sys.exit(1)

    run(args.vision, pid, args.location)
