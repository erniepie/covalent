import base64
import re
from pathlib import Path
from typing import Tuple

from .._shared_files import logger
from .._shared_files.config import get_config

_QE_DB_DATA_MARKER = "<====QELECTRON_DB_DATA====>"
_QE_DB_LOCK_MARKER = "<====QELECTRON_DB_LOCK====>"

_DATA_FILENAME = "data.mdb"
_LOCK_FILENAME = "lock.mdb"

_QE_DB_DIRNAME = ".database"

app_log = logger.app_log


def print_qelectron_db(dispatch_id: str, node_id: int) -> None:
    """
    Check for QElectron database file and dump it into stdout

    Args(s)
        dispatch_id: Dispatch ID of the workflow
        node_id: ID of the node in the transport graph

    Return(s)
        None
    """
    db_dir = Path(get_config("dispatcher")["qelectron_db_path"]).resolve()
    task_subdir = db_dir / dispatch_id / f"node-{node_id}"
    if not task_subdir.exists():
        # qelectron database not found for dispatch_id/node
        return

    with open(task_subdir / _DATA_FILENAME, "rb") as data_mdb_file:
        data_bytes = base64.b64encode(data_mdb_file.read())

    with open(task_subdir / _LOCK_FILENAME, "rb") as lock_mdb_file:
        lock_bytes = base64.b64encode(lock_mdb_file.read())

    output_string = "".join([
        _QE_DB_DATA_MARKER,
        data_bytes.decode(),
        _QE_DB_DATA_MARKER,
        _QE_DB_LOCK_MARKER,
        lock_bytes.decode(),
        _QE_DB_LOCK_MARKER
    ])

    print(output_string)


def extract_qelectron_db(s: str) -> Tuple[str, bytes, bytes]:
    """
    Detect Qelectron data in `s` and process into dict if found

    Arg(s):
        s: captured stdout string from a node in the transport graph

    Return(s):
        s_without_db: captured stdout string without Qelectron data
        bytes_data: bytes representing the `data.mdb` file
        bytes_lock: bytes representing the `lock.mdb` file
    """
    # do nothing if string is empty
    if not s:
        return s, b'', b''

    # check that data exists in the string
    match_data = re.match(f".*{_QE_DB_DATA_MARKER}(.*){_QE_DB_DATA_MARKER}.*", s)
    match_lock = re.match(f".*{_QE_DB_LOCK_MARKER}(.*){_QE_DB_LOCK_MARKER}.*", s)
    if not (match_data and match_lock):
        app_log.debug("No Qelectron data detected")
        return s, b'', b''

    # load qelectron data and convert back to bytes
    app_log.debug("Detected Qelectron output data")
    bytes_data = base64.b64decode(match_data.groups()[0])
    bytes_lock = base64.b64decode(match_lock.groups()[0])

    # remove decoded database bytes from `s`
    s_without_db = remove_qelectron_db(s)

    return s_without_db, bytes_data, bytes_lock


def remove_qelectron_db(output: str):
    """
    Replace the Qelectron DB string in `s` with the empty string.

    Arg:
        s:

    Return:
        the string `s` without any Qelectron database
    """
    for marker in (_QE_DB_DATA_MARKER, _QE_DB_LOCK_MARKER):
        output = re.sub(f"{marker}.*{marker}", "", output)

    return output.strip()


def write_qelectron_db(
    dispatch_id: str,
    node_id: int,
    bytes_data: bytes,
    bytes_lock: bytes,
) -> None:
    """
    Reproduces the Qelectron database inside the results_dir sub-directory for
    given dispatch and node IDs.

    That is, creates the tree

    .database
    └── <dispatch-id>
        └── <node-id>
            ├── data.mdb
            └── lock.mdb

    inside the `results_dir/dispatch_id`.
    """
    results_dir = Path(get_config("dispatcher")["results_dir"]).resolve()

    # create the database directory if it does not exist
    qelectron_db_dir = results_dir / dispatch_id / _QE_DB_DIRNAME
    if not qelectron_db_dir.exists():
        qelectron_db_dir.mkdir()

    # create node subdirectory if it does not exist
    node_dir = qelectron_db_dir / dispatch_id / f"node-{node_id}"
    if not node_dir.exists():
        node_dir.mkdir(parents=True)

    # write 'data.mdb' and 'lock.mdb' files if they do not exist
    data_mdb_path = node_dir / _DATA_FILENAME
    app_log.debug(f"Writing Qelectron database file {str(data_mdb_path)}")
    with open(data_mdb_path, "wb") as data_mdb_file:
        data_mdb_file.write(bytes_data)

    lock_mdb_path = node_dir / _LOCK_FILENAME
    app_log.debug(f"Writing Qelectron database file {str(lock_mdb_path)}")
    with open(lock_mdb_path, "wb") as lock_mdb_file:
        lock_mdb_file.write(bytes_lock)
