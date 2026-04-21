#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src pytest -v -m "not integration" --cov=src --cov-report=xml --cov-report=term --cov-fail-under=74
