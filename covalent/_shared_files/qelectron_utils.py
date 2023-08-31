# Copyright 2023 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

import base64
import re
from pathlib import Path
from typing import Tuple, Union

from ..executor.utils.context import get_context
from .config import get_config
from .logger import app_log

_QE_DB_DATA_MARKER = "<====QELECTRON_DB_DATA====>"
_DATA_FILENAME = "data.mdb"

QE_DB_DIRNAME = ".database"


def _get_qelectron_db_subdir(dispatch_id: str, node_id: Union[int, str]) -> Path:
    """Subdirectory for a given workflow task in the server 'qelectron_db_path'"""
    db_dir = Path(get_config("dispatcher")["qelectron_db_path"]).resolve()
    return db_dir / dispatch_id / f"node-{node_id}"


def _get_results_node_subdir(dispatch_id: str, node_id: Union[int, str]) -> Path:
    """Subdirectory for a given workflow task in the server 'results_dir'"""
    results_dir = Path(get_config("dispatcher")["results_dir"]).resolve()

    # Create DB entry in the "results_dir", if it does not exist.
    qelectron_db_dir = results_dir / dispatch_id / QE_DB_DIRNAME
    if not qelectron_db_dir.exists():
        qelectron_db_dir.mkdir()

    # Create node subdirectory if it does not exist.
    node_dir = qelectron_db_dir / dispatch_id / f"node-{node_id}"
    if not node_dir.exists():
        node_dir.mkdir(parents=True)

    return node_dir


def print_qelectron_db() -> None:
    """
    Check for QElectron database file and dump it into stdout

    Args(s)
        None

    Return(s)
        None
    """
    context = get_context()
    node_id, dispatch_id = context.node_id, context.dispatch_id

    task_subdir = _get_qelectron_db_subdir(dispatch_id, node_id)
    if not task_subdir.exists():
        # QElectron database not found for dispatch_id/node.
        return

    # Create DB entry in the "qelectron_db_path" in case of local execution.
    with open(task_subdir / _DATA_FILENAME, "rb") as data_mdb_file:
        data_bytes = base64.b64encode(data_mdb_file.read())

    output_string = "".join([_QE_DB_DATA_MARKER, data_bytes.decode(), _QE_DB_DATA_MARKER])
    app_log.debug(f"Printing Qelectron data for node_id {node_id}")
    print(output_string)


def extract_qelectron_db(s: Union[None, str]) -> Tuple[str, bytes]:
    """
    Detect Qelectron data in `s` and process into dict if found

    Arg(s):
        s: captured stdout string from a node in the transport graph

    Return(s):
        s_without_db: captured stdout string without Qelectron data
        bytes_data: bytes representing the `data.mdb` file
    """
    # Do nothing if string is empty or no database bytes found in the `s`.
    data_pattern = f".*{_QE_DB_DATA_MARKER}(.*){_QE_DB_DATA_MARKER}.*"
    if not s or not (_matches := re.findall(data_pattern, s)):
        app_log.debug(f"No Qelectron data detected in '{s!s}'")
        return s, b""

    # Load qelectron data and convert back to bytes.
    app_log.debug("Detected Qelectron output data")
    bytes_data = base64.b64decode(_matches.pop())

    # Remove decoded database bytes from `s`.
    s_without_db = remove_qelectron_db(s)

    return s_without_db, bytes_data


def remove_qelectron_db(output: str):
    """
    Replace the Qelectron DB string in `s` with the empty string.

    Arg:
        s:

    Return:
        the string `s` without any Qelectron database
    """
    output = re.sub(f"{_QE_DB_DATA_MARKER}.*{_QE_DB_DATA_MARKER}", "", output)
    return output.strip()


def write_qelectron_db(
    dispatch_id: str,
    node_id: int,
    bytes_data: bytes,
) -> None:
    """
    Reproduces the Qelectron database inside the results_dir sub-directory for
    given dispatch and node IDs.

    That is, creates the tree

    .database
    └── <dispatch-id>
        └── <node-id>
            └── data.mdb

    inside the `results_dir/dispatch_id`.
    """

    # Create DB entry in the "results_dir", if it does not exist.
    node_dir = _get_results_node_subdir(dispatch_id, node_id)

    # Write "data.mdb" file.
    data_mdb_path = node_dir / _DATA_FILENAME
    app_log.debug(f"Writing Qelectron database file in results: {str(data_mdb_path)}")
    with open(data_mdb_path, "wb") as data_mdb_file:
        data_mdb_file.write(bytes_data)

    # Create DB entry in the "qelectron_db_path" in case of remote execution.
    task_subdir = _get_qelectron_db_subdir(dispatch_id, node_id)
    data_mdb_path = task_subdir / _DATA_FILENAME
    if task_subdir.exists():
        app_log.debug(
            f"Task subdirectory already exists in qelectron_db_path: {str(data_mdb_path)}"
        )
    else:
        # Create task subdirectory.
        task_subdir.mkdir(parents=True)
        app_log.debug(
            f"Writing Qelectron database file in qelectron_db_path: {str(data_mdb_path)}"
        )

        # Write "data.mdb" file.
        with open(data_mdb_path, "wb") as server_data_mdb_file:
            server_data_mdb_file.write(bytes_data)