import argparse
import json
import os

def load_config():
    """
    Load configuration from command line arguments
    Returns a dictionary with configuration parameters
    """
    parser = argparse.ArgumentParser(description='Code Indexing Pipeline Configuration')
    parser.add_argument('--config', type=str, help='Path to the config JSON file', required=True)
    args = parser.parse_args()
    
    # Load the config file
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Ensure all paths in the config are absolute
    for key in config:
        if key.endswith('Path') and not os.path.isabs(config[key]):
            config[key] = os.path.abspath(config[key])
    
    return config 