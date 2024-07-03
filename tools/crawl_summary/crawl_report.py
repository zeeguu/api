from collections import Counter
import datetime
import os
import inspect
import json
import pathlib

STR_DATETIME_FORMAT = "%d_%m_%y_%H_%M_%S"
CRAWL_REPORT_DATA = os.environ.get(
    "CRAWL_REPORT_DATA",
    os.path.join(pathlib.Path(__file__).parent.resolve(), "crawl_data"),
)


class CrawlReport:
    def __init__(self) -> None:
        self.save_dir = CRAWL_REPORT_DATA
        self.data = {"lang": {}}
        self.crawl_report_date = datetime.datetime.now()

    def get_days_from_crawl_report_date(self):
        return (datetime.datetime.now() - self.crawl_report_date).days

    def __convert_str_to_dt(self, str_datetime):
        dt_parsed = datetime.datetime.strptime(str_datetime, STR_DATETIME_FORMAT)
        return dt_parsed

    def __convert_dt_to_str(self, datetime):
        return datetime.strftime(STR_DATETIME_FORMAT)

    def _get_feed_dict(self, feed):
        lang_code = feed.language.code
        feed_id = feed.id
        return self.data["lang"][lang_code]["feeds"][feed_id]

    def add_language(self, lang_code: str):
        self.data["lang"][lang_code] = {"feeds": {}, "total_time": None}

    def add_feed(self, feed):
        lang_code = feed.language.code
        feed_id = feed.id
        if lang_code not in self.data["lang"]:
            self.add_language(lang_code)
        self.data["lang"][lang_code]["feeds"][feed_id] = {
            "article_report": {
                "sents_removed": {},
                "quality_error": {},
                "quality_to_url": {},
                "sents_to_url": {},
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

    def add_feed_error(self, feed, error: str):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["feed_errors"].append(error)

    def set_feed_crawl_time(self, feed, crawl_time):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["crawl_time"] = crawl_time

    def set_feed_last_article_date(self, feed, last_article_date):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["last_article_date"] = self.__convert_dt_to_str(last_article_date)

    def set_feed_total_articles(self, feed, total_articles):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["total_articles"] = total_articles

    def set_feed_total_downloaded(self, feed, total_downloaded):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["total_downloaded"] = total_downloaded

    def set_feed_total_low_quality(self, feed, total_low_quality):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["total_low_quality"] = total_low_quality

    def set_feed_total_in_db(self, feed, total_in_db):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["total_in_db"] = total_in_db

    def set_non_quality_reason(self, feed, non_quality_reason_counts: dict):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["article_report"]["quality_error"] = Counter(
            non_quality_reason_counts
        )

    def set_sent_removed(self, feed, sent_removed_count: dict):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["article_report"]["sents_removed"] = Counter(sent_removed_count)

    def add_non_quality_reason(self, feed, non_quality_reason, url=None):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["article_report"]["quality_error"][non_quality_reason] = (
            feed_dict["article_report"]["quality_error"].get(non_quality_reason, 0) + 1
        )
        if url is not None:
            feed_dict["article_report"]["quality_to_url"][non_quality_reason] = (
                feed_dict["article_report"]["quality_to_url"].get(
                    non_quality_reason, []
                )
                + [url]
            )

    def add_sent_removed(self, feed, sent_removed, url=None):
        feed_dict = self._get_feed_dict(feed)
        feed_dict["article_report"]["sents_removed"][sent_removed] = (
            feed_dict["article_report"]["sents_removed"].get(sent_removed, 0) + 1
        )
        if url is not None:
            feed_dict["article_report"]["sents_to_url"][sent_removed] = feed_dict[
                "article_report"
            ]["sents_to_url"].get(sent_removed, []) + [url]

    def save_crawl_report(self):
        timestamp_str = self.__convert_dt_to_str(self.crawl_report_date)
        for lang in self.data["lang"]:
            filename = f"{lang}-crawl-{timestamp_str}.json"
            output_dir = os.path.join(self.save_dir, lang)
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)
            with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
                json.dump(self.data["lang"][lang], f)

    def load_crawl_report_data(self, day_period: int, report_dir_path=None):
        if report_dir_path is None:
            report_dir_path = self.save_dir
        for lang in os.listdir(report_dir_path):
            for file in os.listdir(os.path.join(report_dir_path, lang)):
                lang, _, date = file.split(".")[0].split("-")
                date = self.__convert_str_to_dt(date)
                self.crawl_report_date = min(self.crawl_report_date, date)
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
                        loaded_data = json.load(f)
                        if lang not in self.data["lang"]:
                            self.add_language(lang)
                        lang_dict = self.data["lang"][lang]
                        for feed in loaded_data["feeds"]:
                            if feed not in lang_dict["feeds"]:
                                # We have not loaded any feeds yet:
                                lang_dict["feeds"][feed] = loaded_data["feeds"][feed]
                            else:
                                feed_dict = lang_dict["feeds"][feed]
                                feed_dict["article_report"]["sents_removed"] = Counter(
                                    feed_dict["article_report"]["sents_removed"]
                                ) + Counter(
                                    loaded_data["feeds"][feed]["article_report"][
                                        "sents_removed"
                                    ]
                                )
                                feed_dict["article_report"]["quality_error"] = Counter(
                                    feed_dict["article_report"]["quality_error"]
                                ) + Counter(
                                    loaded_data["feeds"][feed]["article_report"][
                                        "quality_error"
                                    ]
                                )
                        print(f"LOADED File (d:{date}, l:{lang}): {file}")
                except Exception as e:
                    print(f"Failed to load: '{file}', with: '{e} ({type(e)})'")

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
                feed_dict = self.data["lang"][lang]["feeds"][feed]
                total_counts += Counter(feed_dict["article_report"]["quality_error"])
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
                feed_dict = self.data["lang"][lang]["feeds"][feed]
                total_counts += Counter(feed_dict["article_report"]["sents_removed"])
        return total_counts
