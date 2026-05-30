# -*- coding: utf-8 -*-
"""
generate_audio.py
Converts audio files to text using OpenAI Whisper (speech-to-text).

Transcribes all WAV files listed in AUDIO_FILES and saves:
  - A per-file transcript:  <stem>_transcript.txt
  - A combined transcript:  all_transcripts.txt
"""

import os
import sys
import io
import shutil

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# pyrefly: ignore [missing-import]
try:
    # pyrefly: ignore [missing-import]
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# ─────────────────────────────────────────────
# CONFIGURATION — add/remove files here
# ─────────────────────────────────────────────
AUDIO_FILES = [
    "sample_audio.wav",
    "s.wav",
    "b.wav",
    "d.wav",
    "v.wav",
]

WHISPER_MODEL = "base"   # tiny | base | small | medium | large


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def check_ffmpeg():
    """Check if FFmpeg is installed (required by Whisper)."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("[ERROR] FFmpeg is not installed or not in PATH.")
        print("  Install: https://ffmpeg.org/download.html")
        print("  Windows: winget install Gyan.FFmpeg")
        return False
    print(f"[OK] FFmpeg found: {ffmpeg_path}")
    return True


def transcribe_file(model, audio_path):
    """
    Transcribes a single audio file using a pre-loaded Whisper model.

    Args:
        model:      Loaded Whisper model.
        audio_path: Absolute path to the audio file.

    Returns:
        str: Transcribed text, or None on failure.
    """
    if not os.path.isfile(audio_path):
        print(f"  [ERROR] File not found: {audio_path}")
        return None

    file_size = os.path.getsize(audio_path)
    print(f"  File : {os.path.basename(audio_path)}  ({file_size / 1024:.2f} KB)")

    try:
        result = model.transcribe(audio_path)
        transcript = result.get("text", "").strip()
        if transcript:
            print(f"  [OK]  Transcribed ({len(transcript)} chars)")
        else:
            print("  [WARN] Whisper returned an empty transcript.")
        return transcript
    except Exception as e:
        print(f"  [ERROR] Transcription failed: {e}")
        return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Audio-to-Text - Whisper Transcription")
    print("=" * 55)

    if not WHISPER_AVAILABLE:
        print("[ERROR] Whisper is not installed.")
        print("  Install with: pip install openai-whisper")
        sys.exit(1)

    if not check_ffmpeg():
        sys.exit(1)

    base_dir   = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, "sample_data")

    # Load model once for all files
    print(f"\nLoading Whisper '{WHISPER_MODEL}' model...")
    model = whisper.load_model(WHISPER_MODEL)
    print("[OK] Model loaded.\n")

    results = {}   # filename -> transcript text

    for filename in AUDIO_FILES:
        audio_path = os.path.join(sample_dir, filename)
        print(f"-- Transcribing: {filename}")
        transcript = transcribe_file(model, audio_path)
        results[filename] = transcript or ""
        print()

    # Save individual transcripts
    print("-" * 55)
    print("  Saving transcripts...")
    print("-" * 55)

    for filename, transcript in results.items():
        stem = os.path.splitext(filename)[0]
        out_path = os.path.join(sample_dir, f"{stem}_transcript.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        print(f"  [OK] {stem}_transcript.txt")

        # Print result to terminal
        print(f"\n  >>> {filename}:")
        print(f"  {transcript or '(empty)'}")
        print()

    # Save combined transcript
    combined_path = os.path.join(sample_dir, "all_transcripts.txt")
    with open(combined_path, "w", encoding="utf-8") as f:
        for filename, transcript in results.items():
            f.write(f"[{filename}]\n")
            f.write(transcript + "\n\n")
    print(f"  [OK] all_transcripts.txt (combined)")

    print("\n" + "=" * 55)
    print("  Done.")
    print("=" * 55)


if __name__ == "__main__":
    main()
