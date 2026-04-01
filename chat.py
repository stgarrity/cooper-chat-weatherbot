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

    def get_inbox(self, unread_only: bool = True) -> list[dict]:
        """Get messages sent to this bot."""
        params = {"unread_only": "true"} if unread_only else {}
        resp = requests.get(
            f"{self.base_url}/api/messages/inbox",
            headers=self._headers(),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("messages", []) or []

    def mark_as_read(self, message_id: int) -> None:
        """Mark a message as read."""
        requests.put(
            f"{self.base_url}/api/messages/{message_id}/read",
            headers=self._headers(),
            timeout=10,
        )

    def get_conversation(self, user_id: int, limit: int = 10) -> list[dict]:
        """Get recent conversation with a user."""
        resp = requests.get(
            f"{self.base_url}/api/messages/conversation/{user_id}",
            headers=self._headers(),
            params={"limit": limit},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("messages", []) or []

    def expire_messages(self, recipient_id: int) -> int:
        """Expire (mark as read) all unread messages sent by this bot to recipient."""
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
