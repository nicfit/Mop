import dataclasses

project_name = "Mop"
version      = "0.1.2"
release_name = "Brown Sugar"
author       = "Travis Shirk"
author_email = "travis@pobox.com"
years        = "2020"

@dataclasses.dataclass
class Version:
    major: int
    minor: int
    maint: int
    release: str
    release_name: str

version_info = Version(0, 1, 1, "final", "Avalanche Master Song")