import json


class ContextIdentifier:
    def __init__(
        self,
        context_type: str,
        article_fragment_id=None,
        article_id=None,
        video_id=None,
        video_caption_id=None,
        example_sentence_id=None,
        level_adapted_article_text_id=None,
    ):
        self.context_type = context_type
        self.article_fragment_id = article_fragment_id
        self.article_id = article_id
        self.video_id = video_id
        self.video_caption_id = video_caption_id
        self.example_sentence_id = example_sentence_id
        self.level_adapted_article_text_id = level_adapted_article_text_id

    def __repr__(self):
        return f"<ContextIdentifier context_type={self.context_type}>"

    # Pre-rename spellings, still arriving from clients. The context identifier is
    # opaque to the app: the server hands it out with a feed payload and the client
    # posts the same blob back when a word is translated. An app holding a payload
    # built before the rename — a cached feed, a backgrounded tab, an older release
    # — will post the old keys, and dropping them would silently lose the anchor so
    # the bookmark could not be highlighted again. Safe to delete once no client can
    # still be holding a pre-rename payload.
    LEGACY_KEYS = {
        "level_adapted_article_text_id": "article_level_summary_id",
    }
    LEGACY_CONTEXT_TYPES = {
        "ArticleLevelSummary": "LevelAdaptedArticleSummary",
        "ArticleLevelTitle": "LevelAdaptedArticleTitle",
    }

    @classmethod
    def _get(cls, dictionary, key):
        value = dictionary.get(key, None)
        if value is None and key in cls.LEGACY_KEYS:
            return dictionary.get(cls.LEGACY_KEYS[key], None)
        return value

    @classmethod
    def from_dictionary(cls, dictionary):
        assert dictionary is not None
        assert "context_type" in dictionary, f"Context type must be provided"

        context_type = dictionary.get("context_type", None)
        context_type = cls.LEGACY_CONTEXT_TYPES.get(context_type, context_type)

        return ContextIdentifier(
            context_type,
            dictionary.get("article_fragment_id", None),
            dictionary.get("article_id", None),
            video_id=dictionary.get("video_id", None),
            video_caption_id=dictionary.get("video_caption_id", None),
            example_sentence_id=dictionary.get("example_sentence_id", None),
            level_adapted_article_text_id=cls._get(
                dictionary, "level_adapted_article_text_id"
            ),
        )

    @classmethod
    def from_json_string(cls, json_string):
        return cls.from_dictionary(json.loads(json_string))

    def as_dictionary(self):
        return {
            "context_type": self.context_type,
            "article_fragment_id": self.article_fragment_id,
            "article_id": self.article_id,
            "video_id": self.video_id,
            "video_caption_id": self.video_caption_id,
            "example_sentence_id": self.example_sentence_id,
            "level_adapted_article_text_id": self.level_adapted_article_text_id,
        }

    def create_context_mapping(self, session, bookmark, commit=False):
        """
        Create the appropriate context mapping for this context identifier.
        Returns the created mapping object or None if no mapping was created.
        """
        from zeeguu.core.model.context_type import ContextType
        
        # Get the appropriate context mapping table
        context_specific_table = ContextType.get_table_corresponding_to_type(self.context_type)
        if not context_specific_table:
            return None

        mapped_context = None

        match self.context_type:
            case ContextType.ARTICLE_FRAGMENT:
                if self.article_fragment_id is None:
                    return None
                from zeeguu.core.model.article_fragment import ArticleFragment
                fragment = ArticleFragment.find_by_id(self.article_fragment_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, fragment, commit=commit
                )
                session.add(mapped_context)
                
            case ContextType.ARTICLE_TITLE:
                if self.article_id is None:
                    return None
                from zeeguu.core.model.article import Article
                article = Article.find_by_id(self.article_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, article, commit=commit
                )
                session.add(mapped_context)
                
            case ContextType.ARTICLE_SUMMARY:
                if self.article_id is None:
                    return None
                from zeeguu.core.model.article import Article
                article = Article.find_by_id(self.article_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, article, commit=commit
                )
                session.add(mapped_context)

            # Both level cases resolve the same LevelAdaptedArticleText row; they
            # differ only in which join table context_specific_table resolved to,
            # so the level's title and its summary keep separate bookmark sets.
            case ContextType.LEVEL_ADAPTED_ARTICLE_SUMMARY | ContextType.LEVEL_ADAPTED_ARTICLE_TITLE:
                if self.level_adapted_article_text_id is None:
                    return None
                from zeeguu.core.model.level_adapted_article_text import LevelAdaptedArticleText
                level_summary = LevelAdaptedArticleText.find_by_id(
                    self.level_adapted_article_text_id
                )
                if level_summary is None:
                    return None
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, level_summary, commit=commit
                )
                session.add(mapped_context)

            case ContextType.VIDEO_TITLE:
                if self.video_id is None:
                    return None
                from zeeguu.core.model.video import Video
                video = Video.find_by_id(self.video_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, video, commit=commit
                )
                session.add(mapped_context)
                
            case ContextType.VIDEO_CAPTION:
                if self.video_caption_id is None:
                    return None
                from zeeguu.core.model.caption import Caption
                video_caption = Caption.find_by_id(self.video_caption_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, video_caption, commit=commit
                )
                session.add(mapped_context)
                
            case ContextType.EXAMPLE_SENTENCE:
                if self.example_sentence_id is None:
                    return None
                from zeeguu.core.model.example_sentence import ExampleSentence
                example_sentence = ExampleSentence.find_by_id(self.example_sentence_id)
                mapped_context = context_specific_table.find_or_create(
                    session, bookmark, example_sentence, commit=commit
                )
                session.add(mapped_context)
                
            case _:
                print(f"## No mapping handler for context type: {self.context_type}")

        return mapped_context