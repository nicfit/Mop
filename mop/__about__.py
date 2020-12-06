# -*- coding: utf-8 -*-
"""
~~~~~~~~~~ DO NOT EDIT THIS FILE! Autogenerated by `regarding` ~~~~~~~~~~
https://github.com/nicfit/regarding
"""
import dataclasses


@dataclasses.dataclass
class Version:
    major: int
    minor: int
    maint: int
    release: str
    release_name: str


project_name = "Mop"
version = "0.1.2a0"
release_name = "Poetry of Fire"
author = "Travis Shirk"
author_email = "travis@pobox.com"
years = "2020"
version_info = Version(
    0, 1, 2,
    "a0", "Poetry of Fire"
)
description = "MPEG ID3 tagger using Python, eyeD3, and GTK+"
homepage = "https://github.com/nicfit/Mop"
