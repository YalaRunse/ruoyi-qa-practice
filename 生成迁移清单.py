"""从首轮结果生成脱敏场景目录；目录登记不等于重新执行。"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from core_specs import SPECS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    sources = [
        ("全业务", args.source_root / "all_business_runs/20261009_044952/全业务合并结果.json"),
        ("性能与安全", args.source_root / "performance_security_runs/20261009_062738/最终合并结果.json"),
    ]
    metadata, rows = [], []
    modules = {s["module"] for s in SPECS}
    exact = {"正常新增并核对落库": ("test_crud", "正常新增"),
             "详情返回本次新增对象": ("test_crud", "详情查询"),
             "按名称查询精确命中测试对象": ("test_crud", "精确筛选"),
             "正常修改并核对持久化": ("test_crud", "正常修改"),
             "名称为空被拒绝": ("test_invalid_input", "名称为空"),
             "缺少必填字段被拒绝": ("test_invalid_input", "缺少必填字段")}
    for suite, path in sources:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8-sig"))
        metadata.append({"套件": suite, "文件名": path.name, "sha256": hashlib.sha256(raw).hexdigest()})
        for case in value["cases"]:
            # 白名单仅保留用例目录，不复制数据、请求、响应、快照、令牌或口令。
            row = {"套件": suite, "编号": case["number"], "模块": case["module"],
                   "场景": case["name"], "首轮状态": case["status"], "运行入口": [],
                   "迁移状态": "历史证据保留，尚未迁移", "工程测试编号": ""}
            mapped = exact.get(case["name"])
            if re.fullmatch(r"名称\d+字符超界拒绝", case["name"]):
                mapped = ("test_invalid_input", "名称超上限")
            if suite == "全业务" and case["module"] in modules and mapped:
                row["运行入口"] = ["tests/test_core_modules.py"]
                row["迁移状态"] = "常规场景已迁移，工程执行结果另存"
                row["工程测试编号"] = f"tests/test_core_modules.py::{mapped[0]}[{mapped[1]}-{case['module']}]"
            rows.append(row)
    result = {"说明": "679条跨套件历史记录；场景迁移保留首轮状态，不当作679条新执行。",
              "来源": metadata, "首轮记录": rows}
    (root / "首轮套件迁移清单.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    mapped_count = sum(bool(r["运行入口"]) for r in rows)
    print(f"迁移目录生成完成：679条历史记录，{mapped_count}条常规场景已关联工程入口。")


if __name__ == "__main__":
    main()
