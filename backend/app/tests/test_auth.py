def test_local_login_and_logout(client):
    # Login
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "password"})
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Logout
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
