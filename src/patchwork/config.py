"""
Import `default_configuration` var into modules requiring access to default configuration.
"""

import logging
import os
import tomli
from appdirs import AppDirs


new_defaults = """# Please consider backing up this file and ensure you're familiar with toml.
# Patchwork will not be able to load an invalid toml file.

[app]
loglevel = "INFO" # See Python logging module for supported levels
starting_directory = "C:/" # Refer to Resolve's supported colors (case-sensitive)

[render]
render_preset = "H.264 Master"
hide_generic_render_presets = false

[advanced]
advanced_stuff = false
"""

default_configuration = {}


logger = logging.getLogger("rich")
logger.setLevel("INFO")

appdir = AppDirs()
appdir.appauthor = "in03"
appdir.appname = "Patchwork"
config_dir = appdir.user_config_dir

defaults_filepath = os.path.join(config_dir, "defaults.toml")

# TODO: Catch exceptions
if not os.path.exists(defaults_filepath):
    logger.warning(f"[yellow]Bookie default configuration file does not exist. Creating at '{defaults_filepath}'")
    os.makedirs(config_dir, exist_ok=True)
    with open(defaults_filepath, "xb") as new_defaults_file:
        new_defaults_file.write(new_defaults.encode())
   

with open(defaults_filepath, "rb") as defaults_file:
    default_configuration = tomli.load(defaults_file)