from core.memory import load_memory, save_memory
from core.brain import process_user_message
from core.utils import (
    ensure_project_files,
    log_event,
)

APP_NAME = "Zoe"
APP_VERSION = "1.0"


def print_header() -> None:
    print("=" * 70)
    print(f"{APP_NAME} — IA conversationnelle")
    print(f"Version : {APP_VERSION}")
    print("Tape ton message pour parler avec Zoe.")
    print("Commandes disponibles :")
    print("  /help   -> afficher l'aide")
    print("  /memory -> afficher un résumé mémoire")
    print("  /clear  -> vider l'historique")
    print("  /exit   -> quitter")
    print("=" * 70)


def print_help() -> None:
    print("\nAide Zoe")
    print("-" * 70)
    print("Écris simplement un message pour discuter avec Zoe.")
    print("Exemples :")
    print("  je suis pas bien")
    print("  je suis content aujourd'hui")
    print("  j'ai passé une mauvaise journée")
    print("")
    print("Commandes :")
    print("  /help   -> affiche cette aide")
    print("  /memory -> montre la mémoire actuelle")
    print("  /clear  -> efface l'historique des échanges")
    print("  /exit   -> quitte le programme")
    print("-" * 70)


def print_memory_summary(memory: dict) -> None:
    history = memory.get("history", [])
    profile = memory.get("profile", {})
    last_emotion = memory.get("last_emotion", "inconnue")
    last_topic = memory.get("last_topic", "inconnu")

    print("\nRésumé mémoire")
    print("-" * 70)
    print(f"Dernière émotion détectée : {last_emotion}")
    print(f"Dernier sujet détecté    : {last_topic}")
    print(f"Nombre d'échanges gardés : {len(history)}")

    if profile:
        print("\nProfil mémorisé :")
        for key, value in profile.items():
            print(f"  - {key} : {value}")
    else:
        print("\nProfil mémorisé : vide")

    if history:
        print("\nDerniers échanges :")
        for item in history[-5:]:
            user_message = item.get("user_message", "")
            zoe_reply = item.get("zoe_reply", "")
            timestamp = item.get("timestamp", "")
            print(f"\n[{timestamp}]")
            print(f"Toi  : {user_message}")
            print(f"Zoe  : {zoe_reply}")
    else:
        print("\nAucun échange enregistré.")

    print("-" * 70)


def clear_conversation(memory: dict) -> dict:
    memory["history"] = []
    memory["last_emotion"] = "unknown"
    memory["last_topic"] = "general"
    memory["context"] = {
        "mode": None,
        "last_question_type": None,
        "awaiting_user_reply": False,
        "riddle_answer": None,
        "riddle_question": None,
        "last_bot_question": None,
    }

    save_memory(memory)
    log_event("Historique vidé par l'utilisateur.")
    print("\nHistorique vidé. Zoe repart sur une base propre.")
    return memory


def handle_user_input(user_input: str, memory: dict) -> dict:
    result = process_user_message(user_input=user_input, memory=memory)

    zoe_reply = result.get(
        "reply",
        "Je suis là. Tu peux m'en dire un peu plus ?"
    )
    emotion = result.get("emotion", "unknown")
    topic = result.get("topic", "general")
    precision = result.get("precision", "vague")
    intent = result.get("intent", "clarify")

    print(f"\nZoe : {zoe_reply}")

    log_event(
        f"Message traité | emotion={emotion} | topic={topic} | "
        f"precision={precision} | intent={intent}"
    )

    return memory


def main() -> None:
    ensure_project_files()
    memory = load_memory()

    print_header()
    log_event("Démarrage de Zoe.")

    while True:
        try:
            user_input = input("\nToi : ").strip()
        except KeyboardInterrupt:
            print("\n\nFermeture demandée. À bientôt.")
            log_event("Arrêt clavier utilisateur.")
            save_memory(memory)
            break
        except EOFError:
            print("\n\nFin de session détectée. À bientôt.")
            log_event("EOF détecté, fermeture.")
            save_memory(memory)
            break

        if not user_input:
            print("Zoe : Je t'écoute.")
            continue

        command = user_input.lower()

        if command == "/exit":
            save_memory(memory)
            log_event("Fermeture normale de Zoe.")
            print("Zoe : À bientôt. Prends soin de toi.")
            break

        if command == "/help":
            print_help()
            continue

        if command == "/memory":
            print_memory_summary(memory)
            continue

        if command == "/clear":
            memory = clear_conversation(memory)
            continue

        try:
            memory = handle_user_input(user_input=user_input, memory=memory)
        except Exception as e:
            log_event(f"Erreur pendant le traitement : {str(e)}")
            print(
                "\nZoe : J'ai eu un petit souci pour répondre correctement. "
                "Tu peux réessayer ?"
            )


if __name__ == "__main__":
    main()