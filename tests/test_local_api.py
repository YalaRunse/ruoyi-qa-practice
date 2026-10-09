"""代表性接口验证；首轮完整业务证据仍以原工作簿和运行目录为准。"""
import uuid
import pytest
from lab import query


@pytest.mark.parametrize("path", ["/getInfo", "/system/user/list", "/system/role/list"])
def test_anonymous_access_is_rejected(anonymous, path):
    # HTTP 状态与业务码分开核对，不将 HTTP 200 误当业务成功。
    response = anonymous.get(path)
    assert response.status_code == 200, "HTTP 响应与当前固定版本不一致"
    assert response.json().get("code") == 401, "未登录请求未被拒绝"


def test_database_schema_is_ready(lab_config):
    # 只读取表是否存在，不输出用户、密码哈希或历史业务记录。
    rows = query(lab_config, "SELECT COUNT(*) FROM information_schema.tables "
                 "WHERE table_schema=DATABASE() AND table_name IN ('sys_user','sys_user_role','sys_user_post')")
    assert rows == ["3"], "用户及关联表未完整准备"


def business_snapshot(config, exclude_name=None):
    # 指纹仅在进程内比较，断言消息不回显快照内容。
    # 排除参数只允许本工程生成的名字，避免将外部字符串拼进 SQL。
    if exclude_name is not None:
        import re
        if not re.fullmatch(r"qe_[0-9a-f]{16}", exclude_name):
            raise ValueError("临时用户名格式不正确")
    where = f" WHERE user_name<>'{exclude_name}'" if exclude_name else ""
    relation_where = f" WHERE user_id IN (SELECT user_id FROM sys_user{where})" if exclude_name else ""
    users = query(config, "SELECT user_id,dept_id,user_name,nick_name,user_type,email,phonenumber,sex,avatar,"
                  "SHA2(password,256),status,del_flag,login_ip,login_date,pwd_update_date,create_by,"
                  f"create_time,update_by,update_time,remark FROM sys_user{where} ORDER BY user_id")
    roles = query(config, f"SELECT user_id,role_id FROM sys_user_role{relation_where} ORDER BY user_id,role_id")
    posts = query(config, f"SELECT user_id,post_id FROM sys_user_post{relation_where} ORDER BY user_id,post_id")
    return users, roles, posts


@pytest.fixture
def temporary_user(admin, lab_config):
    # 每条用例用独立名字，不依赖其他用例；密码是专门的临时测试数据。
    name = "qe_" + uuid.uuid4().hex[:16]
    body = dict(userName=name, nickName="工程整理临时用户", password="QaTest2026!",
                deptId=lab_config.dept_id, roleIds=[lab_config.role_id], postIds=[],
                status="0", sex="0")
    original = business_snapshot(lab_config, exclude_name=name)
    try:
        yield body
    finally:
        # 即使断言失败，也只清理本条用户名的有效记录，不删除历史数据。
        rows = query(lab_config, f"SELECT user_id FROM sys_user WHERE user_name='{name}' AND del_flag='0'")
        for row in rows:
            uid = int(row)
            if uid in (1, 2, 100):
                raise RuntimeError("清理保护触发")
            result = admin.delete(f"/system/user/{uid}")
            if result.status_code != 200 or result.json().get("code") != 200:
                raise RuntimeError("临时用户清理失败；请按本轮记录检查")
            for table in ("sys_user_role", "sys_user_post"):
                if query(lab_config, f"SELECT COUNT(*) FROM {table} WHERE user_id={uid}") != ["0"]:
                    raise RuntimeError("临时用户关联清理不完整")
        assert query(lab_config, f"SELECT COUNT(*) FROM sys_user WHERE user_name='{name}' AND del_flag='0'") == ["0"], "临时有效用户残留"
        assert bool(business_snapshot(lab_config, exclude_name=name) == original), "清理后原用户或关联发生变化"


def create(admin, body):
    response = admin.post("/system/user", json=body)
    assert response.status_code == 200, "新增请求 HTTP 响应异常"
    assert response.json().get("code") == 200, "新增用户未业务成功"


@pytest.mark.write
def test_created_user_matches_database(admin, lab_config, temporary_user):
    create(admin, temporary_user)
    name = temporary_user["userName"]
    rows = query(lab_config, f"SELECT user_id,dept_id,nick_name,status FROM sys_user WHERE user_name='{name}' AND del_flag='0'")
    assert len(rows) == 1, "新增用户条数不正确"
    uid, dept, nickname, status = rows[0].split("\t")
    assert (dept, nickname, status) == (str(lab_config.dept_id), temporary_user["nickName"], "0")
    assert query(lab_config, f"SELECT role_id FROM sys_user_role WHERE user_id={int(uid)}") == [str(lab_config.role_id)]
    body = admin.get("/system/user/list", params={"userName": name}).json()
    assert body.get("code") == 200
    assert [r["userId"] for r in body.get("rows", []) if r["userName"] == name] == [int(uid)]


@pytest.mark.write
def test_duplicate_user_preserves_data(admin, lab_config, temporary_user):
    create(admin, temporary_user)
    before = business_snapshot(lab_config)
    response = admin.post("/system/user", json=dict(temporary_user, password="Changed2026!"))
    assert response.status_code == 200
    assert response.json().get("code") != 200, "重复用户名未拒绝"
    assert bool(business_snapshot(lab_config) == before), "重复请求改变了用户或关联数据"


@pytest.mark.write
def test_long_nickname_preserves_data(admin, lab_config, temporary_user):
    before = business_snapshot(lab_config)
    response = admin.post("/system/user", json=dict(temporary_user, nickName="测" * 31))
    assert response.status_code == 200
    assert response.json().get("code") != 200, "31字符昵称未拒绝"
    assert bool(business_snapshot(lab_config) == before), "非法昵称请求改变了业务数据"
