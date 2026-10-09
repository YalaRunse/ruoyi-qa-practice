"""离线核对源码、目录和首轮迁移登记，不连接业务环境。"""
import json
from pathlib import Path
from collections import Counter


def main():
    root = Path(__file__).resolve().parent
    files = [*root.glob("*.py"), *root.glob("checks/*.py"), *root.glob("tests/*.py")]
    # compile仅检查语法，不导入有外部环境依赖的测试代码。
    for path in files:
        compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    manifest = json.loads((root / "首轮套件迁移清单.json").read_text(encoding="utf-8"))
    rows = manifest["首轮记录"]
    assert len(rows) == 679, "首轮记录总数与基线不符"
    keys = [(row["套件"], row["编号"]) for row in rows]
    assert len(set(keys)) == 679, "套件内编号重复"
    counts = Counter(row["首轮状态"] for row in rows)
    assert counts == Counter({"通过": 552, "失败": 21, "已观察（待确认）": 105, "执行受限": 1})
    for row in rows:
        for path in row["运行入口"]:
            assert (root / path).is_file(), "迁移记录引用不存在的入口"
    # 工作流采用JSON兼容YAML，核对语法，不需要额外安装YAML解析器。
    for path in (root / ".github/workflows").glob("*.yml"):
        text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#"))
        workflow = json.loads(text)
        assert "jobs" in workflow and "on" in workflow
    print(f"工程检查通过：{len(files)}个Python文件；679条历史记录；不代表679条重新执行。")


if __name__ == "__main__":
    main()
