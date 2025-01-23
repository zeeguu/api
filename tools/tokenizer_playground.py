from zeeguu.core.model.language import Language
from zeeguu.core.tokenization.tokenizer import ZeeguuTokenizer, TokenizerModel
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
en_spacy = spacy.load("en_core_web_sm")

while True:
    clear_terminal()
    print("Welcome to the Zeeguu Tokenizer")
    language = Language.find(input("Enter language code (ex. 'en'): ").lower())
    tokenizer_nltk = ZeeguuTokenizer(language, TokenizerModel.NLTK)
    tokenizer_stanza = ZeeguuTokenizer(language, TokenizerModel.STANZA_TOKEN_ONLY)
    tokenizer_stanza_pos = ZeeguuTokenizer(language, TokenizerModel.STANZA_TOKEN_POS)
    text = input("Enter text: ")
    print("Got the following text: ", text)
    nltk_start = time.time()
    tokens = tokenizer_nltk.tokenize_text(text)
    nltk_end = time.time() - nltk_start
    stanza_start = time.time()
    stanza_tokens = tokenizer_stanza.tokenize_text(text)
    stanza_end = time.time() - stanza_start

    stanza_pos_start = time.time()
    stanza_pos_tokens = tokenizer_stanza_pos.tokenize_text(text)
    stanza_pos_end = time.time() - stanza_pos_start

    spacy_start = time.time()
    spacy_tokens = en_spacy(text)
    spacy_end = time.time() - spacy_start
    print("Total chars: ", len(text))
    print(f"Processing NLTK time: {nltk_end:.2f} seconds, for {len(tokens)} tokens")
    print(
        f"Processing stanza time: {stanza_end:.2f} seconds, for {len(stanza_tokens)} tokens"
    )
    print(
        f"Processing stanza with POS time: {stanza_pos_end:.2f} seconds, for {len(stanza_pos_tokens)} tokens"
    )
    print(
        f"Processing spaCy time: {spacy_end:.2f} seconds, for {len(spacy_tokens)} tokens"
    )
    if input("Enter 'n' to skip token details: ") != "n":
        print()
        print("#" * 10 + " NLTK " + "#" * 10)
        for token in tokens:
            pprint(token)
            print("####")
        print("#" * 10 + " stanza " + "#" * 10)
        for token in stanza_tokens:
            print(token)
        print("#" * 10 + " spaCy " + "#" * 10)
        for t in spacy_tokens:
            print(t, t.lemma_, t.pos_, t.dep_)
            print("####")
    if input("Enter 'q' to quit, any other key to continue: ") == "q":
        break
