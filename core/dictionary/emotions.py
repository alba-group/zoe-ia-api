# Émotions et réponses associées pour Zoe IA

NEGATIVE_EMOTIONS = {
    "negative",
    "sadness",
    "sad",
    "triste",
    "mal",
}

STRESS_EMOTIONS = {
    "stress",
    "stressé",
    "stresse",
    "angoisse",
    "pression",
}

FATIGUE_EMOTIONS = {
    "fatigue",
    "fatigué",
    "fatiguee",
    "épuisé",
    "epuise",
    "crevé",
    "creve",
}

ANGER_EMOTIONS = {
    "anger",
    "colère",
    "colere",
    "énervé",
    "enerve",
    "agacé",
    "agace",
}

POSITIVE_EMOTIONS = {
    "positive",
    "joy",
    "heureux",
    "content",
    "bien",
}

def is_negative_emotion(emotion: str) -> bool:
    return isinstance(emotion, str) and emotion.strip().lower() in NEGATIVE_EMOTIONS

def is_stress_emotion(emotion: str) -> bool:
    return isinstance(emotion, str) and emotion.strip().lower() in STRESS_EMOTIONS

def is_fatigue_emotion(emotion: str) -> bool:
    return isinstance(emotion, str) and emotion.strip().lower() in FATIGUE_EMOTIONS

def is_anger_emotion(emotion: str) -> bool:
    return isinstance(emotion, str) and emotion.strip().lower() in ANGER_EMOTIONS

def is_positive_emotion(emotion: str) -> bool:
    return isinstance(emotion, str) and emotion.strip().lower() in POSITIVE_EMOTIONS


def build_emotion_reply(emotion: str, precision: str = "vague", user_name: str = "") -> str:
    safe_name = user_name.strip() if isinstance(user_name, str) else ""
    emo = emotion.strip().lower() if isinstance(emotion, str) else "unknown"
    precision = precision.strip().lower() if isinstance(precision, str) else "vague"

    if emo in NEGATIVE_EMOTIONS:
        if precision == "vague":
            if safe_name:
                return f"Je suis là, {safe_name}. Qu'est-ce qui ne va pas aujourd'hui ?"
            return "Je suis là. Qu'est-ce qui ne va pas aujourd'hui ?"
        return "Je vois. Tu veux m'expliquer un peu plus ce qui s'est passé ?"

    if emo in STRESS_EMOTIONS:
        if precision == "vague":
            return "Tu sembles stressé. Tu sais ce qui te met dans cet état ?"
        return "Je comprends. Qu'est-ce qui te pèse le plus dans cette situation ?"

    if emo in FATIGUE_EMOTIONS:
        if precision == "vague":
            return "Tu as l'air fatigué. Tu sais d'où ça vient aujourd'hui ?"
        return "Je vois. Cette fatigue vient plutôt du corps, du moral ou de ta journée ?"

    if emo in ANGER_EMOTIONS:
        if precision == "vague":
            return "Je sens de la colère dans ce que tu dis. Qu'est-ce qui t'a énervé ?"
        return "Je comprends. Qu'est-ce qui t'a le plus blessé ou agacé dans cette situation ?"

    if emo in POSITIVE_EMOTIONS:
        if precision == "vague":
            return "C'est une bonne nouvelle. Qu'est-ce qui t'a rendu content aujourd'hui ?"
        return "Ça fait plaisir à entendre. Quel moment t'a fait le plus de bien ?"

    if safe_name:
        return f"Je t'écoute, {safe_name}. Tu peux m'en dire un peu plus ?"

    return "Je t'écoute. Tu peux m'en dire un peu plus ?" 
