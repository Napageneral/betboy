# BetBoy

Voice-powered Polymarket search. Speak a sports event and an AI agent finds the closest matching prediction market.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your_key_here"

# Run the server
python server.py
```

Open http://localhost:8000 in your browser (Chrome recommended for voice).

## How it Works

1. **Voice Input** - Click the microphone and say something like "Lakers vs Celtics" or "Super Bowl winner"
2. **AI Agent** - Claude searches Polymarket using multiple relevant terms
3. **Results** - See the betting odds and click through to Polymarket to place bets

## Features

- 🎤 Browser-based voice recognition (no external services)
- 🤖 Claude-powered intelligent market search
- 📊 Real-time Polymarket odds display
- 🔗 Direct links to bet on Polymarket

## Tech Stack

- **Backend**: FastAPI + Python
- **Agent**: Claude (claude-sonnet-4-20250514) with tool use
- **Frontend**: Vanilla JS + Web Speech API
- **Data**: Polymarket Gamma API

