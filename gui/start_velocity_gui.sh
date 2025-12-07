#!/bin/bash
# Wrapper to start Velocity GUI from Desktop functionality
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
python3 app.py
