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
    Returns alternative example sentences for a user_word.

    First tries to serve pre-generated examples from the database.
    Falls back to real-time LLM generation if no pre-generated examples exist.

    :param user_word_id: ID of the UserWord to get examples for
    :return: JSON array with example sentences
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
        
        return json_result(
            {
                "error": "Failed to generate examples. Please try again later.",
                "user_word_id": user_word_id,
                "word": origin_word,
                "translation": translation,
                "examples": []
            },
            status=500
        )


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

    # Tokenize the example sentence to properly find word position
    from zeeguu.core.tokenization import get_tokenizer, TOKENIZER_MODEL
    
    tokenizer = get_tokenizer(
        user_word.meaning.origin.language, TOKENIZER_MODEL
    )
    
    # Tokenize the selected sentence
    tokenized_sentence = tokenizer.tokenize_text(
        selected_sentence, as_serializable_dictionary=False
    )
    
    # Find the target word position in the tokenized content
    target_word = user_word.meaning.origin.content.lower()
    
    # Initialize position variables
    sentence_i = 0
    token_i = 0
    c_sentence_i = 0 
    c_token_i = 0
    found = False
    
    # Search through all tokens to find the target word
    for token in tokenized_sentence:
        token_text = token.text.lower()
        # Clean the token for comparison (remove punctuation)
        clean_token = "".join(c for c in token_text if c.isalnum())
        
        if clean_token == target_word or target_word in clean_token or clean_token in target_word:
            # Found the word - get its position
            sentence_i = token.sent_i
            token_i = token.token_i
            c_sentence_i = token.sent_i  # Context sentence is the same as word sentence
            c_token_i = token.token_i  # Context token is the same as word token
            found = True
            break
    
    # If not found, this is an error - the word should be in the example
    if not found:
        log(f"ERROR: Could not find word '{target_word}' in example sentence '{selected_sentence}'")
        return json_result(
            {
                "error": "Unable to save this example",
                "detail": "The selected example sentence does not contain the word you're learning. Please choose a different example or report this issue.",
                "technical_detail": f"Word '{target_word}' not found in sentence",
                "user_word_id": user_word_id
            },
            status=400  # Changed to 400 (Bad Request) as it's a data issue, not server error
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
