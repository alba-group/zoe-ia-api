# Phrases utiles centralisées pour Zoe IA

IDENTITY_REPLY = "Je m'appelle Zoé. Je suis une intelligence artificielle."

UNKNOWN_NAME_REPLY = "Je ne connais pas encore ton prénom. Tu peux me le dire si tu veux."

WRONG_NAME_REPLY = "D'accord, je retire ce prénom. Si tu veux, tu peux me donner le bon."

LISTENING_REPLY = "Je t'écoute. Tu peux m'en dire un peu plus ?"

MEMORY_EMPTY_REPLY = "Je garde une mémoire légère de nos échanges, mais elle est encore en train de se construire."

RIDDLE_STOP_REPLY = "D'accord, j'arrête les devinettes pour le moment."

GENERAL_POSITIVE_REPLY = "Ça fait plaisir à entendre."
GENERAL_SUPPORT_REPLY = "Je suis là."
GENERAL_CLARIFY_REPLY = "Je vois. Tu veux m'expliquer un peu plus ce qui s'est passé ?"


def build_identity_reply() -> str:
    return IDENTITY_REPLY


def build_unknown_name_reply() -> str:
    return UNKNOWN_NAME_REPLY


def build_wrong_name_reply() -> str:
    return WRONG_NAME_REPLY


def build_listening_reply(user_name: str = "") -> str:
    safe_name = user_name.strip() if isinstance(user_name, str) else ""
    if safe_name:
        return f"Je t'écoute, {safe_name}. Tu peux m'en dire un peu plus ?"
    return LISTENING_REPLY


def build_memory_empty_reply() -> str:
    return MEMORY_EMPTY_REPLY


def build_riddle_stop_reply() -> str:
    return RIDDLE_STOP_REPLY 
