def test_search_patients_route(client, sample_patient):
    response = client.post("/search/patients", json={"name": sample_patient.name})
    assert response.status_code == 200
    results = response.json()
    assert any(p["name"] == sample_patient.name for p in results)
