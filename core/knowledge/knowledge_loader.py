from copy import deepcopy
from pathlib import Path
from typing import Any

from core.config import (
    BUILDINGS_KNOWLEDGE_FILE,
    FAQ_KNOWLEDGE_FILE,
    USER_HELP_KNOWLEDGE_FILE,
    ZOE_IDENTITY_FILE,
)
from core.utils import safe_read_json


DEFAULT_ZOE_IDENTITY = {
    "name": "Zoe",
    "role": "assistante intelligente",
    "language": "fr",
    "tone": "doux, clair, utile, naturel",
    "rules": [
        "ne pas inventer si une info manque",
        "demander une precision si necessaire",
        "utiliser les outils adaptes selon le type de demande",
        "rester coherente avec la memoire",
    ],
    "specialties": [
        "conversation",
        "image",
        "pdf",
        "docx",
        "localisation",
        "analyse de fichiers",
    ],
    "limits": [
        "ne pas pretendre voir ou savoir sans module branche",
        "ne pas donner de faux souvenirs",
        "ne pas repondre hors contexte si l info manque",
    ],
}

DEFAULT_FAQ_KNOWLEDGE = {
    "items": [
        {
            "id": "identity",
            "question": "Qui est Zoe ?",
            "keywords": ["qui es tu", "qui est zoe", "c est quoi zoe"],
            "answer": "Je suis Zoe, une assistante intelligente en francais. Je reste claire, utile et j'utilise mes modules quand ils sont disponibles.",
        },
        {
            "id": "missing_info",
            "question": "Que fait Zoe si une information manque ?",
            "keywords": ["si tu ne sais pas", "si une information manque", "que fais tu si une info manque"],
            "answer": "Si une information importante manque, je le dis clairement et je demande une precision plutot que d'inventer.",
        },
        {
            "id": "memory",
            "question": "Comment fonctionne la memoire de Zoe ?",
            "keywords": ["ta memoire", "comment fonctionne ta memoire", "tu te souviens de quoi"],
            "answer": "Je garde une memoire legere et structuree avec le profil, les preferences, quelques faits fiables, le contexte de session et l'historique recent.",
        },
        {
            "id": "routing",
            "question": "Comment Zoe choisit quoi faire ?",
            "keywords": ["comment tu fonctionnes", "comment tu choisis tes outils", "comment tu choisis quoi faire"],
            "answer": "Je commence par comprendre la demande, puis je choisis la capacite la plus adaptee. Si rien de specifique ne correspond, je continue en conversation normale.",
        },
    ]
}

DEFAULT_BUILDINGS_KNOWLEDGE = {
    "categories": [
        {"name": "restaurant", "keywords": ["restaurant", "resto"], "description": "Lieu ou l'on sert des repas et des boissons sur place ou a emporter."},
        {"name": "magasin", "keywords": ["magasin", "boutique", "commerce"], "description": "Lieu de vente de produits ou de services au public."},
        {"name": "pharmacie", "keywords": ["pharmacie"], "description": "Lieu ou l'on delivre des medicaments et des produits de sante."},
        {"name": "hopital", "keywords": ["hopital"], "description": "Etablissement de sante pour les soins, les urgences et les hospitalisations."},
        {"name": "clinique", "keywords": ["clinique"], "description": "Etablissement de soins, souvent specialise ou prive."},
        {"name": "laboratoire", "keywords": ["laboratoire", "labo"], "description": "Lieu d'analyses medicales, scientifiques ou techniques selon le contexte."},
        {"name": "gare", "keywords": ["gare"], "description": "Lieu de depart, d'arrivee ou de correspondance pour les transports ferroviaires."},
        {"name": "station service", "keywords": ["station service", "essence"], "description": "Lieu pour faire le plein de carburant et parfois acheter des produits de depannage."},
        {"name": "hotel", "keywords": ["hotel"], "description": "Etablissement d'hebergement temporaire pour voyageurs et visiteurs."},
        {"name": "banque", "keywords": ["banque"], "description": "Etablissement financier pour les operations bancaires et le conseil."},
        {"name": "mairie", "keywords": ["mairie"], "description": "Batiment administratif de la commune pour les demarches locales."},
        {"name": "police", "keywords": ["police", "commissariat"], "description": "Service ou batiment lie a la securite publique et aux depots de plainte."},
        {"name": "poste", "keywords": ["poste", "bureau de poste"], "description": "Lieu pour le courrier, les colis et certains services administratifs ou financiers."},
    ]
}

DEFAULT_USER_HELP_KNOWLEDGE = {
    "items": [
        {
            "id": "capabilities_overview",
            "title": "Capacites de Zoe",
            "keywords": ["que peux tu faire", "quelles sont tes capacites", "aide", "help", "que sais tu faire"],
            "description": "Je peux discuter, utiliser mes modules et guider selon le type de demande.",
            "examples": ["Que peux tu faire ?", "Aide moi a comprendre tes fonctions"],
        },
        {
            "id": "image_create_help",
            "title": "Creer une image",
            "keywords": ["comment creer une image", "comment generer une image", "faire une image"],
            "description": "Decris clairement le style, le sujet et le rendu souhaite pour que je genere une image.",
            "skill": "image_create",
            "examples": ["Genere une affiche minimaliste", "Cree une image de paysage doux"],
        },
        {
            "id": "image_edit_help",
            "title": "Modifier une image",
            "keywords": ["comment modifier une image", "retoucher une image", "changer une photo"],
            "description": "Envoie l'image puis explique precisement ce que tu veux changer.",
            "skill": "image_edit",
            "examples": ["Supprime le fond", "Ajoute un ciel orange"],
        },
        {
            "id": "image_analyze_help",
            "title": "Analyser une image",
            "keywords": ["comment analyser une image", "decrire une photo", "lire une image"],
            "description": "Envoie l'image et demande une description, une lecture de texte ou une explication.",
            "skill": "image_analyze",
            "examples": ["Analyse cette photo", "Lis le texte sur cette image"],
        },
        {
            "id": "pdf_read_help",
            "title": "Lire un PDF",
            "keywords": ["comment lire un pdf", "resumer un pdf", "analyser un pdf"],
            "description": "Envoie le PDF puis demande un resume, une analyse ou une reponse a une question precise.",
            "skill": "pdf_analyze",
            "examples": ["Resume ce PDF", "Explique moi ce document PDF"],
        },
        {
            "id": "pdf_create_help",
            "title": "Creer un PDF",
            "keywords": ["comment creer un pdf", "faire un pdf", "exporter en pdf"],
            "description": "Donne le contenu ou la structure voulue et je peux generer un vrai fichier PDF.",
            "skill": "pdf_create",
            "examples": ["Fais moi un rapport en PDF", "Transforme ce texte en PDF"],
        },
        {
            "id": "docx_read_help",
            "title": "Lire un document Word",
            "keywords": ["comment lire un word", "analyser un docx", "resumer un word"],
            "description": "Envoie le fichier DOCX puis demande un resume, une analyse ou une explication.",
            "skill": "docx_analyze",
            "examples": ["Analyse ce Word", "Resume ce docx"],
        },
        {
            "id": "docx_create_help",
            "title": "Creer un document Word",
            "keywords": ["comment creer un word", "generer un docx", "faire un document word"],
            "description": "Donne le contenu a exporter et je peux generer un vrai fichier Word / DOCX.",
            "skill": "docx_create",
            "examples": ["Fais moi une lettre en docx", "Transforme ca en Word"],
        },
        {
            "id": "location_help",
            "title": "Utiliser la localisation",
            "keywords": ["comment utiliser la localisation", "recherche autour de moi", "trouver autour de moi"],
            "description": "Je peux preparer une recherche locale si le telephone m'envoie la latitude et la longitude reelles.",
            "skill": "gps_local_search",
            "examples": ["Trouve une pharmacie autour de moi", "Cherche un hopital a proximite"],
        },
        {
            "id": "web_search_help",
            "title": "Recherche web",
            "keywords": ["comment chercher sur le web", "recherche web", "chercher sur internet"],
            "description": "Je peux lancer une recherche web si la demande le justifie et si la capacite est activee.",
            "skill": "web_search",
            "examples": ["Cherche cette information sur le web"],
        },
    ]
}


def load_zoe_identity() -> dict[str, Any]:
    data = _load_json_file(ZOE_IDENTITY_FILE, DEFAULT_ZOE_IDENTITY)
    return {
        "name": _clean_text(data.get("name")) or DEFAULT_ZOE_IDENTITY["name"],
        "role": _clean_text(data.get("role")) or DEFAULT_ZOE_IDENTITY["role"],
        "language": _clean_text(data.get("language")) or DEFAULT_ZOE_IDENTITY["language"],
        "tone": _clean_text(data.get("tone")) or DEFAULT_ZOE_IDENTITY["tone"],
        "rules": _clean_text_list(data.get("rules"), DEFAULT_ZOE_IDENTITY["rules"]),
        "specialties": _clean_text_list(data.get("specialties"), DEFAULT_ZOE_IDENTITY["specialties"]),
        "limits": _clean_text_list(data.get("limits"), DEFAULT_ZOE_IDENTITY["limits"]),
    }


def load_faq_knowledge() -> dict[str, list[dict[str, Any]]]:
    data = _load_json_file(FAQ_KNOWLEDGE_FILE, DEFAULT_FAQ_KNOWLEDGE)
    items = _normalize_items(
        data.get("items"),
        required_keys=("id", "question", "answer"),
    )
    return {"items": items or deepcopy(DEFAULT_FAQ_KNOWLEDGE["items"])}


def load_buildings_knowledge() -> dict[str, list[dict[str, Any]]]:
    data = _load_json_file(BUILDINGS_KNOWLEDGE_FILE, DEFAULT_BUILDINGS_KNOWLEDGE)
    categories = _normalize_items(
        data.get("categories"),
        required_keys=("name", "description"),
    )
    return {"categories": categories or deepcopy(DEFAULT_BUILDINGS_KNOWLEDGE["categories"])}


def load_user_help_knowledge() -> dict[str, list[dict[str, Any]]]:
    data = _load_json_file(USER_HELP_KNOWLEDGE_FILE, DEFAULT_USER_HELP_KNOWLEDGE)
    items = _normalize_items(
        data.get("items"),
        required_keys=("id", "title", "description"),
    )
    return {"items": items or deepcopy(DEFAULT_USER_HELP_KNOWLEDGE["items"])}


def _load_json_file(file_path: Path, default_value: dict[str, Any]) -> dict[str, Any]:
    loaded = safe_read_json(str(file_path), deepcopy(default_value))
    if not isinstance(loaded, dict):
        return deepcopy(default_value)
    return loaded


def _normalize_items(
    raw_items: Any,
    required_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue

        item: dict[str, Any] = {}
        missing_required = False

        for key in required_keys:
            value = _clean_text(raw_item.get(key))
            if not value:
                missing_required = True
                break
            item[key] = value

        if missing_required:
            continue

        keywords = _clean_text_list(raw_item.get("keywords"), [])
        if keywords:
            item["keywords"] = keywords

        examples = _clean_text_list(raw_item.get("examples"), [])
        if examples:
            item["examples"] = examples

        skill = _clean_text(raw_item.get("skill"))
        if skill:
            item["skill"] = skill

        normalized.append(item)

    return normalized


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _clean_text_list(raw_value: Any, default_value: list[str]) -> list[str]:
    if not isinstance(raw_value, list):
        return deepcopy(default_value)

    values = [
        _clean_text(item)
        for item in raw_value
        if _clean_text(item)
    ]
    return values or deepcopy(default_value)
