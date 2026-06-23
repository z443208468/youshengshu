class YoushengshuError(Exception):
    """Base exception for all youshengshu errors."""


class ConfigError(YoushengshuError):
    """Configuration error."""


class ChapterSplitError(YoushengshuError):
    """Chapter splitting error."""


class LMStudioError(YoushengshuError):
    """LM Studio API error."""


class ContextOverflowError(LMStudioError):
    """LM Studio rejected the request because the prompt exceeded context."""


class TranslationValidationError(YoushengshuError):
    """Translation validation error."""


class TranslationStateError(YoushengshuError):
    """Resume/partial/manifest state is inconsistent."""


class TranslationPipelineStoppedError(YoushengshuError):
    """Translation pipeline stopped after a chapter failure."""
