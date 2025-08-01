import flask
from flask import request

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.example_generation.llm_service import get_llm_service
from zeeguu.core.model import UserWord, User, Bookmark
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.logging import log
from . import api, db_session


@api.route("/alternative_sentences/<user_word_id>", methods=["GET"])
@cross_domain
@requires_session
def alternative_sentences(user_word_id):
    """
    Generate alternative example sentences for a user_word using an LLM.

    Returns 3 example sentences at the appropriate CEFR level without saving them.

    :param user_word_id: ID of the UserWord to generate examples for
    :return: JSON array with generated examples
    """
    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return json_result({"error": "UserWord not found or unauthorized"}, status=404)

    # Get the word and translation
    origin_word = user_word.meaning.origin.content
    translation = user_word.meaning.translation.content
    origin_lang = user_word.meaning.origin.language.code
    translation_lang = user_word.meaning.translation.language.code

    # Determine CEFR level (could be from user preferences, or calculated)
    # For now, let's assume it's passed as a query parameter
    cefr_level = request.args.get("cefr_level", "B1")

    try:
        # Get the LLM service
        llm_service = get_llm_service()

        # Generate examples
        examples = llm_service.generate_examples(
            word=origin_word,
            translation=translation,
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level=cefr_level,
        )

        # Extract model and version from first example (they're all the same)
        llm_model = examples[0]["llm_model"] if examples else "unknown"
        prompt_version = examples[0]["prompt_version"] if examples else "v1"

        # Find or create AIGenerator record
        ai_generator = AIGenerator.find_or_create(
            db_session,
            llm_model,
            prompt_version,
            description="Example generation for language learning",
        )

        return json_result(
            {
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": examples,
                "ai_generator_id": ai_generator.id,
                "llm_model": llm_model,
                "prompt_version": prompt_version,
            }
        )

    except Exception as e:
        log(f"Error generating examples for user_word {user_word_id}: {e}")

        # Fallback to simple templates if LLM fails
        fallback_examples = [
            {
                "sentence": f"Jeg har {origin_word} meget arbejde.",
                "translation": f"I have {translation} a lot of work.",
                "cefr_level": cefr_level,
            },
            {
                "sentence": f"Hun er {origin_word} her.",
                "translation": f"She is {translation} here.",
                "cefr_level": cefr_level,
            },
            {
                "sentence": f"Vi skal {origin_word} mødes.",
                "translation": f"We should {translation} meet.",
                "cefr_level": cefr_level,
            },
        ]

        # Create fallback AIGenerator
        fallback_generator = AIGenerator.find_or_create(
            db_session, "fallback", "v1", description="Fallback template generator"
        )

        return json_result(
            {
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": fallback_examples,
                "ai_generator_id": fallback_generator.id,
                "llm_model": "fallback",
                "prompt_version": "fallback",
                "error": "Failed to generate examples using LLM, using fallback templates",
            }
        )


@api.route("/save_sentence/<user_word_id>", methods=["POST"])
@cross_domain
@requires_session
def save_sentence(user_word_id):
    """
    Save a chosen generated example as a new bookmark and update the user_word's
    preferred_bookmark to point to it.

    Expected request JSON:
    {
        "sentence": "The example sentence",
        "translation": "The translation of the sentence",
        "cefr_level": "A1|A2|B1|B2|C1|C2",
        "ai_generator_id": 123
    }

    :param user_word_id: ID of the UserWord
    :return: JSON with the new bookmark_id
    """
    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return json_result({"error": "UserWord not found or unauthorized"}, status=404)

    # Get the chosen example from request
    example_sentence = request.json["sentence"]
    example_translation = request.json.get("translation")
    cefr_level = request.json.get("cefr_level", "A2")
    ai_generator_id = request.json.get("ai_generator_id")

    if not example_translation:
        return json_result({"error": "Translation field is required"}, status=400)

    # Find the target word position in the sentence
    target_word = user_word.meaning.origin.content.lower()
    sentence_words = example_sentence.lower().split()

    # Find word position (sentence_i=0 since it's a single sentence, token_i is word position)
    token_i = None
    for i, word in enumerate(sentence_words):
        # Handle punctuation by cleaning the word
        clean_word = "".join(c for c in word if c.isalnum())
        if clean_word == target_word:
            token_i = i
            break

    # If exact match not found, try partial match
    if token_i is None:
        for i, word in enumerate(sentence_words):
            clean_word = "".join(c for c in word if c.isalnum())
            if target_word in clean_word or clean_word in target_word:
                token_i = i
                break

    # Default to first word if still not found
    if token_i is None:
        token_i = 0

    # Create the ExampleSentence first
    ai_generator = None
    if ai_generator_id:
        ai_generator = AIGenerator.query.get(ai_generator_id)

    example_sentence_obj = ExampleSentence.create_ai_generated(
        db_session,
        sentence=example_sentence,
        language=user_word.meaning.origin.language,
        meaning=user_word.meaning,
        ai_generator=ai_generator,
        translation=example_translation,
        cefr_level=cefr_level,
        commit=False,
    )

    sentence_i = 0  # Single sentence
    c_sentence_i = 0  # Context sentence index
    c_token_i = token_i  # Context token index

    # Create the context identifier with the example sentence ID
    context_identifier = ContextIdentifier(
        context_type=ContextType.EXAMPLE_SENTENCE,
        example_sentence_id=example_sentence_obj.id,
    )

    # Create a new bookmark with the generated example
    bookmark = Bookmark.find_or_create(
        db_session,
        user,
        user_word.meaning.origin.content,
        user_word.meaning.origin.language.code,
        user_word.meaning.translation.content,
        user_word.meaning.translation.language.code,
        example_sentence,
        None,  # article_id
        None,  # source_id
        sentence_i=sentence_i,
        token_i=token_i,
        total_tokens=1,  # Single word bookmark
        c_sentence_i=c_sentence_i,
        c_token_i=c_token_i,
        context_identifier=context_identifier,
    )

    # Update the user_word's preferred_bookmark
    user_word.preferred_bookmark = bookmark
    db_session.add(user_word)
    db_session.commit()

    # Refresh the user_word from database to get updated preferred_bookmark
    db_session.refresh(user_word)

    return json_result(
        {
            "bookmark_id": bookmark.id,
            "user_word_id": user_word_id,
            "message": "Generated example saved successfully",
            "updated_bookmark": bookmark.as_dictionary(with_context=True, with_context_tokenized=True),
            "bookmark_context_id": bookmark.context.id,
        }
    )
