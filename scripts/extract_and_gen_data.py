import docx
import json
import re
import os
import glob

def extract_questions():
    files = glob.glob("*.docx") + glob.glob("../*.docx")
    filename = ""
    for f in files:
        if "毛概" in f and "期末" in f and not "~$ " in f:
            filename = f
            break
    
    if not filename:
        print("Could not find docx file.")
        return

    print(f"Processing: {filename}")
    doc = docx.Document(filename)
    chapters = []
    
    current_chapter = None
    current_section_type = "single" 
    current_question = None
    
    # Regex
    chapter_pattern = re.compile(r"^\s*(第[一二三四五六七八九十]+章|Chapter\s*\d+).*")
    
    section_single = re.compile(r"^\s*[一二三四]、.*单.*选.*")
    section_multi = re.compile(r"^\s*[一二三四]、.*多.*选.*")
    section_tf = re.compile(r"^\s*[一二三四]、.*判.*断.*")
    section_material = re.compile(r"^\s*[一二三四]、.*材.*料.*")
    
    question_start = re.compile(r"^\s*\d+[\.．、]\s*(.*)")
    material_start = re.compile(r"^\s*材料分析题[（(][一二三四五六七八九十\d]+[)）]")
    option_pattern = re.compile(r"^\s*([A-E])\s*[.．、\s]\s*(.*)")
    answer_pattern = re.compile(r"^\s*(答案|Answer|答案要点)[:：]\s*(.*)")

    def save_current_question():
        nonlocal current_question
        if current_question and current_chapter:
            # Type Safety Check
            if "type" not in current_question:
                current_question["type"] = "single" # Fallback

            # Clean content
            if current_question["type"] == "material":
                current_question["question"] = current_question["question"].strip()
                current_question["answer"] = current_question["answer"].strip()
            
            # Format Multiple Choice
            if current_question["type"] == "multiple":
                 ans = current_question["answer"].upper().replace(" ", "").replace("\t", "")
                 ans = re.sub(r'[^A-E]', '', ans)
                 current_question["answer"] = "".join(sorted(ans))
            
            # Format True/False
            if current_question["type"] == "true_false":
                 ans = current_question["answer"].strip()
                 if any(x in ans for x in ["错", "F", "×"]):
                     current_question["answer"] = "错误"
                 elif any(x in ans for x in ["对", "T", "√", "正"]):
                     current_question["answer"] = "正确"

            current_chapter["questions"].append(current_question)
            current_question = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
            
        # Chapter
        if chapter_pattern.match(text):
            save_current_question()
            if current_chapter:
                chapters.append(current_chapter)
            current_chapter = {"title": text, "questions": []}
            current_section_type = "single"
            continue
        
        if not current_chapter:
             current_chapter = {"title": "绪论/未分类", "questions": []}
             chapters.append(current_chapter)

        # Section
        if section_single.match(text):
            save_current_question()
            current_section_type = "single"
            continue
        elif section_multi.match(text):
            save_current_question()
            current_section_type = "multiple"
            continue
        elif section_tf.match(text):
            save_current_question()
            current_section_type = "true_false"
            continue
        elif section_material.match(text):
            save_current_question()
            current_section_type = "material"
            continue

        # Answer
        ans_match = answer_pattern.match(text)
        if ans_match:
            if current_question:
                if current_section_type == "material":
                    current_question["in_answer_block"] = True
                    current_question["answer"] += ans_match.group(2) + "\n"
                else:
                    current_question["answer"] = ans_match.group(2).strip()
            continue

        # Material Question
        if current_section_type == "material":
            mat_match = material_start.match(text)
            if mat_match:
                save_current_question()
                current_question = {
                    "type": "material",
                    "question": text + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer_block": False
                }
            elif current_question:
                if current_question.get("in_answer_block"):
                    current_question["answer"] += text + "\n"
                else:
                    current_question["question"] += text + "\n"
            else:
                 current_question = {
                    "type": "material",
                    "question": text + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer_block": False
                }

        else: # Single/Multi/TF
            q_match = question_start.match(text)
            if q_match:
                save_current_question()
                current_question = {
                    "type": current_section_type,
                    "question": text,
                    "options": [],
                    "answer": ""
                }
                continue

            # Options Logic
            if current_section_type in ["single", "multiple"]:
                if current_question:
                    opt_match = option_pattern.match(text)
                    if opt_match:
                        # Found explicit option
                        current_question["options"].append(opt_match.group(2))
                    else:
                        # Implicit option handling
                        # If we already have 4 options, this is likely next question start (if missed number) or answer text
                        # But assuming valid doc structure:
                        # If the line is short or we have < 4 options, treat as option?
                        
                        # Heuristic: If we have 0 options so far, and question text length > 10, assume this is Option A.
                        if len(current_question["options"]) == 0 and len(current_question["question"]) > 10:
                            current_question["options"].append(text)
                        elif 0 < len(current_question["options"]) < 4:
                            # If we have some options, assume this is the next one (B, C, D)
                            current_question["options"].append(text)
                        else:
                            # Append to Question Text or Last Option
                            if current_question["options"]:
                                 current_question["options"][-1] += " " + text
                            else:
                                 current_question["question"] += " " + text
            
            elif current_section_type == "true_false":
                if current_question:
                    current_question["question"] += " " + text

    save_current_question()
    
    # Filter empty chapters
    chapters = [ch for ch in chapters if ch["questions"]]

    # Write to data.js in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "data.js")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("const quizData = ")
        json.dump(chapters, f, ensure_ascii=False, indent=2)
        f.write(";")
    
    print(f"Extraction complete. Found {len(chapters)} chapters.")
    print(f"Saved to: {output_path}")
    
    # Verification Print
    count_missing_type = 0
    for ch in chapters:
        for q in ch["questions"]:
            if "type" not in q:
                count_missing_type += 1
    
    if count_missing_type > 0:
        print(f"WARNING: {count_missing_type} questions missing 'type' field!")
    else:
        print("Verification: All questions have 'type' field.")

if __name__ == "__main__":
    extract_questions()