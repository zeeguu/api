from zeeguu.core.model.language import Language
from os import getenv, path
import stanza


def stanza_model_installation():

    ZEEGUU_DATA_FOLDER = getenv("ZEEGUU_DATA_FOLDER")

    for l_code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        stanza.download(
            l_code,
            processors="tokenize,pos",
            model_dir=path.join(ZEEGUU_DATA_FOLDER, "stanza_resources"),
        )


stanza_model_installation()
