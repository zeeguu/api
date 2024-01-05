import os
from zeeguu.core.content_retriever.parse_with_readability_server import READABILITY_SERVER_CLEANUP_URI, download_and_parse

TESTDATA_FOLDER = os.path.join(os.path.dirname(__file__), "test_data")

URL_SPIEGEL_NANCY = "http://www.spiegel.de/politik/ausland/nancy-pelosi-trump-soll-erst-nach-beendigung-des-shutdowns-rede-halten-duerfen-a-1249611.html"

URL_ONION_US_MILITARY = "https://www.theonion.com/u-s-military-announces-plan-to-consolidate-all-wars-in-1824018300"

URL_LEMONDE_VOLS_AMERICAINS = "http://www.lemonde.fr/ameriques/article/2018/03/24/quand-les-vols-americains-se-transforment-en-arche-de-noe_5275773_3222.html"

URL_LEMONDE_FORMATION = "https://www.lemonde.fr/idees/article/2018/02/21/formation-le-big-bang-attendra_5260297_3232.html"

URL_NEWSCIENTIST_FISH = "https://www.newscientist.com/article/2164774-in-30-years-asian-pacific-fish-will-be-gone-and-then-were-next/"

URL_PROPUBLICA_INVESTING = "https://www.propublica.org/article/warren-buffett-recommends-investing-in-index-funds-but-many-of-his-employees-do-not-have-that-option"

URL_FAZ_LEIGHTATHLETIK = "https://www.faz.net/aktuell/sport/mehr-sport/leichtathletik-deutsche-beim-istaf-mit-bestleistungen-nach-der-wm-19150019.html"

URL_SPIEGEL_RSS = "http://www.spiegel.de/index.rss"

URL_SPIEGEL_VENEZUELA = "http://www.spiegel.de/politik/ausland/venezuela-militaer-unterstuetzt-nicolas-maduro-im-machtkampf-gegen-juan-guaido-a-1249616.html"

URL_CNN_KATHMANDU = "https://edition.cnn.com/2018/03/12/asia/kathmandu-plane-crash/index.html"

URL_KLEINE_PRINZ = "http://www.derkleineprinz-online.de/text/2-kapitel/"

URL_BLINDEN_UND_ELEPHANT = "https://www.geschichten-netzwerk.de/geschichten/die-blinden-und-der-elefant/"

URL_ML_JP_PAYWALL = "https://jyllands-posten.dk/kultur/ECE16582800/puk-damsgaard-leverer-voldsom-kritik-af-vestens-krig-i-afghanistan/#:~:text=Man%20kommer%20ikke%20i%20godt,og%20ligestilling%20i%20al%20evighed."

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

    # these are needed for mocking the readability cleanup server
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ: "der_kleine_prinz.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_FAZ_LEIGHTATHLETIK: "faz_leichtathletik.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_CNN_KATHMANDU: "cnn_kathmandu.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_VENEZUELA: "spiegel_venezuela.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_NANCY: "spiegel_nancy.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_LEMONDE_FORMATION: "lemonde_formation.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ: "der_kleine_prinz.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_ML_JP_PAYWALL: "jp_article_example.txt"
}

def mock_requests_get(m):
    def mock_requests_get_for_url(m, url):
        f = open(os.path.join(TESTDATA_FOLDER, URLS_TO_MOCK[url]), encoding="UTF-8")
        content = f.read()

        m.get(url, text=content)
        f.close()

    for each in URLS_TO_MOCK.keys():
        mock_requests_get_for_url(m, each)

def mock_readibility_call(url):
    return download_and_parse(url)