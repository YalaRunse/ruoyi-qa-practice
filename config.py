"""集中管理本机测试配置；在连接前检查隔离边界。"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Config:
    # 配置文件只保存目标位置，不保存口令和令牌。
    url: str
    database: str
    mysql_container: str
    backend_container: str
    dept_id: int
    role_id: int

    @classmethod
    def load(cls, path):
        return cls.validate(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    @classmethod
    def validate(cls, value):
        target = urlparse(value["url"])
        # 此入口专用于已有的本机隔离副本，拒绝原实例和远程系统。
        if (target.scheme != "http" or target.hostname != "127.0.0.1"
                or target.port != 18082 or target.path not in ("", "/")
                or target.query or target.fragment or target.username or target.password):
            raise ValueError("仅允许 http://127.0.0.1:18082 的隔离副本")
        if not re.fullmatch(r"qa_all_[A-Za-z0-9_]+", value["database"]):
            raise ValueError("数据库必须是 qa_all_ 开头的隔离库")
        for key in ("mysql_container", "backend_container"):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value[key]):
                raise ValueError("容器名称格式不正确")
        if not value["backend_container"].startswith("qa-all-backend-"):
            raise ValueError("后端必须是 qa-all-backend- 开头的隔离容器")
        # 部门和角色编号来自准备好的数据；运行前还会查询其有效性。
        if any(type(value[k]) is not int or value[k] <= 0 for k in ("dept_id", "role_id")):
            raise ValueError("部门和角色编号必须是正整数")
        return cls(**{k: value[k] for k in cls.__dataclass_fields__})
