import docx
import json
import re
import os
import glob

def extract_and_split():
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
    
    # Patterns
    chapter_pattern = re.compile(r"^\s*(第[一二三四五六七八九十]+章|Chapter\s*\d+).*")
    
    section_single = re.compile(r"^\s*[一二三四]、.*单.*选.*")
    section_multi = re.compile(r"^\s*[一二三四]、.*多.*选.*")
    section_tf = re.compile(r"^\s*[一二三四]、.*判.*断.*")
    section_material = re.compile(r"^\s*[一二三四]、.*材.*料.*")
    
    question_start = re.compile(r"^\s*\d+[\.．、]\s*(.*)")
    material_start = re.compile(r"^\s*材料分析题[（(][一二三四五六七八九十\d]+[)）]")
    option_pattern = re.compile(r"^\s*([A-E])\s*[.．、\s]\s*(.*)")
    answer_pattern = re.compile(r"^\s*(答案|Answer|答案要点)[:：]\s*(.*)")

    # Heuristic for multi-option lines: "A. xxx B. xxx"
    # This is complex because "B." might be part of the text. 
    # But usually options have space before them.
    # Regex to find " B. " inside text? 
    multi_option_inline = re.compile(r"(\s[A-E][.．、])") 

    def save_current_question():
        nonlocal current_question
        if current_question and current_chapter:
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

        # Material
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

        else: # Normal Types
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

            # Options
            if current_section_type in ["single", "multiple"]:
                if current_question:
                    opt_match = option_pattern.match(text)
                    if opt_match:
                        current_question["options"].append(opt_match.group(2))
                    else:
                        # Append to option or question?
                        # Fallback for implicit options
                        if 0 < len(current_question["options"]) < 5:
                            current_question["options"].append(text)
                        elif len(current_question["options"]) == 0 and len(current_question["question"]) > 10:
                            # Maybe first option A didn't match regex? e.g. "A．xxx" vs "A. xxx"
                            # We already covered most regex cases.
                            # Just append to question text usually.
                            current_question["question"] += "\n" + text
                        else:
                             if current_question["options"]:
                                 current_question["options"][-1] += " " + text
                             else:
                                 current_question["question"] += "\n" + text
            elif current_section_type == "true_false":
                if current_question:
                    current_question["question"] += "\n" + text

    save_current_question()
    if current_chapter and current_chapter not in chapters:
        chapters.append(current_chapter)
    
    # Filter empty
    chapters = [ch for ch in chapters if ch["questions"]]

    # Generate Files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    manifest = []

    # Sort Types Order: Single, Multiple, TF, Material
    type_order = {"single": 0, "multiple": 1, "true_false": 2, "material": 3}

    for i, ch in enumerate(chapters):
        # Sort questions within chapter
        ch["questions"].sort(key=lambda q: type_order.get(q["type"], 99))
        
        file_name = f"chapter_{i+1}.js"
        file_path = os.path.join(data_dir, file_name)
        
        # We wrap in a callback or global assignment
        # window.loadChapterCallback(index, data)
        # OR: window.chapterData_X = ...
        
        js_content = f"window.chapterData_{i} = " + json.dumps(ch, ensure_ascii=False, indent=2) + ";"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(js_content)
        
        manifest.append({
            "index": i,
            "title": ch["title"],
            "file": f"data/{file_name}",
            "globalVar": f"chapterData_{i}"
        })

    # Write Manifest
    manifest_path = os.path.join(script_dir, "data", "manifest.js")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write("const quizManifest = " + json.dumps(manifest, ensure_ascii=False, indent=2) + ";")
        
    print(f"Split complete. Generated {len(chapters)} chapter files and manifest.js in data/.")

if __name__ == "__main__":
    extract_and_split()
