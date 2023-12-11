from .paywall_detector import is_paywalled
import os
from joblib import load

ml_models_path = os.path.dirname(__file__)
PAYWALL_TFIDF_MODEL = load(os.path.join(ml_models_path,'models', 'tfidf_multi_paywall_detect.joblib'))

ID_TO_LABEL_PAYWALL = {
    0: "Normal",
    1: "Paywalled",
    2: "DifficultToRead"
}

