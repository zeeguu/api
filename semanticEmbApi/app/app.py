from flask import Flask, request, Response
from datetime import datetime

import decimal
import json

app = Flask(__name__)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):

        if isinstance(o, datetime):
            # e.g. "2021-04-26T18:51:47"
            return o.isoformat()

        if isinstance(o, decimal.Decimal):
            return int(o)

        return json.JSONEncoder.default(self, o)


def json_result(dictionary):
    stringified = json.dumps(dictionary, cls=DateTimeEncoder)
    resp = Response(stringified, status=200, mimetype="application/json")
    return resp


@app.route("/get_article_embedding", methods=["POST"])
def get_article_embedding():
    from semantic_vector import semantic_embedding_model

    article_content = request.json.get("article_content", "")
    return json_result(semantic_embedding_model.get_vector(article_content))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
