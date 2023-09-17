# e.g. doing it for polish
import zeeguu.core
from zeeguu.core.model import Article
from zeeguu.core.language.difficulty_estimator_factory import DifficultyEstimatorFactory

print("starting...")

for article in Article.query.filter_by(language_id=13).all():
    print(f"Difficulty before: {article.fk_difficulty} for {article.title} ")
    fk_estimator = DifficultyEstimatorFactory.get_difficulty_estimator("fk")
    fk_difficulty = fk_estimator.estimate_difficulty(
        article.content, article.language, None
    )["grade"]

    article.fk_difficulty = fk_difficulty
    print(f"Difficulty after: {article.fk_difficulty} for {article.title} ")
    print(" ")

    zeeguu.core.model.db.session.add(article)
    zeeguu.core.model.db.session.commit()
