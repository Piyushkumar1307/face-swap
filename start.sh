#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
