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

    def get_article_topics_df(self, feed_df):
        print("Getting Article Topics...")
        query = f"""SELECT a.id, l.name Language, a.feed_id, t.title Topic
        FROM article a 
        INNER JOIN article_topic_map atm on a.id = atm.article_id 
        INNER JOIN topic t ON atm.topic_id = t.id
        INNER JOIN language l ON l.id = a.language_id
        WHERE DATEDIFF(CURDATE(), a.published_time) <= {self.DAYS_FOR_REPORT}"""
        df = pd.read_sql(query, con=self.db_connection)
        self.__add_feed_name(df, feed_df)
        return df

    def get_article_df(self, feed_df):
        print("Getting Articles...")
        query = f"""SELECT a.*, l.name Language
        FROM article a     
        INNER JOIN language l ON l.id = a.language_id
        WHERE DATEDIFF(CURDATE(), published_time) <= {self.DAYS_FOR_REPORT}"""
        df = pd.read_sql(query, con=self.db_connection)
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
        print("Getting user activity...")
        query = f"""SELECT a.id, a.language_id, a.feed_id, urs.user_id, SUM(urs.duration) total_reading_time
        FROM article a 
        INNER JOIN user_reading_session urs ON urs.article_id = a.id 
        INNER JOIN user u ON urs.user_id = u.id
        WHERE DATEDIFF(CURDATE(), a.published_time) <= {self.DAYS_FOR_REPORT}
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
                INNER JOIN bookmark_exercise_mapping bem ON e.id = bem.exercise_id
                INNER JOIN bookmark b ON b.id = bem.bookmark_id AND b.user_id = u.id
                INNER JOIN user_word uw ON b.origin_id = uw.id
                INNER JOIN exercise_source es on es.id = e.source_id
                INNER JOIN language l on uw.language_id = l.id and uw.language_id = u.learned_language_id
                WHERE DATEDIFF(CURDATE(), ues.last_action_time) <= {self.DAYS_FOR_REPORT}
                GROUP BY u.learned_language_id, es.source"""
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
                    INNER JOIN bookmark_exercise_mapping bem ON e.id = bem.exercise_id
                    INNER JOIN bookmark b ON b.id = bem.bookmark_id AND b.user_id = u.id
                    INNER JOIN user_word uw ON b.origin_id = uw.id
                    INNER JOIN exercise_source es on es.id = e.source_id
                    INNER JOIN language l on uw.language_id = l.id and uw.language_id = u.learned_language_id
                    WHERE DATEDIFF(CURDATE(), ues.last_action_time) <= {self.DAYS_FOR_REPORT}
                    GROUP BY u.id;"""
        total_user_exercise_activity = pd.read_sql(query, con=self.db_connection)
        total_user_exercise_activity["total_exercise_time"] = (
            total_user_exercise_activity["total_exercise_time"].apply(ms_to_mins)
        )
        return total_user_exercise_activity

    def get_bookmark_df(self):
        print("Getting Bookmarks...")
        query = f"""SELECT b.*, l.name Language, MAX(bem.exercise_id) as last_exercise, COUNT(bem.exercise_id) total_exercises
                    FROM bookmark b
                    LEFT JOIN 
                        bookmark_exercise_mapping bem on b.id = bem.bookmark_id
                    INNER JOIN user_word uw ON b.origin_id = uw.id
                    INNER JOIN language l ON uw.language_id = l.id
                    WHERE DATEDIFF(CURDATE(), b.time) <= {self.DAYS_FOR_REPORT}
                    GROUP by b.id;
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
        print("Getting Topic Reading Times...")
        query = f"""SELECT l.name as Language, t.title Topic, SUM(urs.duration) total_reading_time
        FROM article a 
        LEFT JOIN article_topic_map atm on a.id = atm.article_id
        LEFT JOIN topic t on atm.topic_id = t.id
        INNER JOIN user_reading_session urs ON urs.article_id = a.id
        INNER JOIN language l on a.language_id = l.id
        INNER JOIN user u ON urs.user_id = u.id
        WHERE DATEDIFF(CURDATE(), a.published_time) <= {self.DAYS_FOR_REPORT}
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
