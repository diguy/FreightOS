from argparse import ArgumentParser
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.etl import build_corpus, write_jsonl


def main() -> None:
    parser = ArgumentParser(description="Extract and chunk local logistics documents.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/knowledge/corpus.jsonl"))
    parser.add_argument("--query-date", default=date.today().isoformat())
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=120)
    args = parser.parse_args()
    chunks = build_corpus(
        args.input,
        args.query_date,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    count = write_jsonl(chunks, args.output)
    print(f"wrote {count} chunks to {args.output}")


if __name__ == "__main__":
    main()
