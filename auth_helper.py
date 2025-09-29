#!/usr/bin/env python3
"""
Helper script to generate refresh token for production deployment
Run this locally to get a refresh token, then add it to Railway env vars
"""
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/calendar']
CREDENTIALS_FILE = 'credentials.json'

def get_refresh_token():
    """Get refresh token for production use"""
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE, SCOPES)

    # Run OAuth flow
    creds = flow.run_local_server(port=0)

    # Return the refresh token
    return {
        'refresh_token': creds.refresh_token,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'token_uri': creds.token_uri
    }

if __name__ == "__main__":
    print("🔐 Getting refresh token for production...")
    token_data = get_refresh_token()

    print("\n✅ Add these environment variables to Railway:")
    print(f"GOOGLE_CLIENT_ID={token_data['client_id']}")
    print(f"GOOGLE_CLIENT_SECRET={token_data['client_secret']}")
    print(f"GOOGLE_REFRESH_TOKEN={token_data['refresh_token']}")
    print(f"GOOGLE_TOKEN_URI={token_data['token_uri']}")

    print("\n📝 Save this token data to token_prod.json:")
    with open('token_prod.json', 'w') as f:
        json.dump(token_data, f, indent=2)
    print("✅ Saved to token_prod.json")
