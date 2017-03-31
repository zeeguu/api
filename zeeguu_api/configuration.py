import os


def select_config_file():

    # Loading the default user configuration
    config_file = os.path.expanduser('~/.config/zeeguu/api.cfg')

    # The default config files could be overwritten by the os.environ variable
    if os.environ.has_key("CONFIG_FILE"):
        config_file = os.environ["CONFIG_FILE"]

    print ('running with config file: ' + config_file)

    return config_file
