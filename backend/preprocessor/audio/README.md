# Audio Forensics Preprocessing Module

## Overview
The Audio Forensics Preprocessing Module is responsible for transcribing audio files to text and extracting key entities and relationships for the Tatva AI Forensics System. It processes audio and automatically builds a graph data structure representing entities mentioned in the audio and their relationships to the source file.

## Workflow

```
Audio File 
   ↓
Speech To Text (Whisper)
   ↓
Transcript Generation
   ↓
Entity Extraction (spaCy)
   ↓
Relation Extraction
   ↓
Graph JSON Output
```

## Entities Extracted
The module extracts the following entities, standardizing them to the required TATVA schema:
* `PERSON`: Individuals mentioned in the audio.
* `LOCATION`: Places, cities, countries, or geographical regions.
* `ORGANIZATION`: Companies, institutions, or groups.
* `PHONE_NUMBER`: Phone numbers extracted via pattern matching.
* `AUDIO_FILE`: The main audio source node containing the full transcript.

Each entity output strictly follows the schema:
```json
{
  "temp_id": "ent_12345678",
  "type": "PERSON",
  "attributes": {
    "text": "John Doe"
  },
  "confidence": 0.85,
  "source": "audio"
}
```

## Relations Extracted
The module creates the following relationships between the extracted entities and the source audio file:
* `MENTIONED`: A general entity is mentioned in the audio.
* `REFERENCED`: A location or organization is referenced.
* `SPOKE_IN`: A person is identified as speaking or being a subject in the audio.

Each relation output strictly follows the schema:
```json
{
  "source": "ent_12345678",
  "target": "audio_file_node",
  "relation": "SPOKE_IN",
  "attributes": {},
  "timestamp": null,
  "confidence": 0.85,
  "source_type": "audio"
}
```

## Output Format
The main function returns and saves a `TATVA Graph JSON` which includes lists for `entities` and `relations`. 

The outputs are automatically saved to `backend/preprocessor/Audio/outputs/`:
* `transcript.txt`: The raw text transcript of the audio.
* `audio_graph.json`: The complete final JSON graph containing entities and relations.
* `audio_entities.csv`: A tabular representation of the extracted entities.

## Technologies Used
* **Python**: Core scripting language.
* **OpenAI Whisper**: Used for robust and accurate Speech-to-Text transcription.
* **spaCy**: Used for Named Entity Recognition (NER).
* **JSON/CSV**: Native libraries for output serialization.

## Future Scope
* **Speaker Diarization**: Identifying 'who spoke when' to assign distinct `PERSON` nodes for different speakers.
* **Timestamp Extraction**: Adding precise start/end times to the `timestamp` field of relations.
* **Advanced NER**: Using transformer-based LLMs to extract more specific forensic entities like `WEAPON` or `DRUG`.
