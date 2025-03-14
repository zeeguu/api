import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, Language
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory

VERBOSE = False
CHECKPOINT_STEP = 10000

app = create_app()
app.app_context().push()

print("starting...")

session = zeeguu.core.model.db.session
articles_to_update = Article.query.filter(
    Article.language.has(Language.code.in_(["es", "fr", "it", "nl", "ru"]))
).all()
for i, article in enumerate(articles_to_update):
    if VERBOSE:
        print(f"Article language: {article.language}")
        print(f"Difficulty before: {article.fk_difficulty} for {article.title}")
    fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
    fk_difficulty = fk_estimator.estimate_difficulty(
        article.get_content(), article.language, None
    )["grade"]

    article.fk_difficulty = fk_difficulty
    if VERBOSE:
        print(f"Difficulty after: {article.fk_difficulty} for {article.title}\n")

    session.add(article)
    if (i + 1) % CHECKPOINT_STEP == 0:
        print("Checkpointing changes, commiting...")
        session.commit()
        print(f"Checkpoint done, completed ({i+1}/{len(articles_to_update)}).")
session.commit()
