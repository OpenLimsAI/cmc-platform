"""Presentation follows PM displayName -> unified username, never role sync."""


def identity_presentation(username, display_name):
    if (not isinstance(username, str) or not 1 <= len(username) <= 100
            or username != username.strip() or any(ord(c) < 32 or ord(c) == 127 for c in username)):
        return None
    display = display_name.strip()[:50] if isinstance(display_name, str) and display_name.strip() else username[:50]
    return {"identityUsername": username, "displayName": display}
