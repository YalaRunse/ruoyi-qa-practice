"""整批常规模块验证；每条准备独立对象，通过接口清理自己的数据。"""
import base64
import json
import re
import uuid
import pytest
from core_specs import SPECS, READ_PATHS
from lab import query


def success(response):
    # 不打印响应原文，避免正常读取返回的用户或环境数据进入分享日志。
    assert response.status_code == 200, "HTTP 响应与当前固定版本不一致"
    body = response.json()
    assert body.get("code") == 200, "业务响应未成功"
    return body


def no_diagnostics(body):
    # 完整响应检查；不只查 msg，覆盖SQL异常及纯NPE两种已知披露路径。
    text = json.dumps(body, ensure_ascii=False)
    markers = ("### SQL:", "### Error", "BOOT-INF", "Mapper.xml", "java.lang.",
               "Cannot read the array", "SQLIntegrityConstraintViolationException")
    assert not any(mark in text for mark in markers), "错误响应包含内部诊断"


def table_snapshot(config, spec, marker=None):
    # 字段名与表名只来自固定Spec和库结构；快照留在内存，不写日志。
    columns = query(config, "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                    f"WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{spec['table']}' ORDER BY ORDINAL_POSITION")
    assert columns, "目标表不存在"
    assert all(re.fullmatch(r"[a-zA-Z0-9_]+", name) for name in columns)
    fields = ",".join(f"'{name}',`{name}`" for name in columns)
    owner = spec.get("owner", "remark")
    where = f"WHERE COALESCE({owner},'') NOT LIKE '{marker}%' " if marker else ""
    return query(config, f"SELECT JSON_OBJECT({fields}) FROM {spec['table']} {where}ORDER BY {spec['pk']}")


class Record:
    # 每条的marker保存在备注中；非法名称被错误接受时，也能按归属定位。
    def __init__(self, config, client, spec):
        self.config, self.client, self.spec = config, client, spec
        self.marker = "qe_" + uuid.uuid4().hex[:16]
        self.parent_id = None
        self.body = dict(spec["payload"], remark=self.marker)
        self.body[spec["name"]] = self.marker
        if spec["module"] == "部门管理":
            # 部门表没有remark；用本条专属邮箱定位，修改负责人不会丢失归属。
            self.body["email"] = self.marker + "@example.invalid"
        elif spec["module"] == "菜单管理":
            self.body.update(path=self.marker, routeName="Qe" + self.marker[3:])
        elif spec["module"] == "岗位管理":
            self.body["postCode"] = self.marker
        elif spec["module"] == "字典类型":
            self.body["dictType"] = self.marker
        elif spec["module"] == "字典数据":
            self.body.update(dictType=self.marker, dictValue=self.marker)
        elif spec["module"] == "参数设置":
            self.body["configKey"] = self.marker
        self.before = table_snapshot(config, spec, self.marker)

    def prepare_parent(self):
        # 字典数据独立准备字典类型，不借用系统默认字典，不依赖其他用例。
        if self.spec["module"] == "字典数据":
            success(self.client.post("/system/dict/type", json=dict(
                dictName=self.marker, dictType=self.marker, status="0", remark=self.marker + "_parent")))
            rows = query(self.config, f"SELECT dict_id FROM sys_dict_type WHERE dict_type='{self.marker}'")
            assert len(rows) == 1, "独立父字典准备异常"
            self.parent_id = int(rows[0])

    def ids(self):
        s = self.spec
        owner = s.get("owner", "remark")
        value = self.body[owner]
        where = f"{owner}='{value}'"
        if s.get("deleted"):
            where += f" AND {s['deleted']}='0'"
        return [int(row) for row in query(self.config, f"SELECT {s['pk']} FROM {s['table']} WHERE {where}")]

    def create(self):
        success(self.client.post(self.spec["base"], json=self.body))
        ids = self.ids()
        assert len(ids) == 1, "本条新增对象条数不正确"
        return ids[0]

    def database_value(self, uid, column):
        # 将BLOB等值与普通字段统一为JSON值进行核对。
        s = self.spec
        rows = query(self.config, f"SELECT JSON_OBJECT('value',`{column}`) FROM {s['table']} WHERE {s['pk']}={uid}")
        assert len(rows) == 1
        value = json.loads(rows[0])["value"]
        if isinstance(value, str) and value.startswith("base64:type"):
            value = base64.b64decode(value.rsplit(":", 1)[1]).decode("utf-8")
        return value

    def cleanup(self):
        # 清理严格限定本条备注；不按“新增编号差集”删除未知来源的记录。
        for uid in self.ids():
            success(self.client.delete(f"{self.spec['base']}/{uid}"))
        assert not self.ids(), "本条对象清理后仍有效"
        if self.spec["module"] == "字典数据":
            rows = query(self.config, f"SELECT dict_id FROM sys_dict_type WHERE dict_type='{self.marker}' AND remark='{self.marker}_parent'")
            for row in rows:
                success(self.client.delete(f"/system/dict/type/{int(row)}"))
            assert query(self.config, f"SELECT COUNT(*) FROM sys_dict_type WHERE dict_type='{self.marker}'") == ["0"]
        assert bool(table_snapshot(self.config, self.spec, self.marker) == self.before), "原业务记录发生变化"


@pytest.fixture
def record(spec, lab_config, admin):
    item = Record(lab_config, admin, spec)
    try:
        item.prepare_parent()
        yield item
    finally:
        item.cleanup()


@pytest.mark.write
@pytest.mark.parametrize("spec", SPECS, ids=[s["module"] for s in SPECS])
@pytest.mark.parametrize("action", ["正常新增", "详情查询", "精确筛选", "正常修改"])
def test_crud(spec, action, record):
    uid = record.create()
    assert record.database_value(uid, spec["db_name"]) == record.body[spec["name"]]
    if action == "详情查询":
        before = table_snapshot(record.config, spec)
        data = success(record.client.get(f"{spec['base']}/{uid}"))["data"]
        assert data[spec["api_id"]] == uid and data[spec["name"]] == record.body[spec["name"]]
        assert bool(table_snapshot(record.config, spec) == before), "详情读取改变业务表"
    elif action == "精确筛选":
        before = table_snapshot(record.config, spec)
        params = {spec["name"]: record.body[spec["name"]], "pageNum": 1, "pageSize": 100}
        if spec["module"] == "字典数据":
            params["dictType"] = record.marker
        data = success(record.client.get(spec["base"] + "/list", params=params))
        assert {row[spec["api_id"]] for row in data[spec["listkey"]]} == {uid}
        assert bool(table_snapshot(record.config, spec) == before), "列表读取改变业务表"
    elif action == "正常修改":
        field, value, column = spec["change"]
        payload = dict(record.body, **{spec["api_id"]: uid, field: value})
        success(record.client.put(spec["base"], json=payload))
        assert record.ids() == [uid], "修改改变了对象归属或条数"
        assert record.database_value(uid, column) == value


@pytest.mark.write
@pytest.mark.parametrize("spec", SPECS, ids=[s["module"] for s in SPECS])
@pytest.mark.parametrize("condition", ["名称为空", "名称超上限", "缺少必填字段"])
def test_invalid_input(spec, condition, record):
    payload = dict(record.body)
    if condition == "名称为空":
        payload[spec["name"]] = ""
    elif condition == "名称超上限":
        payload[spec["name"]] = "测" * (spec["limit"] + 1)
    else:
        payload.pop(spec["required"], None)
    before = table_snapshot(record.config, spec)
    response = record.client.post(spec["base"], json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("code") != 200, "非法请求未拒绝"
    assert bool(table_snapshot(record.config, spec) == before), "拒绝请求改变业务数据"
    no_diagnostics(data)


@pytest.mark.parametrize("module,path", READ_PATHS, ids=[s[0] for s in READ_PATHS])
def test_anonymous_read_is_denied(module, path, anonymous):
    response = anonymous.get(path)
    assert response.status_code == 200
    assert response.json().get("code") == 401, "未登录请求访问了受保护读取入口"


@pytest.mark.authenticated
@pytest.mark.parametrize("module,path", READ_PATHS, ids=[s[0] for s in READ_PATHS])
def test_admin_read_is_available(module, path, admin):
    body = success(admin.get(path, params={"pageNum": 1, "pageSize": 10}))
    if "rows" in body:
        assert isinstance(body["rows"], list)
        if "total" in body:
            assert body["total"] >= len(body["rows"])
    # getInfo、服务监控等结构不同；未统一约定的字段不自行增加硬性预期。
