from collections import Counter
import datetime
import os
import inspect
import json

STR_DATETIME_FORMAT = "%d_%m_%y_%H_%M_%S"


class CrawlReport:
    def __init__(self) -> None:
        path_to_dir = os.sep.join(inspect.getfile(self.__class__).split(os.sep)[:-1])
        self.default_save_dir = os.path.join(path_to_dir, "crawl_data")
        self.data = {"lang": {}}

    def __convert_str_to_dt(self, str_datetime):
        dt_parsed = datetime.datetime.strptime(str_datetime, STR_DATETIME_FORMAT)
        return dt_parsed

    def __convert_dt_to_str(self, datetime):
        return datetime.strftime(STR_DATETIME_FORMAT)

    def add_language(self, lang_code: str):
        self.data["lang"][lang_code] = {"feeds": {}, "total_time": None}

    def add_feed(self, lang_code: str, feed_id: int):
        if lang_code not in self.data["lang"]:
            self.add_language(lang_code)
        self.data["lang"][lang_code]["feeds"][feed_id] = {
            "article_report": {
                "sents_removed": {},
                "quality_error": {},
            },
            "last_article_date": None,
            "feed_errors": [],
            "crawl_time": None,
            "total_articles": None,
            "total_downloaded": None,
            "total_low_quality": None,
            "total_in_db": None,
        }

    def set_total_time(self, lang_code: str, total_time):
        self.data["lang"][lang_code]["total_time"] = total_time

    def add_feed_error(self, lang_code: str, feed_id: int, error: str):
        self.data["lang"][lang_code]["feeds"][feed_id]["feed_errors"].append(error)

    def set_feed_crawl_time(self, lang_code: str, feed_id: int, crawl_time):
        self.data["lang"][lang_code]["feeds"][feed_id]["crawl_time"] = crawl_time

    def set_feed_last_article_date(
        self, lang_code: str, feed_id: int, last_article_date
    ):
        self.data["lang"][lang_code]["feeds"][feed_id]["last_article_date"] = (
            self.__convert_dt_to_str(last_article_date)
        )

    def set_feed_total_articles(self, lang_code: str, feed_id: int, total_articles):
        self.data["lang"][lang_code]["feeds"][feed_id][
            "total_articles"
        ] = total_articles

    def set_feed_total_downloaded(self, lang_code: str, feed_id: int, total_downloaded):
        self.data["lang"][lang_code]["feeds"][feed_id][
            "total_downloaded"
        ] = total_downloaded

    def set_feed_total_low_quality(
        self, lang_code: str, feed_id: int, total_low_quality
    ):
        self.data["lang"][lang_code]["feeds"][feed_id][
            "total_low_quality"
        ] = total_low_quality

    def set_feed_total_in_db(self, lang_code: str, feed_id: int, total_in_db):
        self.data["lang"][lang_code]["feeds"][feed_id]["total_in_db"] = total_in_db

    def set_non_quality_reason(
        self, lang_code: str, feed_id: int, non_quality_reason_counts: dict
    ):
        self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
            "quality_error"
        ] = Counter(non_quality_reason_counts)

    def set_sent_removed(self, lang_code: str, feed_id: int, sent_removed_count: dict):
        self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
            "sents_removed"
        ] = Counter(sent_removed_count)

    def add_non_quality_reason(self, lang_code: str, feed_id: int, non_quality_reason):
        self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
            "quality_error"
        ][non_quality_reason] = (
            self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
                "quality_error"
            ].get(non_quality_reason, 0)
            + 1
        )

    def add_sent_removed(self, lang_code: str, feed_id: int, sent_removed):
        self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
            "sents_removed"
        ] = (
            self.data["lang"][lang_code]["feeds"][feed_id]["article_report"][
                "sents_removed"
            ].get(sent_removed, 0)
            + 1
        )

    def save_crawl_report(self):
        timestamp_str = self.__convert_dt_to_str(datetime.datetime.now())
        for lang in self.data["lang"]:
            filename = f"{lang}-crawl-{timestamp_str}.json"
            output_dir = os.path.join(self.default_save_dir, lang)
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)
            with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
                json.dump(self.data["lang"], f)

    def load_crawl_report_data(self, day_period: int, report_dir_path=None):
        if report_dir_path is None:
            report_dir_path = self.default_save_dir
        for lang in os.listdir(report_dir_path):
            for file in os.listdir(os.path.join(report_dir_path, lang)):
                lang, _, date = file.split(".")[0].split("-")
                date = self.__convert_str_to_dt(date)
                day_diff = (date.now() - date).days
                if day_diff > day_period:
                    print(
                        f"File '{file}' outside of day range of '{day_period}', was: '{day_diff}'"
                    )
                    continue
                try:
                    with open(
                        os.path.join(report_dir_path, lang, file), "r", encoding="utf-8"
                    ) as f:
                        self.data["lang"][lang] = json.load(f)[lang]
                except Exception as e:
                    print(f"Failed to load: '{file}', with: '{e}'")

    def __validate_lang(self, lang: str):
        langs_available = set(self.data["lang"].keys())
        if lang not in langs_available:
            raise ValueError(
                f"'{lang}' is not found in current loaded data. Available langs: '{list(langs_available)}'"
            )
        return True

    def get_total_non_quality_counts(self, langs_to_load: list[str] = None):
        if langs_to_load is None:
            langs_to_load = self.data["lang"].keys()
        else:
            for lang in langs_to_load:
                self.__validate_lang(lang)

        total_counts = Counter()
        for lang in langs_to_load:
            for feed in self.data["lang"][lang]["feeds"]:
                total_counts += Counter(
                    self.data["lang"][lang]["feeds"][feed]["article_report"][
                        "quality_error"
                    ]
                )
        return total_counts

    def get_total_removed_sents_counts(self, langs_to_load: list[str] = None):
        if langs_to_load is None:
            langs_to_load = self.data["lang"].keys()
        else:
            for lang in langs_to_load:
                self.__validate_lang(lang)
        total_counts = Counter()
        for lang in langs_to_load:
            for feed in self.data["lang"][lang]["feeds"]:
                total_counts += Counter(
                    self.data["lang"][lang]["feeds"][feed]["article_report"][
                        "sents_removed"
                    ]
                )
        return total_counts
