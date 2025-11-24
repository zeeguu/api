import os
from zeeguu.core.content_retriever.parse_with_readability_server import (
    READABILITY_SERVER_CLEANUP_URI,
    READABILITY_SERVER_CLEANUP_POST_URI,
    download_and_parse,
)
from zeeguu.core.semantic_vector_api import EMB_API_CONN_STRING
import numpy as np

TESTDATA_FOLDER = os.path.join(os.path.dirname(__file__), "test_data")

URL_SPIEGEL_NANCY = "http://www.spiegel.de/politik/ausland/nancy-pelosi-trump-soll-erst-nach-beendigung-des-shutdowns-rede-halten-duerfen-a-1249611.html"

URL_ONION_US_MILITARY = "https://www.theonion.com/u-s-military-announces-plan-to-consolidate-all-wars-in-1824018300"

URL_LEMONDE_VOLS_AMERICAINS = "http://www.lemonde.fr/ameriques/article/2018/03/24/quand-les-vols-americains-se-transforment-en-arche-de-noe_5275773_3222.html"

URL_LEMONDE_FORMATION = "https://www.lemonde.fr/idees/article/2018/02/21/formation-le-big-bang-attendra_5260297_3232.html"

URL_NEWSCIENTIST_FISH = "https://www.newscientist.com/article/2164774-in-30-years-asian-pacific-fish-will-be-gone-and-then-were-next/"

URL_PROPUBLICA_INVESTING = "https://www.propublica.org/article/warren-buffett-recommends-investing-in-index-funds-but-many-of-his-employees-do-not-have-that-option"

URL_FAZ_LEIGHTATHLETIK = "https://www.faz.net/aktuell/sport/fussball-em/polen-und-ukraine-nur-noch-einen-schritt-von-em-qualifikation-entfernt-19603993.html"

URL_SPIEGEL_RSS = "http://www.spiegel.de/index.rss"

URL_SPIEGEL_VENEZUELA = "http://www.spiegel.de/politik/ausland/venezuela-militaer-unterstuetzt-nicolas-maduro-im-machtkampf-gegen-juan-guaido-a-1249616.html"

URL_VERDENS_BEDSTE = "https://verdensbedstenyheder.dk"

URL_VERDENS_BEDSTE_RSS = "https://verdensbedstenyheder.dk/rss"

URL_VERDENS_BEDSTE_FEED = "https://verdensbedstenyheder.dk/feed"

URL_VERDENS_BEDSTE_FEEDS = "https://verdensbedstenyheder.dk/feeds"

URL_VERDENS_INDONESIA = "https://verdensbedstenyheder.dk/nyheder/hajstoev-afsloerer-illegalt-fiskeri-i-indonesien/"

URL_VERDENS_JORD = "https://verdensbedstenyheder.dk/nyheder/foer-ryddede-de-markerne-nu-dyrker-smaaboender-paa-tvaers-af-afrika-millioner-af-traeer-paa-deres-jorde/"

URL_CNN_KATHMANDU = (
    "https://edition.cnn.com/2018/03/12/asia/kathmandu-plane-crash/index.html"
)

URL_KLEINE_PRINZ = "http://www.derkleineprinz-online.de/text/2-kapitel/"

URL_BLINDEN_UND_ELEPHANT = (
    "https://www.geschichten-netzwerk.de/geschichten/die-blinden-und-der-elefant/"
)

URL_ML_JP_PAYWALL = "https://jyllands-posten.dk/kultur/ECE16582800/puk-damsgaard-leverer-voldsom-kritik-af-vestens-krig-i-afghanistan/#:~:text=Man%20kommer%20ikke%20i%20godt,og%20ligestilling%20i%20al%20evighed."

URL_SPIEGEL_IMG_2 = (
    "http://cdn2.spiegel.de/images/image-1387139-860_poster_16x9-fqsg-1387139.jpg"
)

URL_SPIEGEL_IMG_1 = (
    "http://cdn1.spiegel.de/images/image-1387130-860_poster_16x9-gljs-1387130.jpg"
)


URLS_TO_MOCK = {
    URL_BLINDEN_UND_ELEPHANT: "blinden_und_elefant.html",
    URL_CNN_KATHMANDU: "cnn_kathmandu.html",
    URL_KLEINE_PRINZ: "der_kleine_prinz.html",
    URL_FAZ_LEIGHTATHLETIK: "faz_leichtathletik.html",
    URL_LEMONDE_FORMATION: "lemonde_formation.html",
    URL_LEMONDE_VOLS_AMERICAINS: "lemonde_vols_americans.html",
    URL_NEWSCIENTIST_FISH: "newscientist_fish.html",
    URL_ONION_US_MILITARY: "onion_us_military.html",
    URL_PROPUBLICA_INVESTING: "propublica_investing.html",
    URL_SPIEGEL_RSS: "spiegel.rss",
    URL_SPIEGEL_NANCY: "spiegel_nancy.html",
    URL_SPIEGEL_VENEZUELA: "spiegel_venezuela.html",
    URL_ML_JP_PAYWALL: "jp_article_example.html",
    URL_VERDENS_BEDSTE: "verdensbedste.html",
    URL_VERDENS_INDONESIA: "verdensbedste_indonesien.html",
    URL_VERDENS_JORD: "verdensbedste_jorde.html",
    URL_VERDENS_BEDSTE_RSS: "verdensbedste.html",
    URL_VERDENS_BEDSTE_FEED: "verdensbedste.html",
    URL_VERDENS_BEDSTE_FEEDS: "verdensbedste.html",
    # these are needed for mocking the readability cleanup server
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ: "der_kleine_prinz.json",
    READABILITY_SERVER_CLEANUP_URI + URL_FAZ_LEIGHTATHLETIK: "faz_leichtathletik.json",
    READABILITY_SERVER_CLEANUP_URI + URL_CNN_KATHMANDU: "cnn_kathmandu.json",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_VENEZUELA: "spiegel_venezuela.json",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_NANCY: "spiegel_nancy.json",
    READABILITY_SERVER_CLEANUP_URI
    + URL_VERDENS_INDONESIA: "verdensbedste_indonesien.json",
    READABILITY_SERVER_CLEANUP_URI + URL_VERDENS_JORD: "verdensbedste_jorde.json",
    READABILITY_SERVER_CLEANUP_URI + URL_LEMONDE_FORMATION: "lemonde_formation.json",
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ: "der_kleine_prinz.json",
    READABILITY_SERVER_CLEANUP_URI + URL_ML_JP_PAYWALL: "jp_article_example.json",
    # tldextract, dependency of newspaper reaches out for this and makes our tests fail if we don't have net
    "https://publicsuffix.org/list/public_suffix_list.dat": "public_suffix_list.dat",
    URL_SPIEGEL_IMG_1: "spiegel_nancy.html",
    URL_SPIEGEL_IMG_2: "spiegel_nancy.html",
}

# Mapping from article URL to readability JSON response file
URL_TO_READABILITY_JSON = {
    URL_KLEINE_PRINZ: "der_kleine_prinz.json",
    URL_FAZ_LEIGHTATHLETIK: "faz_leichtathletik.json",
    URL_CNN_KATHMANDU: "cnn_kathmandu.json",
    URL_SPIEGEL_VENEZUELA: "spiegel_venezuela.json",
    URL_SPIEGEL_NANCY: "spiegel_nancy.json",
    URL_VERDENS_INDONESIA: "verdensbedste_indonesien.json",
    URL_VERDENS_JORD: "verdensbedste_jorde.json",
    URL_LEMONDE_FORMATION: "lemonde_formation.json",
    URL_ML_JP_PAYWALL: "jp_article_example.json",
}


def mock_requests_get(m):
    def mock_requests_get_for_url(m, url):
        f = open(os.path.join(TESTDATA_FOLDER, URLS_TO_MOCK[url]), encoding="UTF-8")
        content = f.read()

        m.get(url, text=content)
        f.close()

    for each in URLS_TO_MOCK.keys():
        mock_requests_get_for_url(m, each)

    # Mock POST requests to readability server
    # The POST body contains {"url": "...", "htmlContent": "..."}
    # We need to return the appropriate JSON based on the URL in the body
    def readability_post_callback(request, context):
        import json as json_module
        request_data = json_module.loads(request.text)
        article_url = request_data.get("url")

        # Find the matching JSON file for this URL
        if article_url in URL_TO_READABILITY_JSON:
            json_file = URL_TO_READABILITY_JSON[article_url]
            with open(os.path.join(TESTDATA_FOLDER, json_file), encoding="UTF-8") as f:
                return f.read()

        # Default response if URL not found
        context.status_code = 500
        return '{"error": "URL not mocked"}'

    m.post(READABILITY_SERVER_CLEANUP_POST_URI, text=readability_post_callback)

    # When creating a new article we need to be able to "call" the embedding API
    # so we return some random vector; thus, not used in the tests per se, but ensure that Article objects can be
    # created / "downloaded" in the tests
    m.post(
        f"{EMB_API_CONN_STRING}/get_article_embedding",
        json=np.random.random(512).tolist(),
    )


def mock_readability_call(url):
    return download_and_parse(url)
