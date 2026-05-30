"""
=============================================================
  Tatva AI Forensics System
  Audio Forensics Preprocessing Module
  audio_preprocessor.py
=============================================================

Pipeline:
    Audio File
        ↓ Validate File
        ↓ Check FFmpeg
        ↓ Speech-to-Text (Whisper)
        ↓ Transcript Generation
        ↓ Entity Extraction (spaCy)
        ↓ Relation Extraction
        ↓ Graph JSON Output

Outputs:
    - outputs/transcript.txt
    - outputs/audio_graph.json
    - outputs/audio_entities.csv
    - outputs/error_log.txt  (only on failure)
"""

import os
import sys
import json
import csv
import uuid
import re
import shutil
import traceback

# ─────────────────────────────────────────────
# DEPENDENCY IMPORTS (with graceful fallbacks)
# ─────────────────────────────────────────────

# pyrefly: ignore [missing-import]
try:
    # pyrefly: ignore [missing-import]
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
        SPACY_AVAILABLE = True
    except OSError:
        nlp = None
        SPACY_AVAILABLE = False
except ImportError:
    nlp = None
    SPACY_AVAILABLE = False


# ─────────────────────────────────────────────
# SUPPORTED AUDIO FORMATS
# ─────────────────────────────────────────────
SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4"}

# Minimum file size in bytes (a valid WAV header is at least 44 bytes)
MIN_FILE_SIZE_BYTES = 100


# ─────────────────────────────────────────────
# STAGE 1 — FILE VALIDATION
# ─────────────────────────────────────────────

def validate_audio_file(audio_path):
    """
    Validates whether the audio file exists, has a supported format,
    and has a non-trivial file size before passing it to Whisper.

    Returns:
        (bool, str): (is_valid, error_message)
    """
    print("\n[STAGE 1] Validating audio file...")

    # Check existence
    if not os.path.exists(audio_path):
        return False, f"Audio file not found: {audio_path}"

    # Check extension
    ext = os.path.splitext(audio_path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        return False, (
            f"Unsupported file format: '{ext}'. "
            f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )

    # Check file size
    file_size = os.path.getsize(audio_path)
    print(f"  File : {os.path.basename(audio_path)}")
    print(f"  Size : {file_size} bytes ({file_size / 1024:.2f} KB)")
    print(f"  Type : {ext}")

    if file_size < MIN_FILE_SIZE_BYTES:
        return False, (
            f"Audio file is too small ({file_size} bytes). "
            f"It must be at least {MIN_FILE_SIZE_BYTES} bytes. "
            "The sample_audio.wav may be a placeholder. "
            "Please replace it with a real audio file."
        )

    print("  [OK] File validation passed.")
    return True, None


# ─────────────────────────────────────────────
# STAGE 2 — FFMPEG CHECK
# ─────────────────────────────────────────────

def check_ffmpeg():
    """
    Checks whether FFmpeg is installed and available in PATH.
    Whisper requires FFmpeg to decode audio files.

    Returns:
        bool: True if FFmpeg is found, False otherwise.
    """
    print("\n[STAGE 2] Checking FFmpeg availability...")
    ffmpeg_path = shutil.which("ffmpeg")

    if ffmpeg_path:
        print(f"  [OK] FFmpeg found at: {ffmpeg_path}")
        return True
    else:
        print("  [ERR] FFmpeg is not installed or not available in PATH.")
        print("    Install it from: https://ffmpeg.org/download.html")
        print("    Or on Windows: winget install Gyan.FFmpeg")
        return False


# ─────────────────────────────────────────────
# STAGE 3 — AUDIO INFO (optional diagnostics)
# ─────────────────────────────────────────────

def print_audio_info(audio_path):
    """
    Prints basic audio file info: size, format.
    Tries to read WAV duration/sample-rate if the file is a .wav.
    """
    print("\n[STAGE 3] Reading audio file info...")

    file_size = os.path.getsize(audio_path)
    ext = os.path.splitext(audio_path)[1].lower()

    print(f"  Filename    : {os.path.basename(audio_path)}")
    print(f"  Format      : {ext}")
    print(f"  Size        : {file_size / 1024:.2f} KB")

    # For WAV files, try to read sample rate & duration
    if ext == ".wav":
        try:
            import wave
            with wave.open(audio_path, "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / float(sample_rate)
                print(f"  Sample Rate : {sample_rate} Hz")
                print(f"  Channels    : {channels}")
                print(f"  Duration    : {duration:.2f} seconds")
        except Exception as e:
            print(f"  Could not read WAV metadata: {e}")
    else:
        print("  (Detailed metadata requires ffprobe; skipping for non-WAV files)")


# ─────────────────────────────────────────────
# STAGE 4 — TRANSCRIPTION (Whisper)
# ─────────────────────────────────────────────

def transcribe_audio(audio_path):
    """
    Transcribes the audio file to text using OpenAI Whisper (base model).

    Returns:
        str: The transcribed text, or an empty string on failure.
    """
    print("\n[STAGE 4] Starting Whisper transcription...")

    if not WHISPER_AVAILABLE:
        print("  [ERR] Whisper is not installed.")
        print("    Install with: pip install openai-whisper")
        return None

    if not check_ffmpeg():
        print("  [ERR] Cannot transcribe without FFmpeg.")
        return None

    try:
        print("  Loading Whisper 'base' model (this may take a moment)...")
        model = whisper.load_model("base")
        print("  [OK] Whisper model loaded.")

        print(f"  Transcribing: {os.path.basename(audio_path)}")
        result = model.transcribe(audio_path)
        transcript = result.get("text", "").strip()

        if transcript:
            print(f"  [OK] Transcription complete. ({len(transcript)} characters)")
        else:
            print("  [WARN] Whisper returned an empty transcript.")

        return transcript

    except Exception as e:
        print(f"  [ERR] Transcription failed: {e}")
        traceback.print_exc()
        return None


# ─────────────────────────────────────────────
# STAGE 5 — PHONE NUMBER EXTRACTION (regex)
# ─────────────────────────────────────────────

def extract_phone_numbers(text):
    """
    Extracts phone numbers from text using regex.
    Handles Indian (10-digit), US (NNN-NNN-NNNN), and international formats.
    """
    # Matches: 555-123-4567 | (555) 123-4567 | +91-98765-43210 | 9876543210
    phone_pattern = re.compile(
        r'(\+?\d{1,3}[-.\s]?)?'
        r'(\(?\d{2,4}\)?[-.\s]?)'
        r'(\d{3,5}[-.\s]?)'
        r'(\d{4,5})'
    )
    matches = phone_pattern.findall(text)
    phones = []
    seen = set()
    for match in matches:
        phone_str = "".join(match).strip()
        # Only keep results with enough digits
        digits_only = re.sub(r'\D', '', phone_str)
        if len(digits_only) >= 7 and phone_str not in seen:
            seen.add(phone_str)
            phones.append(phone_str)
    return phones


# ─────────────────────────────────────────────
# STAGE 6 — ENTITY & RELATION EXTRACTION
# ─────────────────────────────────────────────

def extract_entities_and_relations(text):
    """
    Extracts entities from the transcript using spaCy NER.
    Falls back to hardcoded mock entities if spaCy is not available.

    Entity types:  PERSON, LOCATION, ORGANIZATION, PHONE_NUMBER, AUDIO_FILE
    Relation types: SPOKE_IN, REFERENCED, MENTIONED
    """
    print("\n[STAGE 5] Extracting entities and relations...")

    entities = []
    relations = []
    extracted_texts = set()

    # ── spaCy NER ──
    if SPACY_AVAILABLE and nlp:
        print("  [OK] Using spaCy en_core_web_sm for NER.")
        doc = nlp(text)

        label_map = {
            "PERSON": "PERSON",
            "GPE": "LOCATION",     # GeoPolitical Entity (countries, cities)
            "LOC": "LOCATION",     # Non-GPE locations
            "ORG": "ORGANIZATION",
        }

        for ent in doc.ents:
            ent_type = label_map.get(ent.label_)
            if ent_type and ent.text.lower() not in extracted_texts:
                extracted_texts.add(ent.text.lower())

                entity_id = f"ent_{uuid.uuid4().hex[:8]}"
                entity = {
                    "temp_id":    entity_id,
                    "type":       ent_type,
                    "attributes": {"text": ent.text},
                    "confidence": 0.85,
                    "source":     "audio",
                }
                entities.append(entity)

                # Pick the right relation type
                if ent_type == "PERSON":
                    rel_type = "SPOKE_IN"
                elif ent_type in ("LOCATION", "ORGANIZATION"):
                    rel_type = "REFERENCED"
                else:
                    rel_type = "MENTIONED"

                relations.append({
                    "source":      entity_id,
                    "target":      "audio_file_node",
                    "relation":    rel_type,
                    "attributes":  {},
                    "timestamp":   None,
                    "confidence":  0.85,
                    "source_type": "audio",
                })

    else:
        # ── Fallback mock NER ──
        print("  [WARN] spaCy not available. Using fallback mock NER.")
        mock_entities = [
            ("PERSON",       "Arjun Sharma"),
            ("PERSON",       "Priya Mehta"),
            ("LOCATION",     "Mumbai"),
            ("LOCATION",     "New Delhi"),
            ("ORGANIZATION", "CBI"),
            ("ORGANIZATION", "ShadowNet"),
        ]
        for ent_type, ent_text in mock_entities:
            entity_id = f"ent_{uuid.uuid4().hex[:8]}"
            entity = {
                "temp_id":    entity_id,
                "type":       ent_type,
                "attributes": {"text": ent_text},
                "confidence": 0.99,
                "source":     "audio",
            }
            entities.append(entity)
            extracted_texts.add(ent_text.lower())

            rel_type = "SPOKE_IN" if ent_type == "PERSON" else "REFERENCED"
            relations.append({
                "source":      entity_id,
                "target":      "audio_file_node",
                "relation":    rel_type,
                "attributes":  {},
                "timestamp":   None,
                "confidence":  0.99,
                "source_type": "audio",
            })

    # ── Phone numbers (regex, always runs) ──
    phone_numbers = extract_phone_numbers(text)
    for phone in phone_numbers:
        if phone not in extracted_texts:
            extracted_texts.add(phone)
            entity_id = f"ent_{uuid.uuid4().hex[:8]}"
            entity = {
                "temp_id":    entity_id,
                "type":       "PHONE_NUMBER",
                "attributes": {"text": phone},
                "confidence": 0.90,
                "source":     "audio",
            }
            entities.append(entity)
            relations.append({
                "source":      entity_id,
                "target":      "audio_file_node",
                "relation":    "REFERENCED",
                "attributes":  {},
                "timestamp":   None,
                "confidence":  0.90,
                "source_type": "audio",
            })

    print(f"  [OK] Extracted {len(entities)} entities and {len(relations)} relations.")
    return entities, relations


# ─────────────────────────────────────────────
# STAGE 7 — SAVE OUTPUTS
# ─────────────────────────────────────────────

def save_outputs(output, transcript, output_dir):
    """
    Saves the pipeline results to:
        - transcript.txt
        - audio_graph.json
    """
    print("\n[STAGE 7] Saving outputs...")
    os.makedirs(output_dir, exist_ok=True)

    # transcript.txt
    transcript_path = os.path.join(output_dir, "transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"  [OK] Transcript saved   : {transcript_path}")

    # audio_graph.json
    graph_path = os.path.join(output_dir, "audio_graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    print(f"  [OK] Graph JSON saved   : {graph_path}")




def save_error_log(error_text, output_dir):
    """Saves an error log to outputs/error_log.txt."""
    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "error_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(error_text)
    print(f"  [ERR] Error log saved    : {log_path}")


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def process_audio(audio_path):
    """
    Full Tatva audio forensics pipeline:
        1. Validate file
        2. Print audio info
        3. Transcribe with Whisper
        4. Extract entities & relations
        5. Build TATVA graph output

    Args:
        audio_path (str): Path to the input audio file.

    Returns:
        dict: TATVA-format output {"entities": [...], "relations": [...]}
    """

    # ── Stage 1: Validate ──
    is_valid, error_msg = validate_audio_file(audio_path)
    if not is_valid:
        print(f"\n  [ERR] Validation failed: {error_msg}")
        return {"entities": [], "relations": []}
        
    # ── Stage 3: Audio info ──
    print_audio_info(audio_path)

    # ── Stage 4: Transcribe ──
    transcript = transcribe_audio(audio_path)

    if not transcript:
        print("  -> No transcript available. Aborting.")
        return {"entities": [], "relations": []}

    # ── Stage 5: NER & Relations ──
    entities, relations = extract_entities_and_relations(transcript)

    # ── Stage 6: Build AUDIO_FILE node ──
    print("\n[STAGE 6] Building TATVA graph structure...")
    audio_entity = {
        "temp_id":    "audio_file_node",
        "type":       "AUDIO_FILE",
        "attributes": {
            "filename":   os.path.basename(audio_path),
            "transcript": transcript,
        },
        "confidence": 1.0,
        "source":     "audio",
    }
    entities.append(audio_entity)
    print(f"  [OK] Graph ready: {len(entities)} nodes, {len(relations)} edges.")

    return {
        "entities": entities,
        "relations": relations,
    }


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  TATVA AI Forensics — Audio Preprocessing Module")
    print("=" * 60)

    # Paths
    base_dir   = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, "sample_data")
    output_dir = os.path.join(base_dir, "outputs")

    # Allow passing a custom audio path as a CLI argument
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        audio_path = os.path.join(sample_dir, "sample_audio.wav")

    print(f"\nTarget file : {audio_path}")

    try:
        output = process_audio(audio_path)

        # Extract transcript for saving
        transcript = ""
        for ent in output["entities"]:
            if ent["type"] == "AUDIO_FILE":
                transcript = ent["attributes"].get("transcript", "")
                break

        save_outputs(output, transcript, output_dir)

        # ── Final terminal output ──
        print("\n" + "=" * 60)
        print("  FINAL TATVA JSON OUTPUT")
        print("=" * 60)
        print(json.dumps(output, indent=4, ensure_ascii=False))

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"\n[ERR] Unexpected error: {e}")
        print(error_details)
        save_error_log(error_details, output_dir)
        sys.exit(1)
