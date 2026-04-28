#!/usr/bin/env python3
"""
10_script_compiler.py — AI Video Pipeline Compiler
====================================================
The meta-brain of the system. Takes a Creative Input Pack and compiles
a fully runnable Python video pipeline script.

Implements:
  1. Prompt Compiler Engine (Brain)
  2. Voice DNA Engine (Identity Layer)
  3. Series Engine (Continuity Layer)
  4. Memory Engine (Context Layer)
  5. Python Script Compiler (Execution Layer)
"""
import os
import sys
import json
import time
import argparse
import textwrap
from pathlib import Path
from typing import List, Dict, Optional

try:
    from google import genai
    from google.genai.types import Tool, VertexAISearch, GenerateContentConfig
except ImportError:
    print("❌ Run: pip install --upgrade google-genai")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
MEMORY_DIR   = PIPELINE_DIR / "memory"
OUTPUT_DIR   = PIPELINE_DIR / "output"
COMPILED_DIR = PIPELINE_DIR / "compiled_scripts"

for d in [MEMORY_DIR, OUTPUT_DIR, COMPILED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MODEL_LLM = "gemini-2.5-flash"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VOICE DNA ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_VOICE_DNA = {
    "identity": "A documentary voice from the future that knows too much but is emotionally unstable",
    "base_tone": "calm, controlled, observant",
    "spike_modes": ["urgency", "fear", "existential shock"],
    "language_rules": [
        "Short, declarative sentences",
        "Heavy use of implication, not explanation",
        "Minimal adjectives unless high impact",
        "Strategic repetition of signature phrases"
    ],
    "rhythm": "Short. Short. Then a longer, heavier sentence that changes meaning.",
    "signature_phrases": [
        "Record this moment…",
        "This is where reality fractures.",
        "You were never supposed to see this.",
        "What happens next is no longer in control.",
        "If you are still watching, you already understand too much."
    ],
    "perspective": "2nd person or omniscient observer",
    "forbidden": ["haha", "guys", "smash that like button", "yo", "what's up"]
}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MEMORY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryEngine:
    def __init__(self, series_id: str):
        self.series_id = series_id
        self.memory_file = MEMORY_DIR / f"{series_id}.json"
        self.state = self._load()

    def _load(self) -> dict:
        if self.memory_file.exists():
            with open(self.memory_file) as f:
                return json.load(f)
        return {
            "series_id": self.series_id,
            "episode_count": 0,
            "world_state": {
                "ai_control": 0.1,
                "human_resistance": 0.9,
                "city_stability": "stable",
                "destruction_index": 0.05
            },
            "character_arc": "introduction",
            "unresolved_hooks": [],
            "episodes": []
        }

    def save(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_episode_number(self) -> int:
        return self.state["episode_count"] + 1

    def get_previous_summary(self) -> str:
        if not self.state["episodes"]:
            return "This is the first episode. No prior context."
        last = self.state["episodes"][-1]
        return f"Episode {last['number']}: {last['summary']}. Unresolved: {', '.join(self.state['unresolved_hooks'][-2:])}"

    def get_world_state_prompt(self) -> str:
        ws = self.state["world_state"]
        return (
            f"World state: AI control at {int(ws['ai_control']*100)}%, "
            f"human resistance at {int(ws['human_resistance']*100)}%, "
            f"city stability: {ws['city_stability']}, "
            f"destruction index: {int(ws['destruction_index']*100)}%."
        )

    def record_episode(self, episode_data: dict):
        self.state["episode_count"] += 1
        self.state["episodes"].append(episode_data)
        # Evolve world state
        ws = self.state["world_state"]
        ws["ai_control"] = min(1.0, ws["ai_control"] + 0.12)
        ws["human_resistance"] = max(0.0, ws["human_resistance"] - 0.08)
        ws["destruction_index"] = min(1.0, ws["destruction_index"] + 0.15)
        if ws["destruction_index"] > 0.7:
            ws["city_stability"] = "collapsed"
        elif ws["destruction_index"] > 0.4:
            ws["city_stability"] = "collapsing"
        self.save()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PROMPT COMPILER ENGINE (BRAIN)
# ═══════════════════════════════════════════════════════════════════════════════

def compile_story(client, config: dict, memory: MemoryEngine, voice_dna: dict) -> dict:
    """
    The Brain. Converts creative input → structured story blueprint.
    """
    ep_num = memory.get_episode_number()
    prev_summary = memory.get_previous_summary()
    world_state = memory.get_world_state_prompt()

    master_prompt = config["master_prompt"]
    brand_style = config.get("brand_style", "dark cinematic documentary, high tension")
    hook_strategy = config.get("hook_strategy", "shock + curiosity")
    cta_strategy = config.get("cta_strategy", "subscribe + next video loop")
    num_scenes = config.get("num_scenes", 4)
    content_format = config.get("format", "long")  # "short" or "long"

    # Build the format-specific structure rules
    if content_format == "short":
        structure_rules = """
FORMAT: SHORT-FORM (15-60 seconds)
- Scene 1 (0-2s): SHOCK HOOK — immediate pattern interrupt, maximum visual impact
- Scene 2 (2-10s): CONTEXT EXPLOSION — rapid establishment of what is happening
- Scene 3 (10-40s): ESCALATION — rapid visual changes every 2-3 seconds
- Scene 4 (last 3s): LOOP ENDING — connect back to beginning, open question
RULE: No slow intro. Every 2-3 seconds must change visual/emotion.
"""
    else:
        structure_rules = f"""
FORMAT: LONG-FORM CINEMATIC ({num_scenes} scenes)
- Scene 1: HOOK — immediate chaos, no buildup, instant crisis
- Scene 2: ESCALATION — situation worsens, new threat layers revealed
- Scene 3: PEAK — maximum intensity, critical turning point
- Scene 4: CLIFFHANGER — open loop ending, unresolved consequence
{"- Scene 5-" + str(num_scenes) + ": Additional escalation/resolution beats" if num_scenes > 4 else ""}
"""

    signature_phrases_str = "\n".join(f'  - "{p}"' for p in voice_dna["signature_phrases"])

    prompt = f"""
You are the Brain of an AI Video Production System.

Your job: Convert this creative brief into a STRUCTURED STORY BLUEPRINT optimized for AI video generation (Veo 3.1).

═══ CREATIVE BRIEF ═══
MASTER PROMPT: "{master_prompt}"
BRAND STYLE: {brand_style}
HOOK STRATEGY: {hook_strategy}
CTA STRATEGY: {cta_strategy}
EPISODE: {ep_num}

═══ SERIES MEMORY ═══
{prev_summary}
{world_state}

═══ STRUCTURE ═══
{structure_rules}

═══ VOICE DNA (NARRATOR IDENTITY) ═══
Identity: {voice_dna['identity']}
Tone: {voice_dna['base_tone']}
Rhythm: {voice_dna['rhythm']}
Perspective: {voice_dna['perspective']}
Signature phrases (inject 1-2 naturally):
{signature_phrases_str}

═══ SAFETY RULES ═══
- Keep all content PG-13 safe for AI video generation
- NO blood, gore, kill, murder, death, dismemberment, terror
- USE plasma fire, explosions, evading, impact, shockwave instead
- Avoid real-world geopolitical references

═══ OUTPUT FORMAT (STRICT JSON) ═══
Return ONLY valid JSON, no markdown, no explanation:
{{
  "style": "3-6 word cinematic style description",
  "emotional_core": "primary emotions driving the story",
  "hook_line": "opening narrator line (1 sentence, Voice DNA style)",
  "scenes": [
    {{
      "id": 1,
      "shot_type": "handheld|drone|tracking|close up|wide|POV",
      "action": "one sentence visual description for Veo",
      "narration": "narrator voiceover for this scene (Voice DNA style)",
      "emotion": "primary emotion of this scene"
    }}
  ],
  "cta_line": "closing narrator line that triggers {cta_strategy}",
  "cliffhanger": "unresolved story hook for next episode",
  "virality_score": 0-100,
  "retention_score": 0-100
}}
"""

    print(f"🧠 Compiling story blueprint (Grounded Episode {ep_num})...")
    
    # Configure Grounding with your Data Store
    project_id = os.environ.get("DEVSHELL_PROJECT_ID")
    search_tool = Tool(
        vertex_ai_search=VertexAISearch(
            datastore=f"projects/{project_id}/locations/global/collections/default_collection/dataStores/viral-knowledge-base"
        )
    )

    response = client.models.generate_content(
        model=MODEL_LLM, 
        contents=prompt,
        config=GenerateContentConfig(
            tools=[search_tool]
        )
    )
    
    # Parse JSON from response
    text = response.text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    
    blueprint = json.loads(text)
    
    print(f"  ✓ Style: {blueprint.get('style', 'N/A')}")
    print(f"  ✓ Virality Score: {blueprint.get('virality_score', 'N/A')}/100")
    print(f"  ✓ Retention Score: {blueprint.get('retention_score', 'N/A')}/100")
    print(f"  ✓ Scenes: {len(blueprint.get('scenes', []))}")
    
    return blueprint


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PYTHON SCRIPT COMPILER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compile_script(config: dict, blueprint: dict, voice_dna: dict, memory: MemoryEngine) -> Path:
    """
    Converts a structured blueprint into a fully runnable Python pipeline script.
    """
    ep_num = memory.get_episode_number()
    series_id = config.get("series_name", "standalone").replace(" ", "_").lower()
    script_name = f"{series_id}_ep{ep_num:03d}.py"
    script_path = COMPILED_DIR / script_name

    style = blueprint["style"]
    scenes = blueprint["scenes"]
    hook_line = blueprint.get("hook_line", "")
    cta_line = blueprint.get("cta_line", "")
    cliffhanger = blueprint.get("cliffhanger", "")

    # Build character/environment locks from config
    char_lock = config.get("character_lock", "same male soldier, mid-30s, short hair, tactical uniform, consistent face")
    env_lock = config.get("environment_lock", "same city, overcast sky, smoky atmosphere, consistent lighting")
    veo_model = config.get("veo_model", "veo-3.1-fast-generate-001")

    # Build scene data as Python list literal
    scene_data_lines = []
    narration_lines = []
    for s in scenes:
        action = s["action"].replace('"', '\\"')
        shot = s.get("shot_type", "tracking")
        narr = s.get("narration", s["action"]).replace('"', '\\"')
        scene_data_lines.append(f'    {{"action": "{action}", "shot": "{shot}"}},')
        narration_lines.append(f'    "{narr}",')

    scene_data_str = "\n".join(scene_data_lines)
    narration_str = "\n".join(narration_lines)

    # Generate the full Python script
    script_content = textwrap.dedent(f'''\
#!/usr/bin/env python3
"""
Auto-generated by 10_script_compiler.py
Series: {series_id} | Episode: {ep_num}
Style: {style}
"""
import os
import sys
import time
import json
import concurrent.futures
from pathlib import Path

try:
    from google import genai
    from google.genai.types import GenerateVideosConfig
    from google.cloud import texttospeech
except ImportError as e:
    print(f"Missing dependency: {{e}}")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
PIPELINE_DIR = Path.home() / "yt-pipeline"
OUTPUT_DIR = PIPELINE_DIR / "output" / "{series_id}_ep{ep_num:03d}"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VEO_MODEL = "{veo_model}"
STYLE = "{style}"
CHARACTER_LOCK = "{char_lock}"
ENVIRONMENT_LOCK = "{env_lock}"
QUALITY = "masterpiece, ultra-detailed, photorealistic, cinematic volumetric lighting, intense color grading, 8k, award-winning cinematography"

# ── Story Data ─────────────────────────────────────────────────────────────────
SCENES = [
{scene_data_str}
]

NARRATIONS = [
{narration_str}
]

HOOK_LINE = "{hook_line}"
CTA_LINE = "{cta_line}"

# ── Prompt Builder ─────────────────────────────────────────────────────────────
def build_prompt(scene, prev_action=None):
    continuity = f"Continuous action from: {{prev_action[:80]}}." if prev_action else ""
    return f"{{STYLE}}. {{scene['shot']}} shot. {{scene['action']}}. {{continuity}} {{CHARACTER_LOCK}}. {{ENVIRONMENT_LOCK}}. {{QUALITY}}".strip()

# ── Video Generation (Parallel) ───────────────────────────────────────────────
def generate_scene(client, i):
    scene = SCENES[i]
    prev = SCENES[i-1]["action"] if i > 0 else None
    prompt = build_prompt(scene, prev)
    out = OUTPUT_DIR / f"seg_{{i:03d}}.mp4"

    print(f"  🎬 Scene {{i+1}}/{{len(SCENES)}} starting...")
    try:
        op = client.models.generate_videos(
            model=VEO_MODEL,
            prompt=prompt,
            config=GenerateVideosConfig(number_of_videos=1, duration_seconds=8, aspect_ratio="16:9"),
        )
        while not op.done:
            time.sleep(10)
            op = client.operations.get(op)

        if getattr(op, "error", None):
            raise ValueError(f"API Error: {{op.error.message}}")

        if op.response and op.response.generated_videos:
            video = op.response.generated_videos[0].video
            with open(out, "wb") as f:
                f.write(video.video_bytes)
            print(f"    ✓ Scene {{i+1}} saved!")
            return out
        else:
            raise ValueError("No video returned.")
    except Exception as e:
        print(f"    ❌ Scene {{i+1}}: {{e}}")
        # Safe fallback
        safe = f"{{STYLE}}. {{scene['shot']}} shot. A sweeping cinematic landscape, futuristic environment, highly detailed. {{CHARACTER_LOCK}}. {{ENVIRONMENT_LOCK}}. {{QUALITY}}"
        try:
            op = client.models.generate_videos(model=VEO_MODEL, prompt=safe, config=GenerateVideosConfig(number_of_videos=1, duration_seconds=8, aspect_ratio="16:9"))
            while not op.done:
                time.sleep(10)
                op = client.operations.get(op)
            if op.response and op.response.generated_videos:
                video = op.response.generated_videos[0].video
                with open(out, "wb") as f:
                    f.write(video.video_bytes)
                print(f"    ✓ Scene {{i+1}} saved (fallback)!")
                return out
        except Exception:
            pass
    return None

# ── Voice Generation (Vertex AI Studio Voices) ───────────────────────────────
def generate_voices():
    print("🔊 Generating ELITE AI narration (Studio-Q)...")
    client = texttospeech.TextToSpeechClient()
    paths = []
    all_narrations = [HOOK_LINE] + NARRATIONS + [CTA_LINE]
    
    for i, text in enumerate(all_narrations):
        if not text: continue
        
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Studio-Q"  # The deep, cinematic male voice
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            pitch=0.0,
            speaking_rate=0.95  # Slightly slower for more tension
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        p = OUTPUT_DIR / f"voice_{{i:03d}}.mp3"
        with open(p, "wb") as out:
            out.write(response.audio_content)
        paths.append(p)
    return paths

# ── Subtitles ─────────────────────────────────────────────────────────────────
def generate_srt():
    print("📝 Generating subtitles...")
    srt = OUTPUT_DIR / "subtitles.srt"
    dur = 8
    with open(srt, "w") as f:
        for i, n in enumerate(NARRATIONS):
            s, e = i * dur, (i + 1) * dur
            f.write(f"{{i+1}}\\n00:00:{{s:02d}},000 --> 00:00:{{e:02d}},000\\n{{n}}\\n\\n")
    return srt

# ── Final Stitch ──────────────────────────────────────────────────────────────
def stitch(video_paths, voice_paths, srt_path):
    print("🔗 Final render...")
    merged = []
    for i, vid in enumerate(video_paths):
        if i < len(voice_paths):
            m = OUTPUT_DIR / f"merged_{{i:03d}}.mp4"
            os.system(f"ffmpeg -y -i {{vid}} -i {{voice_paths[i]}} -c:v copy -c:a aac -shortest {{m}} -loglevel error")
            merged.append(m)
        else:
            merged.append(vid)

    concat_file = OUTPUT_DIR / "concat.txt"
    final = OUTPUT_DIR / "FINAL.mp4"
    with open(concat_file, "w") as f:
        for p in merged:
            f.write(f"file '{{p.absolute()}}'\\n")
    os.system(f"ffmpeg -y -f concat -safe 0 -i {{concat_file}} -c copy {{final}} -loglevel error")
    print(f"\\n✅ COMPLETE: {{final}}")
    return final

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    pid = os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ Set DEVSHELL_PROJECT_ID or run in Cloud Shell.")
        sys.exit(1)

    client = genai.Client(vertexai=True, project=pid, location="us-central1")

    # Parallel video generation (2 workers to avoid rate limits)
    paths = [None] * len(SCENES)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        futs = {{ex.submit(generate_scene, client, i): i for i in range(len(SCENES))}}
        for fut in concurrent.futures.as_completed(futs):
            idx = futs[fut]
            paths[idx] = fut.result()
    paths = [p for p in paths if p]

    if not paths:
        print("❌ No video generated.")
        return

    voices = generate_voices()
    srt = generate_srt()
    stitch(paths, voices, srt)

if __name__ == "__main__":
    main()
''')

    with open(script_path, "w") as f:
        f.write(script_content)

    print(f"  📄 Compiled script: {script_path.name}")
    return script_path


# ═══════════════════════════════════════════════════════════════════════════════
# 5. MASTER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_compiler(config_path: str, project: str, location: str):
    """Main entry point. Reads config, compiles story, generates script."""
    
    # Load creative config
    with open(config_path) as f:
        config = json.load(f)

    # Initialize engines
    series_id = config.get("series_name", "standalone").replace(" ", "_").lower()
    memory = MemoryEngine(series_id)
    voice_dna = config.get("voice_dna", DEFAULT_VOICE_DNA)

    # Initialize Gemini client
    client = genai.Client(vertexai=True, project=project, location=location)

    # Step 1: Compile story blueprint
    blueprint = compile_story(client, config, memory, voice_dna)

    # Step 2: Compile Python script
    script_path = compile_script(config, blueprint, voice_dna, memory)

    # Step 3: Record episode in memory
    memory.record_episode({
        "number": memory.get_episode_number(),
        "topic": config["master_prompt"],
        "style": blueprint.get("style", ""),
        "summary": blueprint.get("cliffhanger", "Episode completed."),
        "scenes": [s["action"] for s in blueprint.get("scenes", [])],
        "virality_score": blueprint.get("virality_score", 0),
        "retention_score": blueprint.get("retention_score", 0)
    })

    # Step 4: Export metadata
    meta = {
        "series": series_id,
        "episode": memory.state["episode_count"],
        "title": f"Episode {memory.state['episode_count']}: {config['master_prompt'][:60]}",
        "thumbnail_prompt": blueprint.get("style", "") + ", close-up human face showing fear, cinematic lighting, viral youtube thumbnail",
        "script_path": str(script_path),
        "world_state": memory.state["world_state"],
        "scores": {
            "virality": blueprint.get("virality_score", 0),
            "retention": blueprint.get("retention_score", 0)
        }
    }
    meta_path = COMPILED_DIR / f"{series_id}_ep{memory.state['episode_count']:03d}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ COMPILATION COMPLETE")
    print(f"{'='*60}")
    print(f"📄 Script:    {script_path}")
    print(f"📦 Metadata:  {meta_path}")
    print(f"🧠 Memory:    {memory.memory_file}")
    print(f"🌍 World:     AI Control {int(memory.state['world_state']['ai_control']*100)}%")
    print(f"\n▶ To run this episode:")
    print(f"  ~/yt-pipeline/venv/bin/python3 {script_path}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Video Pipeline Compiler")
    parser.add_argument("config", help="Path to creative config JSON file")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--location", default="us-central1")
    args = parser.parse_args()

    pid = args.project or os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ GCP Project ID required.")
        sys.exit(1)

    run_compiler(args.config, pid, args.location)
