# 生产运行收尾

## 启动前检查

1. 在 `.env` 中设置 `APP_DATABASE=mysql` 和 `SESSION_STORE=redis`。
2. 确认 `APP_MYSQL_*` 指向业务库，不能指向 RAGFlow 的数据库。
3. 确认 `REDIS_URL` 指向业务会话 Redis。
4. 初始化或迁移数据：

```powershell
poetry run python scripts\init_mysql_schema.py
poetry run python scripts\migrate_sqlite_to_mysql.py
```

## 健康检查

- `/health`：进程存活检查。
- `/health/dependencies`：检查 MySQL 和 Redis 是否可用。

依赖检查失败时会返回 `success: false`，同时隐藏密码和连接字符串。

## 备份

```powershell
$env:MYSQL_BACKUP_DIR="app/data/backups"
poetry run python scripts\backup_mysql.py
```

该脚本要求系统 PATH 中存在 `mysqldump`，密码通过 `MYSQL_PWD` 环境变量传递，
不会出现在进程参数中。Docker 部署可改用：

```powershell
$env:MYSQL_BACKUP_CONTAINER="logistics-mysql"
poetry run python scripts\backup_mysql.py
```

建议至少保留每日备份，并定期执行恢复演练。

## 当前边界

MySQL 连接已使用进程内轻量连接池，默认最小连接数为 1、最大连接数为 5，
可通过 `APP_MYSQL_POOL_MIN_SIZE` 和 `APP_MYSQL_POOL_MAX_SIZE` 调整。
Redis 只保存短期会话状态，订单和工单事实以 MySQL 为准。
