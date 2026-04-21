import re
import unicodedata
from typing import Any


NEGATIVE_KEYWORDS = {
    "mal", "triste", "seul", "vide", "perdu", "fatigue",
    "epuise", "deprime", "angoisse", "stress",
    "pas bien", "peur", "souffrance", "pleure"
}

POSITIVE_KEYWORDS = {
    "bien", "heureux", "content", "joie", "super",
    "genial", "cool", "motive", "fier",
    "soulage", "ravi", "merci", "amour", "aime"
}

ANGER_KEYWORDS = {
    "colere", "enerve", "furieux", "rage",
    "ca m enerve", "agace"
}

STRESS_KEYWORDS = {
    "stress", "angoisse", "pression", "tendu"
}

FATIGUE_KEYWORDS = {
    "fatigue", "epuise", "creve", "lasse"
}


TOPIC_KEYWORDS = {
    "travail": {"travail", "boulot", "job", "patron", "chef", "collegue"},
    "famille": {"famille", "frere", "soeur", "mere", "pere", "parents", "enfant"},
    "couple": {"couple", "femme", "mari", "copine", "copain", "relation", "separation"},
    "sante": {"sante", "medecin", "hopital", "douleur", "malade"},
    "solitude": {"seul", "solitude", "abandon"},
    "fatigue": {"fatigue", "epuise", "creve"},
    "musique": {"musique", "rap", "paroles", "refrain", "couplet", "suno", "chanson"},
    "image": {"image", "photo", "logo", "affiche", "avatar", "dessin"},
    "code": {"code", "python", "kotlin", "java", "html", "css", "javascript"},
    "projet": {"projet", "idee", "application", "app", "business"},
    "joie": {"heureux", "content", "joie", "bonne nouvelle"},
}


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = strip_accents(text)
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def count_keyword_matches(text: str, keywords: set[str]) -> int:
    """
    Match plus propre mot / expression
    """
    count = 0

    for keyword in keywords:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, text):
            count += 1

    return count


def detect_emotion(text: str) -> str:
    scores = {
        "negative": count_keyword_matches(text, NEGATIVE_KEYWORDS),
        "positive": count_keyword_matches(text, POSITIVE_KEYWORDS),
        "anger": count_keyword_matches(text, ANGER_KEYWORDS),
        "stress": count_keyword_matches(text, STRESS_KEYWORDS),
        "fatigue": count_keyword_matches(text, FATIGUE_KEYWORDS),
    }

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "unknown"

    return best


def detect_precision(text: str) -> str:
    precise_markers = {
        "parce que",
        "a cause de",
        "depuis",
        "quand",
        "hier",
        "aujourd hui",
        "ce matin",
        "ce soir",
        "avec ma",
        "avec mon",
        "au travail",
    }

    if len(text.split()) <= 4:
        return "vague"

    for marker in precise_markers:
        if marker in text:
            return "precise"

    if len(text.split()) >= 8:
        return "precise"

    return "vague"


def detect_topic(text: str) -> str:
    scores = {}

    for topic, words in TOPIC_KEYWORDS.items():
        scores[topic] = count_keyword_matches(text, words)

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "general"

    return best


def suggest_intent(emotion: str, precision: str, topic: str) -> str:
    if topic in {"musique", "image", "code", "projet"}:
        return "clarify"

    if emotion in {"negative", "stress", "fatigue"}:
        if precision == "vague":
            return "support"
        return "reflect"

    if emotion == "positive":
        if precision == "precise":
            return "ask_open_question"
        return "encourage"

    if emotion == "anger":
        return "clarify"

    return "clarify"


def analyze_text(text: str, memory: dict[str, Any] | None = None) -> dict[str, Any]:
    memory = memory or {}

    cleaned = normalize_text(text)

    emotion = detect_emotion(cleaned)
    precision = detect_precision(cleaned)
    topic = detect_topic(cleaned)
    intent = suggest_intent(emotion, precision, topic)

    return {
        "cleaned_text": cleaned,
        "emotion": emotion,
        "precision": precision,
        "topic": topic,
        "intent": intent,
    }