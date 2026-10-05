class ApplicationError(Exception):
    """Base exception for application-level errors."""

    def __init__(self, message: str, code: str = "APPLICATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(ApplicationError):
    """Raised when application validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class DocumentProcessingError(ApplicationError):
    """Raised when document processing fails."""

    def __init__(self, message: str):
        super().__init__(message, "DOCUMENT_PROCESSING_ERROR")


class ResourceNotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str):
        super().__init__(message, "RESOURCE_NOT_FOUND")
