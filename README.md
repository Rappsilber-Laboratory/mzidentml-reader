# mzidentml-reader
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

mzidentml-reader processes mzIdentML 1.2.0 and 1.3.0 files with the primary aim of extracting crosslink information.
It has three use cases:
1. to validate mzIdentML files against the criteria given here: https://www.ebi.ac.uk/pride/markdownpage/crosslinking
2. to extract information on crosslinked residue pairs and output it in a form more easily used by modelling software
3. to populate the database that is accessed by [crosslinking-api](https://github.com/PRIDE-Archive/crosslinking-api)

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

`process_dataset` is the CLI entry point. Run it with `-h` to see all options:

```
process_dataset -h
```

Alternative (from the repository root):
```
python -m parser -h
```

### CLI Options Reference

One of the following mutually exclusive options is required:

| Option | Description |
|--------|-------------|
| `-p, --pxid <ID> [ID ...]` | ProteomeXchange accession(s), e.g. `PXD000001` or numbers only. Multiple IDs can be space-separated. |
| `-f, --ftp <URL>` | Process files from the specified FTP location. |
| `-d, --dir <PATH>` | Process files in the specified local directory. |
| `-v, --validate <PATH>` | Validate an mzIdentML file or all files in a directory. Exits after first failure. |
| `--seqsandresiduepairs <PATH>` | Extract sequences and crosslinked residue pairs as JSON. Requires `-j`. |

Additional options:

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --temp <PATH>` | Temp folder for downloaded files or the sqlite DB. | System temp directory |
| `-n, --nopeaklist` | Skip peak list file checks. Works with `-d` and `-v` only. | Off |
| `-w, --writer <db\|api>` | Save data to database (`db`) or API (`api`). Used with `-p`, `-f`, `-d`. | `db` |
| `-j, --json <FILE>` | Output JSON filename. Required when using `--seqsandresiduepairs`. | |
| `-i, --identifier <ID>` | Project identifier for the database. Defaults to PXD accession or directory name. | |
| `--dontdelete` | Don't delete downloaded data after processing. | Off |

### 1. Validate a dataset

Run with the `-v` option to validate a dataset. The argument is the path to a specific mzIdentML file
or to a directory containing multiple mzIdentML files, in which case all of them will be validated. To pass, all the peaklist files
referenced must be in the same directory as the mzIdentML file(s). The converter will create an sqlite database in the
temporary folder which is used in the validation process, the temporary folder can be specified with the `-t` option.

Use `-n` to skip peak list file checks (useful when peak list files are not available locally):

Examples:
```
process_dataset -v ~/mydata
```
```
process_dataset -v ~/mydata/mymzid.mzid -t ~/mytempdir
```
```
process_dataset -v ~/mydata/mymzid.mzid -n
```

The result is written to the console. If the data fails validation but the error message is not informative,
please open an issue on the github repository: https://github.com/PRIDE-Archive/mzidentml-reader/issues

### 2. Extract summary of crosslinked residue pairs

Run with the `--seqsandresiduepairs` option to extract a summary of search sequences and
crosslinked residue pairs. The output is JSON which is written to a file specified with the `-j` option (required).
The argument is the path to an mzIdentML file or a directory containing multiple mzIdentML files, in which case
all of them will be processed.

Examples:
```
process_dataset --seqsandresiduepairs ~/mydata -j output.json -t ~/mytempdir
```

```
process_dataset --seqsandresiduepairs ~/mydata/mymzid.mzid -j output.json
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

### 3. Populate the crosslinking-api database

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
process_dataset -d ~/PXD038060
```

The command line options that populate the database are `-d`, `-f` and `-p`. Only one of these can be used.
- `-d` — process files in a local directory
- `-f` — process files from an FTP location
- `-p` — process by ProteomeXchange identifier(s), space-separated

The `-i` option sets the project identifier in the database. It defaults to the PXD accession or the
name of the directory containing the mzIdentML file.

The `-w` option selects the writer method (`db` for database, `api` for API). Defaults to `db`.

Use `--dontdelete` to keep downloaded data after processing.

Examples:
```
process_dataset -p PXD038060
```
```
process_dataset -p PXD038060 PXD000001 -w api
```
```
process_dataset -f ftp://ftp.jpostdb.org/JPST001914/ -i JPST001914
```

### 4. Cleanup noncov modifications

The `cleanup_noncov` module removes invalid crosslink donor/acceptor modifications (`location="-1"`) from mzIdentML files.
This is useful for pre-processing files that contain noncovalent modifications that are not properly located.

#### Programmatic access

```python
from parser.cleanup_noncov import cleanup_noncov, cleanup_noncov_gz

# For plain .mzid files
peps_cleaned, mods_removed, sii_cleaned = cleanup_noncov("input.mzid", "output.mzid")

# For gzipped .mzid.gz files
peps_cleaned, mods_removed, sii_cleaned = cleanup_noncov_gz("input.mzid.gz", "output.mzid.gz")

print(f"Peptides cleaned: {peps_cleaned}")
print(f"Modifications removed: {mods_removed}")
print(f"SpectrumIdentificationItems cleaned: {sii_cleaned}")
```

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
