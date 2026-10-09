"""显式准备本机环境；令牌仅存在于内存和当前进程环境中。"""
import os
import httpx
import pytest
from config import Config
from lab import preflight


def pytest_addoption(parser):
    parser.addoption("--lab-config", default="config.local.json", help="本机隔离配置路径")


@pytest.fixture(scope="session")
def lab_config(request):
    config = Config.load(request.config.getoption("--lab-config"))
    preflight(config)
    return config


@pytest.fixture(scope="session")
def anonymous(lab_config):
    # 禁用代理继承，确保本机接口不会经过外部代理。
    with httpx.Client(base_url=lab_config.url, trust_env=False, timeout=15) as client:
        yield client


@pytest.fixture(scope="session")
def admin(lab_config):
    token = os.getenv("RUOYI_TEST_TOKEN", "").removeprefix("Bearer ").strip()
    if not token:
        pytest.fail("管理员令牌未提供；请手工登录后使用 Users 模式", pytrace=False)
    with httpx.Client(base_url=lab_config.url, trust_env=False, timeout=15,
                      headers={"Authorization": "Bearer " + token}) as client:
        response = client.get("/getInfo")
        body = response.json()
        if response.status_code != 200 or body.get("code") != 200 or body.get("user", {}).get("userId") != 1:
            pytest.fail("令牌失效或不是管理员；未执行写入", pytrace=False)
        yield client
