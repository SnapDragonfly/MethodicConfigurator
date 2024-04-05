#!/usr/bin/env python3

# This script returns the current version number
# Used as part of building the WIndows setup file (MethodicConfiguratorWinBuild.bat)
# It assumes there is a line like this:
# VERSION = "12344"

# from ..MethodicConfigurator.version import VERSION
# print(VERSION)

# glob supports Unix style pathname extensions
with open("../MethodicConfigurator/version.py", encoding='utf-8') as f:
    searchlines = f.readlines()
    for i, line in enumerate(searchlines):
        if "VERSION = " in line:
            print(line[11:len(line)-2])
            break
