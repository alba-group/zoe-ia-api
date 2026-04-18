# Ajustement du ton des réponses Zoe IA

AVAILABLE_TONES = {
    "neutral",
    "gentle",
    "warm",
    "soft",
    "supportive",
}


def normalize_tone(tone: str) -> str:
    """
    Sécurise le ton demandé.
    """
    if not isinstance(tone, str):
        return "neutral"

    cleaned = tone.strip().lower()

    if cleaned in AVAILABLE_TONES:
        return cleaned

    return "neutral"


def apply_tone(text: str, tone: str = "neutral") -> str:
    """
    Ajuste légèrement une phrase selon le ton voulu.
    """
    if not isinstance(text, str):
        return ""

    base = text.strip()
    mode = normalize_tone(tone)

    if not base:
        return ""

    # Ton doux
    if mode == "gentle":
        if base.startswith("Je suis là"):
            return base
        return f"Je suis là. {base}"

    # Ton chaleureux
    if mode == "warm":
        if base.startswith("Ça fait plaisir"):
            return base
        return f"Ça fait plaisir à entendre. {base}"

    # Ton calme / doux
    if mode == "soft":
        if base.startswith("Je vois"):
            return base
        return f"Je vois. {base}"

    # Ton soutien
    if mode == "supportive":
        if base.startswith("Je suis avec toi"):
            return base
        return f"Je suis avec toi. {base}"

    # Neutre
    return base 
