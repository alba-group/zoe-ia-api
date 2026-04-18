from core.brain import process_user_message


def run_test_case(message: str) -> None:
    memory = {
        "history": [],
        "profile": {},
        "last_emotion": "unknown",
        "last_topic": "general"
    }

    print("=" * 60)
    print(f"TEST MESSAGE : {message}")

    result = process_user_message(
        user_input=message,
        memory=memory
    )

    print("Résultat reçu :")
    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert "reply" in result, "Le champ reply manque."
    assert "emotion" in result, "Le champ emotion manque."
    assert "topic" in result, "Le champ topic manque."
    assert "intent" in result, "Le champ intent manque."

    assert isinstance(result["reply"], str), "reply doit être du texte."
    assert len(result["reply"]) > 0, "reply ne doit pas être vide."

    print("✅ Test validé")


def main():
    run_test_case("je suis pas bien")
    run_test_case("je suis content")
    run_test_case("j'ai passé une mauvaise journée")
    run_test_case("ça m'énerve")
    run_test_case("je suis fatigué")

    print("\nTous les tests brain.py sont terminés.")


if __name__ == "__main__":
    main() 
