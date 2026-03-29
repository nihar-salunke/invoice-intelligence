"""OAuth setup for Google Slides API — local server flow."""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]
CLIENT_SECRET = "/Users/nihar.salunke/.config/gws/client_secret.json"
TOKEN_PATH = "/Users/nihar.salunke/.config/gws/slides_token.json"

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)

print("\nStarting auth server on http://localhost:8085 ...")
print("A URL will appear below — copy it and open in Chrome.\n")

creds = flow.run_local_server(
    port=8085,
    open_browser=False,
    prompt="consent",
    authorization_prompt_message="=== OPEN THIS URL IN CHROME ===\n{url}\n\nWaiting for authentication...",
)

with open(TOKEN_PATH, "w") as f:
    json.dump(json.loads(creds.to_json()), f, indent=2)

print(f"\nAuthentication successful! Token saved to {TOKEN_PATH}")
