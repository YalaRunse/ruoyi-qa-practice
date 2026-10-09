"""只读核对原始结果；输出计数与文件指纹，不复制敏感响应。"""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # 锁定审核过的两份首轮结果，避免 latest 指针变化后误核对另一轮。
    sources = {
        "全业务": ("all_business_runs/20261009_044952/全业务合并结果.json",
                  {"通过": 438, "失败": 18, "已观察（待确认）": 53, "执行受限": 1}),
        "性能与安全": ("performance_security_runs/20261009_062738/最终合并结果.json",
                      {"通过": 114, "失败": 3, "已观察（待确认）": 52}),
    }
    report = {"核对时间": datetime.now().astimezone().isoformat(), "范围": "历史结果一致性核对，不是重新执行业务测试", "套件": []}
    for name, (relative, expected) in sources.items():
        path = args.source_root / relative
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
        counts = dict(Counter(case["status"] for case in data["cases"]))
        if counts != expected or data["counts"] != expected:
            raise RuntimeError(name + "的计数与审核基线不一致")
        # 用例编号在各自套件内唯一，跨套件不声称是独立场景。
        numbers = [case["number"] for case in data["cases"]]
        if len(numbers) != len(set(numbers)):
            raise RuntimeError(name + "套件内用例编号重复")
        report["套件"].append({"名称": name, "记录数": len(numbers), "计数": counts,
                                  "相对证据路径": relative, "sha256": hashlib.sha256(raw).hexdigest()})
    report["跨套件记录数"] = sum(item["记录数"] for item in report["套件"])
    report["说明"] = "679 是跨套件记录数；不能解释为679个独立场景或新增通过数。"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("首轮结果核对完成：全业务510条、性能与安全169条；原始文件未改动。")


if __name__ == "__main__":
    main()
