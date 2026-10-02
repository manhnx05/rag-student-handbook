"""Run PDF ingestion from the command line."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ingest_service import IngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a student handbook PDF")
    parser.add_argument("pdf_path", type=Path, help="Path to the PDF document")
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear the Qdrant collection before indexing",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if not args.pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {args.pdf_path}")
    count = await IngestionService.process_pdf_ingestion(
        str(args.pdf_path), clear_existing=args.clear_existing
    )
    print(f"Indexed {count} chunks from {args.pdf_path}")


if __name__ == "__main__":
    asyncio.run(main())
