from zeeguu.core.model.language import Language
from zeeguu.api.app import create_app
from zeeguu.core.tokenization.tokenizer import ZeeguuTokenizer, TokenizerModel

import os
import time
from pprint import pprint


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


download_method = None
app = create_app()
app.app_context().push()

language = Language.find("fr")
nltk_tokenizer = ZeeguuTokenizer(language, TokenizerModel.NLTK)
stanza_tokenizer = ZeeguuTokenizer(language, TokenizerModel.STANZA_TOKEN_ONLY)

text = """"5 enero 2025 

En un frío día de noviembre, cientos de personas acudieron en masa a un estadio de Coventry, en Reino Unido, que ha acogido en el pasado conciertos de Oasis, Rihanna y Harry Styles, para asistir a un acontecimiento muy diferente. 

Las 500 personas que acudieron -algunas procedentes de lugares tan lejanos como Mongolia y Canadá- participaban en una actividad menos conocida por atraer multitudes: el Campeonato Nacional de "Speedcubing" (armar el cubo de Rubik a una velocidad de vértigo). 

Filas de mesas llenaron el estadio y se celebraron 15 pruebas a lo largo de tres días. En algunas había que resolver el rompecabezas con una mano, en otras con los ojos vendados. El adolescente James Alonso ganó la prueba más importante del torneo: resolver el clásico cubo a toda velocidad, con una media de 6,3 segundos. 

El speedcubing es una actividad popular desde la década de 1980, y el récord mundial de resolución en esa prueba lo ostenta actualmente el estadounidense Max Park, con un tiempo de sólo 3,13 segundos. Está muy lejos de la velocidad inicial de Ernő Rubik, profesor de arquitectura que inventó el cubo de Rubik en 1974 y tardó alrededor de un mes en resolverlo. 

Unas 412.000 personas han participado en competiciones de speedcubing en todo el mundo. Su popularidad también ha aumentado, con unas ventas mundiales de productos del cubo de Rubik de US$86,6 millones en 2023, un 13,5% más que en 2022. (La marca fue adquirida por la multinacional canadiense Spin Master en 2021). 

Eso sin contar las ventas de otros tipos de cubos rompecabezas de diferentes marcas. Algunos son de madera, otros electrónicos con bluetooth incorporado, y luego los hay con todo tipo de diseños coloridos. 

Pero ahora, algunos científicos alaban el speedcubing, no sólo como un pasatiempo popular, sino como uno que también podría tener beneficios para el bienestar. 

"El speedcubing ofrece una combinación única de desafío cognitivo, conexión social y logro personal que contribuye a la felicidad", afirma Polina Beloborodova, investigadora asociada del Centro de Mentes Saludables de la Universidad de Wisconsin-Madison, en Estados Unidos. 

Y ese bienestar va mucho más allá de un simple subidón momentáneo. 

"El speedcubing satisface la necesidad psicológica básica de competencia, sensación de eficacia y dominio", explica Beloborodova. En él intervienen varios factores, como la resolución de problemas, la memoria, el razonamiento espacial y la coordinación motora. 

Según Julia Christensen, investigadora del Instituto Max Planck de Estética Empírica (Alemania), resolver el cubo también puede provocar felicidad, porque despierta otras emociones. "El asombro, la belleza, el sentirse conmovido... son emociones estéticas, y experimentarlas nos produce una sensación extrema de felicidad", explica. 

"Por ejemplo, cuando un patrón es el correcto, cuando un movimiento es particularmente asombroso, estas emociones estéticas pueden brindar experiencias transformadoras". 

Algunas personas que participan en esta actividad describen el estado de ánimo que puede generar como una sensación de "fluidez" o un estado de flujo (conocido también como flow). 

"Este estado se alcanza cuando la dificultad de la actividad se ajusta a tu nivel de habilidad, las distracciones son mínimas, los objetivos están claros y la retroalimentación es inmediata, todas estas características del speedcubing", afirma Beloborodova. 

Según Ian Scheffler, autor de "Descifrando el Cubo", la fluidez puede ser "casi meditativa". "Entras en un estado en el que piensas y no piensas al mismo tiempo: reaccionas a lo que te da el cubo, pero casi de forma instintiva", dice. 

"Es un tipo de atención plena profundamente gratificante... un estado de paz y calma en el que estás completamente en sintonía con cada giro del rompecabezas". 

Según Christensen, hay buenas razones para buscar regularmente un estado de fluidez. "La ciencia demuestra que las personas que lo experimentan con regularidad tienen mejor salud mental, posiblemente mejor salud física, y están más en sintonía. 

"Cuando repetimos movimientos, éstos se registran o codifican desde sistemas de memoria explícitos, que requieren mucho esfuerzo, y pasan a sistemas de memoria implícitos, que requieren menos esfuerzo", prosigue. 

Nicholas Archer, un joven de 17 años de West Yorkshire, en Inglaterra, que ganó la competencia de una mano en el Campeonato de Reino Unido de este año, con un tiempo medio de 8,69 segundos, dice que ha experimentado todo esto. 

"Cuando estoy resolviendo el cubo, desde luego no tengo que pensar demasiado en lo que estoy haciendo. Es todo automático". 

"El speedcubing o resolver un cubo por tu cuenta puede aumentar tu felicidad", señala el Dr. Adil Khan, profesor de neurociencia del King's College de Londres, agregando que cuando se combina con el aspecto social, los beneficios pueden ser mayores. 

"Como es un fenómeno social, quizá el aspecto social se combine con la resolución de rompecabezas para ofrecer una experiencia profundamente satisfactoria". 

Jan Hammer empezó a practicar esta actividad a los 44 años, después de que su hija de 13 se la enseñara. Desde entonces ha resuelto el cubo unas 10.000 veces, pero no cree que hubiera mantenido este nivel de entusiasmo si lo hubiera practicado en solitario. 

"El hecho de poder hacer esto con mi hija y que nos animemos mutuamente es maravilloso. Además, formar parte de la comunidad de los cubos se ha convertido en una enorme motivación". 

En las competiciones suele haber más niños y adolescentes: no es raro que los competidores tengan sólo 6 años. La actividad también es mucho más popular entre los hombres. La Asociación Mundial del Cubo informa de que 221.117 hombres han competido en sus eventos, frente a 24.311 mujeres. 

Independientemente del grupo demográfico, "para quienes consideran el speedcubing una parte importante de su vida -como los participantes en torneos- puede ofrecer felicidad eudemónica, fomentando un sentido de propósito y significado a través de la dedicación, los logros y la comunidad de personas con ideas afines", argumenta Beloborodova. 

Los psicólogos distinguen dos aspectos de la felicidad: el "bienestar hedónico", relacionado con las experiencias emocionales, y el "bienestar eudemónico", que tiene que ver con el sentido y el propósito de la vida. 

"Ambos son esenciales para la felicidad general y el speedcubing puede contribuir a ambos tipos de bienestar", afirma. Todo ello "contribuye a mejorar la salud mental". 

Los efectos del speedcubing en el cerebro y la función cognitiva son, sin embargo, menos claros. 

Mientras resuelve un cubo, el cerebro prueba diferentes movimientos y se pregunta "¿qué puede pasar si muevo el cubo de esta manera? ", explica el Dr. Toby Wise, investigador principal de neuroimagen del King's College de Londres. 

"El cerebro almacena en la memoria distintas configuraciones del cubo y puede probarlas para predecir cuál será la mejor". 

Sin embargo, esto no genera necesariamente beneficios a largo plazo, como mejoras en la función de la memoria. Esto se debe, como explica Khan, a que el cerebro no es como un músculo que hay que flexionar para que crezca. 

Durante muchos años se ha sugerido que resolver rompecabezas, ya sean sudokus o crucigramas, puede contribuir a ralentizar el deterioro cognitivo o la demencia. Sin embargo, esto no es necesariamente cierto. 

Un estudio realizado por la Universidad de Aberdeen y el Aberdeen Royal Infirmary, en Reino Unido, y publicado en la revista  BMJ en 2018, encontró que las personas que realizan actividades intelectuales regularmente a lo largo de la vida tienen capacidades mentales más altas, proporcionando un "punto cognitivo superior" desde el cual declinar, pero que no declinan más lentamente. 

"Casi con toda seguridad no evita el declive de la capacidad cerebral relacionado con la edad", sostiene Khan.
"
 """
print("Got the following text: ", text)
stanza_start = time.time()
stanza_tokens = stanza_tokenizer.tokenize_text(text)
stanza_end = time.time() - stanza_start
nltk_start = time.time()
tokens = nltk_tokenizer.tokenize_text(text)
nltk_end = time.time() - nltk_start
print("Total chars: ", len(text))
print(f"Processing NLTK time: {nltk_end:.2f} seconds, for {len(tokens)} tokens")
print(
    f"Processing stanza time: {stanza_end:.2f} seconds, for {len(stanza_tokens)} tokens"
)
if input("Enter 'n' to skip token details: ") != "n":
    print()
    print("#" * 10 + " NLTK " + "#" * 10)
    for token in tokens:
        pprint(token)
        print("####")
    print("#" * 10 + " stanza " + "#" * 10)
    for token in stanza_tokens:
        pprint(token)
