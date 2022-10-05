import tests.covalent_ui_backend_tests.utils.main as main
from tests.covalent_ui_backend_tests.utils.assert_data.logs import seed_logs_data
from tests.covalent_ui_backend_tests.utils.client_template import MethodType, TestClientTemplate

object_test_template = TestClientTemplate()
output_data = seed_logs_data()


def __get_custom_response(case: str):
    test_data = output_data["test_logs"][case]
    request = test_data["request_data"]["query"]
    response = object_test_template(
        api_path=output_data["test_logs"]["api_path"],
        app=main.fastapi_app,
        method_type=MethodType.GET,
        query_data=request,
    )
    return {"response": response.json(), "request": request}


def test_logs(mocker):
    """Test Logs"""
    mocker.patch(
        "covalent_ui.api.v1.data_layer.logs_dal.UI_LOGFILE",
        "tests/covalent_ui_backend_tests/utils/mock_files/log_files/case_a.log",
    )
    test_data = output_data["test_logs"]["case1"]
    response = object_test_template(
        api_path=output_data["test_logs"]["api_path"],
        app=main.fastapi_app,
        method_type=MethodType.GET,
    )
    assert response.status_code == test_data["status_code"]
    if "response_data" in test_data:
        assert response.json() == test_data["response_data"]


def test_logs_with_queries(mocker):
    """Test Logs With Queries"""
    mocker.patch(
        "covalent_ui.api.v1.data_layer.logs_dal.UI_LOGFILE",
        "tests/covalent_ui_backend_tests/utils/mock_files/log_files/case_b.log",
    )
    test_cases = ["case2", "case3", "case4"]
    json_data = [__get_custom_response(case) for case in test_cases]

    # Case 2 Scenario
    assert (
        len(json_data[0]["response"]["items"]) == json_data[0]["request"]["count"]
        and json_data[0]["response"]["total_count"] == 7
    )

    # Case 3 Scenario
    assert len(json_data[1]["response"]["items"]) == (
        json_data[1]["response"]["total_count"] - json_data[1]["request"]["offset"]
    )

    # Case 4 Scenario
    assert len(json_data[2]["response"]["items"]) == 1


def test_non_existing_logs(mocker):
    """Test Missing Logs"""
    mocker.patch(
        "covalent_ui.api.v1.data_layer.logs_dal.UI_LOGFILE",
        "tests/covalent_ui_backend_tests/utils/mock_files/log_files/case_c.log",
    )
    test_data = output_data["test_logs"]["case5"]
    response = object_test_template(
        api_path=output_data["test_logs"]["api_path"],
        app=main.fastapi_app,
        method_type=MethodType.GET,
    )
    assert response.status_code == test_data["status_code"]
    if "response_data" in test_data:
        assert response.json() == test_data["response_data"]


def test_download_log(mocker):
    mocker.patch(
        "covalent_ui.api.v1.data_layer.logs_dal.UI_LOGFILE",
        "tests/covalent_ui_backend_tests/utils/mock_files/log_files/case_b.log",
    )
    test_data = output_data["test_download_logs"]["case1"]
    response = object_test_template(
        api_path=output_data["test_download_logs"]["api_path"],
        app=main.fastapi_app,
        method_type=MethodType.GET,
    )
    assert response.status_code == test_data["status_code"]
    assert isinstance(response.content, bytes)