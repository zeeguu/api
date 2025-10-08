"""
Detect disturbing content (violence, death, disaster, tragedy) in articles.

This provides fast keyword-based detection before expensive LLM processing.
Articles flagged here will still be saved but marked appropriately.
"""

# Keywords by language for detecting disturbing content
# Focus on words that appear in headlines/titles about violent/tragic current events
DISTURBING_KEYWORDS = {
    "en": [
        # Violence & Crime
        "killed", "murder", "murdered", "shooting", "shot dead", "shot and killed",
        "stabbed", "stabbing", "stabbed to death",
        "assault", "attacked", "attack kills", "deadly attack",
        "bombing", "explosion kills", "terrorist", "terror attack",
        "mass shooting", "gunman", "shooter",
        # Death & Tragedy (specific contexts)
        "found dead", "body found", "bodies found",
        "fatal", "fatality", "fatalities", "casualties",
        "multiple victims", "mass casualties",
        # War & Conflict (specific violent contexts)
        "war crimes", "airstrike", "air strike", "drone strike",
        "civilian casualties", "civilians killed",
        # Disasters & Accidents (with casualties)
        "deadly crash", "fatal crash", "plane crash", "train crash",
        "disaster kills", "earthquake kills", "tsunami kills",
        "building collapse", "fire kills",
    ],
    "fr": [
        # Violence & Crime
        "tué", "tuée", "tués", "tuées", "abattu",
        "meurtre", "assassinat", "assassiné",
        "fusillé", "fusillade",
        "poignardé", "attentat", "attaque terroriste",
        "tuerie", "tueur",
        # Death & Tragedy (specific contexts)
        "retrouvé mort", "corps retrouvé", "cadavre",
        "victime mortelle", "victimes", "plusieurs victimes",
        # War & Conflict (specific violent contexts)
        "crimes de guerre", "frappe aérienne", "bombardement",
        "civils tués", "victimes civiles",
        # Disasters & Accidents (with casualties)
        "accident mortel", "crash mortel",
        "catastrophe fait", "incendie meurtrier", "incendie mortel",
        "effondrement meurtrier",
    ],
    "es": [
        # Violence & Crime
        "asesinado", "asesinada", "asesinato", "asesinados",
        "matado", "muerto a tiros", "tiroteo",
        "apuñalado", "apuñalamiento",
        "atentado", "ataque terrorista", "terrorista",
        "masacre", "tirador",
        # Death & Tragedy (specific contexts)
        "hallado muerto", "cuerpo hallado", "cadáver",
        "víctima mortal", "víctimas", "múltiples víctimas",
        # War & Conflict (specific violent contexts)
        "crímenes de guerra", "ataque aéreo", "bombardeo",
        "civiles muertos", "víctimas civiles",
        # Disasters & Accidents (with casualties)
        "accidente mortal", "choque mortal",
        "desastre deja", "incendio mortal",
        "derrumbe mortal",
    ],
    "de": [
        # Violence & Crime
        "getötet", "ermordet", "Mord", "Mordanschlag",
        "erschossen", "Schießerei", "erstochen",
        "Attentat", "Terroranschlag", "Terrorist",
        "Massaker", "Schütze",
        # Death & Tragedy (specific contexts)
        "tot aufgefunden", "Leiche gefunden",
        "Todesopfer", "Opfer", "mehrere Opfer",
        # War & Conflict (specific violent contexts)
        "Kriegsverbrechen", "Luftangriff", "Bombardierung",
        "Zivilisten getötet", "zivile Opfer",
        # Disasters & Accidents (with casualties)
        "tödlicher Unfall", "tödlicher Absturz",
        "Katastrophe fordert", "tödlicher Brand",
        "Einsturz",
    ],
    "da": [
        # Violence & Crime
        "dræbt", "myrdet", "mord", "drab",
        "skudt ned", "skuddrab", "stukket ned",
        "attentat", "terrorangreb", "terrorist",
        "massedrab", "gerningsmand",
        # Death & Tragedy (specific contexts)
        "fundet død", "lig fundet",
        "dræbt", "ofre", "flere ofre",
        # War & Conflict (specific violent contexts)
        "krigsforbrydelser", "luftangreb", "bombing",
        "civile dræbt", "civile ofre",
        # Disasters & Accidents (with casualties)
        "dødsulykke", "dødsstyrtet",
        "katastrofe koster", "dødsbrand",
        "sammenstyrtning",
    ],
    "nl": [
        # Violence & Crime
        "gedood", "vermoord", "moord", "doodgeschoten",
        "neergeschoten", "schietpartij", "neergestoken",
        "aanslag", "terreuraanval", "terrorist",
        "bloedbad", "schutter",
        # Death & Tragedy (specific contexts)
        "dood aangetroffen", "lichaam gevonden",
        "dodelijk slachtoffer", "slachtoffers", "meerdere slachtoffers",
        # War & Conflict (specific violent contexts)
        "oorlogsmisdaden", "luchtaanval", "bombardement",
        "burgers gedood", "burgersslachtoffers",
        # Disasters & Accidents (with casualties)
        "dodelijk ongeluk", "dodelijke crash",
        "ramp kost", "dodelijke brand",
        "instorting",
    ],
    "it": [
        # Violence & Crime
        "ucciso", "uccisa", "assassinato", "omicidio",
        "sparato", "sparatoria", "accoltellato", "accoltellamento",
        "attentato", "attacco terroristico", "terrorista",
        "strage", "sparatore",
        # Death & Tragedy (specific contexts)
        "trovato morto", "corpo trovato", "cadavere",
        "vittima mortale", "vittime", "più vittime",
        # War & Conflict (specific violent contexts)
        "crimini di guerra", "attacco aereo", "bombardamento",
        "civili uccisi", "vittime civili",
        # Disasters & Accidents (with casualties)
        "incidente mortale", "schianto mortale",
        "disastro causa", "incendio mortale",
        "crollo",
    ],
    "pt": [
        # Violence & Crime
        "assassinado", "assassinada", "assassinato", "assassinados",
        "morto a tiros", "baleado", "tiroteio",
        "esfaqueado", "esfaqueamento",
        "atentado", "ataque terrorista", "terrorista",
        "massacre", "atirador",
        # Death & Tragedy (specific contexts)
        "encontrado morto", "corpo encontrado", "cadáver",
        "vítima fatal", "vítimas", "múltiplas vítimas",
        # War & Conflict (specific violent contexts)
        "crimes de guerra", "ataque aéreo", "bombardeio",
        "civis mortos", "vítimas civis",
        # Disasters & Accidents (with casualties)
        "acidente fatal", "acidente mortal",
        "desastre deixa", "incêndio mortal",
        "desabamento",
    ],
    "ro": [
        # Violence & Crime
        "ucis", "ucisă", "asasinat", "asasinați",
        "împușcat", "împușcătură", "înjunghiat", "înjunghiere",
        "atentat", "atac terorist", "terorist",
        "masacru", "atacator",
        # Death & Tragedy (specific contexts)
        "găsit mort", "corp găsit", "cadavru",
        "victimă mortală", "victime", "mai multe victime",
        # War & Conflict (specific violent contexts)
        "crime de război", "atac aerian", "bombardament",
        "civili uciși", "victime civile",
        # Disasters & Accidents (with casualties)
        "accident mortal", "accident fatal",
        "dezastru lasă", "incendiu mortal",
        "prăbușire", "colaps",
    ],
}


def is_disturbing_content_based_on_keywords(title: str = None, content: str = None, language: str = "en") -> tuple[bool, str]:
    """
    Check if article contains disturbing content (violence, death, disaster, tragedy).

    Uses keyword detection for fast pre-LLM filtering.

    Args:
        title: Article title
        content: Article content (first 500 chars recommended)
        language: Language code (en, fr, es, de, da, nl, it, pt, ro)

    Returns:
        (is_disturbing, reason) tuple
    """
    if not title and not content:
        return False, ""

    # Get keywords for this language, fallback to English
    keywords = DISTURBING_KEYWORDS.get(language, DISTURBING_KEYWORDS["en"])

    # Combine title and content for checking
    text_to_check = ""
    if title:
        text_to_check += title.lower()
    if content:
        # Only check first 500 chars of content to focus on headline/intro
        text_to_check += " " + content[:500].lower()

    # Check for disturbing keywords
    matched_keywords = []
    for keyword in keywords:
        if keyword.lower() in text_to_check:
            matched_keywords.append(keyword)

    # Require at least one keyword match
    if matched_keywords:
        return True, f"Disturbing content keywords: {', '.join(matched_keywords[:3])}"

    return False, ""
