import requests


def retrieve_lingo_rank(text):
    res = requests.get(
        "https://www.wolframcloud.com/obj/929a0113-278c-479d-912a-54ef21b5e0bb",
        params={"x": text},
    )
    # The damn thing returns a ton of digits
    # truncating all but one
    return int(float(res.text) * 10) / 10
