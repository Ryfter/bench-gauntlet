from gauntlet.batteries.embed import cosine, rank_indices, recall_at_k


def test_cosine_identical_and_orthogonal():
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(cosine([1.0, 0.0], [0.0, 1.0]) - 0.0) < 1e-9


def test_cosine_zero_vector_is_zero():
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_indices_orders_by_similarity():
    query = [1.0, 0.0]
    docs = [[0.0, 1.0], [0.9, 0.1], [1.0, 0.0]]
    assert rank_indices(query, docs) == [2, 1, 0]


def test_recall_at_k_counts_relevant_in_top_k():
    rankings = [[2, 1, 0], [0, 2, 1]]   # per-query ranked doc indices
    relevant = [2, 1]                   # query 0 -> doc 2 (rank 0 hit); query 1 -> doc 1 (rank 2 miss@1)
    assert recall_at_k(rankings, relevant, k=1) == 0.5
    assert recall_at_k(rankings, relevant, k=3) == 1.0


def test_run_embed_cell_scores_recall():
    import httpx

    from gauntlet.batteries.embed import run_embed_cell
    from gauntlet.client import OpenAIClient

    vectors = {
        "doc about cats": [1.0, 0.0, 0.0],
        "doc about dogs": [0.0, 1.0, 0.0],
        "doc about cars": [0.0, 0.0, 1.0],
        "feline pet": [0.9, 0.1, 0.0],     # closest to cats
        "automobile": [0.0, 0.1, 0.9],     # closest to cars
    }

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        payload = _json.loads(request.content.decode())
        data = [{"embedding": vectors[text]} for text in payload["input"]]
        return httpx.Response(200, json={"data": data})
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))

    corpus = ["doc about cats", "doc about dogs", "doc about cars"]
    queries = ["feline pet", "automobile"]
    relevant = [0, 2]                      # cats=0, cars=2
    cell = run_embed_cell(client, model="nomic-embed", target="box-b",
                          box="RTX 2070 Super laptop", context=2048,
                          corpus=corpus, queries=queries, relevant=relevant)
    assert cell.capability == "embed"
    assert cell.quality == 1.0            # both queries retrieve the right doc @k=1
    assert cell.cases == 2
