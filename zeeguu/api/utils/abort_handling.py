from flask import jsonify


def make_error(
    status_code,
    message,
):
    response = jsonify(
        {
            "message": message,
        }
    )
    response.status_code = status_code
    return response
