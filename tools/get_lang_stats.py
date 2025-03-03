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
import copy


app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session
TOTAL_ARTCILE_SAMPLE = 500
LANGUAGES_TO_CALCULATE_STATS_FOR = [
    # Languages we have FK values for
    "es",
    "it",
    "nl",
    "fr",
    "ru",
    "de",
    "en",
    # Languages WITHOUT FK values for
    "da",
    "ro",
]
RESULTS = {}
CALCULATED_STATS = ["token_length_list", "token_syllables", "sentence_length_list"]


def token_len_sent_len_vec(lang_code, result_dict):
    vector = []
    counts = []
    for stat in CALCULATED_STATS:
        counts += [len(result_dict[lang_code][stat])]
        vector += [np.array(result_dict[lang_code][stat]).mean()]
    return np.array(vector), counts


def normalize_results(result_dict, outlier_threshold_per_stat=[0.01, 0.01, 0.01]):
    for i, stat in enumerate(CALCULATED_STATS):
        accumulated = []
        outlier_threshold = outlier_threshold_per_stat[i]
        for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
            lang_stats = np.array(result_dict[lang_code][stat])
            accumulated += lang_stats[
                (lang_stats > np.quantile(lang_stats, outlier_threshold))
                & (lang_stats < np.quantile(lang_stats, 1 - outlier_threshold))
            ].tolist()
        np_accumulated = np.array(accumulated)
        mean = np_accumulated.mean()
        std = np_accumulated.std()
        for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
            lang_stats = np.array(result_dict[lang_code][stat])
            lang_stats_outliers_removed = lang_stats[
                (lang_stats > np.quantile(lang_stats, outlier_threshold))
                & (lang_stats < np.quantile(lang_stats, 1 - outlier_threshold))
            ]
            np_normalized = (lang_stats_outliers_removed - mean) / std
            result_dict[lang_code][stat] = np_normalized.tolist()
    return result_dict


def print_stats_for_lang(lang_code, result_dict):
    dist_to_other_languages = []
    lang_code_vec, _ = token_len_sent_len_vec(lang_code, result_dict)
    for code in LANGUAGES_TO_CALCULATE_STATS_FOR:
        if code == lang_code:
            continue
        other_lang_vec, _ = token_len_sent_len_vec(code, result_dict)
        dist = np.linalg.norm(lang_code_vec - other_lang_vec)
        dist_to_other_languages.append((f"{lang_code}-{code}", round(dist, 4)))
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
normalized_outlier_removed_results = normalize_results(copy.deepcopy(RESULTS))
print("################## Normalized and outlier removed results ##################")
for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
    print("## Results for language: ", lang_code)
    vector, counts = token_len_sent_len_vec(
        lang_code, normalized_outlier_removed_results
    )
    print("Vector: ", vector)
    print("Counts per stat: ", counts)
    print_stats_for_lang(lang_code, normalized_outlier_removed_results)
    print()
print()
print("################## Original results ##################")
for lang_code in LANGUAGES_TO_CALCULATE_STATS_FOR:
    print("## Results for language: ", lang_code)
    vector, counts = token_len_sent_len_vec(lang_code, RESULTS)
    print("Vector: ", vector)
    print("Counts per stat: ", counts)
    print_stats_for_lang(lang_code, RESULTS)
    print()
