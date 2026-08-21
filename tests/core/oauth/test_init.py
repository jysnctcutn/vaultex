def test_oauth_package_exports():
    from core.oauth import VaultexOAuthProvider, login_handler

    assert VaultexOAuthProvider is not None
    assert callable(login_handler)
