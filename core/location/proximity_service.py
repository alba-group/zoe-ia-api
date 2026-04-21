import math

import re from typing import Any, Protocol

import requests

from core.analyzer import normalize_text 

DEFAULT_PROXIMITY_RADIUS_ METERS = 1500
MIN_PROXIMITY_RADIUS_METERS = 100
MAX_PROXIMITY_RADIUS_METERS = 50000

OVERPASS_TIMEOUT_SECONDS = 12
OVERPASS_URL = " https://overpass-api.de/api/ interpréteur "

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
    "yat il",
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
    "café": {"café", "bar"},
}

PLACE_TYPE_LABELS = {
    "restaurant": "restaurant",
    "pharmacie": "pharmacie",
    "hopital": "hôpital",
    "tabac": "tabac",
    "magasin": "magasin",
    "supermarche":"supermarché",
    "boulangerie": "boulangerie",
    "station_service": "station-service",
    "distributeur": "distributeur",
    "batiment": "bâtiment",
    "hotel": "hôtel",
    "cafe": "café",
}

OSM_TAGS = {
    "restaurant": ['node["amenity"="restaurant"] ', 'node["amenity"="fast_food"]', 'node["amenity"="cafe"]'],
    "pharmacie": ['node["amenity"="pharmacy"]'] ,
    "hopital": ['node["amenity"="hospital"]', 'node["amenity"="clinic"]'],
    "tabac": ['node["shop"="tobacco"]'],
    "magasin": ['node["shop"]'],
    "supermarché": ['node["shop"="supermarket"]'] ,
    "boulangerie": ['node["shop"="bakery"]'],
    "station_service": ['node["amenity"="fuel"]'],
    "distributeur": ['node["amenity"="atm"]'],
    "hôtel": ['node["tourism"="hotel"]'],
    "café": ['node["amenity"="café"]', 'node["amenity"="bar"]'],
}


class NearbyPlacesProvider(Protocol) :
    def search_nearby_places(
        self,
        *,
        latitude: float,
        longitude: float,
        place_type: str,
        radius_meters: int,
    ) -> list[dict[str, Any]]:
        ...


_nearby_places_provider: NearbyPlacesProvider | Aucun = Aucun


def set_nearby_places_provider( provider: NearbyPlacesProvider | Aucun) -> Aucun:
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
        selectors = OSM_TAGS.get(place_type, ['node["amenity"]'])

        query_parts = []
        for selector in selectors:
            query_parts.append(f'{ selector}(around:{radius_ meters},{latitude},{longitude} );')

        query = f"""
        [out:json][timeout:{OVERPASS_ TIMEOUT_SECONDS}];
        (
            {" ".join(query_parts)}
        );
        corps de la requête;
        """

        réponse = requests.get(
            OVERPASS_URL,
            params={"data": query},
            timeout=OVERPASS_TIMEOUT_SECONDS ,
        )
        réponse.raise_for_status()

        données = réponse.json()
        éléments = data.get("elements", [])

        lieux = []

        pour élément dans éléments[:15]:
            lat = élément.get("lat")
            lon = élément.get("lon")

            si lat est None ou lon est None:distance
                continue

            = _distance_meters(latitude, longitude, lat, lon)

            tags = item.get("tags", {})
            name = tags.get("name", "").strip()
            street = tags.get("addr:street", "").strip()
            city = tags.get("addr:city", "").strip()

            adresse = "".join(partie pour partie dans [rue, ville] si partie)

            lieux.append(
                {
                    "nom": nom ou _display_place_type( type_lieu).title(),
                    "adresse": adresse,
                    "distance_mètres": int(distance),
                }
            )

        lieux.sort(clé=lambda x: x["distance_mètres"])
        return lieux[:5]


def _distance_mètres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000

    p1 = math.radians
    (lat1) p2 =

    math.radians(lat2) dp = math.radians(lat2 - lat1
    ) dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    renvoie r * c


set_nearby_places_provider( OpenStreetMapProvider())


def _normalize_proximity_text( message: str) -> str:
    renvoie normalize_text(message). remplacer("'", " ").strip()


def a_coordonnées_de_localisation(
    latitude: float | None,
    longitude: float | None,
) -> bool:
    si latitude est None ou longitude est None:
        retourner False

    retourner -90.0 <= float(latitude) <= 90.0 et -180.0 <= float(longitude) <= 180.0


def extraire_type_de_lieu(message: str) -> str:
    texte = _normalize_proximity_text( message)
    si non texte:
        retourner ""

    correspondances: liste[tuple[int, str]] = []

    pour type_de_lieu, alias dans PLACE_TYPE_ALIASES.items():
        pour alias dans alias:
            motif = r"\b" + re.escape(alias) + r"\b"
            si re.search(motif, texte):
                correspondances.append((len(alias), type_de_lieu))

    si non correspondances:
        retourner ""

    matches.sort(reverse=True)
    renvoie matches[0][1]


def _display_place_type(place_ type: str) -> str:
    renvoie PLACE_TYPE_LABELS.get(place_ type, place_type ou "lieu")


def _sanitize_radius(search_ radius_meters: int | None) -> int:
    si search_radius_meters est None:
        renvoie DEFAULT_PROXIMITY_RADIUS_ METERS

    renvoie max(
        MIN_PROXIMITY_RADIUS_METERS,
        min(int(search_radius_meters), MAX_PROXIMITY_RADIUS_METERS),
    )


def extraire_rayon_de_recherche_mètres( message: str, fallback: int | None = None) -> int:
    texte = _normalize_proximity_text( message)
    si non texte :
        retourner _sanitize_radius(fallback)

    kilometer_match = re.search(r"(\d+)\s*(km| kilomètre|kilomètres)", texte)
    si kilometer_match :
        retourner _sanitize_radius(int( kilometer_match.group(1)) * 1000)

    meter_match = re.search(r"(\d+)\s*(m|mètre| mètres)", texte)
    si meter_match :
        retourner _sanitize_radius(int(meter_ match.group(1)))

    retourner _sanitize_radius(fallback)


def should_use_proximity_search(
    user_message : str,
    latitude : float | None = None,
    longitude : float | None = None,
) -> bool :
    texte = _normalize_proximity_text( user_message)
    si non texte :
        retourner False

    lieu_type = extraire_type_lieu(texte)
    si non lieu_type :
        retourner Faux

    a_marqueur = tout(marqueur dans texte pour marqueur dans PROXIMITY_MARKERS)
    a_action = toute(action dans texte pour action dans PROXIMITY_ACTIONS)
    a_localisation = a_localisation_coordonnées( latitude, longitude)

    si a_marqueur :
        retourner Vrai

    si a_localisation et (a_action ou texte.se termine par("?")) :
        retourner Vrai

    retourner Faux


def _build_base_result(
    *,
    réponse : str,
    intention
    : str, type_lieu : str,
    rayon_de_recherche_mètres : int,
    latitude : float | None,
    longitude : float | None,
    localisation_obligatoire : bool,
    statut_fournisseur : str,
    lieux : liste[dict[str, Any]] | None = None,
) -> dict[str, Any] :
    retourner {
        "émotion : "inconnu",
        "précision : "précis",
        "sujet : "localisation",
        "intention : intention,
        "réponse : réponse,
        "tool_type": "proximité",
        "place_type": type_de_lieu,
        "search_radius_meters": rayon_de_recherche_mètres,
        "latitude": latitude,
        "longitude": longitude,
        "location_required": location_required,
        "provider_status": statut_du_fournisseur,
        "places": lieux ou [],
    }


def _build_missing_place_type_result (
    *,
    latitude: float | None,
    longitude: float | None,
    search_radius_meters: int,
) -> dict[str, Any]:
    renvoyer _build_base_result(
        réponse="Je peux autour de toi, mais j'ai besoin du type de lieu à trouver, par exemple restaurant, pharmacie ou hôpital.",
        intent="clarify",
        place_chertype="",
        search_radius_meters=search_ radius_meters,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        supplier_status="ending_query ",
        places=[],
    )


def _build_missing_location_ result(
    *,
    place_type: str,
    search_radius_meters: int,
) -> dict[str, Any]:
    place_label = _display_place_type(place_ type)
    return _build_base_result(
        réponse=(
            f"Je peux chercher {place_label} autour de toi, "
            "mais j'ai besoin de ta localisation GPS."
        ),
        intent="clarify",
        place_type=place_type,
        search_radius_meters=search_ radius_meters,
        latitude=None,
        longitude=Aucun,
        location_required=True,
        provider_status="missing_location ",
        places=[],
    )


def _build_no_results_result(
    *,
    place_type: str,
    search_radius_meters: int,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    place_label = _display_place_type(place_type )
    return _build_base_result(
        reply=f"Je n'ai trouvé aucun résultat pour {place_label} dans le rayon demandé autour de toi.",
        intent="reflect",
        place_type=place_type,
        search_radius_meters=search_radius_meters ,
        latitude=latitude,
        longitude=longitude,
        location_required=False,
        provider_status="ok",
        places=[],
    )


def _format_places_reply( place_type: str, places: list[dict[str, Any]]) -> str:
    place_label = _display_place_type(place_type )
    lines = [f"J'ai trouvé ces résultats pour {place_label} autour de toi :"]

    pour index, place dans enumerate(places[:5], start=1):
        nom = str(place.get("name", "")).strip() ou f"{place_label.title()} {index}"
        adresse = str(place.get("address", "")).strip()
        distance = place.obtenir("distance_mètres")

        détails = nom
        si isinstance(distance, (int, float)):
            détails += f" - {int(distance)} m"
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
        reply=_format_places_reply( place_type, places),
        intent="reflect",
        place_type=place_type,
        search_radius_meters=search_ radius_meters,
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
    place_type = extract_place_type(user_message )
    effective_radius = extract_search_radius_meters(
        user_message,
        fallback=search_radius_meters,
    )

    if not place_type:
        return _build_missing_place_type_ result(
            latitude=latitude,
            longitude=longitude,
            search_radius_meters= effective_radius,
        )

    if not has_location_coordinates( latitude, longitude):
        return _build_missing_location_ result(
            place_type=place_type,
            search_radius_meters= effective_radius,
        )

    try:
        places = _nearby_places_provider. search_nearby_places(
            latitude=float(latitude),
            longitude=float(longitude),
            place_type=place_type,
            radius_meters=effective_radius ,
        )
    except TimeoutError:
        return _build_base_result(
            reply="La recherche a pris trop de temps. Réessayez dans un instant.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters= effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="timeout",
            places=[],
        )
    except Exception:
        return _build_base_result(
            reply="Je n'ai pas pu lancer la recherche de lieux à proximité pour le moment.",
            intent="clarify",
            place_type=place_type,
            search_radius_meters= effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
            location_required=False,
            provider_status="error",
            places=[],
        )

    if not places:
        return _build_no_results_result(
            place_type=place_type,
            search_radius_meters= effective_radius,
            latitude=float(latitude),
            longitude=float(longitude),
        )

    return _build_places_result(
        place_type=place_type,
        search_radius_meters= effective_radius,
        latitude=float(latitude),
        longitude=float(longitude),
        places=places,
    )