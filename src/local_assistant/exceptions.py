class LocalAssistantError(Exception):
    """Base exception for app-level errors."""


class StorageError(LocalAssistantError):
    """Raised when persistent storage fails."""


class ProviderError(LocalAssistantError):
    """Raised when the LLM provider is unavailable or returns invalid data."""


class ActionError(LocalAssistantError):
    """Raised when an assistant action is invalid or unsafe to execute."""
