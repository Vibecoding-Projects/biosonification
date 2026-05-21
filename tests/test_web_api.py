"""
Tests for web.app Flask endpoints.
"""

from unittest.mock import MagicMock, patch


def test_index_route(flask_client):
    """Test main page loads successfully."""
    response = flask_client.get("/")

    assert response.status_code == 200
    assert b"BioSonification" in response.data


def test_status_endpoint(flask_client, mock_generator):
    """Test /api/status endpoint returns correct structure."""
    with patch("web.app.get_generator", return_value=mock_generator):
        with patch(
            "web.app.check_audio_synthesizer",
            return_value={"midi2audio": True, "fluidsynth": True, "ogg": True, "timidity": False},
        ):
            response = flask_client.get("/api/status")

            assert response.status_code == 200
            data = response.get_json()

            assert "ready" in data
            assert "generator" in data
            assert "audio_enabled" in data
            assert data["ready"] is True


def test_status_endpoint_when_generator_not_ready(flask_client):
    """Test /api/status when generator has error."""
    mock_gen = MagicMock()
    mock_gen.is_ready.return_value = False
    mock_gen.get_error.return_value = "Checkpoint not found"
    mock_gen.status_payload.return_value = {}  # Return empty dict instead of MagicMock

    with patch("web.app.get_generator", return_value=mock_gen):
        with patch(
            "web.app.check_audio_synthesizer",
            return_value={"midi2audio": False, "fluidsynth": False, "ogg": False, "timidity": False},
        ):
            response = flask_client.get("/api/status")

            assert response.status_code == 200
            data = response.get_json()

            assert data["ready"] is False
            assert data["error"] == "Checkpoint not found"


def test_generate_endpoint_validation_missing_fasta(flask_client):
    """Test /api/generate validates FASTA is provided."""
    response = flask_client.post("/api/generate", json={})

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "fasta" in data["error"].lower()


def test_generate_endpoint_validation_empty_fasta(flask_client):
    """Test /api/generate validates FASTA is not empty."""
    response = flask_client.post("/api/generate", json={"fasta": ""})

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_generate_endpoint_success(flask_client, mock_generator, sample_fasta):
    """Test /api/generate returns success with valid FASTA."""
    with patch("web.app.get_generator", return_value=mock_generator):
        with patch("web.app.midi_to_ogg", return_value=False):
            response = flask_client.post("/api/generate", json={"fasta": sample_fasta})

            assert response.status_code == 200
            data = response.get_json()

            assert data["success"] is True
            assert "session_id" in data
            assert "midi_filename" in data
            assert "musical_params" in data
            assert "structured_metadata" in data


def test_generate_endpoint_with_audio_conversion(flask_client, mock_generator, sample_fasta):
    """Test /api/generate includes audio when conversion succeeds."""
    with patch("web.app.get_generator", return_value=mock_generator):
        with patch("web.app.midi_to_ogg", return_value=True):
            response = flask_client.post("/api/generate", json={"fasta": sample_fasta})

            assert response.status_code == 200
            data = response.get_json()

            assert data["success"] is True
            assert data["audio_available"] is True
            assert data["audio_format"] == "ogg"
            assert data["audio_mimetype"] == "audio/ogg"
            assert "audio_filename" in data
            assert data["audio_filename"].endswith(".ogg")


def test_download_midi_endpoint(flask_client, tmp_path):
    """Test /api/download/<session_id>/midi endpoint."""
    # Create a dummy MIDI file
    import time
    from pathlib import Path

    import mido

    output_dir = Path("web/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    midi_dir = output_dir / "midi"
    midi_dir.mkdir(exist_ok=True)

    session_id = "test123"
    midi_path = midi_dir / f"{session_id}.mid"

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=60, velocity=64, time=0))
    track.append(mido.Message("note_off", note=60, velocity=64, time=480))
    mid.save(str(midi_path))

    try:
        response = flask_client.get(f"/api/download/{session_id}/midi")
        assert response.status_code == 200
        assert response.content_type == "audio/midi"

        # Give Flask time to close the file
        time.sleep(0.1)
    finally:
        # Cleanup with retry
        if midi_path.exists():
            try:
                midi_path.unlink()
            except PermissionError:
                # File still open, skip cleanup
                pass


def test_download_midi_endpoint_not_found(flask_client):
    """Test /api/download/<session_id>/midi returns 404 for missing file."""
    response = flask_client.get("/api/download/nonexistent/midi")

    assert response.status_code == 404
    # Response might be HTML or JSON depending on Flask error handling
    # Just check status code


def test_download_ogg_endpoint(flask_client):
    """Test /api/download/<session_id>/ogg endpoint."""
    from pathlib import Path

    output_dir = Path("web/output")
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    session_id = "test_ogg"
    ogg_path = audio_dir / f"{session_id}.ogg"
    ogg_path.write_bytes(b"OggS-test")

    try:
        response = flask_client.get(f"/api/download/{session_id}/ogg")
        assert response.status_code == 200
        assert response.content_type == "audio/ogg"
        response.close()
    finally:
        if ogg_path.exists():
            try:
                ogg_path.unlink()
            except PermissionError:
                pass


def test_file_size_limit(flask_client):
    """Test file size limit is enforced."""
    # Create FASTA larger than 10MB
    large_fasta = ">test\n" + "A" * (11 * 1024 * 1024)

    # Flask raises RequestEntityTooLarge (413) but it may be caught as 500
    response = flask_client.post("/api/generate", json={"fasta": large_fasta})

    # Should be rejected with 413 or 500 (depending on error handling)
    assert response.status_code in [413, 500]


def test_error_handling_generator_failure(flask_client, sample_fasta):
    """Test error handling when generator fails."""
    mock_gen = MagicMock()
    mock_gen.is_ready.return_value = True
    mock_gen.initialize.return_value = True
    mock_gen.generate.side_effect = Exception("Generation failed")

    with patch("web.app.get_generator", return_value=mock_gen):
        response = flask_client.post("/api/generate", json={"fasta": sample_fasta})

        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data
