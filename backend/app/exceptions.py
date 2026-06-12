from typing import Optional, Dict, Any

class ApplicationError(Exception):
    """Base application exception."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details

class ResourceNotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)

class DuplicateResourceError(ApplicationError):
    """Raised when a resource already exists or violates a unique constraint."""
    def __init__(self, message: str = "Resource already exists", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)

class InvalidOperationError(ApplicationError):
    """Raised when an operation is invalid for the current state."""
    def __init__(self, message: str = "Invalid operation", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
