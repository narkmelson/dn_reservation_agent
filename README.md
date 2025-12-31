# Date Night Reservation Agent

An AI-powered reservation agent that discovers upscale DC-area restaurants, maintains a curated list in Google Sheets, finds available reservations matching your preferences, and handles the booking process through a conversational interface.

## Features

### Restaurant Discovery
- Automatically searches authoritative DC sources (Eater DC, Washington Post, Washingtonian)
- Filters for upscale dining ($$-$$$$ price range)
- Evaluates based on reviews, ambience, and trending status
- Proposes additions/removals to your curated list

### Smart List Management
- Maintains restaurant list in Google Sheets with detailed metadata
- Requires user approval before making changes
- Supports conversational editing via chat interface

### Reservation Booking
- Searches your curated list for available reservations
- Matches your day/time preferences automatically
- Integrates with OpenTable, Resy, and Tock
- Presents up to 3 options, then books your selection

## Quick Start

### 1. Clone and Setup Python Environment

```bash
git clone <repository-url>
cd dn_reservation_agent
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure Google Sheets

Follow the detailed guide in [docs/GoogleAPI.md](docs/GoogleAPI.md):

1. Create a Google Cloud project and enable Sheets API
2. Set up OAuth 2.0 credentials (download as `credentials.json`)
3. Create a Google Sheet named "Date Night Restaurant List"
4. Add the spreadsheet ID to `.env`

### 3. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# Required
GOOGLE_SHEETS_SPREADSHEET_ID=<your-spreadsheet-id>
OPENAI_API_KEY=<your-openai-key>
ANTHROPIC_API_KEY=<your-anthropic-key>

# Optional (for reservation booking)
OPENTABLE_API_KEY=<your-opentable-key>
RESY_API_KEY=<your-resy-key>
TOCK_API_KEY=<your-tock-key>
YELP_API_KEY=<your-yelp-key>

# Customize preferences
DEFAULT_CITY=Washington
DEFAULT_STATE=DC
DAY_OF_WEEK=[Friday, Saturday]
TIME_OF_DAY_START=5:30PM
TIME_OF_DAY_END=8:00PM
PARTY_SIZE=2
```

### 4. Run the Application

```bash
# Test configuration and Google Sheets connection
python src/main.py

# Test Google Sheets client directly
python src/clients/google_sheets_client.py
```

## Project Structure

```
dn_reservation_agent/
├── docs/                      # Documentation
│   ├── GoogleAPI.md          # Google Sheets setup guide
│   └── PRD.md                # Product requirements
├── src/                       # Python source code
│   ├── agents/               # LangGraph AI agents
│   ├── clients/              # API clients (Google Sheets, etc.)
│   ├── models/               # Data models
│   ├── utils/                # Config and logging
│   └── main.py               # Application entry point
├── frontend/                  # React UI (planned)
├── tests/                     # Test suite
├── data/                      # Local data storage
└── logs/                      # JSON log files
```

## Documentation

- **[docs/PRD.md](docs/PRD.md)** - Complete product requirements and feature specifications
- **[docs/GoogleAPI.md](docs/GoogleAPI.md)** - Google Sheets API setup and usage guide
- **[CLAUDE.md](CLAUDE.md)** - Development guide for Claude Code

## Technology Stack

- **Backend**: Python 3.10+, LangGraph for AI agents
- **Frontend**: React (planned)
- **AI Models**: OpenAI GPT-5-mini, Anthropic Claude
- **Data Storage**: Google Sheets + local JSON
- **APIs**: OpenTable, Resy, Tock, Yelp

## Development Status

**Phase 1 (In Progress):**
- ✅ Project structure and configuration
- ✅ Google Sheets integration
- ✅ Data models and utilities
- ⏳ Restaurant discovery agent
- ⏳ Web scraping for restaurant sources

**Phase 2 (Planned):**
- ⏳ Reservation availability search
- ⏳ Booking automation
- ⏳ React frontend
- ⏳ Chat interface

## Requirements

- Python 3.10.7 or higher
- Google Cloud account (for Sheets API)
- API keys for AI services and reservation platforms
- Chrome browser (for frontend, when implemented)

## Contributing

This is a personal project for planning date nights in the DC area. See [docs/PRD.md](docs/PRD.md) for the full vision and roadmap.

## License

Private project - not licensed for public use.
