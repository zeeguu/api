from zeeguu.core.model.language import Language
from zeeguu.api.app import create_app

import os
import stanza
import time


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


download_method = None
app = create_app()
app.app_context().push()
en_nlp = stanza.Pipeline("fr")
language = Language.find("fr")
text = """Depuis l’annonce de l’accord, des chauffeurs de camion égyptiens ont convergé vers le point de passage de Rafah pour apporter de la nourriture, de l’eau et du carburant aux Gazaouis. 
 
 GAZA - En file indienne. Dans la ville frontalière égyptienne d’Arish, des convois de camions d’aide humanitaire se préparaient, jeudi 16 janvier, à traverser vers Gaza dès l’ouverture du point de passage de Rafah après l’annonce du prochain cessez-le-feu. Les chauffeurs de camion égyptiens qui attendaient près de la frontière ont exprimé à la fois soulagement et optimisme, beaucoup célébrant la fin imminente des hostilités à Gaza, comme vous pouvez le voir dans la vidéo en tête d’article. 
 
 Un accord de cessez-le-feu et de libération d’otages a été annoncé mercredi pour mettre fin à 15 mois de guerre entre Israël et le Hamas. L’accord, qui doit entrer en vigueur dimanche 19 juin, prévoit un cessez-le-feu initial de six semaines avec le retrait progressif des forces israéliennes de la bande de Gaza, où des dizaines de milliers de personnes ont été tuées. 
 
 Les otages pris par le Hamas lors de l’attaque du 7 octobre 2023 seraient libérés en échange de prisonniers palestiniens détenus par Israël. L’accord prévoit que 600 camions d’aide humanitaire soient autorisés à entrer à Gaza chaque jour du cessez-le-feu, 50 d’entre eux transportant du carburant, 300 camions étant affectés au nord. L’ONU et le Comité international de la Croix-Rouge ont déclaré qu’ils se préparaient à intensifier leurs opérations d’aide. 
 
 Au cours des 15 mois de conflit, l’ONU et les organisations humanitaires ont accusé à maintes reprises Israël de bloquer ou de retarder la distribution de nourriture, de médicaments et de carburant pourtant essentiels, des accusations qu’Israël a démenties. 
 
 Seule une dizaine de camions d’aide humanitaire ont distribué de l’eau et de la nourriture dans le nord de Gaza en deux mois et demi, a encore affirmé en décembre dernier l’ONG Oxfam, ce qu’a démenti Israël, avançant de son côté un chiffre de plus de 2 000 camions. 
 
  :
 """
print("Got the following text: ", text)
stanza_start = time.time()
stanza_tokens = en_nlp(text)
stanza_end = time.time() - stanza_start
print("Total chars: ", len(text))
print(
    f"Processing stanza time: {stanza_end:.2f} seconds, for {stanza_tokens.num_tokens} tokens"
)
if input("Enter 'n' to skip token details: ") != "n":
    print("#" * 10 + " stanza " + "#" * 10)
    for sentence in stanza_tokens.sentences:
        for word in sentence.words:
            print(word)
            print(word.text, word.lemma)
