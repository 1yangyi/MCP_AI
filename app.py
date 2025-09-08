#!/usr/bin/env python3
"""
University Data Collection System - Main Entry Point
"""

import sys
import os
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pipeline.university_data_pipeline import UniversityDataPipeline
from config import INPUT_DIR

def main():
    parser = argparse.ArgumentParser(description='University Data Collection System')
    parser.add_argument('--input', default=os.path.join(INPUT_DIR, 'top500_school_websites.json'),
                       help='Input universities JSON file')
    parser.add_argument('--start', type=int, default=0,
                       help='Start index for processing')
    parser.add_argument('--end', type=int, default=10,
                       help='End index for processing')
    parser.add_argument('--single', type=str,
                       help='Process single university by name')
    
    args = parser.parse_args()
    
    pipeline = UniversityDataPipeline(args.input)
    
    if args.single:
        pipeline.run_single_university(args.single)
    else:
        pipeline.run(start_index=args.start, end_index=args.end)

if __name__ == "__main__":
    main()