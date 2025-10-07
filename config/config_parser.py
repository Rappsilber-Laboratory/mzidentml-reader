"""
config_parser.py
"""

import os
from configparser import ConfigParser


def parse_config(filename, section="postgresql"):
    """
    Parse database.ini file
    :param filename:
    :param section:
    :return:
    """
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    configs = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            configs[param[0]] = param[1]
    else:
        print(
            "Section {0} not found in the {1} file".format(section, filename)
        )
    return configs


def get_conn_str():
    """
    Get database related configurations
    """
    db_info = parse_config(find_config_file())
    hostname = os.environ.get("DB_HOST") or db_info.get("host")
    database = os.environ.get("DB_DATABASE_NAME") or db_info.get("database")
    username = os.environ.get("DB_USER") or db_info.get("user")
    password = os.environ.get("DB_PASSWORD") or db_info.get("password")
    port = os.environ.get("DB_PORT") or db_info.get("port")
    conn_str = (
        f"postgresql://{username}:{password}@{hostname}:{port}/{database}"
    )
    return conn_str


def get_api_configs():
    """
    Get API related configurations
    """
    api_configs = parse_config(find_config_file(), "api")
    config = {
        "base_url": os.environ.get("BASE_URL") or api_configs.get("base_url"),
        "api_key": os.environ.get("API_KEY") or api_configs.get("api_key"),
        "api_key_value": os.environ.get("API_KEY_VALUE")
        or api_configs.get("api_key_value"),
    }
    return config


def find_config_file():
    """
    Find config ini file
    """
    config_file = "database.ini"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config = os.environ.get("DB_CONFIG", os.path.join(script_dir, config_file))
    return config
