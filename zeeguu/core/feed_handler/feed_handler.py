class FeedHandler:
    def __init__(self, url: str, feed_type: int):
        self.url = url
        self.feed_type = feed_type
        self.title = ""
        self.description = ""
        self.image_url_string = ""

    def extract_feed_metadata() -> None:
        """
        Performs the logic to fill the properties of the
        object. These are accessed from the other classes.
        """
        NotImplementedError

    def get_feed_articles(self) -> list[dict]:
        """
        Returns a list[dictionary] containing the following fields:
            title:str, the title of the article
            url:str, the url to the article
            content:str, the content of the article
            summary:str, the summary of the article if available
            published:str, the date of the article as string
            published_datetime:datetime, date time of the article
        """
        NotImplementedError
