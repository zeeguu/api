def fk_to_cefr(fk_difficulty):
    if fk_difficulty < 17:
        return "A1"
    elif fk_difficulty < 34:
        return "A2"
    elif fk_difficulty < 51:
        return "B1"
    elif fk_difficulty < 68:
        return "B2"
    elif fk_difficulty < 85:
        return "C1"
    else:
        return "C2"


# notes for the future
# - consider using some of the LLMs
#   - fine-tuning
# - even ask the LLM about grammar?
# - Tiago: try Gemma
