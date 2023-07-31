import os

os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser("<path-to-/endpoints.cfg")

os.environ["FLASK_MONITORING_DASHBOARD_CONFIG"] = os.path.expanduser(
    "<path-to-/dashboard.cfg"
)

os.environ["DASHBOARD_LOG_DIR"] = os.path.expanduser("<path-to-/.logs/")

os.environ["GOOGLE_TRANSLATE_API_KEY"] = ""
os.environ["MICROSOFT_TRANSLATE_API_KEY"] = ""
os.environ["WORDNIK_API_KEY"] = ""
