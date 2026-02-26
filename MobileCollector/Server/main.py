"""MobileCollector - KeyUI-based auto exploration CLI entry point."""
from .config import parse_args
from .utils.logging import setup_logging
from .server import CollectorServer


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logging(args.data_dir)

    from loguru import logger
    logger.info("MobileCollector starting...")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  Model: {args.model}")
    logger.info(f"  Threshold: {args.threshold}")
    logger.info(f"  Vision: {args.vision}")
    logger.info(f"  Data dir: {args.data_dir}")
    logger.info(f"  Reasoning: {args.reasoning_effort}")

    server = CollectorServer(
        port=args.port,
        data_dir=args.data_dir,
        threshold=args.threshold,
        model=args.model,
        vision=args.vision,
        reasoning_effort=args.reasoning_effort,
    )

    server.start()


if __name__ == "__main__":
    main()
