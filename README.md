# xi-mzidentml-converter
![python-app](https://github.com/Rappsilber-Laboratory/xi-mzidentml-converter/actions/workflows/python-app.yml/badge.svg)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

xi-mzidentml-converter processes mzIdentML 1.2.0 and 1.3.0 files with the primary aim of extracting crosslink information. 
It has three use cases:
1. to validate mzIdentML files against the criteria given here: https://www.ebi.ac.uk/pride/markdownpage/crosslinking
2. to extract information on crosslinked resiude pairs and output it in a form more easily used by modelling software
3. to populate the database that is accessed by [xiview-api](https://github.com/Rappsilber-Laboratory/xiview-api)

It uses the pyteomics library (https://pyteomics.readthedocs.io/en/latest/index.html) as the underlying parser for mzIdentML.
Results are written into a relational database (PostgreSQL or SQLite) using sqlalchemy.

## Requirements:
python3.10

pipenv

sqlite3 for validation and residue pair extraction. postgresql or sqlite3 for creation of xiview-api dtabase 
(the instructions below use posrgresql)

## Installation

Clone git repository and set up python envorment or install via PYPI:

```
git clone https://github.com/Rappsilber-Laboratory/xi-mzidentml-converter.git
cd x-mzidentml-converter
pipenv install --python 3.10
```

PYPI project: https://pypi.org/project/xi-mzidentml-converter/

PYPI instructions: https://packaging.python.org/en/latest/tutorials/installing-packages/

## Usage

proceess_dataset.py is the entry point and running it with the -h option will give a list of options.

```
python parser.py -h
```

alternative:
```
python -m parser -h
```


### 1. Validate a dataset

Run processdataset.py with the -v option to validate a dataset, the argument is the path to a specific mzIdentML file 
or to a directory conatining multiple mzIdentML files, in which case all of them will be validated. To pass, all the peaklist files 
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
please open an issue on the github repository: https://github.com/Rappsilber-Laboratory/xi-mzidentml-converter/issues

### 2. Extract summary of crosslinked residue pairs 

Run processdataset.py with the --seqsandresiduepairs option to extract a summary of search sequences and
crosslinked residue pairs. The output is json which is written to the console. The argument is the path to an mZIdentML 
file or a directory containing multiple mzIdentML files, in which case all of them will be processed.   

Examples:
```
python parser.py --seqsandresiduepairs ~/mydata -t ~/mytempdir
```

```
python parser.py --seqsandresiduepairs ~/mydata/mymzid.mzid
```

It can also be accessed programitically by using the 
`json_sequences_and_residue_pairs(filepath, tmpdir)` function in parser.py. 

### 3. populate the xiview-api database

#### Create the database

```
sudo su postgres
psql
create database xiview;
create user xiadmin with login password 'your_password_here';
grant all privileges on database xiview to xiadmin;
\connect xiview;
GRANT ALL PRIVILEGES ON SCHEMA public TO xiadmin;
```

find the hba.conf file in the postgresql installation directory and add a line to allow  the xiadmin role to access the database:
e.g.
```
sudo nano /etc/postgresql/13/main/pg_hba.conf
```
then add the line:
`local   xiview   xiadmin   md5`

then restart postgresql:
```
sudo service postgresql restart
```


#### Configure the python environment for the file parser

edit the file xi-mzidentml-converter/config/database.ini to point to your postgressql database.
e.g. so its content is:
```
[postgresql]
host=localhost
database=xitest
user=xiadmin
password=your_password_here
port=5432
```

#### Create the database schema 

run create_db_schema.py to create the database tables:
```
python database/create_db_schema.py
```

#### Populate the database
To parse a test dataset:
```
python parser.py -d ~/PXD038060
```

The command line options that populate the database are -d, -f and -p. Only one of these can be used.
The -d option is the directory to process files from, 
the -f option is the path to an ftp directory conatining mzIdentML files, 
the -p option is a ProteomeXchange identifier or a list of ProteomeXchange identifiers separated by spaces.

The -i option is the project identifier to use in the database. It will default to the PXD accession or the 
name of the directory containing the mzIdentML file.



## To run tests

Make sure we have the right db user available
```
psql -p 5432 -c "create role ximzid_unittests with password 'ximzid_unittests';"
psql -p 5432 -c 'alter role ximzid_unittests with login;'
psql -p 5432 -c 'alter role ximzid_unittests with createdb;'
psql -p 5432 -c 'GRANT pg_signal_backend TO ximzid_unittests;'
```
run the tests

```pipenv run pytest```
