"""Middleware package for the Central Intelligence API."""

from app.middleware.auth import AuthMiddleware

__all__ = ["AuthMiddleware"]
