"""由JUnit生成脱敏执行摘要，关联迁移场景但不覆盖首轮状态。"""
import argparse
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    tree = ET.parse(args.run_directory / "结果.xml")
    records = []
    for case in tree.iter("testcase"):
        # 不复制失败堆栈、stdout或响应原文；详情保留在本机证据中。
        state = "准备或清理错误" if case.find("error") is not None else (
            "失败" if case.find("failure") is not None else (
                "跳过" if case.find("skipped") is not None else "通过"))
        node = case.get("classname").replace(".", "/") + ".py::" + case.get("name")
        records.append({"工程测试编号": node, "结果": state, "耗时秒": float(case.get("time", "0"))})
    observed = {record["工程测试编号"]: record["结果"] for record in records}
    catalog = json.loads((root / "首轮套件迁移清单.json").read_text(encoding="utf-8"))
    mapped = [{"套件": row["套件"], "首轮编号": row["编号"], "模块": row["模块"],
               "工程测试编号": row["工程测试编号"], "本轮结果": observed[row["工程测试编号"]]}
              for row in catalog["首轮记录"] if row["工程测试编号"] in observed]
    result = {"生成时间": datetime.now().astimezone().isoformat(), "执行记录数": len(records),
              "计数": dict(Counter(record["结果"] for record in records)),
              "工程执行记录": records, "关联首轮场景": mapped,
              "说明": "工程验证记录；有跨入口重复场景。不追加到首轮业务统计，不覆盖首轮缺陷或观察结论。"}
    (args.run_directory / "执行摘要.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("执行摘要已生成：" + json.dumps(result["计数"], ensure_ascii=False))


if __name__ == "__main__":
    main()
