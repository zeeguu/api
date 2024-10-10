from zeeguu.core.content_retriever.parse_with_readability_server import download_and_parse

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()

na = download_and_parse(
    "https://www.dr.dk/nyheder/indland/flere-laeger-uden-koebenhavn-kronikerpakker-og-kaempe-region-her-er-det-vigtigste-i")
print(na)
