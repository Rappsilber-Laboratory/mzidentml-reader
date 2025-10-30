import logging
from parser import MzIdParser
from parser.DatabaseWriter import DatabaseWriter
from typing import Any

from sqlalchemy import Engine


# noinspection PyUnusedLocal
def parse_mzid_into_postgresql(
    mzid_file: str,
    peaklist: str | bool,
    logger: logging.Logger,
    use_database: bool,
    engine: Engine,
) -> MzIdParser.MzIdParser:
    # create temp user for user_id
    user_id = 1
    # create writer
    writer = DatabaseWriter(engine.url, user_id)
    engine.dispose()

    # parse the mzid file
    id_parser = MzIdParser.MzIdParser(mzid_file, peaklist, writer, logger)
    id_parser.parse()

    # Dispose of the writer's engine to close database connections
    if hasattr(writer, "engine"):
        writer.engine.dispose()

    return id_parser


def parse_mzid_into_sqlite_xispec(
    mzid_file: str, peaklist: str, logger: logging.Logger, engine: Engine
) -> MzIdParser.XiSpecMzIdParser:
    # create writer
    writer = DatabaseWriter(engine.url)
    engine.dispose()

    # parse the mzid file
    id_parser = MzIdParser.XiSpecMzIdParser(
        mzid_file, peaklist, writer, logger
    )
    id_parser.parse()

    # Dispose of the writer's engine to close database connections
    if hasattr(writer, "engine"):
        writer.engine.dispose()

    return id_parser
