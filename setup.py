import codecs
import os.path

from setuptools import find_packages, setup

with open("README.md", encoding="UTF-8") as fh:
    long_description = fh.read()


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(str(here), rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


setup(
    name="mzidentml-reader",
    version="0.4.6",
    description="mzidentml-reader uses pyteomics (https://pyteomics.readthedocs.io/en/latest/index.html) to "
    "parse mzIdentML files (v1.2.0) and extract crosslink information. Results are written to a "
    "relational database (PostgreSQL or SQLite) using sqlalchemy.",
    long_description_content_type="text/markdown",
    long_description=long_description,
    author="Colin Combe, Lars Kolbowski, Suresh Hewapathirana",
    license="'Apache 2.0",
    url="https://github.com/PRIDE-Archive/mzidentml-reader",
    packages=find_packages(),
    include_package_data=True,
    package_data={"config": ["logging.ini"], "schema": ["*.xsd"]},
    install_requires=[
        "lxml>=4.9.1",
        "numpy>=1.14.3",
        "pandas>=0.21.0",
        "pymzml>=0.7.8",
        "pyteomics>=4.7.3",
        "requests>=2.31.0",
        "urllib3>=1.24.2",
        "psycopg2-binary",
        "sqlalchemy>=2.0.38",
        "sqlalchemy-utils",
        "obonet==1.1.0",
        "orjson",
        "certifi>=2023.7.22",
        "python-multipart>=0.0.18",
        "python-jose>=3.3.0",
        "passlib",
        "jose",
    ],
    entry_points={
        "console_scripts": ["process_dataset = parser.process_dataset:main"]
    },
    platforms=["any"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    keywords="crosslinking python proteomics",
    python_requires=">=3.10",
)
