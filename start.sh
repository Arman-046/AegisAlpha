#!/bin/bash
echo "Seeding initial historical data..."
python inject_mock_data.py

echo "Starting AegisAlpha Background Worker..."
python main.py &

echo "Starting AegisAlpha Web Dashboard..."
streamlit run dashboard.py --server.port $PORT --server.address 0.0.0.0
