# forge/exceptions.py

class ForgeError(Exception):
    """Base exception for all Forge errors."""
    pass

class GenerationError(ForgeError):
    """Raised when archive generation fails."""
    pass

class ExtractionError(ForgeError):
    """Raised when archive extraction fails."""
    pass

class CompressionError(ForgeError):
    """Raised when compression fails."""
    pass

class ConfigurationError(ForgeError):
    """Raised for configuration or validation errors."""
    pass
