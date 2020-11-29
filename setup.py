#!/usr/bin/env python
from parcyl import Setup

setup = Setup(info_file="mop/__about__.py").with_packages(".", exclude=["test", "test.*"])
setup(package_dir={"": "."},
      platforms=["Any"],
      entry_points={
                  "console_scripts": [
                      "mop = mop.__main__:main",
                  ]
      },
      package_data={
          "mop": ["*.ui"]
      },
      include_package_data=True,
)
