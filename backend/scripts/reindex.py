"""Rebuild the retrieval corpora.

Corpus A is re-indexed on every app boot without embeddings, so the app is
immediately usable with lexical ranking. This script is the deliberate,
network-touching version: it attaches embedding vectors, which costs API calls
and so should not happen on a cold start.

Usage, from ``backend/``:

    python -m scripts.reindex                  # Corpus A, with embeddings
    python -m scripts.reindex --no-embed       # Corpus A, lexical only
    python -m scripts.reindex --users          # also refresh every learner's Corpus B
    python -m scripts.reindex --stats          # just report what is indexed
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.db import SessionLocal, init_models
from app.models import User
from app.services import indexer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reindex")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild DolFin's retrieval corpora.")
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embeddings and rely on the lexical ranker.",
    )
    parser.add_argument(
        "--users",
        action="store_true",
        help="Also refresh Corpus B for every learner.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Report index contents and exit without writing.",
    )
    args = parser.parse_args()

    init_models()
    embed = not args.no_embed

    with SessionLocal() as db:
        if args.stats:
            for key, value in indexer.corpus_stats(db).items():
                print(f"{key:>14}: {value}")
            return 0

        result = indexer.reindex_corpus_a(db, embed=embed)
        print(
            f"Corpus A: {result['total']} chunks "
            f"({result['inserted']} new, {result['updated']} updated, "
            f"{result['deleted']} removed, {result['embedded']} embedded)"
        )

        if args.users:
            users = db.query(User).all()
            for user in users:
                res = indexer.refresh_corpus_b(db, user, embed=embed)
                print(f"Corpus B for {user.id}: {res['total']} chunks")
            print(f"Refreshed {len(users)} learner corpus(es).")

        stats = indexer.corpus_stats(db)
        print(f"Ranking mode: {stats['ranking']} ({stats['embedded']} vectors stored)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
