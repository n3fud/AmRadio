#!/usr/bin/env python3
"""
Callsign Lookup Web App - Flask Backend
Bridges the web UI to a Linux command line application.

This example uses 'curl' to query the QRZ.com XML API or falls back to
the 'whois' command as a demo. Swap out the subprocess call in
`run_cli_command()` with your actual CLI tool.

Install deps:  pip install flask flask-cors
Run:           python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import shlex
import re
import json

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — change CLI_COMMAND to your actual Linux CLI application
# ─────────────────────────────────────────────────────────────────────────────
# Example 1 (ham radio callsign via curl):
#   CLI_COMMAND = "curl -s 'https://callook.info/{callsign}/json'"
#
# Example 2 (custom CLI tool):
#   CLI_COMMAND = "/usr/local/bin/my-radio-tool --lookup {callsign}"
#
# Example 3 (python script):
#   CLI_COMMAND = "python3 /opt/lookup/lookup.py {callsign}"

CLI_COMMAND = "curl -s 'https://callook.info/{callsign}/json'"


def sanitize_callsign(raw: str) -> str:
    """Strip anything that's not alphanumeric or slash (portable calls)."""
    cleaned = re.sub(r"[^A-Za-z0-9/]", "", raw).upper()
    if len(cleaned) < 3 or len(cleaned) > 12:
        raise ValueError("Callsign must be 3–12 characters.")
    return cleaned


def run_cli_command(callsign: str) -> dict:
    """
    Execute the CLI command and return a structured response dict.
    Modify parse_output() to match your tool's actual output format.
    """
    cmd = CLI_COMMAND.format(callsign=callsign)
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=15,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    return_code = result.returncode

    return {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": return_code,
        "parsed": parse_output(stdout, callsign),
    }


def parse_output(stdout: str, callsign: str) -> dict | None:
    """
    Parse the CLI output into structured fields.
    This default parser handles the callook.info JSON response.
    Replace this with your own parser for a custom CLI tool.
    """
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
        if data.get("status") == "VALID":
            trustee = data.get("trustee", {})
            address = data.get("address", {})
            location = data.get("location", {})
            otherInfo = data.get("otherInfo", {})
            return {
                "callsign": data.get("current", {}).get("callsign", callsign),
                "name": trustee.get("name", "—"),
                "license_class": data.get("current", {}).get("operClass", "—"),
                "grant_date": otherInfo.get("grantDate", "—"),
                "expiry_date": otherInfo.get("expiryDate", "—"),
                "address": f"{address.get('line1','')} {address.get('line2','')}".strip(),
                "latitude": location.get("latitude", "—"),
                "longitude": location.get("longitude", "—"),
                "grid_square": location.get("gridsquare", "—"),
                "status": "VALID",
            }
        elif data.get("status") == "UPDATING":
            return {"status": "UPDATING", "callsign": callsign}
        else:
            return {"status": "INVALID", "callsign": callsign}
    except json.JSONDecodeError:
        # Raw text output — return as-is
        return {"status": "RAW", "callsign": callsign, "raw": stdout}


# ─────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/lookup", methods=["GET"])
def lookup():
    raw_callsign = request.args.get("callsign", "").strip()
    if not raw_callsign:
        return jsonify({"error": "No callsign provided."}), 400

    try:
        callsign = sanitize_callsign(raw_callsign)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        result = run_cli_command(callsign)
        return jsonify({"callsign": callsign, **result})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "CLI command timed out."}), 504
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    print("🔊 Callsign Lookup Server running at http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
