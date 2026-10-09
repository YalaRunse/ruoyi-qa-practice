"""验证错误配置会在访问接口之前被拒绝。"""
import pytest
from config import Config


def sample():
    # 使用虚构的隔离名称，这些检查不会连接 Docker 或服务器。
    return dict(url="http://127.0.0.1:18082", database="qa_all_example",
                mysql_container="ruoyi-practice-mysql-1",
                backend_container="qa-all-backend-example", dept_id=105, role_id=2)


@pytest.mark.parametrize("url", ["http://127.0.0.1:18080", "http://127.0.0.1:18081",
                                 "http://example.org:18082", "http://name:secret@127.0.0.1:18082"])
def test_reject_unsafe_target(url):
    # 拦截原实例、远程地址及 URL 内的凭据。
    with pytest.raises(ValueError):
        Config.validate(dict(sample(), url=url))


def test_reject_original_database():
    with pytest.raises(ValueError):
        Config.validate(dict(sample(), database="ry-vue"))


def test_accept_isolated_target():
    assert Config.validate(sample()).database == "qa_all_example"
