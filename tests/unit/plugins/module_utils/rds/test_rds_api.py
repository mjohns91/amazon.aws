# (c) 2021 Red Hat Inc.
#
# This file is part of Ansible
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from contextlib import nullcontext
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

try:
    import botocore
except ImportError:
    pass

from ansible_collections.amazon.aws.plugins.module_utils.botocore import HAS_BOTO3
from ansible_collections.amazon.aws.plugins.module_utils.rds import get_final_identifier
from ansible_collections.amazon.aws.plugins.module_utils.rds import get_snapshot
from ansible_collections.amazon.aws.plugins.module_utils.rds import handle_errors

if not HAS_BOTO3:
    pytestmark = pytest.mark.skip("test_rds_api.py requires the python modules 'boto3' and 'botocore'")

mod_api = "ansible_collections.amazon.aws.plugins.module_utils._rds.api"


def helper_expected(x):
    return x, nullcontext()


def helper_error(*args, **kwargs):
    return MagicMock(), pytest.raises(*args, **kwargs)


def build_exception(operation_name, code=None, message=None, http_status_code=None, error=True):
    if not HAS_BOTO3:
        return Exception("MissingBotoCore")
    response = {}
    if error or code or message:
        response["Error"] = {}
    if code:
        response["Error"]["Code"] = code
    if message:
        response["Error"]["Message"] = message
    if http_status_code:
        response["ResponseMetadata"] = {"HTTPStatusCode": http_status_code}

    return botocore.exceptions.ClientError(response, operation_name)


@pytest.mark.parametrize(
    "method_name, params, expected",
    [
        ("create_db_snapshot", {"db_snapshot_identifier": "test"}, "test"),
        (
            "create_db_snapshot",
            {"db_snapshot_identifier": "test", "apply_immediately": True},
            "test",
        ),
        (
            "create_db_instance",
            {
                "db_instance_identifier": "test",
                "new_db_instance_identifier": "test_updated",
            },
            "test",
        ),
        (
            "create_db_snapshot",
            {"db_snapshot_identifier": "test", "apply_immediately": True},
            "test",
        ),
        (
            "create_db_instance",
            {
                "db_instance_identifier": "test",
                "new_db_instance_identifier": "test_updated",
                "apply_immediately": True,
            },
            "test_updated",
        ),
        (
            "create_db_cluster",
            {
                "db_cluster_identifier": "test",
                "new_db_cluster_identifier": "test_updated",
            },
            "test",
        ),
        (
            "create_db_snapshot",
            {"db_snapshot_identifier": "test", "apply_immediately": True},
            "test",
        ),
        (
            "create_db_cluster",
            {
                "db_cluster_identifier": "test",
                "new_db_cluster_identifier": "test_updated",
                "apply_immediately": True,
            },
            "test_updated",
        ),
    ],
)
def test__get_final_identifier(method_name, params, expected):
    module = MagicMock()
    module.params = params
    module.check_mode = False

    assert get_final_identifier(method_name, module) == expected


@pytest.mark.parametrize(
    "method_name, exception, expected",
    [
        (
            "modify_db_instance",
            build_exception(
                "modify_db_instance",
                code="InvalidParameterCombination",
                message="No modifications were requested",
            ),
            False,
        ),
        (
            "promote_read_replica",
            build_exception(
                "promote_read_replica",
                code="InvalidDBInstanceState",
                message="DB Instance is not a read replica",
            ),
            False,
        ),
        (
            "promote_read_replica_db_cluster",
            build_exception(
                "promote_read_replica_db_cluster",
                code="InvalidDBClusterStateFault",
                message="DB Cluster that is not a read replica",
            ),
            False,
        ),
    ],
)
def test__handle_errors(method_name, exception, expected):
    assert handle_errors(MagicMock(), exception, method_name, {}) == expected


@pytest.mark.parametrize(
    "method_name, exception, expected, error",
    [
        (
            "modify_db_instance",
            build_exception(
                "modify_db_instance",
                code="InvalidParameterCombination",
                message="ModifyDbCluster API",
            ),
            *helper_expected(
                "It appears you are trying to modify attributes that are managed at the cluster level. Please see"
                " rds_cluster"
            ),
        ),
        (
            "modify_db_instance",
            build_exception("modify_db_instance", code="InvalidParameterCombination"),
            *helper_error(
                NotImplementedError,
                match=(
                    "method modify_db_instance hasn't been added to the list of accepted methods to use a waiter in"
                    " module_utils/rds.py"
                ),
            ),
        ),
        (
            "promote_read_replica",
            build_exception("promote_read_replica", code="InvalidDBInstanceState"),
            *helper_error(
                NotImplementedError,
                match=(
                    "method promote_read_replica hasn't been added to the list of accepted methods to use a waiter in"
                    " module_utils/rds.py"
                ),
            ),
        ),
        (
            "promote_read_replica_db_cluster",
            build_exception("promote_read_replica_db_cluster", code="InvalidDBClusterStateFault"),
            *helper_error(
                NotImplementedError,
                match=(
                    "method promote_read_replica_db_cluster hasn't been added to the list of accepted methods to use a"
                    " waiter in module_utils/rds.py"
                ),
            ),
        ),
        (
            "create_db_cluster",
            build_exception("create_db_cluster", code="InvalidParameterValue"),
            *helper_expected(
                "DB engine fake_engine should be one of ['aurora', 'aurora-mysql', 'aurora-postgresql', 'mysql', 'postgres']"
            ),
        ),
    ],
)
def test__handle_errors_failed(method_name, exception, expected, error):
    module = MagicMock()

    with error:
        handle_errors(module, exception, method_name, {"Engine": "fake_engine"})
        module.fail_json_aws.assert_called_once()
        assert module.fail_json_aws.call_args[1]["msg"] == expected


@pytest.mark.parametrize(
    "snapshots, snapshot_type, convert_tags, expected",
    [
        ([], "cluster", False, {}),
        ([], "instance", True, {}),
        (
            [{"DBSnapshotIdentifier": "my-snapshot", "DBInstanceIdentifier": "my-instance", "TagList": []}],
            "instance",
            False,
            {"DBSnapshotIdentifier": "my-snapshot", "DBInstanceIdentifier": "my-instance", "TagList": []},
        ),
        (
            [
                {
                    "DBClusterSnapshotIdentifier": "my-cluster-snapshot",
                    "DBClusterIdentifier": "my-cluster",
                    "TagList": [],
                }
            ],
            "cluster",
            True,
            {"DBClusterSnapshotIdentifier": "my-cluster-snapshot", "DBClusterIdentifier": "my-cluster", "Tags": {}},
        ),
        (
            [
                {
                    "DBClusterSnapshotIdentifier": "my-cluster-snapshot",
                    "DBClusterIdentifier": "my-cluster",
                    "TagList": [{"Key": "TagOne", "Value": "Value one"}, {"Key": "tag_two", "Value": "Value two"}],
                }
            ],
            "cluster",
            False,
            {
                "DBClusterSnapshotIdentifier": "my-cluster-snapshot",
                "DBClusterIdentifier": "my-cluster",
                "TagList": [{"Key": "TagOne", "Value": "Value one"}, {"Key": "tag_two", "Value": "Value two"}],
            },
        ),
        (
            [
                {
                    "DBSnapshotIdentifier": "my-snapshot",
                    "DBInstanceIdentifier": "my-instance",
                    "TagList": [{"Key": "TagOne", "Value": "Value one"}, {"Key": "tag_two", "Value": "Value two"}],
                }
            ],
            "instance",
            True,
            {
                "DBSnapshotIdentifier": "my-snapshot",
                "DBInstanceIdentifier": "my-instance",
                "Tags": {"TagOne": "Value one", "tag_two": "Value two"},
            },
        ),
    ],
)
@patch(mod_api + ".describe_db_snapshots")
@patch(mod_api + ".describe_db_cluster_snapshots")
def test_get_snapshot_success(
    m_describe_db_cluster_snapshots, m_describe_db_snapshots, snapshots, snapshot_type, convert_tags, expected
):
    client = MagicMock()
    m_describe_db_cluster_snapshots.return_value = snapshots
    m_describe_db_snapshots.return_value = snapshots
    assert get_snapshot(client, "my-snapshot", snapshot_type, convert_tags) == expected


def test_get_snapshot_error():
    client = MagicMock()
    with pytest.raises(ValueError) as e:
        get_snapshot(client, "my-snapshot", "bad parameter")
    assert "Invalid snapshot_type. Expected one of: ('cluster', 'instance')" in str(e)
