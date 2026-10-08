"""Firestore data access for users."""

from datetime import datetime, timezone
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from app.firestore import get_firestore


USERS_COLLECTION = "users"


def _user_ref(user_id: str):
    """Return the Firestore document reference for a user."""
    return get_firestore().collection(USERS_COLLECTION).document(user_id)


def create_user(
    *,
    email: str,
    display_name: str | None,
    persona: str,
    risk_appetite: str,
    language: str,
    cash: float,
) -> dict:
    """Create a new user and return the stored document."""

    user_id = uuid4().hex
    now = datetime.now(timezone.utc)

    data = {
        "id": user_id,
        "email": email.strip().lower(),
        "display_name": display_name,
        "persona": persona,
        "risk_appetite": risk_appetite,
        "language": language,
        "cash": cash,
        "created_at": now,
    }

    _user_ref(user_id).set(data)

    return data


def get_user(user_id: str) -> dict | None:
    """Return a user by ID, or None if the user does not exist."""

    snapshot = _user_ref(user_id).get()

    if not snapshot.exists:
        return None

    return snapshot.to_dict()


def get_user_by_email(email: str) -> dict | None:
    """Return the first user matching an email address."""

    query = (
        get_firestore()
        .collection(USERS_COLLECTION)
        .where(filter=FieldFilter("email", "==", email.strip().lower()))
        .limit(1)
        .stream()
    )

    for document in query:
        return document.to_dict()

    return None


def update_user(user_id: str, updates: dict) -> dict | None:
    """Update selected user fields and return the updated document."""

    ref = _user_ref(user_id)
    snapshot = ref.get()

    if not snapshot.exists:
        return None

    ref.update(updates)

    return ref.get().to_dict()


def delete_user(user_id: str) -> bool:
    """Delete a user document.

    Returns True if the document existed and was deleted,
    otherwise False.
    """

    ref = _user_ref(user_id)
    snapshot = ref.get()

    if not snapshot.exists:
        return False

    ref.delete()
    return True