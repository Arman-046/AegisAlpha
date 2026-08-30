#!/bin/bash
echo "Starting AegisAlpha Background Worker..."
python main.py &

echo "Starting AegisAlpha Web Dashboard..."
streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0
