import pandas as pd
import matplotlib.pyplot as plt
from zeeguu.core.model.article_topic_map import TopicOriginType
from zeeguu.operations.crawler.crawl_report import CrawlReport
import seaborn as sns
from data_extractor import DataExtractor
from sqlalchemy import create_engine
import datetime
import os
import argparse
import pathlib
from collections import Counter
from tqdm import tqdm
from nltk.tokenize import sent_tokenize

FOLDER_FOR_REPORT_OUTPUT = os.environ.get(
    "FOLDER_FOR_REPORT_OUTPUT",
    os.path.join(pathlib.Path(__file__).parent.resolve(), "reports"),
)


def set_legend_to_right_side(ax):
    # https://stackoverflow.com/questions/4700614/how-to-put-the-legend-outside-the-plot
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
    ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))


def get_color_palette(n_items):
    if n_items <= 10:
        return sns.color_palette("tab10")
    else:
        return sns.color_palette("tab20")


def identify_repeating_patterns(article_df, sents_filtered_set: set):
    def normalize_sent(text: str):
        return text.lower().strip()

    def sent_count(text: str):
        return Counter(
            [
                normalize_sent(sent)
                for paragraph in text.split("\n\n")
                for sent in sent_tokenize(paragraph)
                if len(sent.strip()) > 10
            ]
        )

    def get_total_sent_counts(text_list: list[str]):
        total_counts = Counter()
        for text in tqdm(text_list, total=len(text_list)):
            total_counts += sent_count(text)
        return total_counts

    print("Evaluating new repeating patterns...")
    total_counts = get_total_sent_counts(article_df.content)
    sents_occur_more_than_10 = [
        [sent, count]
        for sent, count in total_counts.items()
        if count > 10 and sent not in sents_filtered_set
    ]
    return pd.DataFrame(sents_occur_more_than_10, columns=["Sent", "Count"])


def save_fig_params(filename):
    if not os.path.exists(FOLDER_FOR_REPORT_OUTPUT):
        os.mkdir(FOLDER_FOR_REPORT_OUTPUT)
    img_folder = os.path.join(FOLDER_FOR_REPORT_OUTPUT, "img")
    if not os.path.exists(img_folder):
        os.mkdir(img_folder)
    path_to_img = os.path.join(img_folder, filename)
    rel_path = os.path.join("img", filename)
    plt.savefig(path_to_img, bbox_inches="tight")
    plt.clf()
    return rel_path


def get_new_repeating_sents_table(pd_repeating_sents):
    return generate_html_table(pd_repeating_sents.sort_values("Count", ascending=False))


def get_url_keywords_table(pd_url_keywords_count):
    return generate_html_table(
        pd_url_keywords_count.sort_values("count", ascending=False)
    )


def get_rejected_sentences_table(total_deleted_sents):
    total_deleted_sents["Total"] = sum(total_deleted_sents.values())
    pd_deleted_sents = pd.DataFrame.from_dict(
        total_deleted_sents, orient="index"
    ).reset_index()
    pd_deleted_sents.columns = ["Reason", "Count"]
    return generate_html_table(pd_deleted_sents.sort_values("Count", ascending=False))


def get_total_reject_article_reason_table(total_rejected_article_reasons):
    total_rejected_article_reasons["Total"] = sum(
        total_rejected_article_reasons.values()
    )
    pd_quality_errors = pd.DataFrame.from_dict(
        total_rejected_article_reasons, orient="index"
    ).reset_index()
    pd_quality_errors.columns = ["Reason", "Count"]
    return generate_html_table(pd_quality_errors.sort_values("Count", ascending=True))


def generate_feed_count_plots(feed_df, lang):
    filename = f"feed_downloaded_articles_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    if feed_df[feed_df["Language"] == lang].Count.sum() == 0:
        return ""
    plt.figure(lang)
    sns.barplot(
        x="Feed Name",
        y="Count",
        hue="Feed Name",
        data=feed_df[feed_df["Language"] == lang],
    )
    plt.title(lang)
    plt.xticks(rotation=35, ha="right")
    return save_fig_params(filename)


def generate_bookmarks_by_language_plot(bookmark_df):
    filename = f"bookmarks_plot_{date_str}_d{DAYS_FOR_REPORT}.png"
    bookmark_plot = (
        bookmark_df.groupby(["Language", "Has Exercised"])[["user_id"]]
        .count()
        .reset_index()
        .rename(columns={"user_id": "Count"})
    )
    sns.barplot(data=bookmark_plot, x="Language", y="Count", hue="Has Exercised")
    plt.title("Total Bookmarks by Language")
    plt.xticks(rotation=35, ha="right")
    return save_fig_params(filename)


def generate_topic_by_feed_plot(article_topic_df, lang):
    # If I want to make topics consistant
    # https://stackoverflow.com/questions/39000115/how-can-i-set-the-colors-per-value-when-coloring-plots-by-a-dataframe-column
    filename = f"topics_per_feed_lang_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    topic_monitor = (
        article_topic_df.groupby(["Language", "Feed Name"])
        .Topic.value_counts()
        .reset_index()
    )
    total_sources = len(
        topic_monitor[topic_monitor["Language"] == lang]["Feed Name"].unique()
    )

    ax = plt.subplot(111)
    sns.barplot(
        x="Topic",
        y="count",
        hue="Feed Name",
        data=topic_monitor[topic_monitor["Language"] == lang],
        palette=get_color_palette(total_sources),
    )
    set_legend_to_right_side(ax)
    plt.title(f"{lang} - Topic Report")
    plt.xlabel("Topic")
    plt.xticks(rotation=35, ha="right")
    return save_fig_params(filename)


def generate_topic_by_feed_plot(article_topic_df, lang):
    # If I want to make topics consistant
    # https://stackoverflow.com/questions/39000115/how-can-i-set-the-colors-per-value-when-coloring-plots-by-a-dataframe-column
    filename = f"topics_per_feed_lang_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    topic_monitor = (
        article_topic_df.groupby(["Language", "Feed Name"])
        .Topic.value_counts()
        .reset_index()
    )
    total_sources = len(
        topic_monitor[topic_monitor["Language"] == lang]["Feed Name"].unique()
    )

    ax = plt.subplot(111)
    sns.barplot(
        x="Topic",
        y="count",
        hue="Feed Name",
        data=topic_monitor[topic_monitor["Language"] == lang],
        palette=get_color_palette(total_sources),
    )
    set_legend_to_right_side(ax)
    plt.title(f"{lang} - New Topic Report")
    plt.xlabel("Topic")
    plt.xticks(rotation=35, ha="right")
    return save_fig_params(filename)


def generate_topic_coverage_plot(article_df, article_with_topics_df):
    filename = f"topic_coverage_plot_{date_str}_d{DAYS_FOR_REPORT}.png"
    article_df["Has Topic"] = "No Topic"
    article_df.loc[
        article_df.id.isin(
            article_with_topics_df.loc[
                article_with_topics_df.origin_type == TopicOriginType.HARDSET, "id"
            ]
        ),
        "Has Topic",
    ] = "Hardset Topic"
    article_df.loc[
        article_df.id.isin(
            article_with_topics_df.loc[
                article_with_topics_df.origin_type == TopicOriginType.URL_PARSED, "id"
            ]
        ),
        "Has Topic",
    ] = "Url Keyword Topic"
    article_df.loc[
        article_df.id.isin(
            article_with_topics_df.loc[
                article_with_topics_df.origin_type == TopicOriginType.INFERRED, "id"
            ]
        ),
        "Has Topic",
    ] = "Inferred Topic"
    articles_with_topics = (
        article_df.groupby("Language")["Has Topic"]
        .value_counts(normalize=True)
        .reset_index()
    )
    color_pallete = sns.color_palette("vlag", n_colors=15)
    sns.barplot(
        x="Language",
        y="proportion",
        hue="Has Topic",
        data=articles_with_topics,
        palette={
            "Url Keyword Topic": color_pallete[0],
            "Hardset Topic": color_pallete[1],
            "Inferred Topic": color_pallete[3],
            "No Topic": color_pallete[len(color_pallete) - 1],
        },
    )
    plt.title("Proportion of Articles with Topics")
    plt.xticks(rotation=35, ha="right")
    return save_fig_params(filename)


def generate_total_article_per_language(article_df):
    filename = f"total_articles_downloaded_{date_str}_d{DAYS_FOR_REPORT}.png"
    data = article_df["Language"].value_counts().reset_index()
    sns.barplot(
        x="Language",
        y="count",
        hue="Language",
        data=data,
        palette=get_color_palette(len(data["Language"].unique())),
    )
    plt.title("New Articles Downloaded")
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Total Articles")
    return save_fig_params(filename)


def generate_histogram(article_df, column, bins=20, remove_outliers=False):
    filename = (
        f"hist_{column}_removed_out_{date_str}_d{DAYS_FOR_REPORT}.png"
        if remove_outliers
        else f"hist_{column}_{date_str}_d{DAYS_FOR_REPORT}.png"
    )
    if remove_outliers:
        article_df[article_df[column] < article_df[column].quantile(0.99)].groupby(
            "Language"
        )[column].plot.hist(alpha=0.5, bins=bins)
    else:
        article_df.groupby("Language")[column].plot.hist(alpha=0.5, bins=bins)
    plt.title(f"{column} Distribution")
    plt.legend()
    return save_fig_params(filename)


def generate_user_reading_time(user_reading_time_df, lang=""):
    filename = (
        f"user_reading_time_plot_all_lang_{date_str}_d{DAYS_FOR_REPORT}.png"
        if lang == ""
        else f"user_reading_time_plot_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    )
    plot_total_reading_time = (
        user_reading_time_df.groupby(["Language", "Feed Name"])
        .total_reading_time.sum()
        .reset_index()
        .sort_values("Feed Name")
    )
    if lang == "":
        sns.barplot(
            x="Language",
            y="total_reading_time",
            hue="Language",
            data=plot_total_reading_time,
        )
        plt.title("Total Reading Time by users per Language")
    else:
        sns.barplot(
            x="Feed Name",
            y="total_reading_time",
            hue="Feed Name",
            data=plot_total_reading_time[plot_total_reading_time["Language"] == lang],
        )
        plt.title(f"{lang} - Total Reading time by users per Feed")
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Total Reading time (mins)")
    return save_fig_params(filename)


def generate_unique_articles_read_plot(user_reading_time_df, lang=""):
    filename = (
        f"user_unique_articles_read_plot_all_lang_{date_str}_d{DAYS_FOR_REPORT}.png"
        if lang == ""
        else f"user_unique_articles_read_plot_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    )

    if lang == "":
        plot_unique_articles_read = (
            user_reading_time_df.Language.value_counts().reset_index()
        )
        sns.barplot(
            x="Language",
            y="count",
            hue="Language",
            data=plot_unique_articles_read,
        )
        plt.title("Total Unique Articles Opened by users per Language")
    else:
        plot_unique_articles_read = (
            user_reading_time_df.groupby(["Language"])["Feed Name"]
            .value_counts()
            .reset_index()
            .sort_values("Feed Name")
        )
        sns.barplot(
            x="Feed Name",
            y="count",
            hue="Feed Name",
            data=plot_unique_articles_read[
                plot_unique_articles_read["Language"] == lang
            ],
        )
        plt.title(f"{lang} - Total Unique Articles Opened by users per Feed")
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Total Opened  Article Count")
    return save_fig_params(filename)


def generate_topic_reading_time(topic_reading_time_df, lang=""):
    filename = (
        f"topic_reading_time_plot_all_lang_{date_str}_d{DAYS_FOR_REPORT}.png"
        if lang == ""
        else f"topic_reading_time_plot_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    )
    plot_total_reading_time = (
        topic_reading_time_df.groupby(["Language", "Topic"])
        .total_reading_time.sum()
        .reset_index()
    )
    if lang == "":
        ax = plt.subplot(111)
        sns.barplot(
            x="Language",
            y="total_reading_time",
            hue="Topic",
            data=plot_total_reading_time,
            palette=get_color_palette(len(plot_total_reading_time["Topic"].unique())),
        )
        set_legend_to_right_side(ax)
        plt.title("Total Reading Time by New Topic per Language")
    else:
        sns.barplot(
            x="Topic",
            y="total_reading_time",
            hue="Topic",
            data=plot_total_reading_time[plot_total_reading_time["Language"] == lang],
        )
        plt.title(f"{lang} - Total Reading time by New Topic")
    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Total Reading time (mins)")
    return save_fig_params(filename)


def generate_exercise_activity(exercise_activity_df, lang=""):
    filename = (
        f"exercise_activity_plot_all_lang_{date_str}_d{DAYS_FOR_REPORT}.png"
        if lang == ""
        else f"exercise_activity_plot_{lang}_{date_str}_d{DAYS_FOR_REPORT}.png"
    )
    ax = plt.subplot(111)
    if lang == "":
        sns.barplot(
            x="Source",
            y="total_exercises",
            hue="Language",
            data=exercise_activity_df,
        )
        plt.title("Total Exercises Performed by Language")
        set_legend_to_right_side(ax)
    else:
        sns.barplot(
            x="Source",
            y="total_exercises",
            hue="Source",
            data=exercise_activity_df[exercise_activity_df["Language"] == lang],
        )
        plt.title(f"{lang} - Total Exercses Performed by Type")

    plt.xticks(rotation=35, ha="right")
    plt.ylabel("Total Exercises Count")
    return save_fig_params(filename)


def print_descriptive_stats(df, title, precision=2):
    print(f"############## {title} Descriptive Stats ##############")
    print(df.describe().round(precision).to_string())


def generate_html_table(df, round_precision=2):
    return (
        df.round(round_precision)
        .to_html(index=False)
        .replace('class="dataframe"', 'class="pure-table"')
    )


def generate_active_users_table(active_user_read_ex_pd, bookmark_pd):
    reading_time_ex_time = (
        active_user_read_ex_pd.groupby("Language")[
            ["total_exercise_time", "total_reading_time"]
        ]
        .sum()
        .reset_index()
    )
    reading_time_ex_time["Count"] = (
        active_user_read_ex_pd.groupby("Language")[["user_id"]]
        .count()
        .reset_index()["user_id"]
    )

    bookmark_count = (
        bookmark_pd.groupby(["Language"])["user_id"]
        .describe()["count"]
        .reset_index()
        .rename(columns={"count": "Total Bookmarks"})
    )
    bookmark_review_proportion = (
        bookmark_pd.groupby(["Language"])["Has Exercised"]
        .value_counts(normalize=True)
        .reset_index()
        .rename(columns={"proportion": "Bookmarks % Reviewed"})
    )
    bookmark_review_proportion = bookmark_review_proportion[
        bookmark_review_proportion["Has Exercised"] == "Yes"
    ]
    if len(bookmark_count) > 0:
        reading_time_ex_time = reading_time_ex_time.merge(
            bookmark_review_proportion, on="Language", how="outer"
        )
        reading_time_ex_time = reading_time_ex_time.merge(
            bookmark_count, on="Language", how="outer"
        )
        reading_time_ex_time.loc[
            reading_time_ex_time["Bookmarks % Reviewed"].isna(), "Bookmarks % Reviewed"
        ] = 0
    else:
        reading_time_ex_time["Bookmarks % Reviewed"] = 0
        reading_time_ex_time["Total Bookmarks"] = 0

    return generate_html_table(
        reading_time_ex_time[
            [
                "Language",
                "Count",
                "total_exercise_time",
                "total_reading_time",
                "Bookmarks % Reviewed",
                "Total Bookmarks",
            ]
        ]
    )


def generate_top_opened_articles(
    user_reading_time_df, data_extractor, feed_df, number_of_articles_to_report=5
):
    articles_by_user_interaction = (
        user_reading_time_df.groupby(["id"])
        .agg({"total_reading_time": "mean", "user_id": "count"})
        .reset_index()
    )
    read_articles = data_extractor.get_article_df_with_ids(
        feed_df, articles_by_user_interaction.id.values
    )
    articles_by_user_interaction = articles_by_user_interaction.merge(
        read_articles[["id", "title", "Feed Name", "Language"]], on="id"
    )[["Language", "Feed Name", "id", "title", "user_id", "total_reading_time"]]
    articles_by_user_interaction = articles_by_user_interaction.rename(
        columns={
            "id": "Article id",
            "title": "Article Title",
            "user_id": "Users Count",
            "total_reading_time": "User Avg. Reading Time",
        }
    )
    articles_by_user_interaction = articles_by_user_interaction.sort_values(
        ["Users Count", "User Avg. Reading Time"], ascending=False
    )
    return generate_html_table(
        articles_by_user_interaction.head(number_of_articles_to_report)
    )


def generate_html_page():
    data_extractor = DataExtractor(db_connection, DAYS_FOR_REPORT)

    feed_df = data_extractor.get_feed_df()
    article_df = data_extractor.get_article_df(feed_df)
    article_topics_df = data_extractor.get_article_topics_df(feed_df)
    language_df = data_extractor.get_language_df()
    bookmark_df = data_extractor.get_bookmark_df()
    data_extractor.add_stats_to_feed(feed_df, article_df)
    user_reading_time_df = data_extractor.get_user_reading_activity(
        language_df, feed_df
    )
    user_exercise_time_df = data_extractor.get_user_exercise_activity()
    combined_user_activity_df = (
        data_extractor.get_combined_user_reading_exercise_activity(
            user_exercise_time_df, user_reading_time_df
        )
    )
    topic_reading_time_df = data_extractor.get_topic_reading_time()
    total_unique_articles_opened_by_users = len(
        article_df[article_df.id.isin(user_reading_time_df.id)]
    )
    total_unique_articles_opened_by_users = (
        user_reading_time_df.Language.value_counts().reset_index()["count"].sum()
    )
    exercise_activity_df = data_extractor.get_exercise_type_activity()
    top_subscribed_searches = data_extractor.get_top_search_subscriptions()
    top_filtered_searches = data_extractor.get_top_search_filters()
    newly_added_search_subscriptions = data_extractor.get_added_search_subscriptions()
    pd_url_keywords = data_extractor.get_url_keyword_counts()
    pd_feed_innactivity_time = data_extractor.get_days_since_last_crawl()
    crawl_report = CrawlReport()
    crawl_report.load_crawl_report_data(DAYS_FOR_REPORT)
    total_days_from_crawl_report = crawl_report.get_days_from_crawl_report_date()
    print("############ Report date: ", crawl_report.crawl_report_date)
    total_removed_sents = crawl_report.get_total_removed_sents_counts()
    if DAYS_FOR_REPORT <= 7:
        pd_new_repeated_sents = identify_repeating_patterns(
            article_df, set(total_removed_sents.keys())
        )
    warning_crawl_range = (
        ""
        if total_days_from_crawl_report == DAYS_FOR_REPORT
        else f"<b>WARNING!</b> This date only contains values from the last '{total_days_from_crawl_report}' day(s)."
    )
    ACTIVE_USER_ACTIVITY_TIME_MIN = 1
    articles_with_topic_count = len(article_topics_df.id.unique())
    active_users = combined_user_activity_df[
        (
            combined_user_activity_df["total_reading_time"]
            > ACTIVE_USER_ACTIVITY_TIME_MIN
        )
        | (
            combined_user_activity_df["total_exercise_time"]
            > ACTIVE_USER_ACTIVITY_TIME_MIN
        )
    ]
    total_active_users = len(active_users)
    lang_report = ""
    for lang in article_df["Language"].unique():
        lang_report += f"""
          <h2 id='{lang}'>{lang}</h2>
          <h3>Articles Downloaded</h3>
          <img src="{generate_topic_by_feed_plot(article_topics_df, lang)}" />
          <img src="{generate_feed_count_plots(feed_df, lang)}" />
          <h3>User Activity</h3>
          """
        if lang in active_users["Language"].values:
            lang_report += f"""
            <p><b>Total Active users</b>: {len(active_users[active_users["Language"] == lang])}</p>
            <img src="{generate_topic_reading_time(topic_reading_time_df, lang)}" />
            <img src="{generate_user_reading_time(user_reading_time_df, lang)}" />
            <img src="{generate_unique_articles_read_plot(user_reading_time_df, lang)}" />
            <img src="{generate_exercise_activity(exercise_activity_df, lang)}" />
            <hr>
            """
        else:
            lang_report += """
            <p><b>No active users in this language</b></p>
            <hr>
            """
    lang_links = "<ul>"

    for lang in article_df["Language"].unique():
        lang_links += f"""
            <li><a href="#{lang}">{lang}</a> </li>
          """
    lang_links += "</ul>"
    title = (
        f"""Week Report Nr {CURRENT_WEEK_N}"""
        if DAYS_FOR_REPORT == 7
        else f"Last {DAYS_FOR_REPORT} days Report"
    )
    result = f"""
        <head>
            <meta charset="utf-8">
            <link
                rel="stylesheet"
                href="https://cdn.jsdelivr.net/npm/purecss@3.0.0/build/pure-min.css"
                integrity="sha384-X38yfunGUhNzHpBaEBsWLO+A0HDYOQi8ufWDkZ0k9e0eXz/tH3II7uKZ9msv++Ls"
                crossorigin="anonymous"
            />
        </head>
        <body style="margin-left: 2em">
            <h1>{title}</h1>
            <p>Generated at: {datetime.datetime.now(tz=datetime.timezone.utc)} UTC<p>
            <hr />
                <p><b>Total Articles Crawled: </b> {len(article_df)}</p>
                <p><b>Total Unique Articles Opened: </b> {total_unique_articles_opened_by_users}
                <p><b>New Topic Coverage: </b> {((articles_with_topic_count / len(article_df)) * 100) if len(article_df) > 0 else 0:.2f}%</p>
                <img src="{generate_topic_coverage_plot(article_df, article_topics_df)}" />
                <img src="{generate_total_article_per_language(article_df)}" />
                <h2>Possible Innactive feeds: </h2>
                <p><a href="#inactive-feeds">Full table</a><p>
                {generate_html_table(pd_feed_innactivity_time.head(10))}
                <h2>Articles Rejected:</h2>
                <p>{warning_crawl_range}</p>
                {get_total_reject_article_reason_table(crawl_report.get_total_non_quality_counts())}
                <h2>Word Count:</h2>
                {generate_html_table(article_df.groupby("Language").word_count.describe().reset_index())}
                <h2>FK Difficulty:</h2>
                {generate_html_table(article_df.groupby("Language").fk_difficulty.describe().reset_index())}
                <h2>Top Subscribed Searches:</h2>
            """
    if len(newly_added_search_subscriptions) > 0:
        result += f"""
                <p><b>Newly added searches:</b> {"'" + "', '".join(newly_added_search_subscriptions) + "'"}</p>
                """
    result += f"""
        {generate_html_table(top_subscribed_searches.head(10))}
        <h2>Top Filtered Searches:</h2>
        {generate_html_table(top_filtered_searches.head(10))}
        <h2>Activity Report</h2>
        <p><b>Total Active Users:</b> {total_active_users}</p>
        """
    if total_active_users == 0:
        result += """<p><b>No active users in this period</b></p>
        <hr>"""
    else:
        result += f"""
        {generate_active_users_table(combined_user_activity_df, bookmark_df)}
        <br>
        <h3>Top Articles Read:</h3>
        {generate_top_opened_articles(user_reading_time_df, data_extractor, feed_df)}
        <img src="{generate_unique_articles_read_plot(user_reading_time_df)}" />
        <img src="{generate_exercise_activity(exercise_activity_df)}" />
        <img src="{generate_topic_reading_time(topic_reading_time_df)}" />
        <img src="{generate_bookmarks_by_language_plot(bookmark_df)}" />
        """
    result += f"""
            <p><a href="#removed-articles">Removed Sents Table</a><p>
            <p><a href="#new-url-keywords">New keywords without topics</a><p>
            <h1>Per Language Report:</h1>
            {lang_links}
            <hr />
            {lang_report}
            <hr />
            <h1>Newly identified repeating patterns:</h1>
            <p>Sentences that occur in more than 10 articles during this weeks crawl, and were not filtered.<p>
            {get_new_repeating_sents_table(pd_new_repeated_sents) if DAYS_FOR_REPORT <= 7 else "<p>Skipped due to long period.</p>"}
            <h1 id="removed-articles">Removed Article Sents:</h1>
            <p>{warning_crawl_range}</p>
            {get_rejected_sentences_table(total_removed_sents)}
        </body>
    """

    result += f"""
            <h1 id="new-url-keywords">Newly url keywords without topics:</h1>
            <p>URL Keywords that occur more than 100 times in articles and are not mapped to a topic. They are language unique.<p>
            {get_url_keywords_table(pd_url_keywords) if DAYS_FOR_REPORT <= 7 else "<p>Skipped due to long period.</p>"}
            <br />
            <h1 id="inactive-feeds">Feed activity:</h1>
            {generate_html_table(pd_feed_innactivity_time)}
        </body>
    """

    output_filepath = f"report_zeeguu_{date_str}_d{DAYS_FOR_REPORT}.html"
    with open(
        os.path.join(
            FOLDER_FOR_REPORT_OUTPUT,
            output_filepath,
        ),
        "w",
        encoding="UTF-8",
    ) as f:
        f.write(result)

    print(f"File written to '{output_filepath}'.")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser("generate_plots_report")
    parser.add_argument(
        "number_of_days",
        nargs="?",
        default=7,
        help="Number of days from the current date that will be cnsidered for the report.",
        type=int,
    )
    args = parser.parse_args()
    DAYS_FOR_REPORT = args.number_of_days
    print(
        f"## Reporting for the last {DAYS_FOR_REPORT} days, today is: {datetime.datetime.now()}"
    )
    print(
        "################################################################################"
    )
    from zeeguu.api.app import create_app

    app = create_app()
    sns.set_theme("paper", "whitegrid")
    cur_time = datetime.datetime.now()
    CURRENT_WEEK_N = max(cur_time.isocalendar()[1] - 1, 1)
    date_str = cur_time.strftime("%Y_%m_%d")

    DB_URI = app.config["SQLALCHEMY_DATABASE_URI"]
    # rcParams["figure.figsize"] = 10, 8
    db_connection = create_engine(
        DB_URI,
        pool_recycle=300,
        connect_args={"connect_timeout": 300, "read_timeout": 600},
    )
    generate_html_page()
