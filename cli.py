#!/usr/bin/env python3
"""
Menumind CLI — run each pipeline stage from the command line.

Usage:
    python cli.py parse   menu_inputs/cafe.pdf
    python cli.py chunk   parse_output/raw_markdown/cafe_raw.md
    python cli.py embed   chunks.json
    python cli.py ingest  embeddings.json  --collection my_menu
    python cli.py ask     "What vegetarian dishes are available?"
    python cli.py pipeline menu_inputs/cafe.pdf --collection my_menu
"""

import argparse
import json
import logging
import sys
from pathlib import Path


def cmd_parse(args: argparse.Namespace) -> None:
    from parser import MenuParser

    parser = MenuParser(output_dir=args.output)
    path = Path(args.input)

    if path.is_dir():
        results = parser.parse_folder(str(path), extract_fields=args.extract_fields)
        print(f"\nParsed {len(results)} files")
        for r in results:
            print(f"  {r.file_name}: {r.chunks_count} chunks ({r.processing_time:.1f}s)")
    else:
        result = parser.parse_file(str(path), extract_fields=args.extract_fields)
        print(f"\nParsed {result.file_name}: {result.chunks_count} chunks ({result.processing_time:.1f}s)")
        print(f"  Raw markdown: {result.raw_markdown_path}")
        print(f"  JSON: {result.json_path}")


def cmd_chunk(args: argparse.Namespace) -> None:
    from chunker import MenuChunker

    chunker = MenuChunker()
    chunks = chunker.chunk_file(args.markdown, json_path=args.json)

    print(f"\nCreated {len(chunks)} chunks")
    for c in chunks:
        print(f"  [{c.chunk_id}] page={c.page_number} chars={c.char_count} type={c.chunk_type}")

    if args.save:
        out_path = Path(args.save)
        data = {"chunks": [c.to_dict() for c in chunks]}
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved to {out_path}")


def cmd_embed(args: argparse.Namespace) -> None:
    from chunker import Chunk
    from embedder import GeminiEmbedder

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_chunks = data.get("chunks", data if isinstance(data, list) else [])
    chunks = [
        Chunk(
            chunk_id=c.get("chunk_id", i),
            page_number=c.get("page_number", 0),
            text=c["text"],
            chunk_type=c.get("chunk_type", "unknown"),
        )
        for i, c in enumerate(raw_chunks)
    ]

    embedder = GeminiEmbedder()
    embedded = embedder.embed_chunks(chunks, batch_size=args.batch_size)

    out_path = Path(args.output)
    out_data = {
        "model": embedder.model,
        "dimensions": embedder.dimensions,
        "embedded_chunks": [
            {**ec.chunk.to_dict(), "embedding": ec.embedding}
            for ec in embedded
        ],
    }
    out_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nEmbedded {len(embedded)} chunks -> {out_path}")


def cmd_ingest(args: argparse.Namespace) -> None:
    from chunker import Chunk
    from embedder import EmbeddedChunk
    from ingestor import QdrantIngestor

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw = data.get("embedded_chunks", [])
    embedded_chunks = [
        EmbeddedChunk(
            chunk=Chunk(
                chunk_id=c.get("chunk_id", i),
                page_number=c.get("page_number", 0),
                text=c["text"],
                chunk_type=c.get("chunk_type", "unknown"),
            ),
            embedding=c["embedding"],
        )
        for i, c in enumerate(raw)
    ]

    ingestor = QdrantIngestor(collection_name=args.collection)
    if args.recreate:
        vector_size = len(embedded_chunks[0].embedding) if embedded_chunks else 768
        ingestor.ensure_collection(vector_size, recreate=True)

    result = ingestor.ingest(embedded_chunks)
    print(f"\nIngested {result['ingested']} points ({result.get('failed', 0)} failed, {result.get('elapsed_s', 0)}s)")
    info = ingestor.collection_info()
    print(f"Collection '{info['name']}': {info['points']} points, {info['vector_size']}-dim")


def cmd_ask(args: argparse.Namespace) -> None:
    from rag import MenuRAG

    rag = MenuRAG(collection_name=args.collection)
    result = rag.ask(args.question, page_filter=args.page)

    print(f"\n{result['answer']}")
    print(f"\n--- {result['retrieval_count']} docs retrieved, {result['time_s']}s total ---")
    if result.get("sources"):
        print("Sources:")
        for s in result["sources"]:
            print(f"  Page {s['page']} (score {s['score']}): {s['preview'][:100]}...")


def cmd_pipeline(args: argparse.Namespace) -> None:
    """Run the full pipeline: parse -> chunk -> embed -> ingest."""
    from chunker import MenuChunker
    from embedder import GeminiEmbedder
    from ingestor import QdrantIngestor
    from parser import MenuParser

    print("=" * 60)
    print("MENUMIND FULL PIPELINE")
    print("=" * 60)

    # 1. Parse
    print("\n[1/4] Parsing ...")
    parser = MenuParser(output_dir=args.output)
    result = parser.parse_file(str(args.input), extract_fields=True)
    print(f"  -> {result.chunks_count} chunks, {result.processing_time:.1f}s")

    # 2. Chunk
    print("\n[2/4] Chunking ...")
    chunker = MenuChunker()
    chunks = chunker.chunk_file(result.raw_markdown_path, json_path=result.json_path)
    print(f"  -> {len(chunks)} chunks")

    # 3. Embed
    print("\n[3/4] Embedding with Gemini ...")
    embedder = GeminiEmbedder()
    embedded = embedder.embed_chunks(chunks)
    print(f"  -> {len(embedded)} embeddings ({embedder.dimensions}-dim)")

    # 4. Ingest
    print("\n[4/4] Ingesting into Qdrant ...")
    ingestor = QdrantIngestor(collection_name=args.collection)
    if args.recreate:
        ingestor.ensure_collection(embedder.dimensions, recreate=True)
    stats = ingestor.ingest(embedded)
    info = ingestor.collection_info()

    print(f"\nDone! Collection '{info['name']}': {info['points']} points")
    print(f"Ingested {stats['ingested']} new points in {stats.get('elapsed_s', 0)}s")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    ap = argparse.ArgumentParser(prog="menumind", description="Menumind-AI pipeline CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    # --- parse ---
    p = sub.add_parser("parse", help="Parse PDF/image menus into markdown + JSON")
    p.add_argument("input", help="File or folder path")
    p.add_argument("-o", "--output", default="parse_output", help="Output directory")
    p.add_argument("--no-extract", dest="extract_fields", action="store_false", help="Skip field extraction")

    # --- chunk ---
    p = sub.add_parser("chunk", help="Chunk a parsed markdown file")
    p.add_argument("markdown", help="Path to raw markdown file")
    p.add_argument("--json", help="Path to agentic-doc JSON (for element-level chunks)")
    p.add_argument("--save", help="Save chunks to JSON file")

    # --- embed ---
    p = sub.add_parser("embed", help="Embed chunks with Google Gemini")
    p.add_argument("input", help="Chunks JSON file")
    p.add_argument("-o", "--output", default="embeddings.json", help="Output file")
    p.add_argument("--batch-size", type=int, default=100)

    # --- ingest ---
    p = sub.add_parser("ingest", help="Ingest embeddings into Qdrant")
    p.add_argument("input", help="Embeddings JSON file")
    p.add_argument("-c", "--collection", help="Qdrant collection name")
    p.add_argument("--recreate", action="store_true", help="Recreate collection from scratch")

    # --- ask ---
    p = sub.add_parser("ask", help="Ask a question (RAG)")
    p.add_argument("question", help="Your question")
    p.add_argument("-c", "--collection", help="Qdrant collection name")
    p.add_argument("--page", type=int, help="Filter to a specific page number")

    # --- pipeline ---
    p = sub.add_parser("pipeline", help="Run full pipeline: parse -> chunk -> embed -> ingest")
    p.add_argument("input", help="PDF/image file to process")
    p.add_argument("-c", "--collection", help="Qdrant collection name")
    p.add_argument("-o", "--output", default="parse_output", help="Output directory")
    p.add_argument("--recreate", action="store_true", help="Recreate collection from scratch")

    args = ap.parse_args()

    commands = {
        "parse": cmd_parse,
        "chunk": cmd_chunk,
        "embed": cmd_embed,
        "ingest": cmd_ingest,
        "ask": cmd_ask,
        "pipeline": cmd_pipeline,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
