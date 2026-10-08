"""Firebase Admin / Firestore initialization."""

from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import get_settings


@lru_cache
def get_firestore():
    """Return the shared Firestore client."""
    settings = get_settings()

    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        firebase_admin.initialize_app(cred)

    return firestore.client()