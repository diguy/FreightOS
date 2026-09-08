from app.mysql_database import (
    MYSQL_SCHEMA_STATEMENTS,
    MySQLConfig,
    init_mysql_schema,
)


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.closed = False

    def execute(self, statement):
        self.executed.append(statement)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_mysql_config_uses_separate_business_database(monkeypatch):
    monkeypatch.setenv("APP_MYSQL_HOST", "mysql.example")
    monkeypatch.setenv("APP_MYSQL_PORT", "3307")
    monkeypatch.setenv("APP_MYSQL_DATABASE", "logistics")
    monkeypatch.setenv("APP_MYSQL_USER", "app")
    monkeypatch.setenv("APP_MYSQL_PASSWORD", "secret")

    config = MySQLConfig.from_env()

    assert config.host == "mysql.example"
    assert config.port == 3307
    assert config.database == "logistics"
    assert config.user == "app"


def test_init_mysql_schema_executes_all_statements_and_commits():
    connection = FakeConnection()

    init_mysql_schema(connection)

    assert len(connection.cursor_instance.executed) == len(MYSQL_SCHEMA_STATEMENTS)
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.cursor_instance.closed is True
    combined = "\n".join(connection.cursor_instance.executed)
    assert "CREATE TABLE IF NOT EXISTS orders" in combined
    assert "CREATE TABLE IF NOT EXISTS tickets" in combined


def test_init_mysql_schema_rolls_back_on_failure():
    class FailingCursor(FakeCursor):
        def execute(self, statement):
            raise RuntimeError("schema failure")

    connection = FakeConnection()
    connection.cursor_instance = FailingCursor()

    try:
        init_mysql_schema(connection)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected schema failure")

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.cursor_instance.closed is True
