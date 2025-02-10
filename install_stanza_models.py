from zeeguu.core.model.language import Language

import stanza

from zeeguu.core.tokenization.stanza_tokenizer import STANZA_RESOURCE_DIR


def stanza_model_installation():

    for l_code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        stanza.download(
            l_code,
            processors="tokenize,pos",
            model_dir=STANZA_RESOURCE_DIR,
        )


stanza_model_installation()
