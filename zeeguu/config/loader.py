import os

import sys


def load_configuration_or_abort(app, environ_variable, mandatory_config_keys=[]):
    """

        Try to load config from the file named in the environ variable.

        If a config is loaded, the function makes sure that the mandatory_config_keys are
        in the file

    :return: Returns in case of success. Throws exception otherwise.

    """

    # print(">>>>>>>> In load_configuration.......")
    # import traceback
    #
    # traceback.print_stack()

    print("loading configuration...")
    if _called_from_within_a_test(app):
        _load_core_testing_configuration(app)
        _load_api_testing_configuration(app)
        print("ZEEGUU: Loaded testing configuration.")
    else:
        try:
            config_file = _load_config_file(environ_variable, mandatory_config_keys)
            print(f"config file: {config_file}")
            app.config.from_pyfile(config_file, silent=False)
            _assert_configs(app.config, mandatory_config_keys, config_file)
            print(("ZEEGUU: Loaded {0} config from {1}".format(app.name, config_file)))
            print(app.config)
        except Exception as e:
            print(str(e))
            exit(-1)


def _assert_configs(config, required_keys, config_file_name=None):
    for key in required_keys:
        config_value = config.get(key, None)
        if config_value is None:
            print(
                "Please define the {key} key in the {config} file!".format(
                    key=key, config=config_file_name or "config"
                )
            )
            exit(-1)


def _called_from_within_a_test(app):
    res = app.config["TESTING"]
    return res


def _load_core_testing_configuration(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["MAX_SESSION"] = 99999999
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


def _load_api_testing_configuration(app):
    app.config["HOST"] = "0.0.0.0"
    app.config["DEBUG"] = False
    app.config["SECRET_KEY"] = "lalala"


def _load_config_file(environ_variable, mandatory_config_keys):
    try:
        return os.environ[environ_variable]
    except Exception as e:
        print(
            f"You must define an envvar named {environ_variable} which points to a config file which"
        )
        print(f"defines at least the following constants: {mandatory_config_keys}")
        exit(0)
