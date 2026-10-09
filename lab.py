"""只读数据库适配与环境核对；不调用历史脚本的导入副作用。"""
import json
import re
import subprocess


def query(config, sql):
    # 所有 SQL 均为本工程固定的 SELECT；写入和清理由业务接口负责。
    if not sql.lstrip().upper().startswith("SELECT ") or ";" in sql:
        raise ValueError("数据库入口仅接受单条 SELECT")
    result = subprocess.run([
        "docker", "exec", "-i", config.mysql_container, "sh", "-c",
        'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql --default-character-set=utf8mb4 '
        '-u"$MYSQL_USER" --batch --raw --skip-column-names "$1"',
        "qa-query", config.database,
    ], input=sql.encode("utf-8"), capture_output=True, timeout=20)
    if result.returncode:
        # 不输出容器环境、SQL 完整结果或数据库原始错误。
        raise RuntimeError("数据库只读查询失败，请检查容器、业务账号授权和配置")
    return result.stdout.decode("utf-8").splitlines()


def preflight(config):
    # 验证端口与 JDBC 目标，防止配置指向隔离库而接口实际指向原库。
    result = subprocess.run(["docker", "inspect", config.backend_container],
                            capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError("隔离后端容器不可用")
    container = json.loads(result.stdout)[0]
    if not container["State"]["Running"]:
        raise RuntimeError("隔离后端容器未运行")
    ports = container["NetworkSettings"]["Ports"].get("8080/tcp") or []
    if not any(p["HostIp"] == "127.0.0.1" and p["HostPort"] == "18082" for p in ports):
        raise RuntimeError("后端端口与隔离配置不一致")
    env = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)
    jdbc = env.get("SPRING_DATASOURCE_DRUID_MASTER_URL", "")
    match = re.match(r"jdbc:mysql://([^/:]+)(?::\d+)?/([^?]+)", jdbc)
    if not match or match[2] != config.database:
        raise RuntimeError("后端实际连接的数据库与本机配置不一致")
    # 同时核对容器网络别名，确认查询和接口连接的是同一 MySQL 实例。
    mysql = subprocess.run(["docker", "inspect", config.mysql_container],
                           capture_output=True, timeout=15)
    if mysql.returncode:
        raise RuntimeError("MySQL 容器不可用")
    mysql_info = json.loads(mysql.stdout)[0]
    common = set(container["NetworkSettings"]["Networks"]) & set(mysql_info["NetworkSettings"]["Networks"])
    if not any(match[1] in (mysql_info["NetworkSettings"]["Networks"][n].get("Aliases") or [])
               for n in common):
        raise RuntimeError("JDBC 主机未匹配目标 MySQL 的共同网络别名")
    if query(config, "SELECT DATABASE()") != [config.database]:
        raise RuntimeError("数据库实际目标不一致")
    if query(config, f"SELECT COUNT(*) FROM sys_dept WHERE dept_id={config.dept_id} AND del_flag='0' AND status='0'") != ["1"]:
        raise RuntimeError("测试部门未准备好")
    if query(config, f"SELECT COUNT(*) FROM sys_role WHERE role_id={config.role_id} AND del_flag='0' AND status='0'") != ["1"]:
        raise RuntimeError("测试角色未准备好")
