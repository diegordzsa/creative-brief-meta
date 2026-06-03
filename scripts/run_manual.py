#!/usr/bin/env python3
"""Hair Biolabs Brief Generation System — CLI Entry Point"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import analyze_video, export_to_google_docs, save_to_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def run(video_url: str, dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("Hair Biolabs Brief Generation System")
    logger.info(f"  Video URL: {video_url}")
    logger.info(f"  Dry run: {dry_run}")
    logger.info("=" * 60)

    result = analyze_video(video_url)

    analysis = result["analysis"]
    briefs = result["briefs"]

    logger.info(f"\n--- Classification ---")
    logger.info(f"  Format: {analysis.get('formato_detectado', '')}")
    logger.info(f"  Confidence: {analysis.get('confianza', 0)}%")
    logger.info(f"  Briefs generated: {len(briefs)}")

    for brief in briefs:
        logger.info(f"  → Brief: {brief['formato_origen']} → {brief['formato_destino']}")

    if not dry_run:
        logger.info("\nSaving to database...")
        save_to_database(result)

        logger.info("Exporting to Google Docs...")
        doc_url = export_to_google_docs(result)
        logger.info(f"  Document: {doc_url}")
    else:
        logger.info("\nDRY RUN — skipping database save and Google Docs export")

    logger.info("\n" + "=" * 60)
    logger.info("DONE")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Hair Biolabs Brief Generation System")
    parser.add_argument("--url", type=str, required=True, help="Direct video URL to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to DB or creating docs")
    args = parser.parse_args()

    run(video_url=args.url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
