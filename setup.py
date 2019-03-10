#!/usr/bin/env python
import os
import re

from setuptools import setup, find_packages

readme = None
with open("README.rst") as f:
    readme = f.read()

setup(
    name="tempdb",
    version="0.1.0",
    description=(
        "Create temporary databases for testing."
    ),
    long_description=readme,
    author="Andreas Runfalk",
    author_email="andreas@runfalk.se",
    license="MIT",
    url="https://github.com/runfalk/tempdb",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "psycopg2-binary>=2.5",
    ],
    extras_require={
        "dev": [
            "pytest>=3",
        ],
    },
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Testing :: Unit",
    ],
)
