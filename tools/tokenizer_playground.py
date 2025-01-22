from zeeguu.core.model.language import Language
from zeeguu.core.tokenization.tokenizer import tokenize_text_flat_array
from zeeguu.api.app import create_app


from pprint import pprint
import os
import stanza
import time
import spacy


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


app = create_app()
app.app_context().push()
en_nlp = stanza.Pipeline("en")
en_spacy = spacy.load("en_core_web_sm")

while True:
    clear_terminal()
    print("Welcome to the Zeeguu Tokenizer")
    language = Language.find(input("Enter language code (ex. 'en'): ").lower())
    text = input("Enter text: ")
    print("Got the following text: ", text)
    nltk_start = time.time()
    tokens = tokenize_text_flat_array(text, language, False)
    nltk_end = time.time() - nltk_start
    stanza_start = time.time()
    stanza_tokens = en_nlp(text)
    stanza_end = time.time() - stanza_start

    spacy_start = time.time()
    spacy_tokens = en_spacy(text)
    spacy_end = time.time() - spacy_start
    print("Total chars: ", len(text))
    print(f"Processing NLTK time: {nltk_end:.2f} seconds, for {len(tokens)} tokens")
    print(
        f"Processing stanza time: {stanza_end:.2f} seconds, for {stanza_tokens.num_tokens} tokens"
    )
    print(
        f"Processing spaCy time: {spacy_end:.2f} seconds, for {len(spacy_tokens)} tokens"
    )
    if input("Enter 'n' to skip token details: ") != "n":
        print()
        print("#" * 10 + " NLTK " + "#" * 10)
        for token in tokens:
            pprint(token.as_serializable_dictionary())
            print("####")
        print("#" * 10 + " stanza " + "#" * 10)
        for sentence in stanza_tokens.sentences:
            for word in sentence.words:
                print(word)
                print(word.text, word.lemma)
        print("#" * 10 + " spaCy " + "#" * 10)
        for t in spacy_tokens:
            print(t, t.lemma_, t.pos_, t.dep_)
            print("####")
    if input("Enter 'q' to quit, any other key to continue: ") == "q":
        break
