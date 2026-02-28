from config import settings
import urllib.parse

import secrets

from app.configuration.state_storage import state_storage


def generate_google_auth():
    random_state = secrets.token_urlsafe(16)
    state_storage.add(random_state)
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    query_params = {
        "client_id": settings.AUTH_GOOGLE_CLIENT_ID,
        "redirect_uri": "http://localhost:3000/google/auth",
        "response_type": "code",
        "scope": " " .join([
            "openid",
            "profile",
            "email",
        ]),
        "access_type": "offline",
         "state": random_state,

    }

    query_string = urllib.parse.urlencode(query_params, quote_via=urllib.parse.quote)
    return f"{base_url}?{query_string}"
