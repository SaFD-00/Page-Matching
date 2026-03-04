"""MobileGPT-Collector - KeyUI-based auto exploration CLI entry point."""
from .config import parse_args
from .utils.logging import setup_logging
from .server import CollectorServer


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    import os
    log_file = os.path.join(args.data_dir, "server.log")
    os.makedirs(args.data_dir, exist_ok=True)
    setup_logging(log_file)

    from loguru import logger
    logger.info("MobileGPT-Collector starting...")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  Model: {args.model}")
    logger.info(f"  Threshold: {args.threshold}")
    logger.info(f"  Vision: {args.vision}")
    logger.info(f"  Data dir: {args.data_dir}")
    logger.info(f"  Reasoning: {args.reasoning_effort}")
    logger.info(f"  Subtask threshold: {args.subtask_threshold}")
    logger.info(f"  Memory dir: {args.memory_dir}")
    logger.info(f"  Desc threshold: {args.desc_threshold}")

    server = CollectorServer(
        port=args.port,
        data_dir=args.data_dir,
        threshold=args.threshold,
        model=args.model,
        vision=args.vision,
        reasoning_effort=args.reasoning_effort,
        subtask_threshold=args.subtask_threshold,
        memory_dir=args.memory_dir,
        desc_threshold=args.desc_threshold,
    )

    server.start()


if __name__ == "__main__":
    main()
