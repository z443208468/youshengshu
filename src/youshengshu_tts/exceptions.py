class TtsError(Exception):
    """Base error for TTS module."""


class TtsConfigError(TtsError):
    """Invalid TTS configuration."""


class TtsProviderError(TtsError):
    """TTS provider request or audio processing failed."""


class TtsTransientProviderError(TtsProviderError):
    """Provider failed due to a retryable transport/server-stream interruption."""
