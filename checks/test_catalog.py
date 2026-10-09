"""保证移植的规则和历史状态没有被绿色工程检查改写。"""
import json
from pathlib import Path
from collections import Counter
from core_specs import SPECS


def catalog():
    return json.loads((Path(__file__).resolve().parents[1] / "首轮套件迁移清单.json").read_text(encoding="utf-8"))


def test_history_counts_are_preserved():
    rows = catalog()["首轮记录"]
    assert len(rows) == 679
    assert Counter(row["首轮状态"] for row in rows) == Counter(
        {"通过": 552, "失败": 21, "已观察（待确认）": 105, "执行受限": 1})


def test_migration_targets_are_unique_and_known():
    rows = [row for row in catalog()["首轮记录"] if row["工程测试编号"]]
    assert len({row["工程测试编号"] for row in rows}) == len(rows)
    assert all(row["模块"] in {s["module"] for s in SPECS} for row in rows)


def test_catalog_contains_no_raw_business_evidence():
    allowed = {"套件", "编号", "模块", "场景", "首轮状态", "运行入口", "迁移状态", "工程测试编号"}
    assert all(set(row) == allowed for row in catalog()["首轮记录"])


def test_specs_do_not_target_users_or_secret_tables():
    # 防止通用CRUD适配误扩展到认证数据或会话存储。
    assert len(SPECS) == 7
    assert {s["table"] for s in SPECS} == {
        "sys_dept", "sys_menu", "sys_post", "sys_dict_type", "sys_dict_data", "sys_config", "sys_notice"}
