"""Shared token helpers for the fraud service.

Validates JWTs (HS256) minted by the users service using the shared TOKEN_SECRET.
"""
import os
from functools import wraps

import jwt
from flask import jsonify, request

TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"


def verify_token(token):
    """Return the token payload dict, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, TOKEN_SECRET, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None


def current_identity():
    """Extract and verify the bearer token from the request, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return verify_token(header[len("Bearer "):])


def require_auth(view):
    """Decorator: 401 unless a valid bearer token is present."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = current_identity()
        if identity is None:
            return jsonify({"error": "unauthorized"}), 401
        request.identity = identity
        return view(*args, **kwargs)

    return wrapper
