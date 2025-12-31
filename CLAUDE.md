# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An AI-powered Date Night Reservation Agent that discovers upscale DC-area restaurants, maintains a curated list in Google Sheets, finds available reservations, and handles bookings through a conversational interface.

**Technology Stack:**
- Backend: Python 3.10+ with LangGraph for AI agents
- Frontend: React (planned)
- Data Storage: Google Sheets + local JSON
- AI Models: OpenAI GPT-5-mini, Anthropic Claude

## Project Structure

```
dn_reservation_agent/
├── docs/                      # Documentation
│   ├── GoogleAPI.md          # Google Sheets API setup guide
│   └── PRD.md                # Product Requirements Document
├── src/                       # Python source code
│   ├── agents/               # LangGraph agents
│   │   └── __init__.py
│   ├── clients/              # External API clients
│   │   ├── google_sheets_client.py
│   │   └── __init__.py
│   ├── models/               # Data models
│   │   ├── restaurant.py
│   │   └── __init__.py
│   ├── utils/                # Utilities
│   │   ├── config.py         # Configuration management
│   │   ├── logger.py         # JSON logging
│   │   └── __init__.py
│   ├── main.py               # Application entry point
│   └── __init__.py
├── frontend/                  # React frontend (to be implemented)
├── tests/                     # Test files
│   └── __init__.py
├── data/                      # Local data storage
├── logs/                      # JSON log files
├── .env                       # Environment variables (not in git)
├── .gitignore
├── CLAUDE.md                  # This file
├── README.md
└── requirements.txt
```

## Development Environment

**Python virtual environment** is located at `.venv/`. Activate it with:
```bash
source .venv/bin/activate  # macOS/Linux
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Commands

### Running the Application
```bash
# Run main application
python src/main.py

# Test Google Sheets connection
python src/clients/google_sheets_client.py
```

### Testing
```bash
# Run tests (once configured)
pytest tests/

# Run specific test
pytest tests/test_google_sheets.py
```

### Linting/Formatting
(To be configured - recommend: black, flake8, mypy)

## Configuration

All configuration is managed through `.env` file. See `.env` for required variables:
- API keys (OpenAI, Anthropic, OpenTable, Resy, Tock, Yelp)
- Google Sheets configuration
- Location and reservation preferences

**Important:** Never commit `credentials.json`, `token.json`, or `.env` to git.

## Architecture

### Backend Components

**1. Agents (src/agents/)**
- Restaurant Discovery Agent: Searches for new restaurants, evaluates them, and proposes list updates
- Reservation Booking Agent: Finds availability and books reservations

**2. Clients (src/clients/)**
- `google_sheets_client.py`: Manages the restaurant list in Google Sheets
- Future: OpenTable, Resy, Tock, Yelp API clients

**3. Models (src/models/)**
- `restaurant.py`: Restaurant data model matching Google Sheets schema (FR-2.1)

**4. Utils (src/utils/)**
- `config.py`: Configuration management from .env
- `logger.py`: JSON-formatted logging

### Data Flow

1. **Restaurant Discovery**: Web search → Evaluation → User approval → Google Sheets update
2. **Reservation Booking**: User request → Search availability → Present options → User selects → Book → Confirm

### External Integrations

- **Google Sheets API**: Restaurant list storage (see docs/GoogleAPI.md)
- **OpenTable/Resy/Tock**: Reservation platforms (to be implemented)
- **Yelp API**: Restaurant reviews and ratings
- **Web scraping**: Eater DC, Washington Post, Washingtonian

## Development Guidelines

1. **Follow PRD**: See docs/PRD.md for all functional requirements
2. **Use type hints**: All Python code should include type annotations
3. **Log everything**: Use JSON logging (src/utils/logger.py) for all operations
4. **Test before commit**: Run tests and manual validation
5. **User approval first**: All restaurant list modifications require user confirmation (FR-2.3)
