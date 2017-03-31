import os


def select_config_file():

    # Loading the default user configuration
    config_file = os.path.expanduser('~/.config/zeeguu/api.cfg')

    # The default config files could be overwritten by the os.environ variable
    if os.environ.has_key("CONFIG_FILE"):
        config_file = os.environ["CONFIG_FILE"]

    print ('running with config file: ' + config_file)

    return config_file


def assert_configs(config, required_keys):
    for key in required_keys:
        config_value = config.get(key)
        assert config_value, "Please define the {key} key in the config file!".format(key=key)
