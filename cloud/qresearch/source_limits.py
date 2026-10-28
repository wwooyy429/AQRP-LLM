"""Pure limits for the exact readable source text sent to QuantConnect.

This module does not transform, pack, execute, upload or split source. The
operator must pass the same complete text map it plans to send. Legacy builds
without an explicit configured limit retain their earlier admission path.
"""
from .artifacts import validate_key
from .deployment_sources import MAX_SOURCE_FILES, MAX_SOURCE_PATH_BYTES


_ERRORS = {
    "invalid_limit": "Source character limit must be an explicit positive native integer",
    "invalid_sources": "A complete nonempty source text map is required",
    "invalid_path": "Source paths must be canonical relative Python file paths",
    "invalid_text": "Cloud source must be readable plain UTF-8 text",
    "unsupported_character": "Cloud source contains a character unsupported by the native file API",
    "file_character_limit": "A cloud source file exceeds the frozen native character limit",
}


class SourceLimitError(ValueError):
    """Closed reason and safe size metadata; never include source contents."""
    def __init__(self, reason, *, metadata=None):
        if type(reason) is not str or reason not in _ERRORS:
            raise ValueError("Unknown source limit failure reason") from None
        self.reason = reason
        self.metadata = metadata
        super().__init__(_ERRORS[reason])


def _fail(reason):
    raise SourceLimitError(reason) from None


def _path(name):
    if type(name) is not str:
        _fail("invalid_path")
    try:
        validate_key(name)
        if not name.endswith(".py") or len(name.encode("utf-8")) > MAX_SOURCE_PATH_BYTES:
            _fail("invalid_path")
    except (ValueError, TypeError, UnicodeError):
        _fail("invalid_path")
    return name


def _text(raw):
    if type(raw) not in (str, bytes):
        _fail("invalid_text")
    try:
        text = raw.decode("utf-8") if type(raw) is bytes else raw
        size = len(text.encode("utf-8"))
    except UnicodeError:
        _fail("invalid_text")
    if any((ord(char) < 32 and char not in "\t\n\r") or ord(char) == 127 for char in text):
        _fail("invalid_text")
    # The native file tool explicitly rejects non-BMP characters. BMP text has
    # one UTF-16 code unit per Python character, including CJK source comments.
    if any(ord(char) > 0xFFFF for char in text):
        _fail("unsupported_character")
    return text, size


def validate_source_sizes(source_texts, *, max_file_characters):
    """Return source size metadata, rejecting every over-limit file together.

    UTF-8 bytes are decoded without stripping BOMs or changing line endings;
    strings are counted exactly as supplied. Callers which upload normalized
    text must apply their existing explicit source policy before this check.
    This check proves only text/size prerequisites, not native compilation or
    execution success. It performs no file, network, provider or registry I/O.
    """
    if (type(max_file_characters) is not int
            or not 1 <= max_file_characters <= 2147483647):
        _fail("invalid_limit")
    if type(source_texts) is not dict or not 1 <= len(source_texts) <= MAX_SOURCE_FILES:
        _fail("invalid_sources")
    paths = [_path(name) for name in source_texts]
    files, over_limit, total_characters, total_bytes = {}, [], 0, 0
    for name in sorted(paths):
        text, byte_count = _text(source_texts[name])
        count = len(text)
        files[name] = {"characters": count, "utf8_bytes": byte_count}
        total_characters += count
        total_bytes += byte_count
        if count > max_file_characters:
            over_limit.append(name)
    result = {"schema_version": 1, "status": "passed" if not over_limit else "failed",
              "character_measure": "utf16_code_units", "source_text_policy": "exact_plain_utf8",
              "max_file_characters": max_file_characters, "file_count": len(files),
              "total_characters": total_characters, "total_utf8_bytes": total_bytes,
              "largest_file_characters": max(item["characters"] for item in files.values()),
              "files": files, "over_limit_files": over_limit}
    if over_limit:
        raise SourceLimitError("file_character_limit", metadata=result) from None
    return result
