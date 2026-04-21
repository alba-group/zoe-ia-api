import math
import re
from typing import Any, Protocol

import requests

from core.analyzer import normalize_text


DEFAULT_PROXIMITY_RADIUS_METERS = 1500
MIN_PROXIMITY_RADIUS_METERS = 100
MAX_PROXIMITY_RADIUS_METERS = 50000

OVERPASS_TIMEOUT_SECONDS = 12
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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

OSM_TAGS = {
    "restaurant": [
        'node["amenity"="restaurant"]',
        'node["amenity"="fast_food"]',
        'node["amenity"="cafe"]',
        'way["amenity"="restaurant"]',
        'way["amenity"="fast_food"]',
        'way["amenity"="cafe"]',
    ],
    "pharmacie": [
        'node["amenity"="pharmacy"]',
        'way["amenity"="pharmacy"]',
    ],
    "hopital": [
        'node["amenity"="hospital"]',
        'node["amenity"="clinic"]',
        'way["amenity"="hospital"]',
        'way["amenity"="clinic"]',
    ],
    "tabac": [
        'node["shop"="tobacco"]',
        'way["shop"="tobacco"]',
    ],
    "magasin": [
        'node["shop"]',
        'way["shop"]',
    ],
    "supermarche": [
        'node["shop"="supermarket"]',
        'way["shop"="supermarket"]',
    ],
    "boulangerie": [
        'node["shop"="bakery"]',
        'way["shop"="bakery"]',
    ],
    "station_service": [
        'node["amenity"="fuel"]',
        'way["amenity"="fuel"]',
    ],
    "distributeur": [
        'node["amenity"="atm"]',
        'way["amenity"="atm"]',
    ],
    "hotel": [
        'node["tourism"="hotel"]',
        'way["tourism"="hotel"]',
    ],
    "cafe": [
        'node["amenity"="cafe"]',
        'node["amenity"="bar"]',
        'way["amenity"="cafe"]',
        'way["amenity"="bar"]',
    ],
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


class OpenStreetMapProvider:
    def search_nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        place_type: str,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        selectors = OSM_TAGS.get(place_type, ['node["amenity"]', 'way["amenity"]'])

        query_parts: list[str] = []
        for selector in selectors:
            query_parts.append(
                f"{selector}(around:{radius_meters},{latitude},{longitude});"
            )

        query = f"""
[out:json][timeout:{OVERPASS_TIMEOUT_SECONDS}];
(
    {" ".join(query_parts)}
);
out center tags;
"""

        response = requests.get(
            OVERPASS_URL,
            params={"data": query},
            timeout=OVERPASS_TIMEOUT_SECONDS,
            headers={"User-Agent": "ZoeIA/1.0 (proximity search)"},
        )
        response.raise_for_status()

        data = response.json()
        elements = data.get("elements", [])

        places: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()

        for item in elements:
            lat = item.get("lat")
            lon = item.get("lon")

            if lat is None or lon is None:
                center = item.get("center") or {}
                lat = center.get("lat")
                lon = center.get("lon")

            if lat is None or lon is None:
                continue

            lat = float(lat)
            lon = float(lon)

            distance = _distance_meters(latitude, longitude, lat, lon)

            tags = item.get("tags", {})
            name = str(tags.get("name", "")).strip()
            street = str(tags.get("addr:street", "")).strip()
            house_number = str(tags.get("addr:housenumber", "")).strip()
            postcode = str(tags.get("addr:postcode", "")).strip()
            city = str(tags.get("addr:city", "")).strip()

            street_line = " ".join(part for part in [house_number, street] if part).strip()
            address = " ".join(part for part in [street_line, postcode, city] if part).strip()

            dedupe_key = (
                name.lower(),
                address.lower(),
                round(lat, 6),
                round(lon, 6),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            places.append(
                {
                    "name": name or _display_place_type(place_type).title(),
                    "address": address,
                    "distance_meters": int(distance),
                    "latitude": lat,
                    "longitude": lon,
                }
            )

        places.sort(key=lambda x: x["distance_meters"])
        return places[:5]


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6371000.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


set_nearby_places_provider(OpenStreetMapProvider())


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
            "mais j'ai besoin de ta localisation GPS."
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
    except requests.Timeout:
        return _build_base_result(
            reply="La recherche a pris trop de temps. Reessaie dans un instant.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="timeout",
            places=[],
        )
    except requests.RequestException:
        return _build_base_result(
            reply="Le service de recherche de lieux est temporairement indisponible.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters=effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="provider_unavailable",
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