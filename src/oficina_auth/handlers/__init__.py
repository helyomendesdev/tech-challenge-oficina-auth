"""Entrypoint handler boundaries for authentication."""

from oficina_auth.handlers.auth import (
    HandlerConfig,
    create_auth_handler,
    create_handler_from_environment,
    create_local_demo_handler,
    lambda_handler,
)

__all__ = [
    "HandlerConfig",
    "create_auth_handler",
    "create_handler_from_environment",
    "create_local_demo_handler",
    "lambda_handler",
]
