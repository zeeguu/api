import pandas as pd


def ms_to_mins(ms_time):
    return ms_time / 1000 / 60


class DataExtractor:
    def __init__(self, db_connection, DAYS_FOR_REPORT=7) -> None:
        self.DAYS_FOR_REPORT = DAYS_FOR_REPORT
        self.db_connection = db_connection

    def __add_feed_name(self, df, feed_df, column_with_id="feed_id"):
        df["Feed Name"] = df[column_with_id].apply(
            lambda x: (
                "No Feed"
                if pd.isna(x)
                else str(x) + " " + feed_df.loc[feed_df.id == x, "title"].values[0][:15]
            )
        )

    def run_query(self, query):
        df = pd.read_sql(query, con=self.db_connection)
        return df

    def get_article_topics_df(self, feed_df):
        print("Getting Article Topics...")
        query = f"""SELECT a.id, l.name Language, a.feed_id, t.title Topic, atm.origin_type
        FROM article a 
        INNER JOIN article_topic_map atm on a.id = atm.article_id 
        INNER JOIN topic t ON atm.topic_id = t.id
        INNER JOIN language l ON l.id = a.language_id
        WHERE a.published_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
        AND a.broken = 0"""
        df = pd.read_sql(query, con=self.db_connection)
        self.__add_feed_name(df, feed_df)
        return df

    def get_days_since_last_crawl(self):
        print("Getting Feeds Last Crawl Time...")
        query = f"""
            SELECT
                feed_id,
                f.title,
                DATEDIFF(CURDATE(), MAX(published_time)) days_since_last_article,
                DATEDIFF(CURDATE(), f.last_crawled_time) days_since_last_feed_crawl
            FROM
                article a
                JOIN feed f ON a.feed_id = f.id
            WHERE
                f.deactivated = 0
            GROUP by
                feed_id
            HAVING
                days_since_last_feed_crawl <= {self.DAYS_FOR_REPORT}
            ORDER BY
                days_since_last_article DESC;
        """
        df = pd.read_sql(query, con=self.db_connection)
        return df

    def get_article_df(self, feed_df):
        print("Getting Articles...")
        query = f"""SELECT a.*, l.name Language
        FROM article a     
        INNER JOIN language l ON l.id = a.language_id
        WHERE published_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
        AND a.broken = 0"""
        df = pd.read_sql(query, con=self.db_connection)
        self.__add_feed_name(df, feed_df)
        return df

    def get_url_keyword_counts(self, min_count=100):
        print("Getting URL keyword counts...")
        # Update with values from the code.
        query = f"""SELECT uk.id, l.name, keyword, count
                    FROM url_keyword uk
                    JOIN (SELECT url_keyword_id, count(*) count
                          FROM article_url_keyword_map
                          GROUP BY url_keyword_id) as keyword_count
                    ON uk.id = keyword_count.url_keyword_id
                    JOIN language l ON l.id = language_id
                    WHERE count > {min_count}
                    AND topic_id is NULL
                    AND keyword not in (
                                        "news",
                                        "i",
                                        "nyheter",
                                        "article",
                                        "nieuws",
                                        "aktuell",
                                        "artikel",
                                        "wiadomosci",
                                        "actualites",
                                        "cronaca",
                                        "nyheder",
                                        "jan",
                                        "feb",
                                        "mar",
                                        "apr",
                                        "may",
                                        "jun",
                                        "jul",
                                        "aug",
                                        "sep",
                                        "oct",
                                        "nov",
                                        "dec"
                                        )
                    ORDER BY count DESC;
                """
        df = pd.read_sql(query, con=self.db_connection)
        return df

    def get_article_df_with_ids(self, feed_df, id_to_fetch: list[int]):
        print("Getting Articles with Ids...")
        if not id_to_fetch:
            return pd.DataFrame()
        # Security: Validate all IDs are integers to prevent SQL injection
        validated_ids = [int(v) for v in id_to_fetch]
        # Use parameterized placeholders for the IN clause
        placeholders = ",".join(["%s"] * len(validated_ids))
        query = f"""SELECT a.*, l.name Language
        FROM article a
        INNER JOIN language l ON l.id = a.language_id
        WHERE a.id in ({placeholders})"""
        df = pd.read_sql(query, con=self.db_connection, params=validated_ids)
        self.__add_feed_name(df, feed_df)
        return df

    def get_language_df(self):
        print("Getting Languages...")
        query = "SELECT * from language"
        return pd.read_sql(query, con=self.db_connection)

    def get_feed_df(self):
        print("Getting Feeds...")
        query = """SELECT f.*,l.name Language 
        FROM feed f
        INNER JOIN language l ON f.language_id = l.id
        """
        feed_pd = pd.read_sql(query, con=self.db_connection)
        feed_pd["Feed Name"] = (
            feed_pd["id"].astype(str) + " " + feed_pd["title"].str[:15]
        )
        return pd.read_sql(query, con=self.db_connection)

    def get_user_reading_activity(self, language_df, feed_df):
        print("Getting User Activity...")
        query = f"""SELECT a.id, a.language_id, a.feed_id, urs.user_id, SUM(urs.duration) total_reading_time
        FROM article a 
        INNER JOIN user_reading_session urs ON urs.article_id = a.id 
        INNER JOIN user u ON urs.user_id = u.id
        WHERE urs.start_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
        AND u.learned_language_id = a.language_id
        GROUP BY a.id, a.language_id, a.feed_id, urs.user_id"""
        reading_time_df = pd.read_sql(query, con=self.db_connection)
        # Add the Language Name
        reading_time_df["Language"] = reading_time_df.language_id.apply(
            lambda x: language_df.loc[language_df.id == x, "name"].values[0]
        )
        # Add the Source Names
        reading_time_df["Feed Name"] = "No Feed"
        valid_feed_mask = ~reading_time_df["feed_id"].isna()
        reading_time_df.loc[valid_feed_mask, "Feed Name"] = reading_time_df.loc[
            valid_feed_mask, "feed_id"
        ].apply(lambda x: feed_df.loc[feed_df.id == x, "title"].values[0])
        reading_time_df.loc[valid_feed_mask, "Feed Name"] = (
            reading_time_df.loc[valid_feed_mask].feed_id.apply(int).astype(str)
            + " "
            + reading_time_df.loc[valid_feed_mask, "Feed Name"].str[:15]
        )
        reading_time_df["total_reading_time"] = reading_time_df[
            "total_reading_time"
        ].apply(ms_to_mins)
        return reading_time_df

    def get_exercise_type_activity(self):
        print("Getting Exercise Type Activity...")
        query = f"""SELECT l.name as Language, es.source as Source, sum(e.solving_speed) total_exercise_time, Count(*) total_exercises
                FROM user u 
                INNER JOIN user_exercise_session ues ON ues.user_id = u.id
                INNER JOIN exercise e ON e.session_id = ues.id
                INNER JOIN user_word um on um.id = e.user_word_id
                inner join meaning m on um.meaning_id = m.id
                INNER JOIN phrase p ON m.origin_id = p.id
                INNER JOIN exercise_source es on es.id = e.source_id
                INNER JOIN language l on p.language_id = l.id and p.language_id = u.learned_language_id
                WHERE ues.last_action_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
                GROUP BY u.learned_language_id, es.source
                """
        total_exercise_activity = pd.read_sql(query, con=self.db_connection)
        total_exercise_activity["total_exercise_time"] = total_exercise_activity[
            "total_exercise_time"
        ].apply(ms_to_mins)
        return total_exercise_activity

    def get_user_exercise_activity(self):
        print("Getting User Exercise Activity...")
        query = f"""SELECT u.id user_id, l.name Language, sum(e.solving_speed) total_exercise_time
                    FROM user u
                    INNER JOIN user_exercise_session ues ON ues.user_id = u.id
                    INNER JOIN exercise e ON e.session_id = ues.id
                    INNER JOIN user_word um on um.id = e.user_word_id
                    inner join meaning m on um.meaning_id = m.id
                    INNER JOIN phrase p ON m.origin_id = p.id
                    INNER JOIN exercise_source es on es.id = e.source_id
                    INNER JOIN language l on p.language_id = l.id and p.language_id = u.learned_language_id
                    WHERE ues.last_action_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
                    GROUP BY u.id;"""
        total_user_exercise_activity = pd.read_sql(query, con=self.db_connection)
        total_user_exercise_activity["total_exercise_time"] = (
            total_user_exercise_activity["total_exercise_time"].apply(ms_to_mins)
        )
        return total_user_exercise_activity

    def get_bookmark_df(self):
        print("Getting Bookmarks...")
        query = f"""SELECT um.*, l.name Language, MAX(e.id) as last_exercise, COUNT(e.id) total_exercises
                    FROM user_word um
                        JOIN exercise e on um.id = e.user_word_id
                        JOIN meaning m on um.meaning_id = m.id
                        JOIN phrase p ON m.origin_id = p.id
                        JOIN language l ON p.language_id = l.id
                        JOIN bookmark b ON b.user_word_id = um.id
                    GROUP by um.id
                    HAVING MIN(b.time) >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY);
                """
        bookmarks = pd.read_sql(query, con=self.db_connection)
        bookmarks["Has Exercised"] = bookmarks.last_exercise.apply(
            lambda x: "No" if pd.isna(x) else "Yes"
        )
        return bookmarks

    def get_combined_user_reading_exercise_activity(
        self, pd_exercise_activity, pd_reading_activity
    ):
        user_reading_activity = (
            pd_reading_activity.groupby(["Language", "user_id"])
            .total_reading_time.sum()
            .reset_index()
        )
        combined_exercise_reading_user = pd_exercise_activity[
            ["user_id", "Language", "total_exercise_time"]
        ].merge(user_reading_activity, on="user_id", how="outer")
        combined_exercise_reading_user["Language"] = combined_exercise_reading_user[
            "Language_y"
        ]
        combined_exercise_reading_user.loc[
            combined_exercise_reading_user["Language"].isna(), "Language"
        ] = combined_exercise_reading_user.loc[
            combined_exercise_reading_user["Language"].isna(), "Language_x"
        ]
        combined_exercise_reading_user.loc[
            combined_exercise_reading_user["total_reading_time"].isna(),
            "total_reading_time",
        ] = 0

        combined_exercise_reading_user.loc[
            combined_exercise_reading_user["total_exercise_time"].isna(),
            "total_exercise_time",
        ] = 0

        active_users_reading_or_exercises = combined_exercise_reading_user[
            (combined_exercise_reading_user["total_reading_time"] > 1)
            | (combined_exercise_reading_user["total_exercise_time"] > 1)
        ]
        return active_users_reading_or_exercises

    def get_topic_reading_time(self):
        print("Getting New Topic Reading Times...")
        query = f"""SELECT l.name as Language, t.title Topic, SUM(urs.duration) total_reading_time
        FROM article a 
        LEFT JOIN article_topic_map atm on a.id = atm.article_id
        LEFT JOIN topic t on atm.topic_id = t.id
        INNER JOIN user_reading_session urs ON urs.article_id = a.id
        INNER JOIN language l on a.language_id = l.id
        INNER JOIN user u ON urs.user_id = u.id
        WHERE urs.start_time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY)
        AND u.learned_language_id = a.language_id
        GROUP BY a.language_id, atm.topic_id;"""
        topic_reading_time_df = pd.read_sql(query, con=self.db_connection)
        topic_reading_time_df["total_reading_time"] = topic_reading_time_df[
            "total_reading_time"
        ].apply(ms_to_mins)
        topic_reading_time_df.loc[topic_reading_time_df["Topic"].isna(), "Topic"] = (
            "Unclassified"
        )
        return topic_reading_time_df

    def get_top_search_subscriptions(self):
        print("Getting top search subscriptions...")
        query = """SELECT s.keywords, count(user_id) total_users, sum(receive_email) as total_subscribers
                    FROM search_subscription s_sub 
                    INNER JOIN search s
                    ON s.id = s_sub.search_id
                    GROUP by search_id
                    ORDER BY total_users DESC;"""
        top_search_subscriptions_df = pd.read_sql(query, con=self.db_connection)
        return top_search_subscriptions_df

    def get_added_search_subscriptions(self):
        print("Getting new added search subscriptions...")
        query = f"""SELECT DISTINCT value as search
                    FROM zeeguu_test.user_activity_data
                    WHERE event like 'SUBSCRIBE_TO_SEARCH'
                    AND value in (SELECT keywords from search)
                    AND time >= DATE_SUB(CURDATE(), INTERVAL {self.DAYS_FOR_REPORT} DAY);"""
        newly_added_subscriptions = list(
            pd.read_sql(query, con=self.db_connection)["search"].values
        )
        return newly_added_subscriptions

    def get_top_search_filters(self):
        print("Getting top search filters...")
        query = """SELECT s.keywords, count(user_id) total_users
                    FROM search_filter s_f 
                    INNER JOIN search s
                    ON s.id = s_f.search_id
                    GROUP by search_id
                    ORDER BY total_users DESC;"""
        top_search_filters_df = pd.read_sql(query, con=self.db_connection)
        return top_search_filters_df

    def add_language_to_df(self, df, language_data):
        df["Language"] = df.language_id.apply(
            lambda x: language_data.loc[language_data.id == x, "name"].values[0]
        )

    def add_stats_to_feed(self, feed_df, article_df):
        feed_count = article_df.feed_id.value_counts().reset_index()
        feed_count["feed_id"] = feed_count["feed_id"].apply(int)
        feed_count = feed_count.set_index("feed_id")
        count_dictionary = feed_count.to_dict()["count"]
        feed_df["Count"] = feed_df.id.apply(lambda x: count_dictionary.get(int(x), 0))
        self.__add_feed_name(feed_df, feed_df, "id")
