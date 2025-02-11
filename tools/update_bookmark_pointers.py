import zeeguu
from zeeguu.core.model import Bookmark, Article
from zeeguu.api.app import create_app
from tqdm import tqdm
from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL
from zeeguu.core.tokenization import Token
from time import time

CHECKPOINT_COMMIT_AFTER_ROWS = 1000
TEXTS_NOT_FOUND = 0
ALREADY_SEARCHED_TEXTS = set()


def strip_trainling_punctuation(s):
    return s.strip(Token.PUNCTUATION) if (len(s)) > 1 else s


def get_text_list(l, apply_string_stripping=False):
    return [
        strip_trainling_punctuation(t.text) if apply_string_stripping else t.text
        for t in l
    ]


def find_sublist_in_list(l1, l2):
    """
    Finds the first index in l1, which contains l2
    """
    for i in range(len(l1) - len(l2) + 1):
        if l1[i : i + len(l2)] == l2:
            return i
    return -1


def has_right_elipsis(context_start, tokenized_content):
    return (
        context_start < len(tokenized_content)
        and not tokenized_content[context_start].is_sent_start
    )


def update_bookmark_pointer(bookmark):
    global TEXTS_NOT_FOUND
    global ALREADY_SEARCHED_TEXTS
    # Tokenized text returns paragraph, sents, token
    # Since we know there is not multiple paragraphs, we take the first
    text = bookmark.text
    if text is None:
        print(f"B({bookmark.id}) doesn't have a text associated.")
        return False

    article = None
    if text.article_id:
        article = Article.find_by_id(text.article_id)

    tokenizer = get_tokenizer(bookmark.origin.language, TOKENIZER_MODEL)
    tokenized_context = tokenizer.tokenize_text(text.content, False)
    text_context = get_text_list(tokenized_context)
    if article and text.id not in ALREADY_SEARCHED_TEXTS:
        # So if we have an article, we try to find the context and anchor it.
        tokenized_article_content = tokenizer.tokenize_text(article.content, False)

        text_article_content = get_text_list(tokenized_article_content)

        context_len = len(text_context)
        context_found = False
        token_context_start = None

        # Find the first token of the context
        i_article_title_start = -1
        i_article_context_start = find_sublist_in_list(
            text_article_content, text_context
        )
        if i_article_context_start == -1:
            # We didn't find it, try in title:
            tokenized_article_title = tokenizer.tokenize_text(article.title, False)
            text_article_title = get_text_list(tokenized_article_title)
            i_article_title_start = find_sublist_in_list(
                text_article_title, text_context
            )
            text.in_content = False if i_article_title_start > -1 else None
        else:
            text.in_content = True

        context_found = i_article_context_start > -1 or i_article_title_start > -1
        if context_found:
            index_context_start = max(i_article_context_start, i_article_title_start)
            token_context_start = (
                tokenized_article_content[index_context_start]
                if text.in_content
                else tokenized_article_title[index_context_start]
            )
            index_token_after_context = index_context_start + context_len
            text.paragraph_i = token_context_start.par_i
            text.sentence_i = token_context_start.sent_i
            text.token_i = token_context_start.token_i
            text.left_ellipsis = token_context_start.token_i != 0
            text.right_ellipsis = (
                has_right_elipsis(index_token_after_context, tokenized_article_content)
                if text.in_content
                else has_right_elipsis(
                    index_token_after_context, tokenized_article_title
                )
            )
        else:
            print(f"Text {bookmark.text_id} was not found in article.")
            TEXTS_NOT_FOUND += 1
        db_session.add(text)
        ALREADY_SEARCHED_TEXTS.add(text.id)

    # We anchor the bookmark in the context, if we find it.
    first_token_i = -1
    is_bookmark_substring_of_context = bookmark.origin.word in text.content
    if is_bookmark_substring_of_context:
        tokenized_bookmark = tokenizer.tokenize_text(bookmark.origin.word, False)
        text_bookmark = get_text_list(tokenized_bookmark)
        first_tokenization = text_bookmark
        first_token_i = find_sublist_in_list(text_context, text_bookmark)
        if first_token_i == -1:
            # We didn't find it, we try with the punctuation stripped.
            text_bookmark = [strip_trainling_punctuation(t) for t in text_bookmark]
            second_tokenization = text_bookmark
            first_token_i = find_sublist_in_list(text_context, text_bookmark)
            if first_token_i == -1:
                # Some cases the tokenizer will not tokenize the last token correctly
                # Context: ['Sundhed', '17.', 'jul', '.']
                # Bookmark ('Sundhed 17'): ['Sundhed', '17'], because we trim puctuation at
                # end. In this case, we can try to find it in the context, if we also remove
                # trailing punctuation.
                first_token_i = find_sublist_in_list(
                    [strip_trainling_punctuation(t) for t in text_context],
                    text_bookmark,
                )
                if first_token_i == -1:
                    # The tokenizer doesn't garantee that the same substring in different
                    # contexts is the same, this attempts to emulate the old tokenizer.
                    # 1. ['cessez', 'le-feu', 'sera']
                    # 2. ['cessez', '-le-feu', 'sera']
                    # 3. (This code) ['cessez-le-feu', 'sera']
                    # ['Guerre', 'en', 'Ukraine', ':', 'Macron', 'assure', 'qu’un', 'cessez-le-feu', 'sera', 'demandé', 'à', 'la', 'Russie', 'durant', 'les', 'JO', 'de', 'Paris']
                    text_bookmark = strip_trainling_punctuation(
                        bookmark.origin.word
                    ).split()
                    first_token_i = find_sublist_in_list(text_context, text_bookmark)

    if first_token_i > -1:
        first_token_ocurrence = tokenized_context[first_token_i]
        bookmark.sentence_i = first_token_ocurrence.sent_i
        bookmark.token_i = first_token_ocurrence.token_i
        bookmark.total_tokens = len(text_bookmark)
        db_session.add(bookmark)
        return True
    else:
        if is_bookmark_substring_of_context:
            print("First tokenization: ")
            print(first_tokenization)
            print("Second Tokenization: ")
            print(second_tokenization)
            print("Final Tokenization: ")
            print(text_bookmark)
            print("Context tokenized: ")
            print(text_context)
        print(f"Couldn't find bookmark {bookmark.id} in text {text.id}.")
        print(
            f"Bookmark '{bookmark.origin.word}' is substring of context: {is_bookmark_substring_of_context}"
        )
        if not is_bookmark_substring_of_context:
            print("Context: ")
            print(text.content)
        print(
            "------------------------------------------------------------------------"
        )
        return False


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
for i, b in tqdm(
    enumerate(all_bookmarks[::-1]),
    total=len(all_bookmarks),
    bar_format="{l_bar}{bar:10}{r_bar}{bar:-10b}",
):

    if bookmark_has_coordinates(b):
        skipped_bookmarks += 1
    else:
        if update_bookmark_pointer(b):
            counter_total_updated_bookmarks += 1
    if (i + 1) % CHECKPOINT_COMMIT_AFTER_ROWS == 0:
        print(f"Completed {CHECKPOINT_COMMIT_AFTER_ROWS}, saving progress...")
        print(f"Added coordinates to {counter_total_updated_bookmarks}  bookmarks.")
        print(f"A total of {TEXTS_NOT_FOUND} texts were not found in articles.")
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
