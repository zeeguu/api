from zeeguu.core.model.language import Language
from os import getenv
import stanza


def stanza_model_installation():

    ZEEGUU_DATA_FOLDER = getenv("ZEEGUU_DATA_FOLDER")

    for l_code in Language.CODES_OF_LANGUAGES_THAT_CAN_BE_LEARNED:
        stanza.download(l_code, processors="tokenize,pos", model_dir=ZEEGUU_DATA_FOLDER)
