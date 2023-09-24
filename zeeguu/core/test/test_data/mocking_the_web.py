import os

TESTDATA_FOLDER = os.path.join(os.path.dirname(__file__), "")

URL_SPIEGEL_POLITIK1 = (
    "http://www.spiegel.de/politik/ausland/nancy-pelosi-trump-soll-erst-"
    "nach-beendigung-des-shutdowns-rede-halten-duerfen-a-1249611.html"
)

URL_ONION_ARTICLE1 = "https://www.theonion.com/u-s-military-announces-plan-to-consolidate-all-wars-in-1824018300"

URL_LEMONDE_VOLS_AMERICAINS = (
    "http://www.lemonde.fr/ameriques/article/2018/03/24/quand-les-vols-americains-se-transforment-"
    "en-arche-de-noe_5275773_3222.html"
)

URL_LEMONDE_FORMATION = "https://www.lemonde.fr/idees/article/2018/02/21/formation-le-big-bang-attendra_5260297_3232.html"

URL_FISH_WILL_BE_GONE = (
    "https://www.newscientist.com/"
    "article/2164774-in-30-years-asian-pacific-fish-will-be-gone-and-then-were-next/"
)

URL_INVESTING = (
    "https://www.propublica.org/article/"
    "warren-buffett-recommends-investing"
    "-in-index-funds-but-many-of-his-employees-do-not-have-that-option"
)

URL_LEIGHTATHLETIK = "https://www.faz.net/aktuell/sport/mehr-sport/leichtathletik-deutsche-beim-istaf-mit-bestleistungen-nach-der-wm-19150019.html"

URL_SPIEGEL_RSS = "http://www.spiegel.de/index.rss"

URL_SPIEGEL_VENEZUELA_MILITAER = (
    "http://www.spiegel.de/politik/ausland/venezuela-militaer-unterstuetzt-nicolas-maduro-im-"
    "machtkampf-gegen-juan-guaido-a-1249616.html"
)

URL_PLANE_CRASHES_KATHMANDU = "https://edition.cnn.com/2018/03/12/asia/kathmandu-plane-crash/index.html"

URL_KLEINE_PRINZ_KAPTEL2 = "http://www.derkleineprinz-online.de/text/2-kapitel/"

URL_BLINDEN_UND_ELEPHANT = (
    "https://www.geschichten-netzwerk.de/geschichten/die-blinden-und-der-elefant/"
)

from zeeguu.core.content_retriever.parse_with_readability_server import READABILITY_SERVER_CLEANUP_URI

URLS_TO_MOCK = {
    URL_LEMONDE_VOLS_AMERICAINS: "vols_americans.html",
    URL_ONION_ARTICLE1: "onion_us_military.html",
    URL_FISH_WILL_BE_GONE: "fish_will_be_gone.html",
    URL_INVESTING: "investing_in_index_funds.html",
    URL_SPIEGEL_RSS: "spiegel.rss",
    URL_SPIEGEL_VENEZUELA_MILITAER: "spiegel_militar.html",
    URL_LEIGHTATHLETIK: "leichtathletik.html",
    URL_PLANE_CRASHES_KATHMANDU: "plane_crashes.html",
    URL_SPIEGEL_POLITIK1: "pelosi_sperrt_president.html",
    URL_KLEINE_PRINZ_KAPTEL2: "der_kleine_prinz.html",
    URL_BLINDEN_UND_ELEPHANT: "blinden_und_elefant.html",
    URL_LEMONDE_FORMATION: "formation_professionnelle.html",

    # these are needed for mocking the readability cleanup server
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ_KAPTEL2: "der_kleine_prinz.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_LEIGHTATHLETIK: "leichtathletik.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_PLANE_CRASHES_KATHMANDU: "kathmandu.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_VENEZUELA_MILITAER: "venezuela.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_SPIEGEL_POLITIK1: "nancy_pelosi.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_LEMONDE_FORMATION: "formation.txt",
    READABILITY_SERVER_CLEANUP_URI + URL_KLEINE_PRINZ_KAPTEL2: "der_kleine_prinz.txt"
}


def mock_requests_get(m):
    def mock_requests_get_for_url(m, url):
        f = open(os.path.join(TESTDATA_FOLDER, URLS_TO_MOCK[url]), encoding="UTF-8")
        content = f.read()

        m.get(url, text=content)
        f.close()

    for each in URLS_TO_MOCK.keys():
        mock_requests_get_for_url(m, each)
