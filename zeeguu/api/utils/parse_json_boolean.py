def parse_json_boolean(value):
    """
    Converts a string to a boolean value.
    Used when parsing from the frontend.
    """
    if value is None:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def get_boolean_from_params(params, name, default=None):
    """
    The boolean form/query parameter `name`, or `default` when the client did
    not send it -- or sent something that is not "true"/"false".

    The default is where the two cases part ways: pass False when an absent
    parameter simply means off, and leave it None when absent has to stay
    distinguishable from false (e.g. a partial update that must not clobber
    a stored value it was never told about).
    """
    value = parse_json_boolean(params.get(name))
    return default if value is None else value
