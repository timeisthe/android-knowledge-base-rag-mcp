class KnowledgeBaseError(RuntimeError):
    """Base exception for user-facing knowledge-base failures."""


class ConfigurationError(KnowledgeBaseError):
    """Raised when required runtime configuration is missing or invalid."""


class InvalidDocumentPath(KnowledgeBaseError):
    """Raised when a document path escapes the configured knowledge root."""


class DocumentNotFound(KnowledgeBaseError):
    """Raised when the requested Markdown document does not exist."""


class DocumentAlreadyExists(KnowledgeBaseError):
    """Raised when creating a document would overwrite an existing file."""


class ConsistencyError(KnowledgeBaseError):
    """Raised when an operation fails and a consistency rollback is attempted."""
