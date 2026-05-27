import argparse
import os
import shutil

from src.base import ConfigParser
from src.core.rag.doc.pipeline.base_pipeline import BasePipeline
from src.utils import logger


def main():
    cur_path = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_CONFIG = f"{cur_path}/default.yaml"

    parser = argparse.ArgumentParser(description="Run the Knowledge pipeline")

    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        type=str,
        help="Path to the configuration file",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Input directory containing documents to process",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=str,
        help="Output directory for processing results",
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Create input directory inside output directory
    output_input_dir = os.path.join(args.output, "input")
    os.makedirs(output_input_dir, exist_ok=True)

    # Copy input documents to the new input directory
    if os.path.isdir(args.input):
        for item in os.listdir(args.input):
            src_path = os.path.join(args.input, item)
            dst_path = os.path.join(output_input_dir, item)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)
                logger.info(f"Copied {src_path} to {dst_path}")
    else:
        logger.error(f"Input path {args.input} is not a directory")
        return

    # Load configuration
    config = ConfigParser(args.config)
    config.config["global"]["root_path"] = args.output
    pipeline = BasePipeline(config)
    pipeline.run()


if __name__ == "__main__":
    main()

# Run with custom configuration:
# python -m src.core.rag.doc.main --config config.yaml --input /path/to/input --output /path/to/output
