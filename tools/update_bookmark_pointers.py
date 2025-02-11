import zeeguu
from zeeguu.core.model import Bookmark, Article
from zeeguu.api.app import create_app
from tqdm import tqdm
from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL
from time import time

CHECKPOINT_COMMIT_AFTER_ROWS = 10000


def get_text_list(l):
    return [t.text for t in l]


def update_bookmark_pointer(bookmark):
    # Tokenized text returns paragraph, sents, token
    # Since we know there is not multiple paragraphs, we take the first
    text = bookmark.text
    if text:
        if not text.article_id:
            # There is no article id.
            return False
    article = Article.find_by_id(text.article_id)
    if not article:
        return False
    tokenizer = get_tokenizer(article.language, TOKENIZER_MODEL)
    tokenize_article_content = tokenizer.tokenize_text(article.content, False)
    tokenized_context = tokenizer.tokenize_text(text.content, False)
    tokenized_bookmark = tokenizer.tokenize_text(bookmark.origin.word, False)

    text_article_content = get_text_list(tokenize_article_content)
    text_context = get_text_list(tokenized_context)
    context_len = len(text_context)
    # Find the first token of the context
    context_found = False
    context_current_start = None
    has_right_ellipsis = False
    for article_text_i in range(len(tokenize_article_content) - len(text_context) - 1):
        if (
            text_article_content[article_text_i : article_text_i + context_len]
            == text_context
        ):
            context_found = True
            context_current_start = tokenize_article_content[article_text_i]

        if context_found:
            # Unless, we are not at the end of a text / sentence
            index_token_after_context = article_text_i + context_len
            if (
                index_token_after_context < len(tokenize_article_content)
                and not tokenize_article_content[
                    index_token_after_context
                ].is_sent_start
            ):
                has_right_ellipsis = True
            break
    if not context_found:
        return False
    text.paragraph_i = context_current_start.par_i
    text.sentence_i = context_current_start.sent_i
    text.token_i = context_current_start.token_i
    text.in_content = True
    text.left_ellipsis = context_current_start.token_i != 0
    text.right_ellipsis = has_right_ellipsis
    try:
        first_token_ocurrence = next(
            filter(lambda t: t.text == tokenized_bookmark[0].text, tokenized_context)
        )
        bookmark.sentence_i = first_token_ocurrence.sent_i
        bookmark.token_i = first_token_ocurrence.token_i
        bookmark.total_tokens = len(tokenized_bookmark)
    except StopIteration:
        # print(tokenized_text)
        # print(tokenized_bookmark)
        print(f"Couldn't find bookmark {bookmark.id} in text {text.id}.")
        print(f"Bookmark is substring of text: {bookmark.origin.word in text.content}")
        print(
            "------------------------------------------------------------------------"
        )
        return False
    except Exception as e:
        print(e)
        print(tokenized_context)
        print(tokenized_bookmark)
        print(f"Couldn't find bookmark {bookmark.id} in text {text.id}.")
        print(
            f"Bookmark ({bookmark.origin.word}) is substring of text: {bookmark.origin.word in text.content}"
        )
        print(
            "------------------------------------------------------------------------"
        )
    db_session.add(text)
    db_session.add(bookmark)
    return True


def bookmark_has_coordinates(b):
    return (
        b.sentence_i is not None
        and b.token_i is not None
        and b.total_tokens is not None
    )


app = create_app()
app.app_context().push()

db_session = zeeguu.core.model.db.session


start = time()
all_bookmarks = db_session.query(Bookmark).all()
counter_total_updated_bookmarks = 0
skipped_bookmarks = 0
for i, b in tqdm(enumerate(all_bookmarks[::-1]), total=len(all_bookmarks)):

    if bookmark_has_coordinates(b):
        skipped_bookmarks += 1
    else:
        if update_bookmark_pointer(b):
            counter_total_updated_bookmarks += 1
    if (i + 1) % CHECKPOINT_COMMIT_AFTER_ROWS == 0:
        print(f"Completed {CHECKPOINT_COMMIT_AFTER_ROWS}, saving progress...")
        print(f"Added coordinates to {counter_total_updated_bookmarks}  bookmarks.")
        print(
            "Skipped bookmarks due to already having coordinates: ", skipped_bookmarks
        )
        print(
            "Number of failed updates: ",
            i + 1 - skipped_bookmarks - counter_total_updated_bookmarks,
        )
        db_session.commit()


end = time() - start
print(
    f"Total updated bookmarks: {counter_total_updated_bookmarks} out of {len(all_bookmarks)}, time taken: {end:.2f}"
)
print(f"Total bookmarks that had coordinates: ", skipped_bookmarks)
