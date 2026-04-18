from core.analyzer import analyze_text


def print_title(name: str):
    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)


def test_negative_message():
    print_title("TEST MESSAGE NEGATIF")

    result = analyze_text("je suis pas bien")

    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert result["emotion"] in {"negative", "unknown"}
    assert result["precision"] in {"vague", "precise"}
    assert "topic" in result
    assert "intent" in result

    print("✅ Analyse négative OK")


def test_positive_message():
    print_title("TEST MESSAGE POSITIF")

    result = analyze_text("je suis content aujourd'hui")

    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert result["emotion"] in {"positive", "unknown"}
    assert result["precision"] in {"vague", "precise"}
    assert "topic" in result
    assert "intent" in result

    print("✅ Analyse positive OK")


def test_anger_message():
    print_title("TEST MESSAGE COLERE")

    result = analyze_text("ça m'énerve vraiment")

    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert result["emotion"] in {"anger", "negative", "unknown"}
    assert result["precision"] in {"vague", "precise"}
    assert "topic" in result
    assert "intent" in result

    print("✅ Analyse colère OK")


def test_fatigue_message():
    print_title("TEST MESSAGE FATIGUE")

    result = analyze_text("je suis fatigué")

    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert result["emotion"] in {"fatigue", "negative", "unknown"}
    assert result["precision"] in {"vague", "precise"}
    assert "topic" in result
    assert "intent" in result

    print("✅ Analyse fatigue OK")


def test_precise_message():
    print_title("TEST MESSAGE PRECIS")

    result = analyze_text("je suis pas bien à cause du travail aujourd'hui")

    print(result)

    assert isinstance(result, dict), "Le résultat doit être un dictionnaire."
    assert result["precision"] == "precise"
    assert result["topic"] in {"travail", "general", "quotidien"}
    assert "emotion" in result
    assert "intent" in result

    print("✅ Analyse précise OK")


def main():
    test_negative_message()
    test_positive_message()
    test_anger_message()
    test_fatigue_message()
    test_precise_message()

    print("\nTous les tests analyzer.py sont terminés.")


if __name__ == "__main__":
    main() 
