import re
from typing import Any


NEGATIVE_KEYWORDS = {
    "mal", "triste", "seul", "vide", "perdu", "fatigué", "fatigue",
    "épuisé", "déprimé", "angoissé", "stressé", "stress", "pas bien",
    "honte", "peur", "souffre", "souffrance", "pleure", "pleurer"
}

POSITIVE_KEYWORDS = {
    "bien", "heureux", "content", "joie", "super", "génial", "cool",
    "motivé", "fier", "soulagé", "ravi", "merci", "amour", "aime"
}

ANGER_KEYWORDS = {
    "colère", "énervé", "énervée", "furieux", "furieuse", "rage",
    "ça m'énerve", "sa m'énerve", "agacé", "agacée"
}

STRESS_KEYWORDS = {
    "stress", "stressé", "stressée", "angoisse", "angoissé", "angoissée",
    "pression", "tendu", "tendue"
}

FATIGUE_KEYWORDS = {
    "fatigué", "fatiguée", "épuisé", "épuisée", "crevé", "crevée",
    "lassé", "lassée"
}

TOPIC_KEYWORDS = {
    "travail": {"travail", "boulot", "job", "collègue", "patron", "chef"},
    "famille": {"famille", "frère", "soeur", "sœur", "mère", "père", "parents", "enfant", "fils", "fille"},
    "couple": {"couple", "femme", "mari", "copine", "copain", "amour", "séparation", "relation"},
    "santé": {"santé", "malade", "douleur", "médecin", "hôpital", "fatigue", "fatigué"},
    "solitude": {"seul", "solitude", "abandonné", "abandonnée"},
    "quotidien": {"journée", "matin", "soir", "aujourd'hui", "demain", "semaine"},
    "joie": {"content", "heureux", "joie", "fête", "réussi", "bonne nouvelle"},
    "fatigue": {"fatigue", "fatigué", "épuisé", "crevé"},
}


def normalize_text(text: str) -> str:
    """
    Nettoie et normalise le texte.
    """
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def count_keyword_matches(text: str, keywords: set[str]) -> int:
    """
    Compte combien de mots/expressions-clés apparaissent dans le texte.
    """
    count = 0
    for keyword in keywords:
        if keyword in text:
            count += 1
    return count


def detect_emotion(text: str) -> str:
    """
    Détecte une émotion probable à partir d'indices simples.
    """
    negative_score = count_keyword_matches(text, NEGATIVE_KEYWORDS)
    positive_score = count_keyword_matches(text, POSITIVE_KEYWORDS)
    anger_score = count_keyword_matches(text, ANGER_KEYWORDS)
    stress_score = count_keyword_matches(text, STRESS_KEYWORDS)
    fatigue_score = count_keyword_matches(text, FATIGUE_KEYWORDS)

    scores = {
        "negative": negative_score,
        "positive": positive_score,
        "anger": anger_score,
        "stress": stress_score,
        "fatigue": fatigue_score,
    }

    best_emotion = max(scores, key=scores.get)
    best_score = scores[best_emotion]

    if best_score == 0:
        return "unknown"

    return best_emotion


def detect_precision(text: str) -> str:
    """
    Détecte si le message semble vague ou précis.
    """
    vague_patterns = [
        "je suis pas bien",
        "je vais pas bien",
        "ça va pas",
        "je suis triste",
        "je suis content",
        "je suis fatigué",
        "je suis énervé",
        "je ne sais pas",
        "ça ne va pas"
    ]

    precise_markers = {
        "parce que", "à cause de", "avec", "depuis", "quand", "au travail",
        "avec ma", "avec mon", "hier", "aujourd'hui", "ce matin", "ce soir"
    }

    if text in vague_patterns:
        return "vague"

    for marker in precise_markers:
        if marker in text:
            return "precise"

    if len(text.split()) <= 4:
        return "vague"

    return "precise"


def detect_topic(text: str) -> str:
    """
    Détecte un sujet principal à partir de mots-clés.
    """
    topic_scores = {}

    for topic, keywords in TOPIC_KEYWORDS.items():
        topic_scores[topic] = count_keyword_matches(text, keywords)

    best_topic = max(topic_scores, key=topic_scores.get)
    best_score = topic_scores[best_topic]

    if best_score == 0:
        return "general"

    return best_topic


def suggest_intent(emotion: str, precision: str) -> str:
    """
    Suggère une intention de réponse logique.
    """
    if emotion in {"negative", "stress", "fatigue"} and precision == "vague":
        return "support"

    if emotion in {"negative", "stress", "fatigue"} and precision == "precise":
        return "reflect"

    if emotion == "positive" and precision == "vague":
        return "encourage"

    if emotion == "positive" and precision == "precise":
        return "ask_open_question"

    if emotion == "anger":
        return "clarify"

    return "clarify"


def analyze_text(text: str) -> dict[str, Any]:
    """
    Analyse locale complète d'un message.
    """
    cleaned_text = normalize_text(text)
    emotion = detect_emotion(cleaned_text)
    precision = detect_precision(cleaned_text)
    topic = detect_topic(cleaned_text)
    intent = suggest_intent(emotion, precision)

    return {
        "cleaned_text": cleaned_text,
        "emotion": emotion,
        "precision": precision,
        "topic": topic,
        "intent": intent,
    } 
