"""离线核对CI的权限与触发边界，不将本机服务当作云端可访问服务。"""
import json
import re
from pathlib import Path


def load(name):
    path = Path(__file__).resolve().parents[1] / ".github/workflows" / (name + ".yml")
    # 工作流使用JSON兼容的YAML；只去掉文件顶部的说明注释。
    text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#"))
    return json.loads(text)


def test_cloud_checks_have_no_business_credentials():
    value = load("quality")
    job = value["jobs"]["offline-checks"]
    assert job["runs-on"] == "windows-latest"
    assert "RUOYI_TEST_TOKEN" not in json.dumps(value)
    assert "config.local.json" not in json.dumps(value)
    assert value["permissions"] == {"contents": "read"}


def test_local_job_is_manual_and_serial():
    value = load("local-api")
    assert set(value["on"]) == {"workflow_dispatch"}
    assert value["concurrency"]["cancel-in-progress"] is False
    assert value["jobs"]["local-api"]["runs-on"] == ["self-hosted", "Windows", "X64", "ruoyi-qa"]
    assert value["on"]["workflow_dispatch"]["inputs"]["mode"]["default"] == "ReadOnly"


def test_actions_are_pinned_to_commits():
    for name in ("quality", "local-api"):
        for job in load(name)["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
