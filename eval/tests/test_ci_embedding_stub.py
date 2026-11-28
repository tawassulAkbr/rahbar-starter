"""The Kind embedding stub must satisfy the API startup contract."""

import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

from app.config import Settings, resolve_embedding_version
from scripts.ci_embedding_stub import Handler


def test_stub_exposes_embedding_model_digest() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/tags", timeout=5) as response:
            payload = json.load(response)
        assert response.status == 200
        assert payload["models"] == [{
            "name": "dummy-768:latest",
            "digest": "c614de705f0bb491d39a0578ed4110a3a06b1eec1600f8c1c2e1c290db97fe4e",
        }]
        settings = Settings(retriever="chroma", embed_model="dummy-768",
                            ollama_url=f"http://127.0.0.1:{server.server_port}")
        assert resolve_embedding_version(settings).embed_model_version == payload["models"][0]["digest"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
