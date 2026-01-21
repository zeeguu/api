import flask
from flask import request

from zeeguu.api.utils.json_result import json_result
from zeeguu.api.utils.route_wrappers import cross_domain, requires_session
from zeeguu.core.llm_services import get_llm_service
from zeeguu.core.model import UserWord, User, Bookmark, Language
from zeeguu.core.model.ai_generator import AIGenerator
from zeeguu.core.model.context_identifier import ContextIdentifier
from zeeguu.core.model.context_type import ContextType
from zeeguu.core.model.example_sentence import ExampleSentence
from zeeguu.logging import log
from . import api, db_session


def _validate_before_examples(user_word):
    """
    Validate and fix translation before generating examples.

    This prevents wasting API calls on generating examples for incorrect translations.
    Uses the same validation logic as FourLevelsPerWord scheduling.

    Args:
        user_word: UserWord to validate

    Returns:
        UserWord to use (may be different if fixed), or None if unfixable
    """
    try:
        from zeeguu.core.llm_services.translation_validator import TranslationValidator
        validator = TranslationValidator()
    except (ImportError, ValueError) as e:
        # API key not configured or module not available, skip validation
        log(f"[VALIDATION] Skipping validation in examples: {e}")
        return user_word

    # Get context from preferred bookmark
    bookmark = user_word.preferred_bookmark
    if not bookmark:
        log(f"[VALIDATION] No preferred bookmark, skipping validation")
        return user_word

    context = bookmark.get_context()
    if not context:
        log(f"[VALIDATION] No context available, skipping validation")
        return user_word

    meaning = user_word.meaning

    log(f"[VALIDATION] Validating before examples: '{meaning.origin.content}' -> '{meaning.translation.content}'")

    result = validator.validate_translation(
        word=meaning.origin.content,
        translation=meaning.translation.content,
        context=context,
        source_lang=meaning.origin.language.code,
        target_lang=meaning.translation.language.code
    )

    if result.is_valid:
        log(f"[VALIDATION] Translation is valid")
        meaning.exercise_validated = 1
        # Also set frequency and phrase_type from combined validation
        if result.frequency:
            from zeeguu.core.model.meaning import MeaningFrequency
            freq_map = {"unique": MeaningFrequency.UNIQUE, "common": MeaningFrequency.COMMON,
                       "uncommon": MeaningFrequency.UNCOMMON, "rare": MeaningFrequency.RARE}
            meaning.frequency = freq_map.get(result.frequency)
        if result.phrase_type:
            from zeeguu.core.model.meaning import PhraseType
            type_map = {"single_word": PhraseType.SINGLE_WORD, "collocation": PhraseType.COLLOCATION,
                       "idiom": PhraseType.IDIOM, "expression": PhraseType.EXPRESSION,
                       "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD}
            meaning.phrase_type = type_map.get(result.phrase_type)
        db_session.add(meaning)
        db_session.commit()
        # Update fit_for_study in case phrase_type changed to arbitrary_multi_word
        user_word.update_fit_for_study(db_session)
        return user_word
    else:
        log(f"[VALIDATION] Translation needs fixing: {result.reason}")
        return _fix_bookmark_for_examples(user_word, bookmark, result)


def _fix_bookmark_for_examples(user_word, bookmark, validation_result):
    """
    Fix bookmark with corrected word/translation before generating examples.

    Returns the new user_word to use, or None if unfixable.
    """
    from zeeguu.core.model import Meaning, UserWord
    from zeeguu.core.bookmark_operations.update_bookmark import (
        transfer_learning_progress,
        cleanup_old_user_word
    )

    old_meaning = user_word.meaning

    # Determine what to fix
    new_word = validation_result.corrected_word or old_meaning.origin.content
    new_translation = validation_result.corrected_translation or old_meaning.translation.content

    # If no actual correction was provided, mark as invalid but don't fix
    if new_word == old_meaning.origin.content and new_translation == old_meaning.translation.content:
        log(f"[VALIDATION] No correction provided, marking as invalid")
        old_meaning.exercise_validated = 2  # Invalid
        user_word.fit_for_study = False
        db_session.add_all([old_meaning, user_word])
        db_session.commit()
        return None

    log(f"[VALIDATION] Fixing: '{old_meaning.origin.content}' -> '{old_meaning.translation.content}'")
    log(f"[VALIDATION] To: '{new_word}' -> '{new_translation}'")

    # Create/find correct meaning
    new_meaning = Meaning.find_or_create(
        db_session,
        new_word,
        old_meaning.origin.language.code,
        new_translation,
        old_meaning.translation.language.code
    )
    new_meaning.exercise_validated = 1  # Mark as validated
    # Set frequency and phrase_type from validation result
    if validation_result.frequency:
        from zeeguu.core.model.meaning import MeaningFrequency
        freq_map = {"unique": MeaningFrequency.UNIQUE, "common": MeaningFrequency.COMMON,
                   "uncommon": MeaningFrequency.UNCOMMON, "rare": MeaningFrequency.RARE}
        new_meaning.frequency = freq_map.get(validation_result.frequency)
    if validation_result.phrase_type:
        from zeeguu.core.model.meaning import PhraseType
        type_map = {"single_word": PhraseType.SINGLE_WORD, "collocation": PhraseType.COLLOCATION,
                   "idiom": PhraseType.IDIOM, "expression": PhraseType.EXPRESSION,
                   "arbitrary_multi_word": PhraseType.ARBITRARY_MULTI_WORD}
        new_meaning.phrase_type = type_map.get(validation_result.phrase_type)
    db_session.add(new_meaning)

    # Mark old meaning as invalid
    old_meaning.exercise_validated = 2  # Invalid/fixed
    db_session.add(old_meaning)

    # If meaning actually changed, update user's data
    if new_meaning.id != old_meaning.id:
        # Find or create UserWord for new meaning
        new_user_word = UserWord.find_or_create(
            db_session,
            user_word.user,
            new_meaning
        )

        # Transfer learning progress
        old_user_word = user_word
        transfer_learning_progress(db_session, old_user_word, new_user_word, bookmark)

        # Update bookmark to point to new user_word
        bookmark.user_word = new_user_word
        new_user_word.preferred_bookmark = bookmark
        db_session.add_all([bookmark, new_user_word])

        # Cleanup old user_word if orphaned
        cleanup_old_user_word(db_session, old_user_word, bookmark)

        db_session.commit()
        log(f"[VALIDATION] Fixed and moved to new UserWord {new_user_word.id}")
        return new_user_word
    else:
        # Same meaning (shouldn't happen often), just commit
        db_session.commit()
        log(f"[VALIDATION] Fixed translation, same meaning")
        return user_word


@api.route("/alternative_sentences/<user_word_id>", methods=["GET"])
@cross_domain
@requires_session
def alternative_sentences(user_word_id):
    """
    Returns alternative example sentences for a user_word.

    First validates the translation (if not already validated) to avoid
    generating examples for incorrect translations.

    Then tries to serve pre-generated examples from the database.
    Falls back to real-time LLM generation if no pre-generated examples exist.

    :param user_word_id: ID of the UserWord to get examples for
    :return: JSON array with example sentences
    """
    user = User.find_by_id(flask.g.user_id)
    user_word = UserWord.query.get(user_word_id)

    if not user_word or user_word.user_id != user.id:
        return json_result({"error": "UserWord not found or unauthorized"}, status=404)

    # Validate translation before generating examples (if not already validated)
    # This avoids wasting API calls on incorrect translations
    if user_word.meaning.exercise_validated == 0:
        user_word = _validate_before_examples(user_word)
        if user_word is None:
            return json_result(
                {"error": "Translation validation failed", "examples": []},
                status=400
            )

    # Get the word and translation (may have been fixed by validation)
    origin_word = user_word.meaning.origin.content
    translation = user_word.meaning.translation.content
    origin_lang = user_word.meaning.origin.language.code
    translation_lang = user_word.meaning.translation.language.code

    # Determine CEFR level
    cefr_level = request.args.get("cefr_level", "B1")
    
    # First, try to get pre-generated examples from database
    # Try exact CEFR level match first
    db_examples = ExampleSentence.query.filter(
        ExampleSentence.meaning_id == user_word.meaning_id,
        ExampleSentence.cefr_level == cefr_level
    ).limit(5).all()
    
    # If no exact match, try any CEFR level for this meaning
    if not db_examples:
        db_examples = ExampleSentence.query.filter(
            ExampleSentence.meaning_id == user_word.meaning_id
        ).limit(5).all()
    
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
                "llm_model": db_example.ai_generator.model_name if db_example.ai_generator else "unknown",
                "prompt_version": db_example.ai_generator.prompt_version if db_example.ai_generator else "unknown"
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
                "source": "database"
            }
        )

    # Fallback to real-time generation if no pre-generated examples
    log(f"No pre-generated examples found for user_word {user_word_id}, falling back to real-time generation")
    
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
        log(f"Saved {len(examples)} real-time generated examples to database for user_word {user_word_id}")
        
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
                "source": "realtime_saved"
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
                "examples": []
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
        ExampleSentence.meaning_id == user_word.meaning_id
    ).first()
    
    if not example_sentence_obj:
        return json_result(
            {"error": f"Sentence with ID {sentence_id} not found for this word"}, 
            status=404
        )
    
    selected_sentence = example_sentence_obj.sentence

    # Find word position using shared utility (fuzzy matching for generated examples)
    from zeeguu.core.tokenization.word_position_finder import find_first_occurrence
    
    target_word = user_word.meaning.origin.content
    result = find_first_occurrence(target_word, selected_sentence, user_word.meaning.origin.language)
    
    if not result['found']:
        log(f"ERROR: Could not find word '{target_word}' in example sentence '{selected_sentence}'")
        log(f"Error: {result['error_message']}")
        return json_result(
            {
                "error": "Unable to save this example",
                "detail": "The selected example sentence does not contain the word you're learning. Please choose a different example or report this issue.",
                "technical_detail": result['error_message'],
                "user_word_id": user_word_id
            },
            status=400  # Bad Request as it's a data issue, not server error
        )
    
    # Extract position data
    position_data = result['position_data']
    sentence_i = position_data['sentence_i']
    token_i = position_data['token_i']
    c_sentence_i = position_data['c_sentence_i']
    c_token_i = position_data['c_token_i']
    total_tokens_found = position_data['total_tokens']
    
    log(f"Successfully found '{target_word}' at position sent_i={sentence_i}, token_i={token_i}, total_tokens={total_tokens_found}")

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
            "updated_bookmark": bookmark.as_dictionary(with_context=True, with_context_tokenized=True),
            "bookmark_context_id": bookmark.context.id,
        }
    )


@api.route("/generate_examples/<word>/<from_lang>/<to_lang>", methods=["GET"])
@cross_domain
@requires_session
def generate_examples_for_word(word, from_lang, to_lang):
    """
    Generate example sentences for any word without requiring it to be saved first.
    Useful for the "Add Custom Word" modal to show examples before adding the word.
    
    :param word: The word to generate examples for
    :param from_lang: Source language code (e.g., 'da')
    :param to_lang: Target language code (e.g., 'en')
    :return: JSON array with example sentences
    """
    user = User.find_by_id(flask.g.user_id)
    
    # Get language objects
    origin_lang = Language.find(from_lang)
    translation_lang = Language.find(to_lang)
    
    if not origin_lang or not translation_lang:
        return json_result({"error": "Invalid language codes"}, status=400)
    
    try:
        # Get LLM service and generate examples directly
        llm_service = get_llm_service()
        cefr_level = request.args.get("cefr_level", "B1")
        
        # Generate examples using the LLM service
        examples = llm_service.generate_examples(
            word=word,
            translation="",  # We don't have a translation for the word yet
            source_lang=origin_lang,
            target_lang=translation_lang,
            cefr_level=cefr_level,
            prompt_version="v3",
            count=5
        )
        
        return json_result({"examples": examples, "word": word})
        
    except Exception as e:
        log(f"Error generating examples for word '{word}': {e}")
        # json_result doesn't accept status parameter, use flask.Response for error responses
        from flask import Response
        import json
        error_response = json.dumps({"error": "Failed to generate examples", "examples": []})
        return Response(error_response, status=500, mimetype="application/json")
