#!/bin/sh
# Single-container mode for hosts that expose one public port (Render, Railway, HF Spaces).
# API listens privately on 8000; the Streamlit UI listens on $PORT (default 8501).
set -e
export API_URL="http://127.0.0.1:8000"
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
exec streamlit run frontend/app.py --server.port "${PORT:-8501}" --server.address 0.0.0.0 \
  --server.headless true --server.enableCORS false --server.enableXsrfProtection false
