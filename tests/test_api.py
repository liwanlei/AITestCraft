#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import json
import time
import unittest
from typing import Optional

import requests


API_BASE_URL = "http://localhost:8000"


class TestHealthEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()
        self.client.headers.update({"Content-Type": "application/json"})

    def test_health_check(self):
        response = self.client.get(f"{self.base_url}/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def tearDown(self):
        self.client.close()


class TestRunTaskEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()

    def _submit_text_task(self, task: str) -> dict:
        response = self.client.post(
            f"{self.base_url}/run",
            data={"task": task}
        )
        return response

    def _submit_doc_url_task(self, doc_url: str) -> dict:
        response = self.client.post(
            f"{self.base_url}/run",
            data={"doc_url": doc_url}
        )
        return response

    def test_submit_text_task_success(self):
        response = self._submit_text_task("生成用户登录功能的测试用例")
        self.assertEqual(response.status_code, 200, f"Response: {response.text}")
        data = response.json()
        self.assertIn("task_id", data)
        self.assertIsInstance(data["task_id"], str)

    def test_submit_text_task_empty_content(self):
        response = self._submit_text_task("")
        self.assertEqual(response.status_code, 422, "空内容应该返回 422")

    def test_submit_task_no_params(self):
        response = self.client.post(f"{self.base_url}/run")
        self.assertEqual(response.status_code, 422, "无参数应该返回 422")

    def test_submit_doc_url_unsupported(self):
        response = self._submit_doc_url_task("https://example.com/unsupported")
        self.assertNotEqual(response.status_code, 200, "不支持的URL应该失败")

    def test_submit_task_with_long_content(self):
        long_content = "测试内容 " * 1000
        response = self._submit_text_task(long_content)
        self.assertIn(response.status_code, [200, 413, 422], "长内容应该返回 200/413/422")

    def tearDown(self):
        self.client.close()


class TestGetStatusEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()
        self.client.headers.update({"Content-Type": "application/json"})

    def test_get_status_not_found(self):
        fake_task_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"{self.base_url}/task/{fake_task_id}")
        self.assertEqual(response.status_code, 404, "不存在的任务应该返回 404")

    def test_get_status_invalid_uuid(self):
        response = self.client.get(f"{self.base_url}/task/invalid-id")
        self.assertIn(response.status_code, [404, 500], "无效UUID应该返回错误")

    def test_get_status_empty_id(self):
        response = self.client.get(f"{self.base_url}/task/")
        self.assertNotEqual(response.status_code, 200, "空ID不应该返回200")


class TestGetResultEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()
        self.client.headers.update({"Content-Type": "application/json"})

    def test_get_result_not_found(self):
        fake_task_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"{self.base_url}/result/{fake_task_id}")
        self.assertEqual(response.status_code, 404, "不存在的任务应该返回 404")

    def test_get_result_invalid_uuid(self):
        response = self.client.get(f"{self.base_url}/result/invalid-id")
        self.assertIn(response.status_code, [404, 500], "无效UUID应该返回错误")


class TestGetLogsEndpoint(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()
        self.client.headers.update({"Content-Type": "application/json"})

    def test_get_logs_not_found(self):
        fake_task_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"{self.base_url}/logs/{fake_task_id}")
        self.assertEqual(response.status_code, 404, "不存在的任务应该返回 404")

    def test_get_logs_structure(self):
        fake_task_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"{self.base_url}/logs/{fake_task_id}")
        if response.status_code == 200:
            data = response.json()
            self.assertIn("task_id", data)
            self.assertIn("logs", data)
            self.assertIn("total", data)


class TestMultiFormatOutput(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()

    def _submit_and_wait(self, task: str, timeout: int = 30) -> Optional[str]:
        response = self.client.post(
            f"{self.base_url}/run",
            data={"task": task}
        )
        if response.status_code != 200:
            return None
        task_id = response.json().get("task_id")
        if not task_id:
            return None

        start_time = time.time()
        while time.time() - start_time < timeout:
            status_response = self.client.get(f"{self.base_url}/task/{task_id}")
            if status_response.status_code == 200:
                status = status_response.json().get("status")
                if status == "success":
                    return task_id
                elif status == "failed":
                    return None
            time.sleep(1)
        return None

    def test_result_contains_multi_format(self):
        task_id = self._submit_and_wait("生成一个简单的加法函数测试用例")
        if not task_id:
            self.skipTest("无法在超时内完成任务，跳过此测试")

        response = self.client.get(f"{self.base_url}/result/{task_id}")
        self.assertEqual(response.status_code, 200, f"Response: {response.text}")

        data = response.json()
        result = data.get("result")
        if result is None:
            self.skipTest("任务结果为空，跳过此测试")

        self.assertIn("json", result)
        self.assertIn("markdown", result)
        self.assertIn("xmind", result)

        xmind = result["xmind"]
        self.assertIn("xmind_8", xmind)
        self.assertIn("xmind_2023", xmind)
        self.assertIn("xmind_8_filename", xmind)
        self.assertIn("xmind_2023_filename", xmind)

    def test_markdown_format_valid(self):
        task_id = self._submit_and_wait("测试用户注册功能")
        if not task_id:
            self.skipTest("无法在超时内完成任务，跳过此测试")

        response = self.client.get(f"{self.base_url}/result/{task_id}")
        if response.status_code != 200:
            self.skipTest("无法获取结果")

        data = response.json()
        result = data.get("result")
        if not result:
            self.skipTest("任务结果为空")

        markdown = result.get("markdown", "")
        self.assertIsInstance(markdown, str)
        if markdown:
            self.assertIn("#", markdown, "Markdown应该包含标题")

    def test_xmind_base64_decodable(self):
        task_id = self._submit_and_wait("测试购物车功能")
        if not task_id:
            self.skipTest("无法在超时内完成任务，跳过此测试")

        response = self.client.get(f"{self.base_url}/result/{task_id}")
        if response.status_code != 200:
            self.skipTest("无法获取结果")

        data = response.json()
        result = data.get("result")
        if not result:
            self.skipTest("任务结果为空")

        xmind = result.get("xmind", {})
        xmind_8_b64 = xmind.get("xmind_8", "")

        if xmind_8_b64:
            try:
                decoded = base64.b64decode(xmind_8_b64)
                self.assertIsInstance(decoded, bytes)
                self.assertGreater(len(decoded), 0, "XMind 数据不应为空")
            except Exception as e:
                self.fail(f"XMind Base64 解码失败: {e}")

    def tearDown(self):
        self.client.close()


class TestEndToEndWorkflow(unittest.TestCase):
    def setUp(self):
        self.base_url = API_BASE_URL
        self.client = requests.Session()

    def test_full_workflow(self):
        task_content = "测试一个计算器应用的加法和减法功能"
        response = self.client.post(
            f"{self.base_url}/run",
            data={"task": task_content}
        )

        self.assertEqual(response.status_code, 200, f"提交任务失败: {response.text}")
        task_data = response.json()
        self.assertIn("task_id", task_data)
        task_id = task_data["task_id"]

        start_time = time.time()
        timeout = 60
        final_status = None

        while time.time() - start_time < timeout:
            status_response = self.client.get(f"{self.base_url}/task/{task_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                final_status = status_data.get("status")
                if final_status in ["success", "failed"]:
                    break
            time.sleep(2)

        self.assertIsNotNone(final_status, "任务未在超时内完成")
        self.assertEqual(final_status, "success", f"任务失败: {final_status}")

        result_response = self.client.get(f"{self.base_url}/result/{task_id}")
        self.assertEqual(result_response.status_code, 200)

        result_data = result_response.json()
        result = result_data.get("result")
        self.assertIsNotNone(result, "结果不应为空")

        json_data = result.get("json", {})
        testcases = json_data.get("testcases", [])
        self.assertIsInstance(testcases, list)

    def tearDown(self):
        self.client.close()


def run_tests():
    print("=" * 70)
    print("AITestCraft API 接口测试")
    print("=" * 70)
    print(f"API 地址: {API_BASE_URL}")
    print(f"注意: 请确保 API 服务正在运行 (python main.py)")
    print("=" * 70)

    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(TestHealthEndpoint))
    suite.addTest(unittest.makeSuite(TestRunTaskEndpoint))
    suite.addTest(unittest.makeSuite(TestGetStatusEndpoint))
    suite.addTest(unittest.makeSuite(TestGetResultEndpoint))
    suite.addTest(unittest.makeSuite(TestGetLogsEndpoint))
    suite.addTest(unittest.makeSuite(TestMultiFormatOutput))
    suite.addTest(unittest.makeSuite(TestEndToEndWorkflow))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"测试总数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print("=" * 70)

    return result


if __name__ == "__main__":
    run_tests()
