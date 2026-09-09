class AuthenticationError(Exception):
    """Base exception for authentication use cases."""


class InvalidInput(AuthenticationError):
    """Raised when the request input is invalid."""

    def __init__(self, message: str, *, reason: str = "payload_invalido") -> None:
        super().__init__(message)
        self.reason = reason


class InvalidCredentials(AuthenticationError):
    """Raised when credentials cannot authenticate a client."""

    def __init__(self, message: str, *, reason: str = "nao_encontrado") -> None:
        super().__init__(message)
        self.reason = reason


class DependencyUnavailable(AuthenticationError):
    """Raised when an external dependency required for authentication is unavailable."""
