"""Cooper Chat API client for WeatherBot."""

import requests


class CooperChatClient:
    """Client for the Cooper Chat REST API."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.user_id = None

    def register(self, name: str, family_secret: str, is_bot: bool = True) -> None:
        """Register/login as a bot user. Sets self.token and self.user_id."""
        resp = requests.post(
            f"{self.base_url}/api/auth/register",
            json={"name": name, "family_secret": family_secret, "is_bot": is_bot},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self.token = data["token"]
        self.user_id = data["user"]["id"]

    def _headers(self) -> dict:
        if not self.token:
            raise RuntimeError("Not authenticated — call register() first")
        return {"Authorization": f"Bearer {self.token}"}

    def get_contacts(self) -> list[dict]:
        """Get all users/contacts."""
        resp = requests.get(
            f"{self.base_url}/api/contacts",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("users", [])

    def find_user_by_name(self, name: str) -> dict:
        """Find a user by display name. Raises ValueError if not found."""
        contacts = self.get_contacts()
        for contact in contacts:
            if contact.get("name", "").lower() == name.lower():
                return contact
        available = [c.get("name") for c in contacts]
        raise ValueError(f"User '{name}' not found. Available: {available}")

    def expire_messages(self, recipient_id: int) -> int:
        """Expire (mark as read) all unread messages sent by this bot to recipient.
        Returns the number of expired messages."""
        resp = requests.post(
            f"{self.base_url}/api/messages/expire",
            headers=self._headers(),
            json={"recipient_id": recipient_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("expired_count", 0)

    def send_message(self, recipient_id: int, content: str) -> dict:
        """Send a message to a user. Returns the created message."""
        resp = requests.post(
            f"{self.base_url}/api/messages",
            headers=self._headers(),
            json={"recipient_id": recipient_id, "content": content},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
