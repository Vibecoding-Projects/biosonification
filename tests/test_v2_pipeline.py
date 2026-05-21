from pathlib import Path

import numpy as np
import pytest
import torch

from bio_music_pipeline.v2.bio import BiologicalSequenceEncoder
from bio_music_pipeline.v2.config import BioEncoderConfig, MusicDataConfig
from bio_music_pipeline.v2.corpus import bootstrap_music21_corpus
from bio_music_pipeline.v2.evaluate import compute_structured_midi_metrics
from bio_music_pipeline.v2.structured_generate import _validate_checkpoint_compatibility
from bio_music_pipeline.v2.structured_model import BioConditionedSequenceModel
from bio_music_pipeline.v2.structured_music import (
    HarmonyBar,
    HarmonyTokenizer,
    MelodyTokenizer,
    load_structured_music_corpus,
    render_harmony_and_melody_to_score,
)


def test_bio_encoder_quick_sample():
    encoder = BiologicalSequenceEncoder(BioEncoderConfig(use_esm_embedding=False))
    fasta_path = Path("data/fasta/quick_sample.fa")
    results = encoder.encode_fasta(str(fasta_path))
    assert results
    assert results[0].vector.shape == (encoder.config.embedding_dim,)
    assert results[0].control_profile.shape == (6,)
    assert 0 <= results[0].tonic_pc_hint <= 11


def test_structured_music_extraction_and_render():
    config = MusicDataConfig(midi_dirs=["data/midi/polyphonic_music21"], max_music21_files=4)
    segments, harmony_tokenizer, melody_tokenizer = load_structured_music_corpus(config)
    assert segments
    sample = segments[0]
    assert sample.harmony_token_ids[0] == harmony_tokenizer.bos_token_id
    assert sample.melody_token_ids[0] == melody_tokenizer.bos_token_id
    decoded_harmony = harmony_tokenizer.decode_progression(sample.harmony_token_ids, config.bars_per_segment)
    decoded_melody = melody_tokenizer.decode_melody(sample.melody_token_ids, decoded_harmony, sample.key_tonic_pc)
    score = render_harmony_and_melody_to_score(decoded_harmony, decoded_melody, sample.tempo_bpm, config)
    assert len(score.parts) == 2
    assert len(score.parts[1].flatten().notes) > 0


def test_structured_model_forward_and_generate():
    music_config = MusicDataConfig()
    harmony_tokenizer = HarmonyTokenizer(music_config)
    model = BioConditionedSequenceModel(
        vocab_size=len(harmony_tokenizer.vocab),
        bio_vector_dim=256,
        max_seq_len=64,
        pad_token_id=harmony_tokenizer.pad_token_id,
        bos_token_id=harmony_tokenizer.bos_token_id,
        eos_token_id=harmony_tokenizer.eos_token_id,
        d_model=64,
        n_heads=4,
        n_layers=2,
        dim_feedforward=128,
        dropout=0.1,
    )
    input_ids = torch.randint(0, len(harmony_tokenizer.vocab), (2, 16))
    input_ids[:, -1] = harmony_tokenizer.eos_token_id
    bio_vector = torch.randn(2, 256)
    attention_mask = torch.ones_like(input_ids, dtype=torch.bool)
    loss_mask = torch.ones_like(input_ids, dtype=torch.bool)
    loss_mask[:, :4] = False
    outputs = model.compute_loss(
        input_ids=input_ids,
        bio_vector=bio_vector,
        attention_mask=attention_mask,
        loss_mask=loss_mask,
    )
    assert outputs["loss"].item() >= 0.0

    prefix = [
        harmony_tokenizer.bos_token_id,
        *harmony_tokenizer.control_tokens(np.array([0.5, 0.5, 0.5, 0.5, 0.5, 1.0], dtype=np.float32), 0, "major"),
        harmony_tokenizer.sep_token_id,
    ]
    generated = model.generate(
        bio_vector=torch.randn(256),
        prefix_token_ids=prefix,
        max_new_tokens=8,
        temperature=0.9,
        top_k=8,
        top_p=0.9,
        stop_token_ids=[harmony_tokenizer.eos_token_id],
    )
    assert generated.ndim == 1
    assert generated[0].item() == harmony_tokenizer.bos_token_id


def test_melody_decode_is_bounded_and_monophonic():
    config = MusicDataConfig(bars_per_segment=2)
    tokenizer = MelodyTokenizer(config)
    harmony_bars = [
        HarmonyBar(bar_index=0, root_pc=0, quality="maj", hold=False, key_tonic_pc=0, key_mode="major"),
        HarmonyBar(bar_index=1, root_pc=7, quality="maj", hold=False, key_tonic_pc=0, key_mode="major"),
    ]
    token_ids = [
        tokenizer.bos_token_id,
        tokenizer.sep_token_id,
        tokenizer.token_to_id["BAR"],
        tokenizer.token_to_id["POS_0"],
        tokenizer.token_to_id["RELPC_0"],
        tokenizer.token_to_id["OCT_5"],
        tokenizer.token_to_id["DUR_8"],
        tokenizer.token_to_id["POS_0"],
        tokenizer.token_to_id["RELPC_4"],
        tokenizer.token_to_id["OCT_6"],
        tokenizer.token_to_id["DUR_4"],
        tokenizer.token_to_id["POS_2"],
        tokenizer.token_to_id["RELPC_7"],
        tokenizer.token_to_id["OCT_5"],
        tokenizer.token_to_id["DUR_16"],
        tokenizer.token_to_id["BAR"],
        tokenizer.token_to_id["POS_1"],
        tokenizer.token_to_id["RELPC_0"],
        tokenizer.token_to_id["OCT_5"],
        tokenizer.token_to_id["DUR_16"],
        tokenizer.token_to_id["BAR"],
        tokenizer.token_to_id["POS_0"],
        tokenizer.token_to_id["RELPC_0"],
        tokenizer.token_to_id["OCT_5"],
        tokenizer.token_to_id["DUR_2"],
        tokenizer.eos_token_id,
    ]
    events = tokenizer.decode_melody(token_ids, harmony_bars, tonic_pc=0)
    assert events
    total_steps = len(harmony_bars) * config.steps_per_bar
    assert max(onset + duration for onset, duration, _, _ in events) <= total_steps
    for index in range(len(events) - 1):
        current_onset, current_duration, _, _ = events[index]
        next_onset, _, _, _ = events[index + 1]
        assert next_onset >= current_onset + current_duration


def test_checkpoint_config_mismatch_is_reported_before_model_load():
    config = MusicDataConfig(descriptor_bins=8)
    harmony_tokenizer = HarmonyTokenizer(config)
    melody_tokenizer = MelodyTokenizer(config)
    incompatible_config = MusicDataConfig(descriptor_bins=7)
    from bio_music_pipeline.v2.config import V2PipelineConfig

    checkpoint = {
        "tokenizer_info": {
            "harmony_vocab_size": len(harmony_tokenizer.vocab),
            "melody_vocab_size": len(melody_tokenizer.vocab),
        },
        "config": {
            "music": {"descriptor_bins": config.descriptor_bins},
        },
    }
    with pytest.raises(ValueError, match="Checkpoint/config mismatch"):
        _validate_checkpoint_compatibility(
            V2PipelineConfig(music=incompatible_config),
            checkpoint,
        )


def test_web_status_reports_structured_generator(monkeypatch):
    import web.app as web_app

    class FakeGenerator:
        def is_ready(self):
            return True

        def get_error(self):
            return None

        def status_payload(self):
            return {
                "config_path": "configs/pipeline_v2_small.json",
                "checkpoint_path": "results/example/checkpoints/structured_pipeline.pt",
                "device": "cpu",
            }

    monkeypatch.setattr(web_app, "get_generator", lambda: FakeGenerator())
    monkeypatch.setattr(
        web_app,
        "check_audio_synthesizer",
        lambda: {"midi2audio": False, "fluidsynth": False, "ogg": False, "timidity": False},
    )

    response = web_app.app.test_client().get("/api/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ready"] is True
    assert payload["generator"]["checkpoint_path"].endswith("structured_pipeline.pt")


def test_web_generate_endpoint_returns_structured_metadata(monkeypatch):
    import web.app as web_app

    class FakeGenerator:
        def is_ready(self):
            return True

        def initialize(self):
            return True

        def get_error(self):
            return None

        def generate(self, fasta_text, output_dir):
            return {
                "session_id": "abc12345",
                "midi_path": str(Path(output_dir) / "midi" / "abc12345.mid"),
                "midi_filename": "abc12345.mid",
                "header": "demo",
                "sequence_length": 120,
                "musical_params": {
                    "tempo": 120.0,
                    "key": "C major",
                    "sequence_type": "dna",
                    "harmony_bars": 8,
                    "melody_notes": 16,
                    "device": "cpu",
                },
                "structured_metadata": {
                    "sequence_type": "dna",
                    "generated_melody_note_count": 16,
                },
            }

    monkeypatch.setattr(web_app, "get_generator", lambda: FakeGenerator())
    monkeypatch.setattr(web_app, "midi_to_ogg", lambda midi_path, ogg_path: False)

    response = web_app.app.test_client().post(
        "/api/generate",
        json={"fasta": ">demo\n" + "ACGT" * 30},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["structured_metadata"]["generated_melody_note_count"] == 16
    assert payload["musical_params"]["harmony_bars"] == 8
    assert "midi_path" not in payload


def test_structured_midi_metrics_detect_two_part_score(tmp_path):
    config = MusicDataConfig(bars_per_segment=2)
    harmony_bars = [
        HarmonyBar(bar_index=0, root_pc=0, quality="maj", hold=False, key_tonic_pc=0, key_mode="major"),
        HarmonyBar(bar_index=1, root_pc=7, quality="dom7", hold=False, key_tonic_pc=0, key_mode="major"),
    ]
    melody_events = [
        (0, 2, 60, 0),
        (4, 2, 64, 0),
        (16, 4, 67, 1),
    ]
    metadata = {
        "tonic_pc_hint": 0,
        "generated_harmony_bars": [
            {"root_pc": 0, "quality": "maj", "hold": False},
            {"root_pc": 7, "quality": "dom7", "hold": False},
        ],
    }
    midi_path = tmp_path / "sample.mid"
    score = render_harmony_and_melody_to_score(harmony_bars, melody_events, 96.0, config)
    score.write("midi", fp=str(midi_path))

    metrics = compute_structured_midi_metrics(str(midi_path), metadata)
    assert metrics["valid"] is True
    assert metrics["expected_two_part_score"] is True
    assert metrics["harmony_chord_count"] == 2
    assert metrics["melody_note_count"] == 3
    assert metrics["chord_tone_ratio"] > 0.0

    midi_only_metrics = compute_structured_midi_metrics(str(midi_path))
    assert midi_only_metrics["chord_change_rate"] > 0.0
    assert midi_only_metrics["chord_tone_ratio"] > 0.0


def test_music21_fallback_rejects_unsupported_composer(tmp_path):
    with pytest.raises(ValueError, match="supports only Bach"):
        bootstrap_music21_corpus(str(tmp_path), max_files=1, composers=["mozart"])


def test_v2_public_api_exports_only_structured_stable_surface():
    import bio_music_pipeline.v2 as v2

    removed_api_names = {
        "BioMusicPairDataset",
        "MusicSegment",
        "PolyphonicMusicTokenizer",
        "load_music_corpus",
        "generate_music_from_fasta",
        "ControlConditionedTransformer",
        "PairedSample",
        "build_paired_dataset",
        "train_pipeline",
    }
    assert not removed_api_names.intersection(set(v2.__all__))
    assert "train_structured_pipeline" in v2.__all__
    assert "generate_structured_music_from_fasta" in v2.__all__
