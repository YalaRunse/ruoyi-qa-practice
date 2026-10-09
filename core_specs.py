"""从首轮固定版本设计迁移的模块规则；未知规则不自行补成断言。"""

SPECS = [
    dict(module="部门管理", base="/system/dept", table="sys_dept", pk="dept_id", api_id="deptId",
         name="deptName", db_name="dept_name", limit=30, required="orderNum", listkey="data",
         payload=dict(parentId=101, orderNum=70, leader="测试负责人", phone="", email="", status="0"),
         change=("leader", "更新负责人", "leader"), deleted="del_flag", owner="email"),
    dict(module="菜单管理", base="/system/menu", table="sys_menu", pk="menu_id", api_id="menuId",
         name="menuName", db_name="menu_name", limit=50, required="orderNum", listkey="data",
         payload=dict(parentId=0, orderNum=71, component="system/user/index", menuType="C", isFrame="1",
                      isCache="0", visible="0", status="0", perms="qa:engineering:list", icon="user"),
         change=("visible", "1", "visible")),
    dict(module="岗位管理", base="/system/post", table="sys_post", pk="post_id", api_id="postId",
         name="postName", db_name="post_name", limit=50, required="postSort", listkey="rows",
         payload=dict(postSort=72, status="0"), change=("postSort", 73, "post_sort")),
    dict(module="字典类型", base="/system/dict/type", table="sys_dict_type", pk="dict_id", api_id="dictId",
         name="dictName", db_name="dict_name", limit=100, required="dictType", listkey="rows",
         payload=dict(status="0"), change=("status", "1", "status")),
    dict(module="字典数据", base="/system/dict/data", table="sys_dict_data", pk="dict_code", api_id="dictCode",
         name="dictLabel", db_name="dict_label", limit=100, required="dictValue", listkey="rows",
         payload=dict(dictSort=1, cssClass="", listClass="default", isDefault="N", status="0"),
         change=("dictSort", 2, "dict_sort")),
    dict(module="参数设置", base="/system/config", table="sys_config", pk="config_id", api_id="configId",
         name="configName", db_name="config_name", limit=100, required="configValue", listkey="rows",
         payload=dict(configValue="first_value", configType="N"), change=("configValue", "second_value", "config_value")),
    dict(module="通知公告", base="/system/notice", table="sys_notice", pk="notice_id", api_id="noticeId",
         name="noticeTitle", db_name="notice_title", limit=50, required="noticeTitle", listkey="rows",
         payload=dict(noticeType="1", noticeContent="<p>独立工程验证内容</p>", status="0"),
         change=("noticeContent", "<p>更新内容</p>", "notice_content")),
]

# 仅包含已核对控制器且不会清空缓存或删除历史日志的读取入口。
READ_PATHS = [
    ("登录用户信息", "/getInfo"), ("用户路由", "/getRouters"),
    ("用户管理", "/system/user/list"), ("角色管理", "/system/role/list"),
    ("部门管理", "/system/dept/list"), ("菜单管理", "/system/menu/list"),
    ("岗位管理", "/system/post/list"), ("字典类型", "/system/dict/type/list"),
    ("字典数据", "/system/dict/data/list"), ("参数设置", "/system/config/list"),
    ("通知公告", "/system/notice/list"), ("定时任务", "/monitor/job/list"),
    ("任务日志", "/monitor/jobLog/list"), ("操作日志", "/monitor/operlog/list"),
    ("登录日志", "/monitor/logininfor/list"), ("在线用户", "/monitor/online/list"),
    ("服务监控", "/monitor/server"), ("缓存监控", "/monitor/cache"),
    ("缓存分类", "/monitor/cache/getNames"), ("代码生成列表", "/tool/gen/list"),
]
