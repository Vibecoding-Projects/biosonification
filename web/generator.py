"""Structured v2 music generation backend for the Flask web interface."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from bio_music_pipeline.v2 import generate_structured_music_from_fasta_fragmented

PROJECT_ROOT = Path(__file__).parent.parent
FASTA_SEQUENCE_CHARS = frozenset("ABCDEFGHIKLMNPQRSTUVWXYZ*-.")


class FASTAValidationError(Exception):
    """Raised when the submitted FASTA text cannot be used for generation."""


class BioMusicGenerator:
    """Generates harmony+melody MIDI from biological FASTA input."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        checkpoint_path: Optional[str] = None,
        device: Optional[str] = None,
    ):
        self.config_path = Path(config_path).expanduser() if config_path else self._resolve_default_config_path()
        self.checkpoint_path = (
            Path(checkpoint_path).expanduser() if checkpoint_path else self._resolve_default_checkpoint_path()
        )
        self.device = device or os.getenv("BIOSONIFICATION_DEVICE", "auto")
        self._initialized = False
        self._error = None

        if not self.config_path.exists():
            self._error = f"Config file not found: {self.config_path}"
        elif not self.checkpoint_path.exists():
            self._error = (
                f"Structured checkpoint not found: {self.checkpoint_path}. "
                "Train the v2 pipeline first or set BIOSONIFICATION_STRUCTURED_CHECKPOINT."
            )

    @staticmethod
    def _resolve_default_config_path() -> Path:
        env_config = os.getenv("BIOSONIFICATION_CONFIG_PATH")
        if env_config:
            return Path(env_config).expanduser()
        # Use config matching the 4-bar model
        return PROJECT_ROOT / "configs" / "pipeline_v2_medium_rtx2060_fast.json"

    @staticmethod
    def _resolve_default_checkpoint_path() -> Path:
        env_checkpoint = os.getenv("BIOSONIFICATION_STRUCTURED_CHECKPOINT")
        if env_checkpoint:
            return Path(env_checkpoint).expanduser()

        # Prefer 4-bar model (better validation loss)
        primary = PROJECT_ROOT / "results" / "v2_medium_rtx2060_fast" / "checkpoints" / "structured_pipeline.pt"
        if primary.exists():
            return primary

        # Fallback to 8-bar model
        fallback = PROJECT_ROOT / "results" / "v2_medium_rtx2060_long" / "checkpoints" / "structured_pipeline.pt"
        if fallback.exists():
            return fallback

        candidates = list((PROJECT_ROOT / "results").glob("*/checkpoints/structured_pipeline.pt"))
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
        return primary

    def initialize(self) -> bool:
        """Validate runtime paths. The structured generator loads the model per request."""

        if self._error:
            return False
        self._initialized = True
        return True

    @staticmethod
    def validate_fasta(fasta_text: str) -> Tuple[str, str]:
        fasta_text = fasta_text.lstrip("\ufeff").strip()
        if not fasta_text:
            raise FASTAValidationError("FASTA input is empty")

        if not fasta_text.startswith(">"):
            raise FASTAValidationError("Invalid FASTA format: input must start with a header line beginning with '>'.")

        records = []
        current_header = None
        current_sequence_lines = []
        for raw_line in fasta_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_header is not None:
                    raw_sequence = "".join(current_sequence_lines)
                    if not raw_sequence:
                        raise FASTAValidationError(
                            f"Invalid FASTA format: record '{current_header}' has no sequence symbols."
                        )
                    records.append((current_header, raw_sequence))
                current_header = line[1:].strip() or f"Sequence_{len(records) + 1}"
                current_sequence_lines = []
            else:
                if current_header is None:
                    raise FASTAValidationError(
                        "Invalid FASTA format: sequence content must come after a header line starting with '>'."
                    )
                invalid_chars = sorted({char for char in line.upper() if char not in FASTA_SEQUENCE_CHARS})
                if invalid_chars:
                    preview = ", ".join(repr(char) for char in invalid_chars[:8])
                    raise FASTAValidationError(
                        "Invalid FASTA format: sequence lines may contain only IUPAC DNA/RNA/protein symbols "
                        f"and gap markers. Found: {preview}."
                    )
                current_sequence_lines.append(line)

        if current_header is not None:
            raw_sequence = "".join(current_sequence_lines)
            if not raw_sequence:
                raise FASTAValidationError(
                    f"Invalid FASTA format: record '{current_header}' has no sequence symbols."
                )
            records.append((current_header, raw_sequence))
        if not records:
            raise FASTAValidationError("Invalid FASTA input: no valid FASTA records found.")

        cleaned_records = []
        for header, raw_sequence in records:
            cleaned = re.sub(r"[^A-Za-z*]", "", raw_sequence).upper()
            if cleaned:
                cleaned_records.append((header, cleaned))
        if not cleaned_records:
            raise FASTAValidationError("No valid sequence symbols found in FASTA records.")

        header, sequence = cleaned_records[0]
        if len(cleaned_records) > 1:
            header = f"{header} (record 1/{len(cleaned_records)})"
        if len(sequence) < 90:
            raise FASTAValidationError(f"Sequence too short: {len(sequence)} symbols after cleaning (minimum 90).")
        if len(sequence) > 50000:
            raise FASTAValidationError(f"Sequence too long: {len(sequence)} symbols (maximum 50000).")
        return header, sequence

    def generate(self, fasta_text: str, output_dir: Optional[str] = None) -> Dict:
        if not self._initialized and not self.initialize():
            raise RuntimeError(f"Generator not initialized: {self._error}")

        header, sequence = self.validate_fasta(fasta_text)
        session_id = str(uuid.uuid4())[:8]
        base_output = Path(output_dir) if output_dir is not None else PROJECT_ROOT / "web" / "output"
        midi_dir = base_output / "midi"
        fasta_dir = base_output / "fasta"
        metadata_dir = base_output / "metadata"
        midi_dir.mkdir(parents=True, exist_ok=True)
        fasta_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)

        fasta_path = fasta_dir / f"{session_id}.fa"
        fasta_path.write_text(f">{header}\n{sequence}\n", encoding="utf-8")

        midi_path = midi_dir / f"{session_id}.mid"
        metadata_path = metadata_dir / f"{session_id}.json"

        # Use fragmented generation for better quality on long sequences
        metadata = generate_structured_music_from_fasta_fragmented(
            fasta_path=str(fasta_path),
            checkpoint_path=str(self.checkpoint_path),
            output_path=str(midi_path),
            bars_per_fragment=4,  # Use 4-bar fragments for best quality
            config_path=str(self.config_path),
            metadata_output=str(metadata_path),
            device_name=self.device,
        )

        tonic_names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

        # Extract tonic and mode from first fragment
        first_fragment = metadata.get("fragments", [{}])[0]
        calibrated_profile = first_fragment.get("calibrated_profile", [0.5] * 6)
        tonic_pc = metadata.get("tonic_pc_hint", 0)
        tonic = tonic_names[int(tonic_pc) % 12]
        mode = "major" if calibrated_profile[5] >= 0.5 else "minor"

        # Calculate average tempo across fragments
        fragments = metadata.get("fragments", [])
        avg_tempo = sum(f.get("tempo_bpm", 90) for f in fragments) / len(fragments) if fragments else 90.0

        return {
            "session_id": session_id,
            "midi_path": str(midi_path),
            "midi_filename": f"{session_id}.mid",
            "metadata_filename": f"{session_id}.json",
            "header": header,
            "sequence_length": len(sequence),
            "structured_metadata": metadata,
            "musical_params": {
                "tempo": float(avg_tempo),
                "key": f"{tonic} {mode}",
                "sequence_type": metadata.get("sequence_type", "dna"),
                "harmony_bars": metadata.get("total_bars", 0),
                "melody_notes": metadata.get("total_melody_notes", 0),
                "device": metadata.get("device", self.device),
                "num_fragments": metadata.get("num_fragments", 1),
            },
        }

    def is_ready(self) -> bool:
        return self._initialized and self._error is None

    def get_error(self) -> Optional[str]:
        return self._error

    def status_payload(self) -> Dict[str, Optional[str]]:
        return {
            "config_path": str(self.config_path),
            "checkpoint_path": str(self.checkpoint_path),
            "device": self.device,
        }


_generator = None


def get_generator() -> BioMusicGenerator:
    global _generator
    if _generator is None:
        _generator = BioMusicGenerator()
    return _generator
