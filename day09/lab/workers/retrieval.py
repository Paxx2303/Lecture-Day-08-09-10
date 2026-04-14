"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys

# ── Sprint 2 fix: đảm bảo .env được load khi chạy độc lập ──────────
try:
    from dotenv import load_dotenv
    # Tìm .env từ thư mục gốc project (lab/) dù chạy từ workers/
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3

# ── Sprint 2 fix: tên collection đồng nhất với index script ─────────
CHROMA_COLLECTION = "rag_lab"
CHROMA_PATH = "./chroma_db"


def _get_embedding_fn():
    """
    Trả về embedding function.
    Ưu tiên: Sentence Transformers → OpenAI → random (test only).
    """
    # Option A: Sentence Transformers (offline, không cần API key)
    try:
        from sentence_transformers import SentenceTransformer
        print("[retrieval] Loading Sentence Transformers model...")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        def embed(text: str) -> list:
            return model.encode([text])[0].tolist()
        return embed
    except ImportError:
        pass

    # Option B: OpenAI embeddings
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        def embed(text: str) -> list:
            resp = client.embeddings.create(input=text, model="text-embedding-3-small")
            return resp.data[0].embedding
        print("[retrieval] Using OpenAI embeddings.")
        return embed
    except ImportError:
        pass

    # Fallback: random embeddings (KHÔNG dùng production)
    import random
    print("⚠️  WARNING: Using random embeddings (test only). Install sentence-transformers.")
    def embed(text: str) -> list:
        return [random.random() for _ in range(384)]
    return embed


def _get_collection():
    """
    Kết nối ChromaDB collection 'day09_docs'.
    Nếu chưa có data → in warning rõ ràng.

    Sprint 2 fix: đồng nhất tên collection, resolve path từ gốc project.
    """
    import chromadb

    # Resolve path tương đối từ gốc project (lab/) thay vì CWD
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chroma_path = os.path.join(_root, "chroma_db")

    client = chromadb.PersistentClient(path=chroma_path)

    try:
        collection = client.get_collection(CHROMA_COLLECTION)
        count = collection.count()
        if count == 0:
            print(f"⚠️  Collection '{CHROMA_COLLECTION}' rỗng. Chạy index script trước.")
        return collection
    except Exception:
        # Collection chưa tồn tại → tạo mới và báo lỗi rõ
        collection = client.get_or_create_collection(
            CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
        print(
            f"⚠️  Collection '{CHROMA_COLLECTION}' chưa có data.\n"
            f"    Chạy lệnh index trong README (Step 3) để build index trước."
        )
        return collection


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()

        # Kiểm tra collection có data không
        count = collection.count()
        if count == 0:
            print(f"⚠️  ChromaDB rỗng — returning empty (cần chạy index script).")
            return []

        # n_results không được vượt quá số docs trong collection
        actual_top_k = min(top_k, count)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_top_k,
            include=["documents", "distances", "metadatas"]
        )

        chunks = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0]
        ):
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(1 - dist, 4),   # cosine distance → similarity
                "metadata": meta,
            })
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        return []


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task    = state.get("task", "")
    top_k   = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input":  {"task": task, "top_k": top_k},
        "output": None,
        "error":  None,
    }

    try:
        chunks  = retrieve_dense(task, top_k=top_k)
        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"]  = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"]  = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Index helper — chạy 1 lần để build ChromaDB
# ─────────────────────────────────────────────

def build_index(docs_dir: str = None):
    """
    Build ChromaDB index từ thư mục data/docs/.
    Chạy 1 lần trước khi dùng retrieval.

    Usage:
        python workers/retrieval.py --index
    """
    import chromadb
    from sentence_transformers import SentenceTransformer

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if docs_dir is None:
        docs_dir = os.path.join(_root, "data", "docs")

    chroma_path = os.path.join(_root, "chroma_db")

    print(f"[index] docs_dir  : {docs_dir}")
    print(f"[index] chroma_db : {chroma_path}")

    if not os.path.isdir(docs_dir):
        print(f"❌  Thư mục '{docs_dir}' không tồn tại.")
        print(f"    Tạo thư mục và đặt các file .txt vào đó.")
        return

    client = chromadb.PersistentClient(path=chroma_path)
    # Xoá collection cũ nếu có để re-index sạch
    try:
        client.delete_collection(CHROMA_COLLECTION)
        print(f"[index] Deleted old collection '{CHROMA_COLLECTION}'")
    except Exception:
        pass

    collection = client.create_collection(
        CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )

    model = SentenceTransformer("all-MiniLM-L6-v2")

    doc_ids, doc_texts, doc_metas, doc_embeddings = [], [], [], []

    for fname in sorted(os.listdir(docs_dir)):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(docs_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            print(f"  ⚠️  {fname} rỗng — bỏ qua")
            continue

        # Chunk đơn giản: chia theo đoạn (2 newlines), tối đa 500 ký tự
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < 500:
                current += (" " if current else "") + para
            else:
                if current:
                    chunks.append(current)
                current = para
        if current:
            chunks.append(current)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{fname}__chunk{i}"
            embedding = model.encode([chunk])[0].tolist()
            doc_ids.append(chunk_id)
            doc_texts.append(chunk)
            doc_metas.append({"source": fname, "chunk_index": i})
            doc_embeddings.append(embedding)

        print(f"  ✅  {fname} → {len(chunks)} chunks")

    if doc_ids:
        collection.add(
            ids=doc_ids,
            documents=doc_texts,
            metadatas=doc_metas,
            embeddings=doc_embeddings,
        )
        print(f"\n[index] ✅ Indexed {len(doc_ids)} chunks into '{CHROMA_COLLECTION}'")
    else:
        print("[index] ❌ Không có chunks nào được index.")


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--index" in sys.argv:
        build_index()
        sys.exit(0)

    print("=" * 55)
    print("Retrieval Worker — Standalone Test")
    print("(Chạy với --index để build ChromaDB index trước)")
    print("=" * 55)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")