class ServiceError(Exception):
    """Base class for service layer errors."""


class ServiceValidationError(ServiceError):
    """Raised when user-provided data violates a business rule."""


class ServiceDependencyError(ServiceError):
    """Raised when an optional dependency is unavailable."""
