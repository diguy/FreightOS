from app.agent.dify_client import DifySettings


def test_live_chain_settings_do_not_expose_api_key_in_repr():
    settings = DifySettings(
        base_url="http://dify",
        api_key="secret",
    )

    assert "secret" not in repr(settings)
