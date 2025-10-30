# mzidentml-reader
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

mzidentml-reader processes mzIdentML 1.2.0 and 1.3.0 files with the primary aim of extracting crosslink information. 
It has three use cases:
1. to validate mzIdentML files against the criteria given here: https://www.ebi.ac.uk/pride/markdownpage/crosslinking
2. to extract information on crosslinked residue pairs and output it in a form more easily used by modelling software
3. to populate the database that is accessed by [crosslinking-api](https://github.com/Rappsilber-Laboratory/crosslinking-api)

It uses the pyteomics library (https://pyteomics.readthedocs.io/en/latest/index.html) as the underlying parser for mzIdentML.
Results are written into a relational database (PostgreSQL or SQLite) using sqlalchemy.

## Requirements
- Python 3.10 (includes SQLite3 in standard library)
- pipenv (for dependency management)
- PostgreSQL server (optional, only required for crosslinking-api database creation; validation and residue pair extraction use built-in SQLite3)

## Installation

### Production Installation
Install via PyPI:
```bash
pip install mzidentml-reader
```
PyPI project: https://pypi.org/project/mzidentml-reader/

For more installation details, see: https://packaging.python.org/en/latest/tutorials/installing-packages/

### Development Setup
Clone the repository and set up the development environment:

```bash
git clone https://github.com/PRIDE-Archive/mzidentml-reader.git
cd mzidentml-reader
pipenv install --python 3.10 --dev
pipenv shell
```

## Usage

process_dataset.py is the entry point and running it with the -h option will give a list of options.

```
python parser.py -h
```

alternative:
```
python -m parser -h
```


### 1. Validate a dataset

Run process_dataset.py with the -v option to validate a dataset, the argument is the path to a specific mzIdentML file
or to a directory containing multiple mzIdentML files, in which case all of them will be validated. To pass, all the peaklist files 
referenced must be in the same directory as the mzIdentML file(s). The converter will create an sqlite database in the 
temporary folder which is used in the validation process, the temporary folder can be specified with the -t option.  

Examples:
```
python parser.py -v ~/mydata
```
```
python parser.py -v ~/mydata/mymzid.mzid -t ~/mytempdir
```

The result is written to the console. If the data fails validation but the error message is not informative,
please open an issue on the github repository: https://github.com/Rappsilber-Laboratory/mzidentml-reader/issues

### 2. Extract summary of crosslinked residue pairs

Run process_dataset.py with the --seqsandresiduepairs option to extract a summary of search sequences and
crosslinked residue pairs. The output is json which is written to a file specified with the -j option (required).
The argument is the path to an mZIdentML file or a directory containing multiple mzIdentML files, in which case
all of them will be processed.

Examples:
```
python parser.py --seqsandresiduepairs ~/mydata -j output.json -t ~/mytempdir
```

```
python parser.py --seqsandresiduepairs ~/mydata/mymzid.mzid -j output.json
```

#### Programmatic access

The functionality can also be accessed programmatically in Python:

```python
from parser.process_dataset import sequences_and_residue_pairs
import tempfile

# Get sequences and residue pairs as a dictionary
filepath = "/path/to/file.mzid"  # or directory containing .mzid files
tmpdir = tempfile.gettempdir()   # or specify your own temp directory

data = sequences_and_residue_pairs(filepath, tmpdir)

# Iterate through sequences
print(f"Found {len(data['sequences'])} sequences:")
for seq in data['sequences']:
    print(f"  {seq['accession']}: {seq['sequence'][:50]}... (from {seq['file']})")

# Iterate through crosslinked residue pairs
print(f"\nFound {len(data['residue_pairs'])} unique crosslinked residue pairs:")
for pair in data['residue_pairs']:
    print(f"  {pair['prot1_acc']}:{pair['pos1']} <-> {pair['prot2_acc']}:{pair['pos2']}")
    print(f"    Match IDs: {pair['match_ids']}")
    print(f"    Modification accessions: {pair['mod_accs']}")
```

The returned dictionary has two keys:
- `sequences`: List of protein sequences (id, file, sequence, accession)
- `residue_pairs`: List of crosslinked residue pairs (prot1, prot1_acc, pos1, prot2, prot2_acc, pos2, match_ids, files, mod_accs) 

### 3. populate the crosslinking-api database

#### Create the database

```
sudo su postgres;
psql;
create database crosslinking;
create user xiadmin with login password 'your_password_here';
grant all privileges on database crosslinking to xiadmin;
\connect crosslinking;
GRANT ALL PRIVILEGES ON SCHEMA public TO xiadmin;
```

find the hba.conf file in the postgresql installation directory and add a line to allow  the xiadmin role to access the database:
e.g.
```
sudo nano /etc/postgresql/13/main/pg_hba.conf
```
then add the line:
`local   crosslinking   xiadmin   md5`

then restart postgresql:
```
sudo service postgresql restart
```


#### Configure the python environment for the file parser

edit the file mzidentml-reader/config/database.ini to point to your postgressql database.
e.g. so its content is:
```
[postgresql]
host=localhost
database=crosslinking
user=xiadmin
password=your_password_here
port=5432
```

#### Create the database schema 

run create_db_schema.py to create the database tables:
```
python parser/database/create_db_schema.py
```

#### Populate the database
To parse a test dataset:
```
python parser.py -d ~/PXD038060
```

The command line options that populate the database are -d, -f and -p. Only one of these can be used.
The -d option is the directory to process files from,
the -f option is the path to an ftp directory containing mzIdentML files,
the -p option is a ProteomeXchange identifier or a list of ProteomeXchange identifiers separated by spaces.

The -i option is the project identifier to use in the database. It will default to the PXD accession or the 
name of the directory containing the mzIdentML file.



## Development

### Code Quality
This project uses standardized code quality tools:

```bash
# Format code
pipenv run black .

# Sort imports
pipenv run isort .

# Check style and syntax
pipenv run flake8
```

### Testing
Make sure the test database user is available:
```bash
psql -p 5432 -c "create role ximzid_unittests with password 'ximzid_unittests';"
psql -p 5432 -c 'alter role ximzid_unittests with login;'
psql -p 5432 -c 'alter role ximzid_unittests with createdb;'
psql -p 5432 -c 'GRANT pg_signal_backend TO ximzid_unittests;'
```

Run tests with coverage:
```bash
pipenv run pytest  # Run tests with coverage (80% threshold)
pipenv run pytest --cov-report=html  # Generate HTML coverage report
pipenv run pytest -m "not slow"  # Skip slow tests
```
