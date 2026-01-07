class PlatformError(Exception):
    """Base exception for all platform errors."""
    def __init__(self, message, orig_exc=None):
        super().__init__(message)
        self.message = message
        self.orig_exc = orig_exc

    def __str__(self):
        if self.orig_exc:
            return f"{self.message} (Original Error: {str(self.orig_exc)})"
        return self.message

class AuthenticationError(PlatformError):
    """Raised when authentication fails (401/403). Do NOT retry."""
    pass

class ValidationError(PlatformError):
    """Raised when input/schema validation fails (400). Do NOT retry."""
    pass

class NetworkError(PlatformError):
    """Raised for connection issues (Socket/DNS/Timeout). Retry allowed."""
    pass

class APIError(PlatformError):
    """Raised for server-side errors (500+). Retry allowed."""
    def __init__(self, message, status_code=None, orig_exc=None):
        super().__init__(message, orig_exc)
        self.status_code = status_code
