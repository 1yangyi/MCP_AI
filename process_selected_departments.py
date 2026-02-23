import os
import json
import requests
import time
import logging
import random
from openai import OpenAI
from bs4 import BeautifulSoup
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
DEEPSEEK_API_KEY = "sk-08356d9d33304343a40de1d6d26520f9"
BASE_DIR = Path(r"e:\1_2026上半年\MCP\MCP\MCP_AI\data\selected_departments")
LOG_DIR = Path(r"e:\1_2026上半年\MCP\MCP\MCP_AI\logs")
LOG_DIR.mkdir(exist_ok=True)

# Processing Configuration
MAX_WORKERS = 10  # Increased from 5 to 10 for better concurrency
REQUEST_DELAY = 0.1  # Reduced from 0.5 to 0.1 to speed up
MAX_RETRIES = 1  # Reduced retries to ignore failures quickly

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "process_departments.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# User Agents for scraping
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def get_html_content(url):
    """Fetches HTML content from a URL with minimal retries."""
    for attempt in range(MAX_RETRIES):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            # Add a small delay before request to be polite
            time.sleep(random.uniform(0.1, REQUEST_DELAY))
            
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            # Attempt to decode with utf-8, fall back to other encodings if necessary
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            logging.warning(f"Attempt {attempt+1}/{MAX_RETRIES} failed for {url}: {e}")
            # If it fails, we just try once more or give up depending on MAX_RETRIES
            # No long exponential backoff needed if we want to "ignore"
    
    logging.error(f"Failed to fetch {url} after {MAX_RETRIES} attempts. Ignoring.")
    return None

def extract_teacher_info_with_ai(html_content):
    """Uses DeepSeek API to extract structured teacher information."""
    if not html_content:
        return None
        
    # Limit content length to avoid token limits (rough truncation)
    max_chars = 15000
    if len(html_content) > max_chars:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove scripts and styles to save tokens
        for script in soup(["script", "style"]):
            script.decompose()
        text_content = soup.get_text(separator=' ', strip=True)
        truncated_content = text_content[:max_chars]
    else:
        truncated_content = html_content

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    prompt = f"""
    You are a data extraction assistant. Extract the following information from the text below about a university teacher:
    - Name
    - Gender
    - Age (if available, else null)
    - Major (Research Area)
    - College (School/Faculty)
    - Achievement (Papers, Paper Descriptions, Patents, Projects)
    - Title (Academic Title e.g., Professor, Associate Professor)
    - Award (Honors/Awards)

    Text content:
    {truncated_content}

    Return the result strictly in JSON format with the following structure:
    {{
        "name": "Name",
        "gender": "Gender",
        "age": "Age or null",
        "major": "Major",
        "college": "College Name",
        "achievement": {{
            "papers": ["Paper 1", "Paper 2"],
            "paper_description": ["Description 1", "Description 2"],
            "patents": ["Patent 1", "Patent 2"],
            "projects": ["Project 1", "Project 2"]
        }},
        "title": "Title",
        "award": ["Award 1", "Award 2"]
    }}
    
    Notes:
    - "major": Research Interests/Directions (e.g., "Robotics", "Deep Learning"). Extract from "Research Area" or infer from "Main research results" (主要研究成果) if it lists topics/directions. Keep it concise.
    - "papers": Standard academic paper titles (e.g., "Treatment and outcomes of patients...").
    - "paper_description": Summaries or abstracts of specific papers/works (e.g., "改良CLAG方案治疗..."). Do NOT include general research directions here.
    - "patents" and "projects": Standard lists.
    - Ensure "major" and "paper_description" do not contain the same content. "Major" is for topics; "paper_description" is for specific work descriptions.
    - If a field is not found, use null or an empty string/list as appropriate. 
    - Ensure "achievement" is an object containing "papers", "paper_description", "patents", and "projects".
    - Do not include any markdown formatting or explanations.
    """

    try:
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        content = completion.choices[0].message.content.strip()
        # Clean potential markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())
    except Exception as e:
        logging.error(f"AI extraction failed: {e}")
        return None

def process_teacher(teacher, output_dir):
    """Process a single teacher."""
    name = teacher.get("name")
    url = teacher.get("URL")
    
    if not url or not url.startswith("http"):
        logging.warning(f"Invalid URL for {name}: {url}")
        return None

    # Check if we already have this teacher's info processed
    output_file = output_dir / f"{name}_info.json"
    if output_file.exists():
        logging.info(f"Skipping {name}, already processed.")
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error reading existing file {output_file}: {e}")
            return None

    logging.info(f"Processing {name} at {url}...")
    html = get_html_content(url)
    if html:
        info = extract_teacher_info_with_ai(html)
        if info:
            if isinstance(info, list):
                # If AI returns a list instead of a dict, take the first item if possible, or wrap it
                logging.warning(f"AI returned a list for {name}, using first element or converting.")
                if len(info) > 0 and isinstance(info[0], dict):
                    info = info[0]
                else:
                    # Fallback empty structure
                    info = {}
            
            if not isinstance(info, dict):
                 logging.error(f"AI returned invalid format for {name}: {type(info)}. Expected dict.")
                 return None

            # Generate unique ID
            uni_name = output_dir.parent.name
            # Clean university name (remove leading "1_", "25_" etc if present)
            if "_" in uni_name and uni_name.split('_')[0].isdigit():
                clean_uni_name = uni_name.split('_', 1)[1]
            else:
                clean_uni_name = uni_name
                
            dept_name = output_dir.name
            
            # Create a unique ID based on university, department, and name
            # Using a shorter hash (4 chars) is sufficient for collisions within same name group
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:4]
            unique_id = f"{clean_uni_name}_{dept_name}_{name}_{url_hash}"
            
            # Add metadata
            info["id"] = unique_id
            info["university"] = uni_name
            info["department"] = dept_name
            info["original_url"] = url
            
            # Save individual file (optional, good for resume capability)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=4)
            
            return info
    
    return None

def process_department(dept_path):
    """Process all teachers in a department."""
    # Find the teachers.json file
    json_files = list(dept_path.glob("*_teachers.json"))
    if not json_files:
        return
    
    teacher_file = json_files[0]
    logging.info(f"Found teacher list: {teacher_file}")
    
    try:
        with open(teacher_file, 'r', encoding='utf-8') as f:
            teachers = json.load(f)
    except Exception as e:
        logging.error(f"Error reading {teacher_file}: {e}")
        return

    processed_data = []
    
    # Use ThreadPool to speed up network requests
    # Using a list to collect futures to iterate over them
    futures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for teacher in teachers:
            futures.append(executor.submit(process_teacher, teacher, dept_path))
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                processed_data.append(result)
    
    # Save combined results
    if processed_data:
        combined_file = dept_path / "teachers_detailed_info.json"
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)
        logging.info(f"Saved {len(processed_data)} detailed records to {combined_file}")

def main():
    import sys
    
    # Default to BASE_DIR
    target_path = BASE_DIR
    slice_start = 0
    slice_end = None

    # Argument parsing logic
    # Usage: 
    # 1. python script.py  -> Process all in BASE_DIR
    # 2. python script.py -15 -> Process last 15 in BASE_DIR
    # 3. python script.py "1_北京大学" -> Process that folder
    # 4. python script.py "data/selected_departments" -5 -> Process last 5 in that folder
    
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        # Check if arg1 is a range string "0:15"
        if ':' in arg1:
             slice_start = arg1
             logging.info(f"Range string detected: {slice_start}")
        else:
             try:
                 # Check if arg1 is an integer (e.g., -15 or 5)
                 slice_start = int(arg1)
                 logging.info(f"Integer argument detected. Processing BASE_DIR with slice start: {slice_start}")
             except ValueError:
                 # It's a path
                 input_path_str = arg1
                 # Try resolving as absolute path or relative to CWD
                 possible_path_1 = Path(input_path_str).resolve()
                 # Try resolving relative to BASE_DIR
                 possible_path_2 = (BASE_DIR / input_path_str).resolve()
                 
                 if possible_path_1.exists():
                     target_path = possible_path_1
                 elif possible_path_2.exists():
                     target_path = possible_path_2
                 else:
                     logging.error(f"Path not found: {input_path_str}")
                     return
                     
                 # Check for second argument as slice
                 if len(sys.argv) > 2:
                     try:
                         slice_start = int(sys.argv[2])
                         logging.info(f"Second argument detected as slice start: {slice_start}")
                     except ValueError:
                         pass

    logging.info(f"Target path resolved to: {target_path}")

    # Determine processing mode based on directory content
    
    # Case 1: It's a single department (Contains specific teacher json file)
    if list(target_path.glob("*_teachers.json")):
        logging.info(f"Detected single department: {target_path.name}")
        process_department(target_path)
        return

    # Case 2: It's a university directory (Contains department directories)
    is_university_dir = False
    try:
        for sub in target_path.iterdir():
            if sub.is_dir() and list(sub.glob("*_teachers.json")):
                is_university_dir = True
                break
    except Exception as e:
        logging.error(f"Error accessing directory {target_path}: {e}")
        return
            
    if is_university_dir:
        logging.info(f"Detected university directory: {target_path.name}")
        departments = sorted([d for d in target_path.iterdir() if d.is_dir()])
        for dept_dir in departments:
            logging.info(f"  Processing Department: {dept_dir.name}")
            process_department(dept_dir)
        return

    # Case 3: It's the root directory (Contains university directories)
    is_root_dir = False
    try:
        for sub in target_path.iterdir():
            if sub.is_dir():
                for subsub in sub.iterdir():
                    if subsub.is_dir() and list(subsub.glob("*_teachers.json")):
                        is_root_dir = True
                        break
            if is_root_dir:
                break
    except Exception as e:
        pass 
            
    if is_root_dir:
        logging.info(f"Detected root directory: {target_path.name}")
        # Sort universities numerically if they start with number, else alphabetically
        universities = sorted([d for d in target_path.iterdir() if d.is_dir()], 
                              key=lambda x: int(x.name.split('_')[0]) if '_' in x.name and x.name.split('_')[0].isdigit() else float('inf'))
        
        # Apply slice logic
        selected_universities = []
        if isinstance(slice_start, str) and ':' in slice_start:
             parts = slice_start.split(':')
             start = int(parts[0]) if parts[0] else 0
             end = int(parts[1]) if parts[1] else None
             selected_universities = universities[start:end]
             logging.info(f"Processing slice [{start}:{end}]")
        else:
             # Fallback to previous simple integer behavior
             start_idx = int(slice_start) if isinstance(slice_start, (int, float, str)) and str(slice_start).lstrip('-').isdigit() else 0
             if start_idx != 0:
                 selected_universities = universities[start_idx:]
             else:
                 selected_universities = universities
             
        logging.info(f"Found {len(universities)} universities. Processing {len(selected_universities)} of them.")

        for university_dir in selected_universities:
            logging.info(f"Scanning University: {university_dir.name}")
            departments = sorted([d for d in university_dir.iterdir() if d.is_dir()])
            for dept_dir in departments:
                logging.info(f"  Processing Department: {dept_dir.name}")
                process_department(dept_dir)
        return

    logging.error(f"Could not determine structure for path: {target_path}. No teacher JSON files found structure matching expectations.")

if __name__ == "__main__":
    # Disable warnings for unverified HTTPS requests
    requests.packages.urllib3.disable_warnings()
    main()
