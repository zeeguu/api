/*
  Tag existing feeds with retention_class based on their title/known nature.
  Untagged feeds remain 'unknown' (the column default).

  Tagging principle:
    ephemeral = daily/weekly news outlets, sports, politics, current-affairs
    perennial = science / history / culture / travel / cooking / long-form
                magazines, blogs, and essays whose content is re-readable

  When the call is borderline (e.g., DR Kultur, Courrier International,
  general-interest newspapers' opinion sections), we err on 'ephemeral'
  if the feed's defining frame is "latest article from a newspaper" and
  on 'perennial' if it's a topical magazine/blog.
*/

-- EPHEMERAL: daily/weekly news, sports, politics, daily-news adjacent
UPDATE feed SET retention_class = 'ephemeral' WHERE id IN (
  4,    -- Der Spiegel - Nachrichten
  15,   -- Neue Züricher Zeitung
  41,   -- Telegraaf - Nieuws
  46,   -- de Volkskrant - Nieuws
  47,   -- Tweakers Hardware and Tech
  50,   -- metronieuws.nl
  59,   -- Le Figaro - Santé
  60,   -- Le Figaro - Actualité
  66,   -- Le Monde
  75,   -- El País
  76,   -- Frankfurter Allgemeine
  80,   -- L'Equipe
  81,   -- Hotnews.ro Life
  83,   -- 1Jour1Actu
  84,   -- Marianne.net
  85,   -- Trouw
  87,   -- NRC
  89,   -- NOS Nieuws
  90,   -- NU.nl
  92,   -- ProPublica
  95,   -- El Comercio (Peru)
  96,   -- Times In Plain English
  97,   -- Simple English News
  101,  -- El Universal (Mexico)
  102,  -- The Onion
  104,  -- BBC Mundo
  106,  -- Liberation
  107,  -- L'Obs
  108,  -- L'Express
  110,  -- Guardian Weekly
  111,  -- The Economist - International
  112,  -- The Economist - Europe
  113,  -- BBC News - Home
  115,  -- CNN.com
  116,  -- Il Sole - 24 Ore
  117,  -- Reppublica.it
  118,  -- Corriere.it
  119,  -- Il Post
  120,  -- Internazionale
  121,  -- Lercio
  122,  -- openDemocracy
  123,  -- Nachrichtenleicht
  127,  -- WSJ.com: Opinion
  128,  -- WSJ.com: World News
  129,  -- Economy | The Guardian
  130,  -- Musique: dernières actus
  131,  -- Ligetil | DR
  132,  -- Gazeta.pl
  133,  -- Newsweek Polska
  135,  -- Jyllands-Posten
  136,  -- Politiken.dk
  137,  -- B.T. Nyhedder
  138,  -- DR Nyheder
  139,  -- Kultur | DR
  140,  -- Indland | DR
  141,  -- Udland | DR
  142,  -- Penge | DR
  143,  -- Politik | DR
  145,  -- Sport | DR
  146,  -- Vejret | DR
  147,  -- OLFI
  148,  -- Akademikerne
  149,  -- Ingeniøren
  151,  -- Аргументы и Факты
  152,  -- nyheter24.se
  153,  -- 8 Sidor
  154,  -- Siste – Siste nytt – NRK
  155,  -- Dagbladet
  156,  -- Aftenposten
  157,  -- VG RSS
  158,  -- TV 2
  159,  -- Le HuffPost
  161,  -- DN.se
  162,  -- SvD
  163,  -- Nyheter Idag
  164,  -- Tagesschau
  165,  -- NDR
  166,  -- WDR
  173,  -- giga
  174,  -- CHIP
  178,  -- Bilmagasinet
  182,  -- 20MINUTOS.ES
  186,  -- Latest Content - Fotogramas
  187,  -- rtve
  191,  -- La Stampa
  192,  -- Il Fatto Quotidiano
  193,  -- Panorama
  194,  -- lespresso
  199,  -- ComputerBlog.Ro
  200,  -- adevarul.ro
  204,  -- RTP Notícias
  205,  -- CNN Portugal
  206,  -- Abola.pt
  207,  -- IGN Portugal
  208,  -- Visão
  209,  -- Exame Informática
  210,  -- VISÃO Saúde
  212,  -- ΡΟΗ ΕΙΔΗΣΕΩΝ
  213,  -- Ελεύθερος Τύπος
  214,  -- Der Postillon
  215,  -- Le Figaro
  220,  -- Techmaniacs
  221,  -- Η ΝΑΥΤΕΜΠΟΡΙΚΗ
  222,  -- ΕΘΝΟΣ
  223,  -- The TOC
  224,  -- Courrier international
  226   -- NPR Topics: News
);

-- PERENNIAL: science, history, culture, travel, cooking, long-form essays
UPDATE feed SET retention_class = 'perennial' WHERE id IN (
  61,   -- La Blogothèque (music)
  71,   -- Urgeschmack (cooking blog)
  82,   -- Den Lille Bogblog (book blog)
  88,   -- NEMO Kennislink (Dutch science museum)
  91,   -- Taalblad (language learning)
  94,   -- New Yorker (long-form essays/fiction)
  103,  -- Wired (tech features)
  109,  -- New Scientist
  114,  -- Stories by Tom Standage on Medium
  124,  -- Planet Backpack (travel)
  125,  -- Mircea Lungu - Stories
  126,  -- HBR.org
  144,  -- Viden | DR
  150,  -- Atlas Magasin
  160,  -- videnskab (Danish science)
  168,  -- Kultur Blog
  169,  -- Artefakte
  170,  -- ausstellungskritik
  172,  -- Reisedepeschen (travel)
  175,  -- Flaneurin
  176,  -- Ekko (Danish film magazine)
  177,  -- Illustreret Videnskab
  179,  -- Historie (Danish history)
  180,  -- Muy Interesante
  181,  -- Vogue España
  183,  -- Viajar Elperiodico
  184,  -- Historia National Geographic
  185,  -- National Geographic en Español
  188,  -- GialloZafferano (recipes)
  189,  -- Stefano Tiozzo (travel)
  190,  -- Irene's Closet (lifestyle blog)
  195,  -- Vogue Italia
  196,  -- il Mulino (Italian political/cultural review)
  197,  -- rollingstone
  198,  -- Limes (geopolitical analysis)
  201,  -- Revista Cultura
  202,  -- Revista România Culturală
  203,  -- National Geographic Portugal
  211,  -- ScienceDaily
  216,  -- Sciences et Avenir
  217,  -- Le Monde - Sciences
  218,  -- Futura Sciences
  219,  -- Pour la Science
  225   -- Les Inrocks
);

-- The following stay as 'unknown' because the title doesn't make
-- the call obvious from outside the editorial frame:
--   167  Arcufo
--   171  snoopsmaus
