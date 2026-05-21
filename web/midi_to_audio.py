"""
MIDI to Audio Converter

Converts MIDI files to browser-playable audio formats using FluidSynth.
"""

import os
import shutil
import subprocess
from importlib.util import find_spec
from pathlib import Path
from typing import Optional


def _find_soundfont(soundfont_path: Optional[str] = None) -> Optional[str]:
    """Find a usable SoundFont file."""
    if soundfont_path:
        return soundfont_path

    possible_paths = [
        Path(__file__).parent / "static" / "soundfonts" / "default.sf2",
        Path(__file__).parent / "static" / "soundfonts" / "FluidR3_GM.sf2",
        Path(__file__).parent / "static" / "soundfonts" / "FluidR3Mono_GM.sf3",
        Path(__file__).parent / "static" / "soundfonts" / "GeneralUser.sf2",
    ]
    for path in possible_paths:
        if path.exists():
            return str(path)

    return None


def _fluidsynth_command() -> str:
    """Return the best FluidSynth executable path for this machine."""
    configured = os.getenv("BIOSONIFICATION_FLUIDSYNTH")
    if configured:
        return configured

    discovered = shutil.which("fluidsynth")
    if discovered:
        return discovered

    windows_default = Path(r"C:\Tools\fluidsynth\bin\fluidsynth.exe")
    if windows_default.exists():
        return str(windows_default)

    return "fluidsynth"


def _try_midi2audio(midi_path: str, wav_path: str, soundfont_path: Optional[str] = None) -> bool:
    """
    Try converting MIDI to WAV using midi2audio library.

    Args:
        midi_path: Path to input MIDI file
        wav_path: Path to output WAV file
        soundfont_path: Optional path to soundfont file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        from midi2audio import FluidSynth

        # Create output directory if needed
        Path(wav_path).parent.mkdir(parents=True, exist_ok=True)

        soundfont_path = _find_soundfont(soundfont_path)

        # Initialize FluidSynth
        fs = FluidSynth(sound_font=soundfont_path)

        # Convert MIDI to WAV
        fs.midi_to_audio(midi_path, wav_path)

        # Check if output file was created
        if Path(wav_path).exists() and Path(wav_path).stat().st_size > 0:
            return True

        return False

    except Exception as e:
        print(f"midi2audio conversion failed: {e}")
        return False


def _try_fluidsynth_cli(midi_path: str, wav_path: str, soundfont_path: Optional[str] = None) -> bool:
    """
    Try converting MIDI to WAV using fluidsynth CLI.

    Args:
        midi_path: Path to input MIDI file
        wav_path: Path to output WAV file
        soundfont_path: Optional path to soundfont file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        # Create output directory if needed
        Path(wav_path).parent.mkdir(parents=True, exist_ok=True)

        soundfont_path = _find_soundfont(soundfont_path)

        if soundfont_path is None:
            return False

        # Try fluidsynth command
        cmd = [
            _fluidsynth_command(),
            "-ni",  # no interactive mode
            soundfont_path,
            midi_path,
            "-F",
            wav_path,  # output to file
            "-r",
            "44100",  # sample rate
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Check if output file was created
        if result.returncode == 0 and Path(wav_path).exists() and Path(wav_path).stat().st_size > 0:
            return True

        return False

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"fluidsynth CLI conversion failed: {e}")
        return False


def _try_timidity_cli(midi_path: str, wav_path: str) -> bool:
    """
    Try converting MIDI to WAV using timidity CLI.

    Args:
        midi_path: Path to input MIDI file
        wav_path: Path to output WAV file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        # Create output directory if needed
        Path(wav_path).parent.mkdir(parents=True, exist_ok=True)

        # Try timidity command
        cmd = ["timidity", midi_path, "-Ow", "-o", wav_path]  # output WAV

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Check if output file was created
        if result.returncode == 0 and Path(wav_path).exists() and Path(wav_path).stat().st_size > 0:
            return True

        return False

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"timidity CLI conversion failed: {e}")
        return False


def midi_to_wav(midi_path: str, wav_path: str, soundfont_path: Optional[str] = None) -> bool:
    """
    Convert MIDI to WAV using available methods with fallback.

    Tries methods in order:
    1. midi2audio library (recommended)
    2. fluidsynth CLI
    3. timidity CLI

    Args:
        midi_path: Path to input MIDI file
        wav_path: Path to output WAV file
        soundfont_path: Optional path to soundfont file

    Returns:
        True if conversion succeeded, False otherwise
    """
    # Try midi2audio first (most reliable)
    if _try_midi2audio(midi_path, wav_path, soundfont_path):
        return True

    # Fallback to fluidsynth CLI
    if _try_fluidsynth_cli(midi_path, wav_path, soundfont_path):
        return True

    # Fallback to timidity CLI
    if _try_timidity_cli(midi_path, wav_path):
        return True

    return False


def _try_fluidsynth_ogg_cli(midi_path: str, ogg_path: str, soundfont_path: Optional[str] = None) -> bool:
    """
    Try converting MIDI directly to OGG using FluidSynth CLI.

    Args:
        midi_path: Path to input MIDI file
        ogg_path: Path to output OGG file
        soundfont_path: Optional path to soundfont file

    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        Path(ogg_path).parent.mkdir(parents=True, exist_ok=True)

        soundfont_path = _find_soundfont(soundfont_path)
        if soundfont_path is None:
            return False

        cmd = [
            _fluidsynth_command(),
            "-ni",  # no interactive mode
            "-T",
            "oga",  # Ogg Vorbis output via libsndfile
            soundfont_path,
            midi_path,
            "-F",
            ogg_path,
            "-r",
            "44100",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and Path(ogg_path).exists() and Path(ogg_path).stat().st_size > 0:
            return True

        return False

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"fluidsynth OGG conversion failed: {e}")
        return False


def midi_to_ogg(midi_path: str, ogg_path: str, soundfont_path: Optional[str] = None) -> bool:
    """
    Convert MIDI to OGG for browser playback.

    FluidSynth can write OGG directly, so the normal path does not create a
    temporary WAV file.

    Args:
        midi_path: Path to input MIDI file
        ogg_path: Path to output OGG file
        soundfont_path: Optional path to soundfont file

    Returns:
        True if conversion succeeded, False otherwise
    """
    return _try_fluidsynth_ogg_cli(midi_path, ogg_path, soundfont_path)


def _check_midi2audio() -> bool:
    """Check if midi2audio library is available."""
    return find_spec("midi2audio") is not None


def _check_fluidsynth_cli() -> bool:
    """Check if fluidsynth CLI is available."""
    try:
        result = subprocess.run([_fluidsynth_command(), "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_fluidsynth_ogg_cli() -> bool:
    """Check if FluidSynth can render OGG and a SoundFont is available."""
    if _find_soundfont() is None:
        return False

    try:
        result = subprocess.run([_fluidsynth_command(), "-T", "help"], capture_output=True, text=True, timeout=5)
        output = f"{result.stdout}\n{result.stderr}".lower()
        return result.returncode == 0 and "'oga'" in output
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_timidity_cli() -> bool:
    """Check if timidity CLI is available."""
    try:
        result = subprocess.run(["timidity", "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_audio_synthesizer() -> dict:
    """
    Check which audio synthesizers are available.

    Returns:
        Dict with availability status for each method
    """
    return {
        "midi2audio": _check_midi2audio(),
        "fluidsynth": _check_fluidsynth_cli(),
        "ogg": _check_fluidsynth_ogg_cli(),
        "timidity": _check_timidity_cli(),
    }


def get_install_instructions() -> str:
    """
    Get installation instructions for audio synthesizers.

    Returns:
        String with installation instructions
    """
    status = check_audio_synthesizer()

    if status.get("ogg"):
        return "Audio playback enabled via FluidSynth OGG renderer."

    if status.get("fluidsynth") or status.get("timidity"):
        return "Audio synthesizer found, but OGG rendering is unavailable. Check SoundFont and FluidSynth OGG support."

    return """
Audio playback requires a MIDI synthesizer with OGG output. Install FluidSynth:

1. FluidSynth:
   - Windows: install to C:\\Tools\\fluidsynth or set BIOSONIFICATION_FLUIDSYNTH
   - macOS: brew install fluid-synth
   - Linux: apt-get install fluidsynth

After installation, restart the web server.
"""
