import re
from typing import Any, Protocol

from core.analyzer import normalize_text


DEFAULT_PROXIMITY_RADIUS_METERS = 1500
MIN_PROXIMITY_RADIUS_METERS = 100
MAX_PROXIMITY_RADIUS_METERS = 50000

PROXIMITY_MARKERS = (
    "autour de moi",
    "pres de moi",
    "a proximite",
    "a cote de moi",
    "dans le coin",
    "proche de moi",
    "le plus proche",
    "la plus proche",
    "les plus proches",
    "autour d ici",
    "pres d ici",
)

PROXIMITY_ACTIONS = (
    "trouve",
    "cherche",
    "je cherche",
    "y a t il",
    "il y a",
    "ou est",
    "ou sont",
    "montre moi",
    "donne moi",
    "localise",
)

PLACE_TYPE_ALIASES: dict[str, set[str]] = {
    "restaurant": {"restaurant", "resto", "brasserie", "snack"},
    "pharmacie": {"pharmacie"},
    "hopital": {"hopital", "clinique", "urgences", "centre hospitalier"},
    "tabac": {"tabac", "bureau de tabac"},
    "magasin": {"magasin", "boutique", "commerce"},
    "supermarche": {"supermarche", "superette", "epicerie"},
    "boulangerie": {"boulangerie"},
    "station_service": {"station service", "station essence", "essence"},
    "distributeur": {"distributeur", "distributeur bancaire", "atm", "bancomat"},
    "batiment": {"batiment", "immeuble", "building"},
    "hotel": {"hotel"},
    "cafe": {"cafe", "bar"},
}

PLACE_TYPE_LABELS = {
    "restaurant": "restaurant",
    "pharmacie": "pharmacie",
    "hopital": "hôpital",
    "tabac": "tabac",
    "magasin": "magasin",
    "supermarche": "supermarché",
    "boulangerie": "boulangerie",
    "station_service": "station-service",
    "distributeur": "distributeur",
    "batiment": "bâtiment",
    "hotel": "hôtel",
    "cafe": "café",
}


class NearbyPlacesProvider(Protocol):
    def search_nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        place_type: str,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        ...


_nearby_places_provider: NearbyPlacesProvider | None = None


def set_nearby_places_provider(provider: NearbyPlacesProvider | None) -> None:
    global _nearby_places_provider
    _nearby_places_provider = provider


def _normalize_proximity_text(message: str) -> str:
    return normalize_text(message).replace("'", " ").strip()


def has_location_coordinates(
    latitude: float | None,
    longitude: float | None,
) -> bool:
    if latitude is None or longitude is None:
        return False

    return -90.0 <= float(latitude) <= 90.0 and -180.0 <= float(longitude) <= 180.0


def extract_place_type(message: str) -> str:
    text = _normalize_proximity_text(message)
    if not text:
        return ""

    matches: list[tuple[int, str]] = []

    for place_type, aliases in PLACE_TYPE_ALIASES.items():
        for alias in aliases:
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text):
                matches.append((len(alias), place_type))

    if not matches:
        return ""

    matches.sort(reverse=True)
    return matches[0][1]


def _display_place_type(place_type: str) -> str:
    return PLACE_TYPE_LABELS.get(place_type, place_type or "lieu")


def _sanitize_radius(search_radius_meters: int | None) -> int:
    if search_radius_meters is None:
        return DEFAULT_PROXIMITY_RADIUS_METERS

    return max(
        MIN_PROXIMITY_RADIUS_METERS,
        min(int(search_radius_meters), MAX_PROXIMITY_RADIUS_METERS),
    )


def extract_search_radius_meters(message: str, fallback: int | None = None) -> int:
    text = _normalize_proximity_text(message)
    if not text:
        return _sanitize_radius(fallback)

    kilometer_match = re.search(r"(\d+)\s*(km|kilometre|kilometres)", text)
    if kilometer_match:
        return _sanitize_radius(int(kilometer_match.group(1)) * 1000)

    meter_match = re.search(r"(\d+)\s*(m|metre|metres)", text)
    if meter_match:
        return _sanitize_radius(int(meter_match.group(1)))

    return _sanitize_radius(fallback)


def should_use_proximity_search(
    user_message: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> bool:
    text = _normalize_proximity_text(user_message)
    if not text:
        return False

    place_type = extract_place_type(text)
    if not place_type:
        return False

    has_marker = any(marker in text for marker in PROXIMITY_MARKERS)
    has_action = any(action in text for action in PROXIMITY_ACTIONS)
    has_location = has_location_coordinates(latitude, longitude)

    if has_marker:
        return True

    if has_location and (has_action or text.endswith("?")):
        return True

    return False


def _build_base_result(
    *,
    reply: str,
    intent: str,
    place_type: str,
    search_radius_meters: int,
    latitude: float | None,
    longitude: float | None,
    location_required: bool,
    provider_status: str,
    places: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "location",
        "intent": intent,
        "reply": reply,
        "tool_type": "proximity",
        "place_type": place_type,
        "search_radius_meters": search_radius_meters,
        "latitude": latitude,
        "longitude": longitude,
        "location_required": location_required,
        "provider_status": provider_status,
        "places": places or [],
    }


def _build_missing_place_type_result(
    *,
    latitude: float | None,
    longitude: float | None,
    search_radius_meters: int,
) -> dict[str, Any]:
    return _build_base_result(
        reply="Je peux chercher autour de toi, mais j'ai besoin du type de lieu a trouver, par exemple restaurant, pharmacie ou hôpital.",
        intent="clarify",
        place_type="",
        search_radius_meters=search_radius_meters,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        provider_status="pending_query",
        places=[],
    )


def _build_missing_location_result(
    *,
    place_type: str,
    search_radius_meters: int,
) -> dict[str, Any]:
    place_label = _display_place_type(place_type)
    return _build_base_result(
        reply=(
            f"Je peux chercher {place_label} autour de toi, "
            "mais j'ai besoin de ta localisation GPS. "
            "Autorise la localisation sur le telephone puis renvoie la demande."
        ),
        intent="clarify",
        place_type=place_type,
        search_radius_meters=search_radius_meters,
        latitude=None,
        longitude=None,
        location_required=True,
        provider_status="missing_location",
        places=[],
    )


def _build_provider_not_ready_result(
    *,
    place_type: str,
    search_radius_meters: int,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    place_label = _display_place_type(place_type)
    return _build_base_result(
        reply=(
            f"J'ai bien recu ta position pour chercher {place_label} autour de toi, "
            "mais aucune source locale maps/places n'est encore branchee sur ce backend."
        ),
        intent="clarify",
        place_type=place_type,
        search_radius_meters=search_radius_meters,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        provider_status="not_configured",
        places=[],
    )


def _build_no_results_result(
    *,
    place_type: str,
    search_radius_meters: int,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    place_label = _display_place_type(place_type)
    return _build_base_result(
        reply=f"Je n'ai trouve aucun resultat pour {place_label} dans le rayon demande autour de toi.",
        intent="reflect",
        place_type=place_type,
        search_radius_meters=search_radius_meters,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        provider_status="ok",
        places=[],
    )


def _format_places_reply(place_type: str, places: list[dict[str, Any]]) -> str:
    place_label = _display_place_type(place_type)
    lines = [f"J'ai trouve ces resultats pour {place_label} autour de toi :"]

    for index, place in enumerate(places[:5], start=1):
        name = str(place.get("name", "")).strip() or f"{place_label.title()} {index}"
        address = str(place.get("address", "")).strip()
        distance = place.get("distance_meters")

        details = name
        if isinstance(distance, (int, float)):
            details += f" - {int(distance)} m"
        if address:
            details += f" - {address}"

        lines.append(f"{index}. {details}")

    return "\n".join(lines)


def _build_places_result(
    *,
    place_type: str,
    search_radius_meters: int,
    latitude: float,
    longitude: float,
    places: list[dict[str, Any]],
) -> dict[str, Any]:
    return _build_base_result(
        reply=_format_places_reply(place_type, places),
        intent="reflect",
        place_type=place_type,
        search_radius_meters=search_radius_meters,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        provider_status="ok",
        places=places,
    )


def build_proximity_reply(
    user_message: str,
    latitude: float | None = None,
    longitude: float | None = None,
    search_radius_meters: int | None = None,
) -> dict[str, Any]:
    place_type = extract_place_type(user_message)
    effective_radius = extract_search_radius_meters(
        user_message,
        fallback=search_radius_meters,
    )

    if not place_type:
        return _build_missing_place_type_result(
            latitude=latitude,
            longitude=longitude,
            search_radius_meters=effective_radius,
        )

    if not has_location_coordinates(latitude, longitude):
        return _build_missing_location_result(
            place_type=place_type,
            search_radius_meters=effective_radius,
        )

    if _nearby_places_provider is None:
        return _build_provider_not_ready_result(
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
        )

    try:
        places = _nearby_places_provider.search_nearby_places(
            latitude=float(latitude),
            longitude=float(longitude),
            place_type=place_type,
            radius_meters=effective_radius,
        )
    except TimeoutError:
        return _build_base_result(
            reply="La recherche de lieux autour de toi a pris trop de temps. Reessaie dans un instant.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="timeout",
            places=[],
        )
    except Exception:
        return _build_base_result(
            reply="Je n'ai pas reussi a lancer la recherche de lieux a proximite pour le moment.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="error",
            places=[],
        )

    if not places:
        return _build_no_results_result(
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
        )

    return _build_places_result(
        place_type=place_type,
        search_radius_meters=effective_radius,
        latitude=float(latitude),
        longitude=float(longitude),
        places=places,
    )
