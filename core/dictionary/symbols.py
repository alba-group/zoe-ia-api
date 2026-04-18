# Symboles fréquents dans les messages utilisateur

PUNCTUATION_SYMBOLS = [
    ".", ",", ";", ":", "!", "?",
    "...", "…"
]

QUOTE_SYMBOLS = [
    "'", '"', "’", "`", "«", "»"
]

BRACKET_SYMBOLS = [
    "(", ")", "[", "]", "{", "}",
    "<", ">"
]

MATH_SYMBOLS = [
    "+", "-", "*", "/", "\\", "=",
    "%", "^"
]

MONEY_SYMBOLS = [
    "$", "€", "£", "¥"
]

SOCIAL_SYMBOLS = [
    "@", "#", "&", "_"
]

LINE_SYMBOLS = [
    "|", "~"
]

SPACE_SYMBOLS = [
    "\n", "\r", "\t"
]

ALL_SYMBOLS = (
    PUNCTUATION_SYMBOLS
    + QUOTE_SYMBOLS
    + BRACKET_SYMBOLS
    + MATH_SYMBOLS
    + MONEY_SYMBOLS
    + SOCIAL_SYMBOLS
    + LINE_SYMBOLS
) 
