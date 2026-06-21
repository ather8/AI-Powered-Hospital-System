from app.services.search import search_patients

def test_search_patients_by_name(db_session, sample_patient):
    results = search_patients(db_session, name=sample_patient.name)
    assert len(results) == 1
    assert results[0].name == sample_patient.name
