"""
 * @file loggingsetup.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Sets up logging configuration.
 * 
 * @date Last Modified: 2024-10-23
 * 
 * @copyright Copyright (c) 2024
 * 
 """

import logging

VERBOSE = logging.DEBUG + 1

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def addLoggingLevel(levelName, levelNum, methodName=None):
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        raise AttributeError("{} already defined in logging module".format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError("{} already defined in logging module".format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError("{} already defined in logger class".format(methodName))

    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)

def loggingLevelHandler(level):
    """Changes logging level of 'logger' to debug, verbose, or info, depending on argument.

    Args:
        verbose (int): 1 for INFO, 2 for VERBOSE, 3 for DEBUG.
    """
    if level == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif level == 2:
        logging.getLogger().setLevel(VERBOSE)
    elif level == 3:
        logging.getLogger().setLevel(logging.DEBUG)


addLoggingLevel("TERMINAL", logging.INFO + 1)
addLoggingLevel("SERIAL", logging.INFO + 2)
addLoggingLevel("TIMEOUT", logging.INFO + 3)

addLoggingLevel("VERBOSE", VERBOSE)
