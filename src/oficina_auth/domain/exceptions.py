class AuthenticationError(Exception):
    """Base exception for authentication use cases."""


class InvalidInput(AuthenticationError):
    """Raised when the request input is invalid."""


class InvalidCredentials(AuthenticationError):
    """Raised when credentials cannot authenticate a client."""


class DependencyUnavailable(AuthenticationError):
    """Raised when an external dependency required for authentication is unavailable."""
