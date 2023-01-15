#
# This file is part of FortiCfgParser -  A parser for FortiGate Configuration Files
#
# Copyright (C) 2022  Jean Noel Meurisse
# SPDX-License-Identifier: GPL-3.0-only
#

""" FortiCfgParser - A FortiGate configuration file parser """
__version__ = '1.0'

import io

from typing import Optional

from ._config import FgtConfig, FgtConfigRoot
from ._config import FgtConfigObject, FgtConfigTable, FgtConfigSet, FgtConfigUnset, FgtConfigRoot
from ._config import qus, uqs
from ._config import section_object, section_table
from ._parser import FgtConfigRootFactory, FgtConfigParser


def parse_config(config: str, root_factory: Optional[FgtConfigRootFactory] = None) -> FgtConfig:
    """ Parse a FortiGate configuration string.

    :param config: the configuration.
    :param root_factory: a function that returns a FgtRootConfig subclass.
    :return: a `FgtConfig` object
    :raise FgtSyntaxError: if a syntax error is detected
    :raise FgtEosError: if an end of stream is encountered during the parsing.
    """
    with io.StringIO(config) as config_stream:
        return FgtConfigParser.parse(config_stream, root_factory)


def parse_file(file: str, root_factory: Optional[FgtConfigRootFactory] = None) -> FgtConfig:
    """ Parse a FortiGate configuration file.

    :param file: the configuration file name.
    :param root_factory: a function that returns a FgtRootConfig subclass.
    :return: a `FgtConfig` object
    :raise FgtSyntaxError: if a syntax error is detected
    :raise FgtEosError: if an end of stream is encountered during the parsing.
    """
    with io.open(file, "r", encoding='ascii') as config_stream:
        return FgtConfigParser.parse(config_stream, root_factory)
