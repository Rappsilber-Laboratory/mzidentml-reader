"""Utilities for decompressing mzIdentML and peak list archive files."""
import gzip
import os
import shutil
import zipfile


def extract_gz(path: str) -> str:
    """Decompress a gzip file, writing the result alongside the original.

    Args:
        path: Path to the .gz file.

    Returns:
        Path to the decompressed file (same path with .gz removed).

    Raises:
        ValueError: If the path does not end with .gz.
    """
    if not path.endswith(".gz"):
        raise ValueError(f"Expected a .gz file, got: {path}")
    out_path = path[:-3]  # strip .gz
    with gzip.open(path, "rb") as in_f, open(out_path, "wb") as out_f:
        shutil.copyfileobj(in_f, out_f)
    return out_path


def extract_zip_safe(zip_file: str, out_dir: str) -> str:
    """Extract a zip archive to out_dir with path-traversal protection.

    Args:
        zip_file: Path to the .zip file.
        out_dir: Directory to extract into (created if it does not exist).

    Returns:
        The out_dir path.

    Raises:
        ValueError: If a zip member would extract outside out_dir.
        IOError: If the zip file cannot be read.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.abspath(out_dir) + os.sep
    with zipfile.ZipFile(zip_file, "r") as zf:
        for member in zf.infolist():
            dest = os.path.abspath(os.path.join(out_dir, member.filename))
            if not dest.startswith(base):
                raise ValueError(f"Illegal path in zip: {member.filename}")
            zf.extract(member, out_dir)
    return out_dir


def extract_mzid_archive(path: str) -> str:
    """Decompress a .mzid.gz or .mzid.zip archive and return the .mzid path.

    Args:
        path: Path to the archive (.mzid.gz or .mzid.zip).

    Returns:
        Path to the extracted .mzid file.

    Raises:
        ValueError: If the path is not a supported archive type, or if a zip
            contains zero or more than one .mzid file.
    """
    if path.endswith(".gz"):
        return extract_gz(path)

    if path.endswith(".zip"):
        out_dir = path + "_unzip"
        extract_zip_safe(path, out_dir)
        mzid_files = []
        for root, dir_names, file_names in os.walk(out_dir):
            dir_names[:] = [d for d in dir_names if not d.startswith(".")]
            for name in file_names:
                if name.startswith("."):
                    continue
                if name.lower().endswith(".mzid"):
                    mzid_files.append(os.path.join(root, name))
                else:
                    raise IOError(f"Unsupported file type in zip: {name}")
        if len(mzid_files) != 1:
            raise ValueError(
                f"Expected exactly one .mzid file in zip, found {len(mzid_files)}: {path}"
            )
        return mzid_files[0]

    raise ValueError(f"Unsupported archive type (expected .gz or .zip): {path}")
