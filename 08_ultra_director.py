#!/usr/bin/env python3
"""
08_ultra_director.py — All-in-One AI Movie Studio
Uses Gemini for storyboard, Veo 3 for video segments, gTTS for narration, FFmpeg for stitching.
"""
import os
import sys
import time
import argparse
from pathlib import Path
from typing import List

try:
    from google import genai
    from google.genai import types
    from google.genai.types import GenerateVideosConfig
    from gtts import gTTS
except ImportError as e:
    print(f"❌ Dependency Error: {e}")
    print("Run: ~/yt-pipeline/venv/bin/pip install --upgrade google-genai gTTS")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
OUTPUT_DIR = PIPELINE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_TEXT = "gemini-2.5-flash"
MODEL_VIDEO = "veo-2.0-generate-001"
# Other options: "veo-3.0-fast-generate-001", "veo-3.0-generate-001", "veo-3.1-generate-001"

# ── GLOBAL LOCKS (For extreme consistency) ────────────────────────────────────
CHARACTER_LOCK = "same male soldier, mid-30s, short hair, tactical uniform, consistent face"
ENVIRONMENT_LOCK = "same city, overcast sky, smoky war atmosphere, consistent lighting"
SHOT_TYPES = ["handheld", "drone shot", "tracking shot", "close up"]

# ── AI DIRECTOR MULTI VARIATION ───────────────────────────────────────────────

def generate_variations(client, vision, n=3):
    """Generates N storyboard variations and returns them."""
    variations = []
    print(f"🧠 Brainstorming {n} cinematic variations...")

    for i in range(n):
        prompt = f"""
You are an elite film director specializing in cinematic war simulations.

Your job is to transform the idea below into a visually stunning, emotionally intense 4-scene storyboard optimized for AI video generation (Veo).

VISION: "{vision}"

DIRECTING RULES:
- Every scene must feel like a moment from a high-budget film
- Use specific visual language: camera angle, movement, lighting, environment
- Include human elements (soldiers, civilians, command rooms, pilots, etc.)
- Maintain strong continuity (each scene progresses in time)
- Focus on clarity + intensity, not abstract descriptions
- Avoid generic phrases

OUTPUT FORMAT (STRICT):
STYLE: [3-6 words describing cinematic style, lighting, realism, tone]
SCENE 1: [one sentence]
SCENE 2: [one sentence]
SCENE 3: [one sentence]
SCENE 4: [one sentence]

IMPORTANT:
- Each scene must be ONE sentence only
- Each sentence must be highly visual and concrete
- Do NOT explain — only describe what is seen on screen
"""
        try:
            response = client.models.generate_content(
                model=MODEL_TEXT,
                contents=prompt
            )
            lines = response.text.strip().split("\n")
            style, scenes = "", []
            for line in lines:
                line = line.strip()
                if line.startswith("STYLE:"):
                    style = line.replace("STYLE:", "").strip()
                elif line.startswith("SCENE") and ":" in line:
                    content = line.split(":", 1)[1].strip()
                    if content:
                        scenes.append(content)

            if len(scenes) == 4:
                variations.append((style, scenes))
                print(f"  ✓ Variation {i+1}: {style}")
        except Exception as e:
            print(f"  ⚠ Variation {i+1} failed: {e}")

    return variations


# ── SIMPLE SCORING ENGINE ─────────────────────────────────────────────────────

def score_story(scenes: List[str]) -> int:
    """Scores a storyboard for cinematic intensity."""
    score = 0
    keywords = ["explosion", "camera", "soldier", "fire", "smoke", "panic",
                 "running", "tracking", "drone", "rain", "bullet", "tank"]
    for s in scenes:
        s_low = s.lower()
        for k in keywords:
            if k in s_low:
                score += 2
        if len(s.split()) > 15:
            score += 1
    return score


def pick_best(variations):
    if not variations:
        return None, None
    scored = [(score_story(scenes), style, scenes) for style, scenes in variations]
    scored.sort(reverse=True)
    winner = scored[0]
    print(f"🏆 Best storyboard selected (score: {winner[0]})")
    return winner[1], winner[2]


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────

def build_prompt(style, scene, prev_scene, shot_type):
    continuity = f"Follow the action from: {prev_scene[:100]}." if prev_scene else ""
    return f"""{style}, cinematic realism, 8k.
{CHARACTER_LOCK}. {ENVIRONMENT_LOCK}.
{shot_type}.
{continuity}
{scene}""".strip()


# ── VIDEO GENERATION (Veo 3.1 via google-genai SDK) ──────────────────────────

def generate_video_segments(client, style, scenes):
    """Generates video segments using Veo 3.1."""
    paths = []
    prev = None

    for i, scene in enumerate(scenes):
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        prompt = build_prompt(style, scene, prev, shot)
        out = OUTPUT_DIR / f"ultra_seg_{i}.mp4"

        print(f"  🎬 Generating Scene {i+1}/{len(scenes)}...")
        print(f"     Prompt: {prompt[:80]}...")

        try:
            # Start the long-running video generation operation
            operation = client.models.generate_videos(
                model=MODEL_VIDEO,
                prompt=prompt,
                config=GenerateVideosConfig(
                    number_of_videos=1,
                    duration_seconds=8,
                    aspect_ratio="16:9",
                ),
            )

            # Poll until the operation completes
            print(f"     ⏳ Waiting for Veo to finish (this takes 2-5 min per scene)...")
            while not operation.done:
                time.sleep(15)
                operation = client.operations.get(operation)

            # Save the generated video
            if operation.response and operation.response.generated_videos:
                video = operation.response.generated_videos[0].video
                # Write the video bytes to a file
                with open(out, "wb") as f:
                    f.write(video.video_bytes)
                paths.append(out)
                print(f"     ✓ Scene {i+1} saved to {out.name}")
            else:
                print(f"     ❌ Scene {i+1}: No video returned.")

            prev = scene

        except Exception as e:
            print(f"     ❌ Scene {i+1} failed: {e}")

    return paths


# ── TTS NARRATION ─────────────────────────────────────────────────────────────

def generate_voice(scenes: List[str]) -> Path:
    print("🔊 Generating AI Narration...")
    text = ". ".join(scenes)
    tts = gTTS(text=text, lang="en", slow=False)
    audio_path = OUTPUT_DIR / "voice.mp3"
    tts.save(str(audio_path))
    return audio_path


# ── SUBTITLE GENERATION ──────────────────────────────────────────────────────

def generate_subtitle(scenes: List[str], duration_per_scene=8) -> Path:
    print("📝 Generating Subtitles...")
    srt_path = OUTPUT_DIR / "subtitles.srt"

    def fmt(t):
        mm = t // 60
        ss = t % 60
        return f"00:{mm:02d}:{ss:02d},000"

    with open(srt_path, "w") as f:
        for i, scene in enumerate(scenes):
            start = i * duration_per_scene
            end = start + duration_per_scene
            f.write(f"{i+1}\n{fmt(start)} --> {fmt(end)}\n{scene}\n\n")
    return srt_path


# ── FINAL STITCH ─────────────────────────────────────────────────────────────

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
    sub_path = str(subtitle.absolute()).replace("\\", "/").replace(":", "\\\\:")
    os.system(
        f"ffmpeg -y -i {temp} -i {audio} "
        f"-vf \"subtitles='{sub_path}'\" "
        f"-c:v libx264 -c:a aac -shortest {final}"
    )

    return final


# ── MAIN ─────────────────────────────────────────────────────────────────────

def run(vision, project, location):
    # Initialize the genai client for Vertex AI
    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
    )

    # Step 1: AI Director brainstorms storyboards
    variations = generate_variations(client, vision, n=3)
    style, scenes = pick_best(variations)

    if not scenes:
        print("❌ Could not generate a storyboard. Try a different vision.")
        return

    for i, s in enumerate(scenes):
        print(f"  📖 Scene {i+1}: {s}")

    # Step 2: Generate video segments with Veo 3.1
    paths = generate_video_segments(client, style, scenes)
    if not paths:
        print("❌ No video segments were generated.")
        return

    # Step 3: Generate narration
    audio = generate_voice(scenes)

    # Step 4: Generate subtitles
    subs = generate_subtitle(scenes)

    # Step 5: Stitch everything together
    final = stitch_video(paths, audio, subs)

    print(f"\n✅ MISSION COMPLETE: {final}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ultra Director — AI Movie Studio")
    parser.add_argument("vision", help="The vision for your movie (in quotes)")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", default="us-central1", help="Vertex AI region")
    args = parser.parse_args()

    pid = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ Error: GCP Project ID required. Use --project or set DEVSHELL_PROJECT_ID.")
        sys.exit(1)

    run(args.vision, pid, args.location)
