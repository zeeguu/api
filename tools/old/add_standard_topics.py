#!/usr/bin/env python


"""

    Script that adds standard topics like sport
    health tech e.g. for all languages, after
    this has been added, one can run the
    'tag_existing_articles' script to tag them.


"""

import zeeguu.core
from zeeguu.core.model.topic import Topic
from zeeguu.core.model.language import Language
from zeeguu.core.model.localized_topic import LocalizedTopic

db_session = zeeguu.core.model.db.session

count = 0
TOPICS = [
    "Sport",
    "Health",
    "Technology",
    "Politics",
    "Science",
    "Culture",
    "Travel",
    "Food",
]
LANGUAGES = [
    Language.find("es"),
    Language.find("fr"),
    Language.find("nl"),
    Language.find("de"),
    Language.find("en"),
    Language.find("it"),
]
SPANISH_TOPICS = [
    ["Sport", "juego sport deporte"],
    ["Salud", "salud hospital"],
    ["Technologia", "tech technologia"],
    ["Politica", "politica diplomatico"],
    ["Ciencia", "ciencia"],
    ["Cultura", "cultura"],
    ["Viaje", "viaje viajes"],
    ["Comida", "comida alimento"],
]
FRENCH_TOPICS = [
    ["Sport", "sport divertissement jouer"],
    ["Sante", "sante hopital"],
    ["Technologie", "tech technologie"],
    ["Politique", "politique politologie"],
    ["Science", "science savoir"],
    ["Culture", "culture"],
    ["Voyage", "voyager voyage"],
    ["Aliments", "nourriture aliments"],
]
DUTCH_TOPICS = [
    ["Sport", "sport spel"],
    ["Gezondheid", "gezondheid ziekenhuis gezond"],
    ["Technologie", "tech technologie"],
    ["Politiek", "politiek politisch"],
    ["Wetenschap", "wetenschap"],
    ["Cultuur", "cultuur cultureel"],
    ["Reizen", "reizen reis"],
    ["Eten", "eten voedsel eet"],
]
GERMAN_TOPICS = [
    ["Sport", "sport sportart spielart abart"],
    ["Gesundheit", "gesundheit gesundheitszustand"],
    ["Technologie", "technologie technik"],
    ["Politik", "politik politologie"],
    ["Wissenschaft", "wissenschaft"],
    ["Kultur", "kultur bildung"],
    ["Reise", "reise reisen"],
    ["Essen", "lebensmittel essen"],
]
ENGLISH_TOPICS = [
    ["Sport", "sport playing"],
    ["Health", "health hospital healthy"],
    ["Technology", "tech technology"],
    ["Politics", "politics politic"],
    ["Science", "science scientist"],
    ["Culture", "culture cultural"],
    ["Travel", "travel travels"],
    ["Food", "food eat"],
]
ITALIAN_TOPICS = [
    ["Sport", "sport gioco divertimento"],
    ["Salute", "salute salutare hospedale"],
    ["Technologia", "tech technologia"],
    ["Politica", "politica"],
    ["Scienza", "scienza scientifico"],
    ["Cultura", "cultura"],
    ["Viaggi", "viaggio viaggi"],
    ["Cibo", "cibo vitto"],
]


def add_topic(title):
    new_topic = Topic(title)
    db_session.add(new_topic)
    return new_topic


def add_localized_topic(topic: Topic, language: Language, name, keywords):
    new_loc_topic = LocalizedTopic(topic, language, name, keywords)
    db_session.add(new_loc_topic)
    return new_loc_topic


for topic_name in TOPICS:
    topic = add_topic(topic_name)
    add_localized_topic(
        topic, LANGUAGES[0], SPANISH_TOPICS[count][0], SPANISH_TOPICS[count][1]
    )
    add_localized_topic(
        topic, LANGUAGES[1], FRENCH_TOPICS[count][0], FRENCH_TOPICS[count][1]
    )
    add_localized_topic(
        topic, LANGUAGES[2], DUTCH_TOPICS[count][0], DUTCH_TOPICS[count][1]
    )
    add_localized_topic(
        topic, LANGUAGES[3], GERMAN_TOPICS[count][0], GERMAN_TOPICS[count][1]
    )
    add_localized_topic(
        topic, LANGUAGES[4], ENGLISH_TOPICS[count][0], ENGLISH_TOPICS[count][1]
    )
    add_localized_topic(
        topic, LANGUAGES[5], ITALIAN_TOPICS[count][0], ITALIAN_TOPICS[count][1]
    )
    count += 1
    db_session.commit()
