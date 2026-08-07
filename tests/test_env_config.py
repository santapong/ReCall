"""B3: a blank env var must behave exactly like an unset one.

`os.environ.get(k, "nan")` returns its default only when the key is *absent*. An
empty string goes straight into `float("")` and raises at import — so
`cp .env.example .env && source .env` (the quickstart README:AC9 promises works)
detonated every import with no hint why, and blank values in the Lambda console did
the same in production.

These run in a subprocess on purpose: the constants are evaluated at import time, so
a fresh interpreter is the only honest way to test them.
"""

import subprocess
import sys
from pathlib import Path

LAMBDA_DIR = Path(__file__).resolve().parents[1] / "lambda"

# Exactly what .env.example ships pre-tuning: present, and empty.
BLANK_ENV = {
    "CONFIDENCE_HIGH_MAX_DIST": "",
    "CONFIDENCE_NONE_MIN_DIST": "",
    "DECAY_HALF_LIFE_DAYS": "",
    "EMBED_DIM": "",
}


def _import_in_subprocess(module: str, env_overrides: dict) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, "PYTHONPATH": str(LAMBDA_DIR), **env_overrides}
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=env, capture_output=True, text=True,
    )


def test_tools_imports_with_blank_threshold_vars():
    result = _import_in_subprocess("tools", BLANK_ENV)
    assert result.returncode == 0, result.stderr


def test_embed_imports_with_blank_dimension():
    result = _import_in_subprocess("embed", BLANK_ENV)
    assert result.returncode == 0, result.stderr


def test_blank_thresholds_are_nan_not_zero():
    """NaN, not 0.0 — an untuned threshold must not silently label everything
    'high'. Every comparison against NaN is False, so the bands stay unusable until
    P1 tuning writes real numbers, which is the intended loud failure (AC13)."""
    import os

    env = {**os.environ, "PYTHONPATH": str(LAMBDA_DIR), **BLANK_ENV}
    result = subprocess.run(
        [sys.executable, "-c",
         "import math, tools; "
         "print(math.isnan(tools.CONF_HIGH_MAX_DIST), math.isnan(tools.CONF_NONE_MIN_DIST))"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True True"


def test_blank_decay_half_life_falls_back_to_the_documented_default():
    import os

    env = {**os.environ, "PYTHONPATH": str(LAMBDA_DIR), **BLANK_ENV}
    result = subprocess.run(
        [sys.executable, "-c", "import tools; print(tools.DECAY_HALF_LIFE_DAYS)"],
        env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "90.0"
