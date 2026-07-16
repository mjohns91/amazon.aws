# (c) 2021 Red Hat Inc.
#
# This file is part of Ansible
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import MagicMock

import pytest

try:
    import botocore
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import HAS_BOTO3
from ansible_collections.amazon.aws.plugins.module_utils.rds import wait_for_cluster_snapshot_status
from ansible_collections.amazon.aws.plugins.module_utils.rds import wait_for_instance_snapshot_status

if not HAS_BOTO3:
    pytestmark = pytest.mark.skip("test_rds_waiters.py requires the python modules 'boto3' and 'botocore'")


@pytest.mark.parametrize("waiter_name", ["", "db_snapshot_available"])
def test__wait_for_instance_snapshot_status(waiter_name):
    wait_for_instance_snapshot_status(MagicMock(), MagicMock(), "test", waiter_name)


@pytest.mark.parametrize("waiter_name", ["", "db_cluster_snapshot_available"])
def test__wait_for_cluster_snapshot_status(waiter_name):
    wait_for_cluster_snapshot_status(MagicMock(), MagicMock(), "test", waiter_name)


@pytest.mark.parametrize(
    "waiter_name, expected",
    [
        (
            "db_snapshot_available",
            "Failed to wait for DB snapshot test to be available",
        ),
        ("db_snapshot_deleted", "Failed to wait for DB snapshot test to be deleted"),
    ],
)
def test__wait_for_instance_snapshot_status_failed(waiter_name, expected):
    spec = {"get_waiter.side_effect": [botocore.exceptions.WaiterError(None, None, None)]}
    client = MagicMock(**spec)
    module = MagicMock()

    wait_for_instance_snapshot_status(client, module, "test", waiter_name)
    module.fail_json_aws.assert_called_once()
    assert module.fail_json_aws.call_args[1]["msg"] == expected


@pytest.mark.parametrize(
    "waiter_name, expected",
    [
        (
            "db_cluster_snapshot_available",
            "Failed to wait for DB cluster snapshot test to be available",
        ),
        (
            "db_cluster_snapshot_deleted",
            "Failed to wait for DB cluster snapshot test to be deleted",
        ),
    ],
)
def test__wait_for_cluster_snapshot_status_failed(waiter_name, expected):
    spec = {"get_waiter.side_effect": [botocore.exceptions.WaiterError(None, None, None)]}
    client = MagicMock(**spec)
    module = MagicMock()

    wait_for_cluster_snapshot_status(client, module, "test", waiter_name)
    module.fail_json_aws.assert_called_once()
    assert module.fail_json_aws.call_args[1]["msg"] == expected
