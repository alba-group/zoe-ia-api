from core.memory import (
    load_memory,
    save_memory,
    add_message_to_history,
    update_profile_from_analysis,
    clear_memory,
)


def print_title(name: str):
    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)


def test_load_memory():
    print_title("TEST LOAD MEMORY")

    memory = load_memory()

    assert isinstance(memory, dict), "memory doit être un dictionnaire"
    assert "history" in memory
    assert "profile" in memory

    print("✅ Chargement mémoire OK")


def test_add_history():
    print_title("TEST ADD HISTORY")

    memory = load_memory()

    add_message_to_history(
        memory=memory,
        user_message="je suis pas bien",
        zoe_reply="Je suis là. Qu'est-ce qui ne va pas ?",
        emotion="negative",
        topic="general",
        precision="vague",
        intent="support",
        timestamp="2026-04-17 20:00:00"
    )

    assert len(memory["history"]) >= 1

    print("✅ Historique ajouté")


def test_update_profile():
    print_title("TEST UPDATE PROFILE")

    memory = load_memory()

    analysis = {
        "emotion": "stress",
        "topic": "travail"
    }

    update_profile_from_analysis(
        memory=memory,
        analysis=analysis
    )

    profile = memory["profile"]

    assert "last_detected_emotion" in profile
    assert profile["last_detected_emotion"] == "stress"

    print("✅ Profil mis à jour")


def test_save_memory():
    print_title("TEST SAVE MEMORY")

    memory = load_memory()
    save_memory(memory)

    print("✅ Sauvegarde mémoire OK")


def test_clear_memory():
    print_title("TEST CLEAR MEMORY")

    memory = clear_memory()

    assert memory["history"] == []
    assert memory["profile"] == {}

    print("✅ Reset mémoire OK")


def main():
    test_load_memory()
    test_add_history()
    test_update_profile()
    test_save_memory()
    test_clear_memory()

    print("\nTous les tests memory.py sont terminés.")


if __name__ == "__main__":
    main() 
