"""
BioSonification Web Interface - Flask Application

Web interface for generating music from biological FASTA sequences.
"""

import os
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, render_template, request, send_file

from .generator import BioMusicGenerator, FASTAValidationError, get_generator
from .midi_to_audio import check_audio_synthesizer, get_install_instructions, midi_to_ogg

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Flask app
app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "web" / "templates"),
    static_folder=str(PROJECT_ROOT / "web" / "static"),
    static_url_path="/static",
)

# Disable caching for development
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def add_header(response):
    """Disable caching for all responses"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response


# Output directory for generated files
OUTPUT_DIR = PROJECT_ROOT / "web" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Max file size (10MB)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


def _audio_enabled(synth_status: dict) -> bool:
    """Return whether browser-playable generated audio can be rendered."""
    return bool(synth_status.get("ogg"))


@app.route("/")
def index():
    """Main page."""
    # Check synthesizer availability
    synth_status = check_audio_synthesizer()
    return render_template(
        "index.html",
        audio_enabled=_audio_enabled(synth_status),
        install_instructions=get_install_instructions(),
    )


@app.route("/api/generate", methods=["POST"])
def generate():
    """Generate music from FASTA sequence."""
    try:
        # Get FASTA input
        data = request.get_json(silent=True) if request.is_json else {}
        if data is None:
            data = {}
        fasta_text = data.get("fasta", "").strip()
        fasta_file = request.files.get("fasta_file")

        # Try file upload first, then text
        if fasta_file and fasta_file.filename:
            try:
                fasta_text = fasta_file.read().decode("utf-8")
            except UnicodeDecodeError:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Uploaded file is not valid UTF-8 text. Please upload a plain-text FASTA file.",
                        }
                    ),
                    400,
                )
        elif not fasta_text:
            return jsonify({"success": False, "error": "Please provide a FASTA file or paste a FASTA sequence"}), 400

        # Validate the submitted content before initializing the generator/model.
        BioMusicGenerator.validate_fasta(fasta_text)

        # Get generator
        generator = get_generator()

        # Initialize if needed
        if not generator.is_ready():
            if not generator.initialize():
                return (
                    jsonify({"success": False, "error": generator.get_error() or "Failed to initialize generator"}),
                    500,
                )

        # Generate music
        result = generator.generate(fasta_text, str(OUTPUT_DIR))

        # Try to convert MIDI to OGG for audio playback
        midi_path = result["midi_path"]
        session_id = result["session_id"]
        ogg_path = str(OUTPUT_DIR / "audio" / f"{session_id}.ogg")

        audio_available = False
        if midi_to_ogg(midi_path, ogg_path):
            result["audio_path"] = ogg_path
            result["audio_filename"] = f"{session_id}.ogg"
            result["audio_format"] = "ogg"
            result["audio_mimetype"] = "audio/ogg"
            audio_available = True

        result["audio_available"] = audio_available
        result["success"] = True

        # Remove internal paths from response
        del result["midi_path"]

        return jsonify(result)

    except FASTAValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": f"Generation failed: {str(e)}"}), 500


@app.route("/api/download/<session_id>/<file_type>")
def download_file(session_id, file_type):
    """Download generated file (MIDI or OGG)."""
    if file_type == "midi":
        file_path = OUTPUT_DIR / "midi" / f"{session_id}.mid"
        mimetype = "audio/midi"
        as_attachment = True
    elif file_type == "ogg":
        file_path = OUTPUT_DIR / "audio" / f"{session_id}.ogg"
        mimetype = "audio/ogg"
        as_attachment = True
    else:
        return jsonify({"error": "Invalid file type"}), 400

    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(str(file_path), mimetype=mimetype, as_attachment=as_attachment, download_name=file_path.name)


@app.route("/api/status")
def status():
    """Check application status."""
    generator = get_generator()
    if not generator.is_ready() and generator.get_error() is None:
        generator.initialize()
    synth_status = check_audio_synthesizer()

    return jsonify(
        {
            "ready": generator.is_ready(),
            "error": generator.get_error() if not generator.is_ready() else None,
            "generator": generator.status_payload(),
            "audio_synthesizers": synth_status,
            "audio_enabled": _audio_enabled(synth_status),
        }
    )


@app.route("/api/survey/submit", methods=["POST"])
def submit_survey():
    """Submit human evaluation survey responses."""
    import json
    from datetime import datetime

    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No data provided"}), 400

        timestamp = datetime.now().isoformat()
        if isinstance(data, list):
            payload = {"timestamp": timestamp, "responses": data}
        elif isinstance(data, dict):
            payload = data
            payload["timestamp"] = timestamp
        else:
            return jsonify({"error": "Invalid payload format"}), 400

        # Save response
        surveys_dir = PROJECT_ROOT / "results" / "surveys"
        surveys_dir.mkdir(parents=True, exist_ok=True)

        # Append to responses file
        responses_file = surveys_dir / "survey_responses.jsonl"
        with open(responses_file, "a") as f:
            f.write(json.dumps(payload) + "\n")

        return jsonify({"success": True, "message": "Response saved"})

    except Exception as e:
        return jsonify({"error": f"Failed to save response: {str(e)}"}), 500


@app.route("/api/survey/results")
def survey_results():
    """Get aggregated survey results (for admin)."""
    import json

    surveys_dir = PROJECT_ROOT / "results" / "surveys"
    responses_file = surveys_dir / "survey_responses.jsonl"

    if not responses_file.exists():
        return jsonify({"error": "No responses yet", "count": 0})

    # Load all responses
    responses = []
    with open(responses_file, "r") as f:
        for line in f:
            if line.strip():
                responses.append(json.loads(line))

    # Compute statistics
    if not responses:
        return jsonify({"count": 0})

    def _flatten_responses(items):
        flat = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("responses"), list):
                flat.extend(item["responses"])
            elif isinstance(item, list):
                flat.extend(item)
            elif isinstance(item, dict):
                flat.append(item)
        return flat

    flat_responses = _flatten_responses(responses)
    if not flat_responses:
        return jsonify({"count": 0})

    # Aggregate ratings by condition
    stats = {"total_responses": len(flat_responses), "by_condition": {}, "attention_check_pass_rate": 0.0}

    attention_total = 0
    attention_ok = 0
    for resp in flat_responses:
        if not isinstance(resp, dict):
            continue
        condition = resp.get("condition", "unknown")
        if condition not in stats["by_condition"]:
            stats["by_condition"][condition] = {
                "count": 0,
                "musicality_mean": [],
                "structure_mean": [],
                "variety_mean": [],
            }

        stats["by_condition"][condition]["count"] += 1
        stats["by_condition"][condition]["musicality_mean"].append(resp.get("musicality", 0))
        stats["by_condition"][condition]["structure_mean"].append(resp.get("structure", 0))
        stats["by_condition"][condition]["variety_mean"].append(resp.get("variety", 0))
        if resp.get("is_attention_check"):
            attention_total += 1
            if resp.get("musicality") == 3 and resp.get("structure") == 3 and resp.get("variety") == 3:
                attention_ok += 1

    # Compute means
    for condition in stats["by_condition"]:
        c = stats["by_condition"][condition]
        c["musicality_mean"] = float(np.mean(c["musicality_mean"]))
        c["structure_mean"] = float(np.mean(c["structure_mean"]))
        c["variety_mean"] = float(np.mean(c["variety_mean"]))
    stats["attention_check_pass_rate"] = float(attention_ok / attention_total) if attention_total else None

    return jsonify(stats)


@app.route("/api/examples")
def get_examples():
    """Get list of example compositions."""
    from .examples_data import EXAMPLES

    return jsonify({"examples": EXAMPLES})


@app.route("/api/examples/<example_id>/midi")
def download_example_midi(example_id):
    """Download example MIDI file."""
    from .examples_data import EXAMPLES

    example = next((ex for ex in EXAMPLES if ex["id"] == example_id), None)
    if not example:
        return jsonify({"error": "Example not found"}), 404

    midi_path = PROJECT_ROOT / "web" / "static" / "examples" / "midi" / example["midi_filename"]
    if not midi_path.exists():
        return jsonify({"error": "MIDI file not found"}), 404

    return send_file(str(midi_path), mimetype="audio/midi", as_attachment=True, download_name=example["midi_filename"])


@app.route("/api/examples/<example_id>/audio")
def stream_example_audio(example_id):
    """Stream example audio (OGG)."""
    from .examples_data import EXAMPLES

    example = next((ex for ex in EXAMPLES if ex["id"] == example_id), None)
    if not example:
        return jsonify({"error": "Example not found"}), 404

    audio_dir = PROJECT_ROOT / "web" / "static" / "examples" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    ogg_filename = example["midi_filename"].replace(".mid", ".ogg")
    ogg_path = audio_dir / ogg_filename

    # Convert MIDI to OGG if not exists
    if not ogg_path.exists():
        midi_path = PROJECT_ROOT / "web" / "static" / "examples" / "midi" / example["midi_filename"]
        if not midi_path.exists():
            return jsonify({"error": "MIDI file not found"}), 404

        if not midi_to_ogg(str(midi_path), str(ogg_path)):
            return jsonify({"error": "Audio conversion failed. Install FluidSynth with OGG support."}), 500

    return send_file(str(ogg_path), mimetype="audio/ogg", as_attachment=False)


@app.route("/health")
def health():
    """Health check endpoint for monitoring."""
    from datetime import datetime

    generator = get_generator()

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "generator_ready": generator.is_ready(),
    }

    # Check GPU availability
    try:
        import torch

        health_status["gpu_available"] = torch.cuda.is_available()
    except Exception:
        health_status["gpu_available"] = False

    if not generator.is_ready():
        health_status["status"] = "degraded"
        health_status["error"] = generator.get_error()

    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large. Maximum size is 10MB."}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500


def setup_logging():
    """Configure logging for production."""
    import logging
    from logging.handlers import RotatingFileHandler

    log_level = os.getenv("BIOSONIFICATION_LOG_LEVEL", "INFO")
    log_file = os.getenv("BIOSONIFICATION_LOG_FILE")

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(file_handler)

    # Set Flask app logger level
    app.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def main():
    """Run the web application."""
    # Setup logging
    setup_logging()

    # Pre-initialize generator
    print("Initializing BioSonification generator...")
    generator = get_generator()
    if generator.initialize():
        print("Generator ready!")
    else:
        print(f"Generator initialization failed: {generator.get_error()}")
        print("Please ensure you have run the full pipeline first to train a model.")

    print("\nStarting web server...")

    host = os.getenv("BIOSONIFICATION_HOST", "127.0.0.1")
    port_str = os.getenv("BIOSONIFICATION_PORT", "5001")
    try:
        port = int(port_str)
    except ValueError:
        port = 5001
        print(f"Invalid BIOSONIFICATION_PORT='{port_str}', fallback to {port}")

    debug_flag = os.getenv("BIOSONIFICATION_DEBUG", "").strip().lower()
    debug = debug_flag in {"1", "true", "yes", "on"}

    print(f"Server config: host={host}, port={port}, debug={debug}")
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    main()
