from app.persistence import file_store, relational_db, vector_store


def test_relational_store_create_and_read():
    relational_db.init_db()
    concept_id = relational_db.create_concept("Test Concept", "created by test")
    row = relational_db.get_concept(concept_id)
    assert row is not None
    assert row["name"] == "Test Concept"


def test_vector_store_create_and_read():
    vector_store.init_vector_store()
    chunk_id = vector_store.insert_embedding(
        document_id="doc-1",
        chunk_text="hello world",
        embedding=[0.1, 0.2, 0.3],
        metadata={"page": 1},
    )
    row = vector_store.get_embedding(chunk_id)
    assert row is not None
    assert row["chunk_text"] == "hello world"
    assert row["embedding"] == [0.1, 0.2, 0.3]


def test_vector_store_search_ranks_closest_first():
    vector_store.init_vector_store()
    vector_store.insert_embedding("doc-1", "close match", [1.0, 0.0, 0.0])
    vector_store.insert_embedding("doc-1", "far match", [0.0, 1.0, 0.0])
    results = vector_store.search([1.0, 0.0, 0.0], top_k=2)
    assert results[0]["chunk_text"] == "close match"


def test_file_store_create_and_read():
    content = b"a test note"
    path = file_store.save_file("notes", "note.txt", content)
    read_back = file_store.read_file(path)
    assert read_back == content
