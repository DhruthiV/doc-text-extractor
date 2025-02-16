from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import fitz  # PyMuPDF
import re
import json

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Setup
client = MongoClient("mongodb://localhost:27017/")
db = client["docextractor"]
syllabi_collection = db["syllabi"]
othersections_collection = db["othersections"]

# Function to extract text from PDF
def extract_text_with_newlines(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join([page.get_text() for page in doc])
    return text

# Function to extract course details
def extract_other_sections(text):
    sections = {}
    course_details_pattern = r'^(?P<code>UQ\d{2}[A-Z]+\d+[A-Z]?)\s+(?P<title>.+)'
    credits_pattern = r'^\((?P<credits>[\d-]+)\)'
    lines = text.splitlines()
    
    if len(lines) >= 2:
        code_title_match = re.match(course_details_pattern, lines[0].strip())
        credits_match = re.match(credits_pattern, lines[1].strip())
        if code_title_match:
            sections['Course Code'] = code_title_match.group('code')
            sections['Title'] = code_title_match.group('title').strip()
        if credits_match:
            sections['Credits'] = credits_match.group('credits')
    
    patterns = {
        'Course Objectives': r'Course Objectives:(.*?)(?=Course Outcomes:)',
        'Course Outcomes': r'Course Outcomes:(.*?)(?=Course Overview:)',
        'Course Overview': r'Course Overview:(.*?)(?=Course Content:)',
        'Text Books': r'Text Books:(.*?)(?=Reference Books:)',
        'Reference Books': r'Reference Books:(.*)'  
    }
    for title, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections[title] = match.group(1).strip().replace('\n', ' ')
    
    return sections

# Function to extract syllabus details
def extract_syllabus(text):
    syllabus = {}
    unit_pattern = r'Unit\s?(\d+):\s(.*?)\n(.*?)(?=(Unit\s?\d+:|Text Books:|Reference Books:|$))'
    units = re.findall(unit_pattern, text, re.DOTALL)

    for unit in units:
        unit_number = f"unit_{unit[0]}"
        title = unit[1].strip()
        content = unit[2]

        topics_pattern = r'(.*?)(?=Experiential learning:)'
        experiential_pattern = r'Experiential learning:(.*?)(\d+\s?\+\s?\d+\s?Hours)'

        topics_match = re.search(topics_pattern, content, re.DOTALL)
        experiential_match = re.search(experiential_pattern, content, re.DOTALL)

        topics = []
        if topics_match:
            raw_topics = topics_match.group(1).strip().replace('\n', ' ')
            expanded_topics = []
            pattern = r'(.*?)( - )(.*?)(\.)'
            matches = re.finditer(pattern, raw_topics)
            last_pos = 0
            for match in matches:
                before_pattern = raw_topics[last_pos:match.start()].strip()
                if before_pattern:
                    expanded_topics += [t.strip() for t in before_pattern.split(',') if t.strip()]
                prefix = match.group(1).strip()
                subtopics = match.group(3).strip()
                last_pos = match.end()
                for subtopic in subtopics.split(','):
                    expanded_topics.append(f"{prefix} - {subtopic.strip()}")
            remaining_text = raw_topics[last_pos:].strip()
            if remaining_text:
                remaining_parts = re.split(r'[.,]\s+', remaining_text)
                for part in remaining_parts:
                    part = part.strip()
                    if ' - ' in part and ',' in part:
                        prefix, items = part.split(' - ', 1)
                        prefix = prefix.strip()
                        for item in items.split(','):
                            expanded_topics.append(f"{prefix} - {item.strip()}")
                    else:
                        expanded_topics.append(part)
            topics = expanded_topics

        experiential_learning = []
        if experiential_match:
            raw_experiential = experiential_match.group(1).strip().replace('\n', ' ')
            experiential_learning = [e.strip() for e in re.split(r'[.,]\s+', raw_experiential) if e.strip()]

        syllabus[unit_number] = {
            "title": title,
            "topics": topics,
            "experiential_learning": experiential_learning
        }

    return syllabus

# Function to split topics and remove duplicates
def split_topics_and_remove_duplicates(syllabus):
    for unit in syllabus.values():
        seen = set()
        unique_topics = []
        for topic in unit["topics"]:
            for subtopic in topic.split(","):
                subtopic = subtopic.strip()
                if subtopic not in seen:
                    seen.add(subtopic)
                    unique_topics.append(subtopic)
        unit["topics"] = unique_topics
    return syllabus

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    text = extract_text_with_newlines(await file.read())
    other_sections = extract_other_sections(text)
    syllabus = extract_syllabus(text)
    syllabus = split_topics_and_remove_duplicates(syllabus)
    if 'Course Code' not in other_sections:
        raise HTTPException(status_code=400, detail="Invalid syllabus format")
    course_code = other_sections['Course Code']
    syllabi_collection.insert_one({"course_code": course_code, **syllabus})
    othersections_collection.insert_one({"course_code": course_code, **other_sections})
    return {"message": "File processed successfully", "course_code": course_code}

@app.get("/courses/")
def get_courses():
    courses = othersections_collection.find({}, {"course_code": 1, "Title": 1})
    return [{"course_code": c["course_code"], "title": c.get("Title", "Unknown")} for c in courses]

@app.get("/course/{course_code}")
def get_course(course_code: str):
    course = syllabi_collection.find_one({"course_code": course_code}, {"_id": 0})
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course
