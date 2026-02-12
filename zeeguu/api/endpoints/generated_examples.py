import json
import traceback

import flask
from flask import request, Response

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.llm_services import get_llm_service
from zeeguu.core.llm_services.llm_service import prepare_learning_card
from zeeguu.core.model import UserWord, User, Bookmark, Language, Meaning
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.bookmark_user_preference import UserWordExPreference
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.core.tokenization.word_position_finder import (
    find_first_occurrence,
    validate_single_occurrence,
)
from zeeguu.core.word_scheduling.basicSR.four_levels_per_word import FourLevelsPerWord
from zeeguu.logging import log
from . import api, db_session

# Constants
MAX_EXAMPLES_ALTERNATIVE = 5  # Max examples for alternative_sentences endpoint
MAX_EXAMPLES_GENERATE = 3     # Max examples for generate_examples endpoint
DEFAULT_CEFR_LEVEL = "B1"


@api.route("/alternative_sentences/<user_word_id>", methods=["GET"])
@cross_domain
@requires_session
def alternative_sentences(user_word_id):
    """
    Returns alternative example sentences for a user_word.

    Tries to serve pre-generated examples from the database.
    Falls back to real-time LLM generation if no pre-generated examples exist.

    :param user_word_id: ID of the UserWord to get examples for
    :return: JSON array with example sentences
    """
    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return json_result({"error": "UserWord not found or unauthorized"}, status=404)

    origin_word = user_word.meaning.origin.content
    translation = user_word.meaning.translation.content
    origin_lang = user_word.meaning.origin.language.code
    translation_lang = user_word.meaning.translation.language.code

    # Determine CEFR level
    cefr_level = request.args.get("cefr_level", DEFAULT_CEFR_LEVEL)

    # First, try to get pre-generated examples from database
    # Try exact CEFR level match first
    db_examples = (
        ExampleSentence.query.filter(
            ExampleSentence.meaning_id == user_word.meaning_id,
            ExampleSentence.cefr_level == cefr_level,
        )
        .limit(MAX_EXAMPLES_ALTERNATIVE)
        .all()
    )

    # If no exact match, try any CEFR level for this meaning
    if not db_examples:
        db_examples = (
            ExampleSentence.query.filter(
                ExampleSentence.meaning_id == user_word.meaning_id
            )
            .limit(MAX_EXAMPLES_ALTERNATIVE)
            .all()
        )

    if db_examples:
        # Format database examples
        examples = []
        ai_generator_id = None
        llm_model = "database"
        prompt_version = "pregenerated"

        for db_example in db_examples:
            example_dict = {
                "id": db_example.id,  # Include the sentence ID
                "sentence": db_example.sentence,
                "translation": db_example.translation,
                "cefr_level": db_example.cefr_level,
                "llm_model": (
                    db_example.ai_generator.model_name
                    if db_example.ai_generator
                    else "unknown"
                ),
                "prompt_version": (
                    db_example.ai_generator.prompt_version
                    if db_example.ai_generator
                    else "unknown"
                ),
            }
            examples.append(example_dict)

            # Use the first example's ai_generator_id for consistency
            if not ai_generator_id and db_example.ai_generator:
                ai_generator_id = db_example.ai_generator.id
                llm_model = db_example.ai_generator.model_name
                prompt_version = db_example.ai_generator.prompt_version

        return json_result(
            {
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": examples,
                "ai_generator_id": ai_generator_id,
                "llm_model": llm_model,
                "prompt_version": prompt_version,
                "source": "database",
            }
        )

    # Fallback to real-time generation if no pre-generated examples
    log(
        f"No pre-generated examples found for user_word {user_word_id}, falling back to real-time generation"
    )

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
            prompt_version="v3",
        )

        # Extract model and version from first example (they're all the same)
        llm_model = examples[0]["llm_model"] if examples else "unknown"
        prompt_version = examples[0]["prompt_version"] if examples else "v1"

        # Find or create AIGenerator record
        ai_generator = AIGenerator.find_or_create(
            db_session,
            llm_model,
            prompt_version,
            description="Real-time example generation for language learning",
        )

        # Save the generated examples to database for future use
        saved_examples = []
        for example in examples:
            example_sentence = ExampleSentence.create_ai_generated(
                db_session,
                sentence=example["sentence"],
                language=user_word.meaning.origin.language,
                meaning=user_word.meaning,
                ai_generator=ai_generator,
                translation=example.get("translation"),
                cefr_level=example.get("cefr_level", cefr_level),
                commit=False,
            )
            saved_examples.append(example_sentence)

        # Commit all the new examples
        db_session.commit()
        log(
            f"Saved {len(examples)} real-time generated examples to database for user_word {user_word_id}"
        )

        # Add IDs to the examples we're returning
        for i, example in enumerate(examples):
            example["id"] = saved_examples[i].id

        return json_result(
            {
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": examples,
                "ai_generator_id": ai_generator.id,
                "llm_model": llm_model,
                "prompt_version": prompt_version,
                "source": "realtime_saved",
            }
        )

    except Exception as e:
        log(f"Error generating examples for user_word {user_word_id}: {e}")

        resp = json_result(
            {
                "error": "Failed to generate examples. Please try again later.",
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": [],
            }
        )
        resp.status_code = 500
        return resp


@api.route("/set_preferred_example/<user_word_id>", methods=["POST"])
@cross_domain
@requires_session
def set_preferred_example(user_word_id):
    """
    Endpoint: POST /set_preferred_example/<user_word_id>

    Set the user's preferred example/context for a word by creating a bookmark
    from the selected ExampleSentence.

    Request body (JSON):
    {
        "sentence_id": 123  // ID of the ExampleSentence to set as preferred
    }

    Success Response (200):
    {
        "bookmark_id": 456,
        "user_word_id": 789,
        "message": "Generated example saved successfully",
        "updated_bookmark": { ... },  // Full bookmark data
        "bookmark_context_id": 101
    }

    Error Response (400):
    {
        "error": "Unable to save this example",
        "detail": "The selected example sentence does not contain the word you're learning. Please choose a different example or report this issue.",
        "technical_detail": "Word 'example' not found in sentence",
        "user_word_id": 789
    }

    Error Response (404):
    {
        "error": "UserWord not found or unauthorized"
    }
    OR
    {
        "error": "Sentence with ID 123 not found for this word"
    }

    :param user_word_id: ID of the UserWord
    :return: JSON response with bookmark data or error message
    """
    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return json_result({"error": "UserWord not found or unauthorized"}, status=404)

    # Get the sentence_id from request
    data = request.get_json()
    if not data or "sentence_id" not in data:
        return json_result({"error": "sentence_id is required"}, status=400)

    sentence_id = data["sentence_id"]

    # Find the ExampleSentence - must belong to this user's meaning
    example_sentence_obj = ExampleSentence.query.filter(
        ExampleSentence.id == sentence_id,
        ExampleSentence.meaning_id == user_word.meaning_id,
    ).first()

    if not example_sentence_obj:
        return json_result(
            {"error": f"Sentence with ID {sentence_id} not found for this word"},
            status=404,
        )

    selected_sentence = example_sentence_obj.sentence

    # Find word position using shared utility (fuzzy matching for generated examples)
    target_word = user_word.meaning.origin.content
    result = find_first_occurrence(
        target_word, selected_sentence, user_word.meaning.origin.language
    )

    if not result["found"]:
        log(
            f"ERROR: Could not find word '{target_word}' in example sentence '{selected_sentence}'"
        )
        log(f"Error: {result['error_message']}")
        return json_result(
            {
                "error": "Unable to save this example",
                "detail": "The selected example sentence does not contain the word you're learning. Please choose a different example or report this issue.",
                "technical_detail": result["error_message"],
                "user_word_id": user_word_id,
            },
            status=400,  # Bad Request as it's a data issue, not server error
        )

    # Extract position data
    position_data = result["position_data"]
    sentence_i = position_data["sentence_i"]
    token_i = position_data["token_i"]
    c_sentence_i = position_data["c_sentence_i"]
    c_token_i = position_data["c_token_i"]
    total_tokens_found = position_data["total_tokens"]

    log(
        f"Successfully found '{target_word}' at position sent_i={sentence_i}, token_i={token_i}, total_tokens={total_tokens_found}"
    )

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
        selected_sentence,
        None,  # article_id
        None,  # source_id
        sentence_i=sentence_i,
        token_i=token_i,
        total_tokens=total_tokens_found,  # Use calculated token count
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
            "updated_bookmark": bookmark.as_dictionary(
                with_context=True, with_context_tokenized=True
            ),
            "bookmark_context_id": bookmark.context.id,
        }
    )


@api.route("/generate_examples/<word>/<from_lang>/<to_lang>", methods=["GET"])
@cross_domain
@requires_session
def generate_examples_for_word(word, from_lang, to_lang):
    """
    Generate example sentences for any word without requiring it to be saved first.
    Useful for the Translate tab and "Add Custom Word" modal.

    If a translation is provided, this will:
    1. Find or create the Meaning (word+translation pair)
    2. Check for existing pre-generated examples in DB
    3. If none exist, generate new examples and save them for future use

    :param word: The word to generate examples for
    :param from_lang: Source language code (e.g., 'da')
    :param to_lang: Target language code (e.g., 'en')
    :query translation: Optional translation/meaning to generate examples for specific sense
    :query cefr_level: User's CEFR level for appropriate difficulty (default: B1)
    :return: JSON array with example sentences
    """
    user = User.find_by_id(flask.g.user_id)

    # Get language objects
    origin_lang = Language.find(from_lang)
    translation_lang = Language.find(to_lang)

    if not origin_lang or not translation_lang:
        return json_result({"error": "Invalid language codes"}, status=400)

    cefr_level = request.args.get("cefr_level", DEFAULT_CEFR_LEVEL)
    translation = request.args.get("translation", "")

    try:
        # If we have a translation, try to find/create meaning and check for existing examples
        if translation:
            meaning = Meaning.find_or_create(
                db_session,
                word,
                from_lang,
                translation,
                to_lang,
            )
            db_session.commit()

            # Check for existing examples in DB for this meaning at user's CEFR level
            db_examples = (
                ExampleSentence.query.filter(
                    ExampleSentence.meaning_id == meaning.id,
                    ExampleSentence.cefr_level == cefr_level,
                )
                .limit(MAX_EXAMPLES_GENERATE)
                .all()
            )

            if db_examples:
                log(f"Found {len(db_examples)} existing examples for meaning {meaning.id}")
                examples = []
                for db_example in db_examples:
                    examples.append({
                        "id": db_example.id,
                        "sentence": db_example.sentence,
                        "translation": db_example.translation,
                        "cefr_level": db_example.cefr_level,
                    })
                return json_result({
                    "examples": examples,
                    "word": word,
                    "meaning_id": meaning.id,
                    "source": "database",
                })

            # No existing examples - generate and save them
            log(f"No examples found for meaning {meaning.id}, generating new ones")

        # Get LLM service and generate examples
        llm_service = get_llm_service()
        examples = llm_service.generate_examples(
            word=word,
            translation=translation,
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level=cefr_level,
            prompt_version="v3",
            count=MAX_EXAMPLES_GENERATE,
        )

        # If we have a meaning, save the generated examples
        if translation and meaning:
            llm_model = examples[0]["llm_model"] if examples else "unknown"
            prompt_version = examples[0]["prompt_version"] if examples else "v3"

            ai_generator = AIGenerator.find_or_create(
                db_session,
                llm_model,
                prompt_version,
                description="Example generation for Translate tab",
            )

            saved_examples = []
            for example in examples:
                example_sentence = ExampleSentence.create_ai_generated(
                    db_session,
                    sentence=example["sentence"],
                    language=origin_lang,
                    meaning=meaning,
                    ai_generator=ai_generator,
                    translation=example.get("translation"),
                    cefr_level=example.get("cefr_level", cefr_level),
                    commit=False,
                )
                saved_examples.append(example_sentence)

            db_session.commit()
            log(f"Saved {len(saved_examples)} examples for meaning {meaning.id}")

            # Add IDs to returned examples
            for i, example in enumerate(examples):
                example["id"] = saved_examples[i].id

        return json_result({
            "examples": examples,
            "word": word,
            "meaning_id": meaning.id if translation else None,
            "source": "generated",
        })

    except Exception as e:
        log(f"Error generating examples for word '{word}': {e}")
        traceback.print_exc()

        error_response = json.dumps(
            {"error": "Failed to generate examples", "examples": []}
        )
        return Response(error_response, status=500, mimetype="application/json")


@api.route("/add_word_to_learning", methods=["POST"])
@cross_domain
@requires_session
def add_word_to_learning():
    """
    Add a word to learning with LLM-optimized word form, translation, and example.

    The LLM will:
    - Normalize the word to dictionary form (e.g., "ophæv" -> "ophæve")
    - Clean up the translation (e.g., "cancel" -> "to cancel")
    - Select or generate the best example sentence

    Request body (JSON):
    {
        "word": "ophæv",
        "translation": "cancel",
        "from_lang": "da",
        "to_lang": "en",
        "examples": ["Jeg vil gerne ophæve min reservation.", ...]
    }

    Success Response (200):
    {
        "success": true,
        "bookmark_id": 123,
        "learning_card": {
            "word": "ophæve",
            "translation": "to cancel",
            "example": "Jeg vil gerne ophæve min reservation.",
            "example_translation": "I would like to cancel my reservation."
        }
    }
    """
    user = User.find_by_id(flask.g.user_id)
    data = request.get_json()

    if not data:
        return json_result({"error": "JSON body required"}, status=400)

    word = data.get("word", "").strip()
    translation = data.get("translation", "").strip()
    from_lang = data.get("from_lang", "")
    to_lang = data.get("to_lang", "")
    examples = data.get("examples", [])

    if not word or not translation or not from_lang or not to_lang:
        return json_result({"error": "word, translation, from_lang, to_lang required"}, status=400)

    # Get user's CEFR level
    cefr_level = data.get("cefr_level", DEFAULT_CEFR_LEVEL)

    # Get language objects
    origin_lang = Language.find(from_lang)
    target_lang = Language.find(to_lang)

    if not origin_lang or not target_lang:
        return json_result({"error": "Invalid language codes"}, status=400)

    try:
        # Call LLM to prepare the optimal learning card
        learning_card = prepare_learning_card(
            searched_word=word,
            translation=translation,
            source_lang=origin_lang.name,
            target_lang=target_lang.name,
            cefr_level=cefr_level,
            examples=examples
        )

        final_word = learning_card["word"]
        final_translation = learning_card["translation"]
        final_example = learning_card["example"]

        # Create or find the meaning
        meaning = Meaning.find_or_create(
            db_session, final_word, from_lang, final_translation, to_lang
        )

        # Create UserWord with is_user_added flag
        user_word = UserWord.find_or_create(
            db_session, user, meaning, is_user_added=True
        )

        user_word.user_preference = UserWordExPreference.USE_IN_EXERCISES
        user_word.update_fit_for_study(db_session)

        # Validate word position in example
        validation_result = validate_single_occurrence(final_word, final_example, origin_lang)

        if not validation_result["valid"]:
            log(f"Word validation failed for '{final_word}' in example: {validation_result['error_message']}")
            # Use fallback position data
            sentence_i = 0
            token_i = 0
            c_sentence_i = 0
            c_token_i = 0
            total_tokens = len(final_example.split())
        else:
            position_data = validation_result["position_data"]
            sentence_i = position_data["sentence_i"]
            token_i = position_data["token_i"]
            c_sentence_i = position_data["c_sentence_i"]
            c_token_i = position_data["c_token_i"]
            total_tokens = position_data["total_tokens"]

        # Create context identifier for user-added word
        context_identifier = ContextIdentifier(
            context_type=ContextType.USER_EDITED_TEXT
        )

        # Create bookmark
        bookmark = Bookmark.find_or_create(
            db_session,
            user,
            final_word,
            from_lang,
            final_translation,
            to_lang,
            final_example,
            None,  # article_id
            None,  # source_id
            sentence_i=sentence_i,
            token_i=token_i,
            total_tokens=total_tokens,
            c_sentence_i=c_sentence_i,
            c_token_i=c_token_i,
            context_identifier=context_identifier,
        )

        # Set as preferred bookmark and schedule for learning
        user_word.preferred_bookmark = bookmark
        # Note: find_or_create has side effect of creating schedule and setting level=1
        FourLevelsPerWord.find_or_create(db_session, user_word)

        db_session.add(user_word)
        db_session.commit()

        return json_result({
            "success": True,
            "bookmark_id": bookmark.id,
            "user_word_id": user_word.id,
            "learning_card": learning_card
        })

    except Exception as e:
        db_session.rollback()
        log(f"Error adding word to learning: {e}")
        traceback.print_exc()

        return json_result({
            "error": "Failed to prepare learning card. Please try again.",
            "detail": str(e)
        }, status=500)


@api.route("/preview_learning_card", methods=["POST"])
@cross_domain
@requires_session
def preview_learning_card():
    """
    Preview a learning card without saving it.

    Returns cached explanation/level_note from Meaning if available,
    otherwise generates via LLM and caches for future use.

    Request body (JSON):
    {
        "word": "ophæv",
        "translation": "cancel",
        "from_lang": "da",
        "to_lang": "en",
        "examples": ["Jeg vil gerne ophæve min reservation.", ...]
    }

    Response (200):
    {
        "word": "ophæve",
        "translation": "to cancel",
        "example": "Jeg vil gerne ophæve min reservation.",
        "example_translation": "I would like to cancel my reservation.",
        "explanation": "Common verb for canceling...",
        "level_note": "appropriate for B1...",
        "recommendation": "recommended"
    }
    """
    user = User.find_by_id(flask.g.user_id)
    data = request.get_json()

    if not data:
        return json_result({"error": "JSON body required"}, status=400)

    word = data.get("word", "").strip()
    translation = data.get("translation", "").strip()
    from_lang = data.get("from_lang", "")
    to_lang = data.get("to_lang", "")
    examples = data.get("examples", [])

    if not word or not translation or not from_lang or not to_lang:
        return json_result({"error": "word, translation, from_lang, to_lang required"}, status=400)

    cefr_level = data.get("cefr_level", DEFAULT_CEFR_LEVEL)

    origin_lang = Language.find(from_lang)
    target_lang = Language.find(to_lang)

    if not origin_lang or not target_lang:
        return json_result({"error": "Invalid language codes"}, status=400)

    # Check if we have cached explanation/cefr_level in Meaning
    meaning = Meaning.find_or_create(
        db_session, word, from_lang, translation, to_lang
    )

    if meaning.translation_explanation and meaning.word_cefr_level:
        # Return cached data - no LLM call needed
        return json_result({
            "word": word,
            "translation": translation,
            "explanation": meaning.translation_explanation,
            "word_cefr_level": meaning.word_cefr_level,
            "example": examples[0] if examples else "",
            "example_translation": "",
            "recommendation": "recommended",
            "cached": True
        })

    try:
        # Generate via LLM
        learning_card = prepare_learning_card(
            searched_word=word,
            translation=translation,
            source_lang=origin_lang.name,
            target_lang=target_lang.name,
            cefr_level=cefr_level,
            examples=examples
        )

        # Cache in Meaning for future use
        if learning_card.get("explanation"):
            meaning.translation_explanation = learning_card["explanation"]

        # Parse CEFR level from level_note (e.g., "appropriate for B1 - ..." → "B1")
        level_note = learning_card.get("level_note", "")
        import re
        cefr_match = re.search(r'\b(A1|A2|B1|B2|C1|C2)\b', level_note)
        if cefr_match:
            meaning.word_cefr_level = cefr_match.group(1)
            learning_card["word_cefr_level"] = cefr_match.group(1)

        db_session.add(meaning)
        db_session.commit()

        return json_result(learning_card)

    except Exception as e:
        log(f"Error previewing learning card: {e}")
        return json_result({
            "error": "Failed to generate preview",
            "detail": str(e)
        }, status=500)
