"""
 * @file defaultconfig.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Sets up default configuration. Should be loaded in main.py in the event of an error loading config.toml.
 * 
 * @date Last Modified: 2025-1-23
 * 
 * @copyright Copyright (c) 2025
 * 
 """

import logging
import tomllib
from pathlib import Path

config = """
[database]


[calibration]
# Encoder home is the encoder position when the dish is parked (azimuth at true north, elevation straight up).
x_enc_home = -235753513
y_enc_home = 239092664
# Encoder counts per rotation is the amount of counts per 360 degree rotation of the antenna, not the encoder.
x_countsperrotation = 45936033
y_countsperrotation = 45936033

[theme]
ttk = "clearlooks"
select_background = "#00ff00"
clock_font = ['Arial', 15]
terminal_font = ['Courier', 11]
font = ['Arial', 12]
"""

def generateConfig():
    try:
        f = open(Path(__file__).parent.absolute() / 'config.toml', "w")
        f.write(config)
        f.close()
    except Exception as e:
        logging.error('Could not generate config.toml')
        logging.error(e)
    else:
        logging.info('Generating config.toml')

cfg = tomllib.loads(config)