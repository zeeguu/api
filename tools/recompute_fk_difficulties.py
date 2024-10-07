import zeeguu.core
from zeeguu.api.app import create_app
from zeeguu.core.model import Article, Language
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory

app = create_app()
app.app_context().push()

print("starting...")


session = zeeguu.core.model.db.session
with session.begin():
    for article in Article.query.filter(
        Article.language.has(Language.code.in_(["es", "fr", "it", "nl", "ru"]))
    ).all():
        print(f"Article language: {article.language}")
        print(f"Difficulty before: {article.fk_difficulty} for {article.title}")
        fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
        fk_difficulty = fk_estimator.estimate_difficulty(
            article.content, article.language, None
        )["grade"]

        article.fk_difficulty = fk_difficulty
        print(f"Difficulty after: {article.fk_difficulty} for {article.title}\n")

        session.add(article)
    session.commit()
