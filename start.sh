#!/usr/bin/env bash
cd mcp_server
python server.py &
sleep 3
cd ../backend
uvicorn main:app --host 0.0.0.0 --port $PORT