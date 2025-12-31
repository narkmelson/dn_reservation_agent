# Product Requirements Document: Date Night Reservation Agent

**Version:** 1.0
**Last Updated:** 2025-12-30
**Status:** Draft

---

## 1. Overview

### 1.1 Problem Statement
Planning date nights requires significant time investment to discover new restaurants, check availability, and make reservations. The current process involves browsing multiple websites, comparing options, and manually tracking which restaurants have been tried.

### 1.2 Solution
An AI-powered reservation agent that discovers upscale DC-area restaurants, maintains a curated list, finds available reservations matching preferences, and handles the booking process through a conversational interface.

### 1.3 Target Users
- Primary: You and your wife for planning date nights
- Use case: Monthly upscale dining experiences

---

## 2. Goals & Success Metrics

### 2.1 Goals
- Reduce time spent planning date nights from manual browsing to a single conversation
- Discover new, high-quality restaurants automatically
- Maintain an organized, up-to-date list of restaurant options
- Streamline the reservation booking process

### 2.2 Success Metrics
- Time from user initiated reservation request to successful booking (target: < 5 minutes?)
- Percentage of successful bookings on first attempt (target: >80%)

---

## 3. User Stories

### Core Workflows

**As a user, I want to:**

1. **Discover new restaurants**
   - See newly opened or trending upscale restaurants in my area
   - Get recommendations from authoritative sources (Eater DC, Washington Post, Washingtonian)
   - Filter out fast-casual and budget options automatically

2. **Manage my restaurant list**
   - Review recommended additions/removals before they're applied
   - Edit the restaurant list through natural conversation
   - See descriptions and booking website for each restaurant

3. **Find and book reservations**
   - Request reservation options matching my day/time preferences
   - See up to 3 restaurant options with available reservations
   - Confirm a restaurant and have the agent attempt booking
   - Be notified if booking fails so I can take manual action
---

## 4. Functional Requirements

### 4.1 Restaurant Discovery Engine

**FR-1.1: Web Search for New Restaurants**
- Search authoritative DC-area restaurant sources:
  - Eater DC, especially the "Hot" restaurants
  - Washington Post Food section
  - Washingtonian magazine
  - Other credible publications (e.g. Time Out)
- Filter criteria:
  - Location matches `.env` preferences
  - Upscale/fine dining
  - Interesting and high-quality food
  - Price range bounds of $$-$$$$ on typical scales
  - EXCLUDE: Fast-casual, cheap restaurants, chains

**FR-1.2: Restaurant Evaluation Criteria**
- Priority 1: "hot" or "trending" restaurant lists from sources
- Priority 2: great customer reviews on Yelp
- Priority 3: Nice environment/ambience
- Priority 4: a great cocktail/wine list
- Priority 5: Restaurants within limits of city in location preferences, even if search radius includes a broader area

**FR-1.3: Priority Rank**
- For restaurants that meet the filter criteria, please assign a rank of "Top", "Great", "Good", "Medium", or "Low" based on the criteria

### 4.2 Restaurant List Management

**FR-2.1: Google Sheet Set-Up **


**FR-2.1: Google Sheets **
- Maintain restaurant list in Google Sheets with fields:
  - Restaurant Name
  - Booking website
  - Brief Description
  - Yelp Review Average
  - Recommendation Source
  - Price Range
  - Cuisine Type
  - Priority Rank
  - Date Added

**FR-2.2: Google Sheet Update Workflow**
- Compare discovery results against existing list
- Surface additions and removals to user for confirmation. For additions, please surface the restuarant name, priority rank, Yelp review avg, and brief description.
- Only apply changes after user approval
- Support conversational editing (add/remove/update restaurants via chat)

**FR-2.3: User Control**
- All list modifications require user confirmation
- Support manual overrides and edits

### 4.3 Reservation Search & Booking

**FR-3.1: Availability Search**
- Search curated restaurant list for available reservations
- Search for dates between next 30 days
- Match against "Reservation Preferences" from `.env`:
  - DAY_OF_WEEK: comma-seperated list of days of week (e.g. Monday, Tuesday)
  - TIME_OF_DAY_START: the start time for reservation times
  - TIME_OF_DAY_END: the end of reservation times range. Please only include reservation times that are between or equal to the start and end times.
  - PARTY_SIZE: the number of people to search for
- Return up to 3 restaurant options with available reservations

**FR-3.2: Booking Process**
- User confirms restaurant selection from options
- Agent attempts to book the reservation
- Report success or failure to user

**FR-3.3: Reservation Apps**
- Connect to restaurants available on OpenTable, Resy, or Tock. Any other restaurant on the list will need to be manually searched and booked by user.
-  Required .env variables:
  - OPENTABLE_API_KEY
  - RESY_API_KEY
  - TOCK_API_KEY

**FR-3.4: Booking Failure Handling**
- If restaurant requires credit card, inform user so they can manually book
- If agent runs into any error connecting with the reservation platform, either searching for restaurant availability or booking the reservation, please inform user of failure with both a natural language and technical description of the error

### 4.5 Quick Actions

**FR-5.1: Predefined Actions**
- "Update Restaurant List" button that initiates the restaurant discovery process
- "Book Reservation" button that initiates the find and book reservation process

---

## 5. Non-Functional Requirements

### 5.1 Performance
- Max time for restaurant discovery search: 5 minutes
- Max time for reservation availability check: 3 minutes
- Max time for booking attempt: 3 minutes

### 5.2 Reliability
Reliability requirements:
- If agent fails in search or booking, please retry once more and then reply back to user with the technical description of the error

### 5.3 Usability
- Simple, conversational chat interface
- Clear feedback on all operations
- Confirmation required for all modifications

---

## 6. Technical Architecture

### 6.1 Frontend Specifications
- **Platform:** Locally hosted web application
- **Interface:** Chat-based conversational UI
- **Features:**
  - Bidirectional conversation
  - Dynamic recommendation updates based on user feedback
  - Quick action buttons for common tasks
  - Display of restaurant options and reservations

Frontend technical details:
- Use React framework
- Only will be used on desktop, no mobile design frameworks needed
- Single-user/single-device
- Browser compatibility with Chrome

### 6.2 Backend Specifications
- **Data Storage:**
  - Restaurant list: Google Sheets
  - All other data: Local storage

Backend technical details:
- Local storage in JSON files within project repository
- Google Sheets API authentication using credentials in `.env`
- Concurrency: Only support a single user session
- API rate limiting considerations?
- Please create logs in JSON format with 

### 6.3 External Integrations
- **Required:**
  - Google Sheets API
  - Web search and scraping tool for Restaurant searches
  - Different integrations are needed for OpenTable, Resy, and Tock
  - OpenTable use API

### 6.4 AI/LLM Integration
- Use LangGraph for the agent framework
- Use gpt-5-mini for LLM in LangGraph
- Create two different graphs: one for the restaurant research and list management, and another for the reservation booking

---

## 7. Scope

### 7.1 In Scope - Phase 1 (MVP)
- Restaurant discovery from specified DC sources
- Google Sheets integration for restaurant list
- User confirmation workflow for list updates
- Basic chat interface

### 7.2 In Scope - Phase 2 (MVP)
- Reservation availability search
- Agentic reservation booking
- Manual booking process in failure (agent provides booking link/info)

### 7.3 Explicitly Out of Scope
- Ride/transportation booking
- Activity planning beyond dining
- Group reservations (larger parties)
- Multi-city support (DC only for now)
- Budget/cheap restaurants
- Fast-casual dining
- Food delivery services

---

## 8. User Experience & Workflows

### 8.1 Primary User Flow: Finding a Reservation

```
1. User: "Find me a reservation for Friday night"
2. Agent: Searches curated list for Friday reservations (7-9pm based on .env)
3. Agent: Presents 3 options with available times
4. User: "I'll take option 2"
5. Agent: Attempts booking and confirms success/failure
```

### 8.2 Restaurant Discovery Flow

```
1. User: Clicks "Update restaurant list" OR says "Find new restaurants"
2. Agent: Searches Eater DC, WaPo, Washingtonian, etc.
3. Agent: "I found 5 new restaurants and 2 closed. Add them?"
   - Lists new restaurants with descriptions
4. User: Reviews and confirms/modifies
5. Agent: Updates Google Sheet
```

### 8.3 List Management Flow

```
1. User: "Remove [Restaurant X] from my list"
2. Agent: "Confirm removing [Restaurant X]?"
3. User: "Yes"
4. Agent: Updates Google Sheet
```