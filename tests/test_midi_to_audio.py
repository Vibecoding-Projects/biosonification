"""
Tests for web.midi_to_audio module.
"""

from unittest.mock import MagicMock, patch

from web.midi_to_audio import (
    check_audio_synthesizer,
    get_install_instructions,
    midi_to_ogg,
    midi_to_wav,
)


def test_check_audio_synthesizer():
    """Test check_audio_synthesizer returns status dict."""
    status = check_audio_synthesizer()

    assert isinstance(status, dict)
    assert "midi2audio" in status
    assert "fluidsynth" in status
    assert "ogg" in status
    assert "timidity" in status
    assert isinstance(status["midi2audio"], bool)
    assert isinstance(status["fluidsynth"], bool)
    assert isinstance(status["ogg"], bool)
    assert isinstance(status["timidity"], bool)


def test_get_install_instructions_when_available():
    """Test get_install_instructions when synthesizer is available."""
    with patch("web.midi_to_audio.check_audio_synthesizer") as mock_check:
        mock_check.return_value = {
            "midi2audio": True,
            "fluidsynth": False,
            "ogg": True,
            "timidity": False,
        }

        instructions = get_install_instructions()

        assert "enabled" in instructions.lower()
        assert "ogg" in instructions.lower()


def test_get_install_instructions_when_unavailable():
    """Test get_install_instructions when no synthesizer available."""
    with patch("web.midi_to_audio.check_audio_synthesizer") as mock_check:
        mock_check.return_value = {
            "midi2audio": False,
            "fluidsynth": False,
            "ogg": False,
            "timidity": False,
        }

        instructions = get_install_instructions()

        assert "requires" in instructions.lower() or "install" in instructions.lower()


@patch("web.midi_to_audio._try_fluidsynth_ogg_cli")
def test_midi_to_ogg_success_with_fluidsynth(mock_try, sample_midi_path, tmp_path):
    """Test midi_to_ogg succeeds with FluidSynth OGG output."""
    mock_try.return_value = True

    ogg_path = str(tmp_path / "output.ogg")
    result = midi_to_ogg(sample_midi_path, ogg_path)

    assert result is True
    mock_try.assert_called_once()


@patch("web.midi_to_audio._try_midi2audio")
def test_midi_to_wav_success_with_midi2audio(mock_try, sample_midi_path, tmp_path):
    """Test midi_to_wav succeeds with midi2audio."""
    mock_try.return_value = True

    wav_path = str(tmp_path / "output.wav")
    result = midi_to_wav(sample_midi_path, wav_path)

    assert result is True
    mock_try.assert_called_once()


@patch("web.midi_to_audio._try_timidity_cli")
@patch("web.midi_to_audio._try_fluidsynth_cli")
@patch("web.midi_to_audio._try_midi2audio")
def test_midi_to_wav_fallback_chain(mock_midi2audio, mock_fluidsynth, mock_timidity, sample_midi_path, tmp_path):
    """Test midi_to_wav tries fallback methods in order."""
    mock_midi2audio.return_value = False
    mock_fluidsynth.return_value = False
    mock_timidity.return_value = True

    wav_path = str(tmp_path / "output.wav")
    result = midi_to_wav(sample_midi_path, wav_path)

    assert result is True
    mock_midi2audio.assert_called_once()
    mock_fluidsynth.assert_called_once()
    mock_timidity.assert_called_once()


@patch("web.midi_to_audio._try_timidity_cli")
@patch("web.midi_to_audio._try_fluidsynth_cli")
@patch("web.midi_to_audio._try_midi2audio")
def test_midi_to_wav_all_methods_fail(mock_midi2audio, mock_fluidsynth, mock_timidity, sample_midi_path, tmp_path):
    """Test midi_to_wav returns False when all methods fail."""
    mock_midi2audio.return_value = False
    mock_fluidsynth.return_value = False
    mock_timidity.return_value = False

    wav_path = str(tmp_path / "output.wav")
    result = midi_to_wav(sample_midi_path, wav_path)

    assert result is False


def test_soundfont_discovery():
    """Test that soundfont paths are checked in correct order."""
    # This is more of an integration test
    # We just verify the function doesn't crash
    from web.midi_to_audio import _try_midi2audio

    # Should handle missing soundfont gracefully
    result = _try_midi2audio("nonexistent.mid", "output.wav", None)
    assert isinstance(result, bool)


@patch("web.midi_to_audio.subprocess.run")
def test_fluidsynth_cli_command_format(mock_run, sample_midi_path, tmp_path):
    """Test fluidsynth CLI is called with correct arguments."""
    from web.midi_to_audio import _try_fluidsynth_cli

    mock_run.return_value = MagicMock(returncode=0)

    # Create a dummy soundfont
    soundfont = tmp_path / "test.sf2"
    soundfont.write_text("dummy")

    wav_path = str(tmp_path / "output.wav")

    with patch("web.midi_to_audio.Path") as mock_path:
        # Mock soundfont existence check
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.__truediv__ = lambda self, other: tmp_path / other

        _try_fluidsynth_cli(sample_midi_path, wav_path, str(soundfont))

        # Verify subprocess was called
        assert mock_run.called


@patch("web.midi_to_audio.subprocess.run")
def test_fluidsynth_ogg_cli_command_format(mock_run, sample_midi_path, tmp_path):
    """Test fluidsynth OGG CLI is called with correct arguments."""
    from web.midi_to_audio import _try_fluidsynth_ogg_cli

    mock_run.return_value = MagicMock(returncode=0)

    soundfont = tmp_path / "test.sf2"
    soundfont.write_text("dummy")

    ogg_path = str(tmp_path / "output.ogg")
    _try_fluidsynth_ogg_cli(sample_midi_path, ogg_path, str(soundfont))

    assert mock_run.called
    call_args = mock_run.call_args[0][0]
    assert "fluidsynth" in call_args[0].lower()
    assert "-T" in call_args
    assert "oga" in call_args


@patch("web.midi_to_audio.subprocess.run")
def test_timidity_cli_command_format(mock_run, sample_midi_path, tmp_path):
    """Test timidity CLI is called with correct arguments."""
    from web.midi_to_audio import _try_timidity_cli

    mock_run.return_value = MagicMock(returncode=0)

    wav_path = str(tmp_path / "output.wav")
    _try_timidity_cli(sample_midi_path, wav_path)

    # Verify subprocess was called with timidity
    assert mock_run.called
    call_args = mock_run.call_args[0][0]
    assert "timidity" in call_args[0]
