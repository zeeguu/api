import flask


class CrossDomainApp(flask.Flask):
    """Allows cross-domain requests for all error pages"""

    def handle_user_exception(self, e):
        rv = super(CrossDomainApp, self).handle_user_exception(e)
        rv = self.make_response(rv)
        rv.headers["Access-Control-Allow-Origin"] = "*"
        return rv
