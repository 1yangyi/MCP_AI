import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.pipeline.university_data_pipeline import UniversityDataPipeline

if __name__ == "__main__":
    # Use relative path to test data
    pipeline = UniversityDataPipeline("data/test/whu_test.json")
    pipeline.run(start_index=0, end_index=1)