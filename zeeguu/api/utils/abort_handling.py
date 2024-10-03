from flask import jsonify, make_response


def make_error(
    status_code,
    message,
):
    response = jsonify(
        {
            "message": message,
        }
    )
    return make_response(response, status_code)
