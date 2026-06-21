class YoushengshuError(Exception):
    """Base exception for all youshengshu errors."""


class ConfigError(YoushengshuError):
    """Configuration error."""


class ChapterSplitError(YoushengshuError):
    """Chapter splitting error."""


class LMStudioError(YoushengshuError):
    """LM Studio API error."""


class TranslationValidationError(YoushengshuError):
    """Translation validation error."""
