# coding=utf-8

import zeeguu.core
from zeeguu.core.model import Article, Language
import stanza
from zeeguu.api.app import create_app
import numpy as np
from tqdm import tqdm
import os
from pprint import pprint
import pyphen


app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session
TOTAL_ARTCILE_SAMPLE = 500
LANGUAGES_TO_CALCULATE_STATS_FOR = [
    "da",
    "nl",
    "en",
    "fr",
    "de",
    "hu",
    "it",
    "no",
    "pl",
    "pt",
    "ru",
    "es",
    "sv",
]
RESULTS = {}


def token_len_sent_len_vec(lang_code):
    lang_stats = RESULTS[lang_code]
    np_token_length_list = np.array(lang_stats["token_length_list"])
    np_token_syl_list = np.array(lang_stats["token_syllables"])
    np_sentence_length_list = np.array(lang_stats["sentence_length_list"])
    return np.array(
        (
            np_token_length_list.mean(),
            np_token_syl_list.mean(),
            np_sentence_length_list.mean(),
        )
    )


def print_stats_for_lang(lang_code):
    lang_stats = RESULTS[lang_code]
    np_token_length_list = np.array(lang_stats["token_length_list"])
    np_sentence_length_list = np.array(lang_stats["sentence_length_list"])
    np_token_syl_list = np.array(lang_stats["token_syllables"])
    print("#" * 10 + f" Results for {lang_code} " + "#" * 10)
    print(
        f"Token AVG Length: {np_token_length_list.mean():.2f}, std: {np_token_length_list.std():.2f}"
    )
    print(
        f"Token Syllable AVG Length: {np_token_syl_list.mean():.2f}, std: {np_token_syl_list.std():.2f}"
    )
    print(
        f"Sentence AVG Length: {np_sentence_length_list.mean():.2f}, std: {np_sentence_length_list.std():.2f}"
    )
    print(
        f"Unique tokens: {lang_stats["unique_vocab"]} out of a total of {lang_stats["total_tokens"]}"
    )
    dist_to_other_languages = []
    lang_code_vec = token_len_sent_len_vec(lang_code)
    for code in LANGUAGES_TO_CALCULATE_STATS_FOR:
        if code == lang_code:
            continue
        other_lang_vec = token_len_sent_len_vec(code)
        dist = np.linalg.norm(lang_code_vec - other_lang_vec)
        dist_to_other_languages.append((f"{lang_code}-{code}", dist))
    dist_to_other_languages.sort(key=lambda x: x[1])
    pprint(dist_to_other_languages)


for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
    language = Language.find_or_create(lang_code)
    nlp = stanza.Pipeline(lang=lang_code, processors="tokenize")
    target_ids = np.array(
        [
            a_id[0]
            for a_id in db_session.query(Article.id)
            .filter(Article.language_id == language.id)
            .all()
        ]
    )
    print("Got articles for language, total: ", len(target_ids))
    sampled_ids = np.random.choice(
        target_ids, min(TOTAL_ARTCILE_SAMPLE, len(target_ids)), replace=False
    )
    print("Starting calculation of stats")
    stats = {
        "token_length_list": [],
        "sentence_length_list": [],
        "token_syllables": [],
        "total_tokens": 0,
    }
    unique_vocab = set()
    for a_id in tqdm(sampled_ids, total=len(sampled_ids)):
        article = Article.find_by_id(a_id)
        doc = nlp(article.content)
        for sent in doc.sentences:
            stats["sentence_length_list"].append(len(sent.tokens))
            for token in sent.tokens:
                text = token.text
                stats["token_length_list"].append(len(text))
                unique_vocab.add(text)
                stats["total_tokens"] += 1
                pyphen_lang = lang_code
                if pyphen_lang == "pt":
                    pyphen_lang = "pt_PT"
                if pyphen_lang == "no":
                    pyphen_lang = "nb"
                dic = pyphen.Pyphen(lang=pyphen_lang)
                syllables = len(dic.positions(text)) + 1
                stats["token_syllables"].append(syllables)

    stats["unique_vocab"] = len(unique_vocab)
    RESULTS[lang_code] = stats

os.system("cls" if os.name == "nt" else "clear")
for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
    print_stats_for_lang(lang_code)
    print()
    print()
