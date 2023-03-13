# Copyright 2021 Agnostiq Inc.
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

"""Tests for Asset"""

import os
import tempfile

import pytest

from covalent_dispatcher._dal.asset import Asset
from covalent_dispatcher._db import models
from covalent_dispatcher._db.datastore import DataStore


@pytest.fixture
def test_db():
    """Instantiate and return an in-memory database."""

    return DataStore(
        db_URL="sqlite+pysqlite:///:memory:",
        initialize_db=True,
    )


def test_asset_load_data():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as temp:
        temp.write("Hello\n")
        temppath = temp.name
        key = os.path.basename(temppath)

    storage_path = "/tmp"
    a = Asset("load_test", storage_path, key)
    assert a.load_data() == "Hello\n"
    os.unlink(temppath)


def test_asset_store_data():
    with tempfile.NamedTemporaryFile("w", delete=True, suffix=".txt") as temp:
        temppath = temp.name
        key = os.path.basename(temppath)
    storage_path = "/tmp"
    a = Asset("store_test", storage_path, key)
    a.store_data("Hello\n")

    with open(temppath, "r") as f:
        assert f.read() == "Hello\n"

    os.unlink(temppath)


def test_upload_asset():
    with tempfile.NamedTemporaryFile("w", delete=True, suffix=".txt") as temp:
        src_path = temp.name
        src_key = os.path.basename(src_path)
    storage_path = "/tmp"
    a = Asset("upload_test", storage_path, src_key)
    a.store_data("Hello\n")

    with tempfile.NamedTemporaryFile("w", delete=True, suffix=".txt") as temp:
        dest_path = temp.name
        dest_key = os.path.basename(dest_path)

    a.upload(dest_path)

    with open(dest_path, "r") as f:
        assert f.read() == "Hello\n"
    os.unlink(dest_path)


def test_download_asset():
    with tempfile.NamedTemporaryFile("w", delete=True, suffix=".txt") as temp:
        src_path = temp.name
        src_key = os.path.basename(src_path)
    with open(src_path, "w") as f:
        f.write("Hello\n")

    storage_path = "/tmp"
    with tempfile.NamedTemporaryFile("w", delete=True, suffix=".txt") as temp:
        dest_path = temp.name
        dest_key = os.path.basename(dest_path)

    a = Asset("download_test", storage_path, dest_key)
    a.set_remote(src_path)

    a.download()

    assert a.load_data() == "Hello\n"

    os.unlink(dest_path)


def test_asset_meta(test_db, mocker):
    dispatch_id = "test_asset_meta"
    with test_db.session() as session:
        lattice_row = models.Lattice(
            dispatch_id="test_asset_meta",
            name="workflow",
            status="NEW_OBJ",
            electron_num=2,
            completed_electron_num=0,
        )
        session.add(lattice_row)

    storage_path = "/tmp"
    object_key = "value.pkl"
    asset_id = storage_path + "/" + object_key
    with test_db.session() as session:
        meta = models.AssetMeta(
            dispatch_id=dispatch_id,
            asset_id=asset_id,
            digest_alg="sha1",
            digest_hex="a234f",
        )
        session.add(meta)

    with test_db.session() as session:
        asset = Asset("asset_meta_1", storage_path, object_key, session)
    assert asset.meta["dispatch_id"] == dispatch_id
    assert asset.meta["digest_hex"] == "a234f"

    with test_db.session() as session:
        asset = Asset("asset_meta_2", storage_path, "nonexistent.pkl", session)
        assert asset.meta == {}
