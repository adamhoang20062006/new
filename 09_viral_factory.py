#!/usr/bin/env python3
"""
09_viral_factory.py — The Ultimate Automated Content Factory
Integrates Retention Engine, Topic Engine, CTR Engine, and Per-Scene Audio Sync.
"""
import os
import sys
import time
import json
import random
import argparse
from pathlib import Path
from typing import List

try:
    from google import genai
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
MODEL_VIDEO = "veo-3.1-fast-generate-001" # Veo 3.1 Fast as requested

# ── GLOBAL LOCKS ──────────────────────────────────────────────────────────────
CHARACTER_LOCK = "same male soldier, mid-30s, short hair, tactical uniform, consistent face"
ENVIRONMENT_LOCK = "same city, overcast sky, smoky war atmosphere, consistent lighting"
SHOT_TYPES = ["handheld", "drone shot", "tracking shot", "close up"]

# ── 3. TOPIC ENGINE ───────────────────────────────────────────────────────────
def generate_topics():
    base = [
        "What happens if an alien mothership attacks Earth",
        "What happens if AI controls a futuristic robot army",
        "What happens if a rogue AI launches an orbital strike",
        "What happens during a cyberpunk city uprising",
        "What happens if mechs replace soldiers",
    ]
    modifiers = [
        "in 2077",
        "in the next 24 hours",
        "from inside the futuristic battlefield",
        "from a cyborg soldier’s perspective",
    ]
    topics = []
    for b in base:
        for m in modifiers:
            topics.append(f"{b} {m}")
    random.shuffle(topics)
    return topics

# ── 1. RETENTION ENGINE & DIRECTOR ────────────────────────────────────────────
RETENTION_RULES = """
- Scene 1: immediate chaos, no buildup
- Scene 2: escalation, situation gets worse
- Scene 3: peak destruction or turning point
- Scene 4: aftermath + unresolved consequence
"""

def score_retention(scenes):
    score = 0
    for i, s in enumerate(scenes):
        s = s.lower()
        # HOOK (Scene 1)
        if i == 0:
            if any(w in s for w in ["explosion", "panic", "attack", "suddenly", "chaos"]):
                score += 6
            if len(s.split()) < 18:
                score += 2  # punchy
        # ESCALATION
        if i == 1 and any(w in s for w in ["spreads", "intensifies", "more", "escalates"]):
            score += 4
        # PEAK CHAOS
        if i == 2 and any(w in s for w in ["massive", "devastating", "collapse", "critical"]):
            score += 5
        # OPEN LOOP
        if i == 3 and any(w in s for w in ["unknown", "uncertain", "next", "consequence", "not over"]):
            score += 6
        # HUMAN FACTOR
        if any(w in s for w in ["soldier", "civilian", "commander", "pilot"]):
            score += 2
    return score

def generate_variations(client, topic, n=5):
    variations = []
    print(f"🧠 Brainstorming {n} variations for retention...")

    for i in range(n):
        prompt = f"""
You are an elite film director specializing in cinematic war simulations.
Transform this topic into a visually stunning 4-scene storyboard optimized for AI video generation (Veo).

TOPIC: "{topic}"

DIRECTING RULES:
{RETENTION_RULES}
- Include human/cyborg elements.
- Maintain strong continuity.
- Focus on clarity + intensity, not abstract descriptions.
- CRITICAL VEO SAFETY: Keep action PG-13. Do NOT use words like blood, gore, kill, murder, death, dismemberment, or terror. Use "plasma fire", "explosions", "evading", "impact" instead.

OUTPUT FORMAT (STRICT):
STYLE: [3-6 words describing cinematic style, lighting, realism, tone]
SCENE 1: [one sentence]
SCENE 2: [one sentence]
SCENE 3: [one sentence]
SCENE 4: [one sentence]
"""
        try:
            response = client.models.generate_content(model=MODEL_TEXT, contents=prompt)
            lines = response.text.strip().split("\n")
            style, scenes = "", []
            for line in lines:
                line = line.strip()
                if line.startswith("STYLE:"):
                    style = line.replace("STYLE:", "").strip()
                elif line.startswith("SCENE") and ":" in line:
                    content = line.split(":", 1)[1].strip()
                    if content: scenes.append(content)

            if len(scenes) == 4:
                variations.append((style, scenes))
        except Exception as e:
            print(f"  ⚠ Variation {i+1} failed: {e}")

    return variations

def pick_best(variations):
    if not variations: return None, None
    scored = [(score_retention(scenes), style, scenes) for style, scenes in variations]
    scored.sort(reverse=True)
    winner = scored[0]
    print(f"🏆 Best storyboard selected (Retention Score: {winner[0]})")
    return winner[1], winner[2]

def build_prompt(style, scene, prev_scene, shot_type):
    continuity = f"Continuous action from: {prev_scene[:80]}." if prev_scene else ""
    quality_boosters = "masterpiece, ultra-detailed, photorealistic, cinematic volumetric lighting, intense color grading, 8k resolution, award-winning cinematography"
    
    # Restructured for Veo: Style -> Shot -> Action -> Continuity -> Locks -> Quality
    return f"{style}. {shot_type}. {scene}. {continuity} {CHARACTER_LOCK}. {ENVIRONMENT_LOCK}. {quality_boosters}".strip()

# ── VIDEO GENERATION ──────────────────────────────────────────────────────────
def generate_video(client, style, scenes, batch_id):
    paths = []
    prev = None
    print(f"🎬 Generating {len(scenes)} video segments...")
    
    for i, scene in enumerate(scenes):
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        prompt = build_prompt(style, scene, prev, shot)
        out = OUTPUT_DIR / f"batch_{batch_id}_seg_{i}.mp4"

        try:
            print(f"  ⏳ Scene {i+1} (Veo 3.1)...")
            operation = client.models.generate_videos(
                model=MODEL_VIDEO,
                prompt=prompt,
                config=GenerateVideosConfig(number_of_videos=1, duration_seconds=8, aspect_ratio="16:9"),
            )
            while not operation.done:
                time.sleep(15)
                operation = client.operations.get(operation)

            if operation.response and operation.response.generated_videos:
                video = operation.response.generated_videos[0].video
                with open(out, "wb") as f:
                    f.write(video.video_bytes)
                paths.append(out)
                print(f"    ✓ Saved {out.name}")
            else:
                print(f"    ❌ Scene {i+1} failed.")
            prev = scene
        except Exception as e:
            print(f"    ❌ Scene {i+1} exception: {e}")

    return paths

# ── 2. VOICE + SYNC (FIXED) ───────────────────────────────────────────────────
def generate_voice_segments(scenes, batch_id):
    print("🔊 Generating per-scene voiceover...")
    audio_paths = []
    for i, s in enumerate(scenes):
        short = s[:110] # Keep it short for punchy delivery
        tts = gTTS(text=short, lang="en", slow=False)
        path = OUTPUT_DIR / f"batch_{batch_id}_voice_{i}.mp3"
        tts.save(str(path))
        audio_paths.append(path)
    return audio_paths

def stitch_video(video_paths: List[Path], audio_paths: List[Path], batch_id):
    print("🔗 Merging audio and stitching final video...")
    merged_paths = []
    
    # Merge audio per segment
    for i, (vid, aud) in enumerate(zip(video_paths, audio_paths)):
        merged = OUTPUT_DIR / f"batch_{batch_id}_merged_{i}.mp4"
        os.system(f"ffmpeg -y -i {vid} -i {aud} -c:v copy -c:a aac -shortest {merged} -loglevel error")
        merged_paths.append(merged)

    # Concat all merged segments
    list_file = OUTPUT_DIR / f"batch_{batch_id}_concat.txt"
    final = OUTPUT_DIR / f"FINAL_FACTORY_{batch_id}.mp4"
    
    with open(list_file, "w") as f:
        for p in merged_paths:
            f.write(f"file '{p.absolute()}'\n")

    os.system(f"ffmpeg -y -f concat -safe 0 -i {list_file} -c copy {final} -loglevel error")
    return final

# ── 4. CTR ENGINE ─────────────────────────────────────────────────────────────
def generate_title(topic):
    templates = [
        f"What Happens If {topic}?",
        f"This Is What Happens If {topic}",
        f"If {topic}, This Happens",
        f"The Reality of {topic}",
    ]
    return random.choice(templates)

def advanced_thumbnail_prompt(topic):
    emotions = ["fear", "shock", "urgency", "desperation"]
    emotion = random.choice(emotions)
    return f"""
close-up human face showing {emotion},
war background, fire and smoke,
cinematic lighting, high contrast,
{topic},
ultra detailed, viral youtube thumbnail
"""

# ── 5. EXPORT METADATA ────────────────────────────────────────────────────────
def export_package(video_path, title, topic, thumb_prompt, batch_id):
    data = {
        "title": title,
        "topic": topic,
        "thumbnail_prompt": thumb_prompt,
        "video": str(video_path)
    }
    meta_path = OUTPUT_DIR / f"metadata_{batch_id}.json"
    with open(meta_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"📦 Package exported to {meta_path.name}")

# ── 6. MASTER RUN LOOP ────────────────────────────────────────────────────────
def run_full_system(project, location, num_videos=1):
    client = genai.Client(vertexai=True, project=project, location=location)
    topics = generate_topics()

    for batch_id, topic in enumerate(topics[:num_videos]):
        print(f"\n{'='*50}\n🚀 PROCESSING BATCH {batch_id}: {topic}\n{'='*50}")

        variations = generate_variations(client, topic, n=5)
        style, scenes = pick_best(variations)

        if not scenes:
            print("❌ Skipping topic due to variation failure.")
            continue
            
        for i, s in enumerate(scenes):
            print(f"  📖 Scene {i+1}: {s}")

        video_paths = generate_video(client, style, scenes, batch_id)
        if len(video_paths) != 4:
            print("❌ Video generation incomplete. Skipping stitch.")
            continue

        audio_paths = generate_voice_segments(scenes, batch_id)
        final_video = stitch_video(video_paths, audio_paths, batch_id)

        title = generate_title(topic)
        thumb = advanced_thumbnail_prompt(topic)
        export_package(final_video, title, topic, thumb, batch_id)

        print(f"✅ BATCH {batch_id} COMPLETE: {final_video.name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Viral Content Factory")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--count", type=int, default=1, help="Number of videos to generate in loop")
    args = parser.parse_args()

    pid = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ Error: GCP Project ID required.")
        sys.exit(1)

    run_full_system(pid, args.location, args.count)
