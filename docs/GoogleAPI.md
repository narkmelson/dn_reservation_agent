# Google Sheets API - Technical Requirements

**Document Version:** 1.0
**Last Updated:** 2025-12-30
**Purpose:** Technical setup and requirements for authenticating and updating the "Date Night Restaurant List" Google Sheet

---

## 1. Overview

This document outlines the technical requirements for integrating with Google Sheets API to manage the restaurant list for the Date Night Reservation Agent.

**Google Sheet Name:** "Date Night Restaurant List"
**Primary Operations:** Read, Write, Update cell values
**Authentication Method:** OAuth 2.0 (Desktop Application)

---

## 2. Prerequisites

### 2.1 Software Requirements
- Python 3.10.7 or greater
- pip package manager
- Google Account with access to Google Drive and Google Sheets

### 2.2 Python Packages
The following packages are required (already added to `requirements.txt`):
```
google-api-python-client>=2.108.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.0
```

Install with:
```bash
pip install -r requirements.txt
```

---

## 3. Google Cloud Setup

### 3.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note the project name and ID

### 3.2 Enable Google Sheets API

1. In Google Cloud Console, navigate to **APIs & Services > Library**
2. Search for "Google Sheets API"
3. Click **Enable**

### 3.3 Configure OAuth Consent Screen

1. Navigate to **APIs & Services > OAuth consent screen**
2. Select **User type: Internal** (for testing) or **External** (for broader use)
3. Fill in required information:
   - App name: "Date Night Reservation Agent"
   - User support email: Your email
   - Developer contact information: Your email
4. Click **Save and Continue**
5. Skip adding scopes for now (we'll use them in the application)
6. Click **Save and Continue** through remaining screens

### 3.4 Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services > Credentials**
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**
3. Select **Application type: Desktop app**
4. Name: "Date Night Agent Desktop Client"
5. Click **Create**
6. Download the credentials JSON file
7. Save it as `credentials.json` in the project root directory
8. **IMPORTANT:** Add `credentials.json` to `.gitignore` to prevent committing sensitive data

---

## 4. Google Sheets Setup

### 4.1 Create the Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Create a new spreadsheet
3. Name it: **"Date Night Restaurant List"**

### 4.2 Sheet Structure (FR-2.1 Requirements)

The spreadsheet must have the following columns (in this order):

| Column | Field Name | Data Type | Description |
|--------|------------|-----------|-------------|
| A | Restaurant Name | Text | Full name of the restaurant |
| B | Booking Website | URL | URL for making reservations |
| C | Brief Description | Text | Short description of cuisine/atmosphere |
| D | Yelp Review Average | Number | Average Yelp rating (e.g., 4.5) |
| E | Recommendation Source | Text | Where restaurant was discovered |
| F | Price Range | Text | $ to $$$$ scale |
| G | Cuisine Type | Text | Type of cuisine (Italian, French, etc.) |
| H | Priority Rank | Text | Top, Great, Good, Medium, or Low |
| I | Date Added | Date | Date added to list (YYYY-MM-DD) |

**Header Row:** Row 1 should contain the column names listed above.

### 4.3 Get Spreadsheet ID

The Spreadsheet ID is found in the URL of your Google Sheet:

```
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
```

Copy the `SPREADSHEET_ID` portion and add it to your `.env` file:
```
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
```

---

## 5. Authentication Flow

### 5.1 OAuth 2.0 Scopes Required

The application requires the following OAuth scope:
```
https://www.googleapis.com/auth/spreadsheets
```

This scope provides full read/write access to Google Sheets.

**Alternative scopes** (if broader access needed):
- `https://www.googleapis.com/auth/drive` - Full Drive access
- `https://www.googleapis.com/auth/drive.file` - Access only to files created by the app

### 5.2 Authentication Process

**First Run:**
1. Application loads `credentials.json`
2. Initiates OAuth flow via browser
3. User logs in and grants permissions
4. Application receives access token
5. Token saved to `token.json` for future use

**Subsequent Runs:**
1. Application loads `token.json`
2. Checks if token is valid
3. If expired, automatically refreshes using refresh token
4. If refresh fails, re-initiates OAuth flow

### 5.3 Token Storage

- **credentials.json**: OAuth client credentials (from Google Cloud Console)
- **token.json**: User access and refresh tokens (generated after first authentication)

**Security Note:** Both files contain sensitive data and should be in `.gitignore`.

---

## 6. API Operations

### 6.1 Read Operations

**Get All Restaurants:**
```python
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range='Date Night Restaurant List!A2:I'
).execute()
```

### 6.2 Write Operations

**Add New Restaurant:**
```python
values = [[
    "Restaurant Name",
    "https://booking-url.com",
    "Description",
    4.5,
    "Eater DC",
    "$$$",
    "Italian",
    "Top",
    "2025-12-30"
]]

service.spreadsheets().values().append(
    spreadsheetId=SPREADSHEET_ID,
    range='Date Night Restaurant List!A:I',
    valueInputOption='USER_ENTERED',
    body={'values': values}
).execute()
```

**Update Existing Restaurant:**
```python
values = [["New Description"]]

service.spreadsheets().values().update(
    spreadsheetId=SPREADSHEET_ID,
    range='Date Night Restaurant List!C5',  # Row 5, Column C
    valueInputOption='USER_ENTERED',
    body={'values': values}
).execute()
```

### 6.3 Value Input Options

- **RAW**: Data inserted as-is, no parsing (strings remain strings)
- **USER_ENTERED**: Data parsed like manual entry (formulas evaluated, dates formatted)

**Recommendation:** Use `USER_ENTERED` for most operations to allow proper date/number formatting.

---

## 7. Environment Variables

Required variables in `.env`:

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_TOKEN_FILE=token.json
GOOGLE_SHEETS_SHEET_NAME=Date Night Restaurant List
```

---

## 8. Error Handling

### 8.1 Common Errors

**Authentication Errors:**
- Missing `credentials.json`: Ensure file exists in project root
- Invalid token: Delete `token.json` and re-authenticate
- Insufficient permissions: Check OAuth scopes

**API Errors:**
- Invalid range: Verify A1 notation syntax
- Rate limiting: Implement exponential backoff
- Spreadsheet not found: Verify spreadsheet ID

### 8.2 Rate Limits

Google Sheets API limits:
- 300 read requests per minute per project
- 300 write requests per minute per project

**Mitigation:**
- Batch operations when possible
- Use `batchUpdate` for multiple writes
- Implement retry logic with exponential backoff

---

## 9. Security Considerations

### 9.1 Credential Management

1. **Never commit sensitive files:**
   ```
   # Add to .gitignore
   credentials.json
   token.json
   .env
   ```

2. **Restrict OAuth scope:** Use minimum required scope (`spreadsheets` only)

3. **Token refresh:** Application handles automatic token refresh

### 9.2 Access Control

- Use OAuth consent screen to control who can authenticate
- Set to "Internal" for personal use only
- Monitor usage in Google Cloud Console

---

## 10. Testing

### 10.1 Manual Testing Steps

1. Verify credentials are set up correctly
2. Run authentication flow and check token generation
3. Test read operation (get all restaurants)
4. Test write operation (add test restaurant)
5. Test update operation (modify test restaurant)
6. Verify data appears correctly in Google Sheets

### 10.2 Sample Test Data

```python
test_restaurant = [
    "Test Restaurant",
    "https://example.com",
    "A test entry for validation",
    4.0,
    "Manual Test",
    "$$",
    "American",
    "Medium",
    "2025-12-30"
]
```

---

## 11. References

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Python Quickstart Guide](https://developers.google.com/sheets/api/quickstart/python)
- [OAuth 2.0 Scopes](https://developers.google.com/sheets/api/scopes)
- [API Reference - spreadsheets.values](https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values)

---

## 12. Troubleshooting

### Issue: "The caller does not have permission"
**Solution:** Verify OAuth scopes include `spreadsheets` and user has granted permissions

### Issue: "Unable to parse range"
**Solution:** Check A1 notation syntax, ensure sheet name matches exactly (case-sensitive)

### Issue: Token refresh fails
**Solution:** Delete `token.json` and re-authenticate

### Issue: Spreadsheet not found
**Solution:** Verify spreadsheet ID in `.env`, ensure sharing permissions grant access to authenticated account
