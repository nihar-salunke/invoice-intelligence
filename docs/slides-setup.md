# Google Slides Pitch Deck — Setup Guide

How we set up programmatic Google Slides creation using the Slides API and Python, authenticated with a personal Gmail account.

## Prerequisites

- **Google Cloud project** with billing enabled (we used `project-ai-api-keys`)
- **gcloud CLI** installed and authenticated
- **Python 3.10+** with `venv`
- **Node.js 18+** (for optional `gws` CLI)

## Step-by-Step Setup

### 1. Authenticate gcloud with your personal email

If your default browser is not Chrome, force it open in Chrome:

```bash
BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" gcloud auth login
```

This opens Chrome for Google sign-in. After approval:

```
You are now logged in as [your-email@gmail.com].
```

### 2. Set the GCP project

```bash
gcloud config set project project-ai-api-keys
```

### 3. Enable the Slides and Drive APIs

```bash
gcloud services enable slides.googleapis.com drive.googleapis.com --project project-ai-api-keys
```

### 4. Configure the OAuth consent screen

1. Open: https://console.cloud.google.com/apis/credentials/consent?project=project-ai-api-keys
2. Set **User Type** to **External**
3. Fill in app name (e.g., `gws CLI`) and support email
4. Click **Save and Continue** through all screens
5. Under **Test users**, click **Add Users** and add your Gmail address

This last step is critical — without adding yourself as a test user, OAuth will fail with "This app is blocked".

### 5. Create an OAuth Desktop client

1. Open: https://console.cloud.google.com/apis/credentials?project=project-ai-api-keys
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `gws CLI`
5. Click **Create**
6. Download the JSON file (e.g., `client_secret_<id>.apps.googleusercontent.com.json`)

### 6. Place the client secret

```bash
mkdir -p ~/.config/gws
cp ~/Downloads/client_secret_*.json ~/.config/gws/client_secret.json
```

### 7. Install Python dependencies

```bash
source venv_gemini/bin/activate
pip install google-api-python-client google-auth-oauthlib
```

### 8. Run the OAuth flow

We use a local-server OAuth flow (`slides_auth.py`):

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

flow = InstalledAppFlow.from_client_secrets_file(
    "~/.config/gws/client_secret.json", SCOPES
)
creds = flow.run_local_server(port=8085, open_browser=False)
```

Run the script in a **foreground terminal** (not backgrounded):

```bash
python slides_auth.py
```

It prints a URL — open it in Chrome, sign in, approve scopes. The browser redirects to `localhost:8085` and the script captures the token.

The token is saved to `~/.config/gws/slides_token.json`.

### 9. Create the presentation

With the token saved, `create_slides.py` uses the Google Slides API directly:

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_authorized_user_file("~/.config/gws/slides_token.json")
slides_service = build("slides", "v1", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

pres = slides_service.presentations().create(
    body={"title": "My Presentation"}
).execute()
```

Run the deck builder:

```bash
source venv_gemini/bin/activate
python create_slides.py
```

This creates the presentation in your Google Drive and prints the URL.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "This app is blocked" | Email not added as test user | Add yourself under OAuth consent screen > Test users |
| "Required parameter is missing: response_type" | Bug in `gws` CLI auth flow | Use Python `InstalledAppFlow` instead |
| "Insufficient authentication scopes" | Token doesn't have Slides/Drive scopes | Re-run `slides_auth.py` with correct SCOPES |
| "invalid_grant: Bad Request" | Expired gcloud tokens | Run `gcloud auth login` again |
| Script runs in background, no URL visible | CLI tool backgrounded the process | Run in a separate foreground terminal |

## Files

| File | Purpose |
|------|---------|
| `slides_auth.py` | One-time OAuth flow — saves token for Slides + Drive access |
| `create_slides.py` | Builds the full 10-slide pitch deck via Slides API |
| `~/.config/gws/client_secret.json` | OAuth Desktop client credentials (not committed) |
| `~/.config/gws/slides_token.json` | Saved OAuth token (not committed) |

## Notes

- We initially tried the [`@googleworkspace/cli` (`gws`)](https://github.com/googleworkspace/cli) npm package but hit a bug in its OAuth URL construction (`response_type` parameter missing). The Python `google-api-python-client` + `google-auth-oauthlib` approach worked reliably.
- The OAuth consent screen must be in **Testing** mode with your email as a test user for personal Gmail accounts.
- Tokens are stored locally and not committed to git.
