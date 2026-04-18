"""
Sous-package dictionary de Zoe IA.

Centralise :
- alphabet.py
- symbols.py
- emojis.py
- greetings.py
- emotions.py
- tones.py
- sentences.py
"""

from core.dictionary.alphabet import (
    LOWERCASE_LETTERS,
    UPPERCASE_LETTERS,
    ACCENTED_LETTERS,
    ACCENTED_UPPERCASE,
    ALL_LETTERS,
)

from core.dictionary.symbols import (
    PUNCTUATION_SYMBOLS,
    QUOTE_SYMBOLS,
    BRACKET_SYMBOLS,
    MATH_SYMBOLS,
    MONEY_SYMBOLS,
    SOCIAL_SYMBOLS,
    LINE_SYMBOLS,
    SPACE_SYMBOLS,
    ALL_SYMBOLS,
)

from core.dictionary.emojis import (
    HAPPY_EMOJIS,
    LAUGH_EMOJIS,
    LOVE_EMOJIS,
    SAD_EMOJIS,
    ANGRY_EMOJIS,
    THINKING_EMOJIS,
    FIRE_EMOJIS,
    GESTURE_EMOJIS,
    TECH_EMOJIS,
    ALL_EMOJIS,
)

from core.dictionary.greetings import (
    GREETING_WORDS,
    GREETING_PHRASES,
    POLITE_GREETINGS,
    ALL_GREETINGS,
    is_greeting,
    build_greeting_reply,
)

from core.dictionary.emotions import (
    NEGATIVE_EMOTIONS,
    STRESS_EMOTIONS,
    FATIGUE_EMOTIONS,
    ANGER_EMOTIONS,
    POSITIVE_EMOTIONS,
    is_negative_emotion,
    is_stress_emotion,
    is_fatigue_emotion,
    is_anger_emotion,
    is_positive_emotion,
    build_emotion_reply,
)

from core.dictionary.tones import (
    AVAILABLE_TONES,
    normalize_tone,
    apply_tone,
)

from core.dictionary.sentences import (
    IDENTITY_REPLY,
    UNKNOWN_NAME_REPLY,
    WRONG_NAME_REPLY,
    LISTENING_REPLY,
    MEMORY_EMPTY_REPLY,
    RIDDLE_STOP_REPLY,
    GENERAL_POSITIVE_REPLY,
    GENERAL_SUPPORT_REPLY,
    GENERAL_CLARIFY_REPLY,
    build_identity_reply,
    build_unknown_name_reply,
    build_wrong_name_reply,
    build_listening_reply,
    build_memory_empty_reply,
    build_riddle_stop_reply,
)

__all__ = [
    "LOWERCASE_LETTERS",
    "UPPERCASE_LETTERS",
    "ACCENTED_LETTERS",
    "ACCENTED_UPPERCASE",
    "ALL_LETTERS",

    "PUNCTUATION_SYMBOLS",
    "QUOTE_SYMBOLS",
    "BRACKET_SYMBOLS",
    "MATH_SYMBOLS",
    "MONEY_SYMBOLS",
    "SOCIAL_SYMBOLS",
    "LINE_SYMBOLS",
    "SPACE_SYMBOLS",
    "ALL_SYMBOLS",

    "HAPPY_EMOJIS",
    "LAUGH_EMOJIS",
    "LOVE_EMOJIS",
    "SAD_EMOJIS",
    "ANGRY_EMOJIS",
    "THINKING_EMOJIS",
    "FIRE_EMOJIS",
    "GESTURE_EMOJIS",
    "TECH_EMOJIS",
    "ALL_EMOJIS",

    "GREETING_WORDS",
    "GREETING_PHRASES",
    "POLITE_GREETINGS",
    "ALL_GREETINGS",
    "is_greeting",
    "build_greeting_reply",

    "NEGATIVE_EMOTIONS",
    "STRESS_EMOTIONS",
    "FATIGUE_EMOTIONS",
    "ANGER_EMOTIONS",
    "POSITIVE_EMOTIONS",
    "is_negative_emotion",
    "is_stress_emotion",
    "is_fatigue_emotion",
    "is_anger_emotion",
    "is_positive_emotion",
    "build_emotion_reply",

    "AVAILABLE_TONES",
    "normalize_tone",
    "apply_tone",

    "IDENTITY_REPLY",
    "UNKNOWN_NAME_REPLY",
    "WRONG_NAME_REPLY",
    "LISTENING_REPLY",
    "MEMORY_EMPTY_REPLY",
    "RIDDLE_STOP_REPLY",
    "GENERAL_POSITIVE_REPLY",
    "GENERAL_SUPPORT_REPLY",
    "GENERAL_CLARIFY_REPLY",
    "build_identity_reply",
    "build_unknown_name_reply",
    "build_wrong_name_reply",
    "build_listening_reply",
    "build_memory_empty_reply",
    "build_riddle_stop_reply",
] 
