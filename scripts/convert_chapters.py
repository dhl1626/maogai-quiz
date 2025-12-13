import os
import re
import json

def normalize_text(text):
    text = text.replace('（', '(').replace('）', ')').replace('：', ':').replace('．', '.')
    text = text.replace('\u200c', '') # Remove ZWNJ
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_chapter_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    chapter_title = "Unknown Chapter"
    questions = []
    
    current_section = "single"  # default
    current_question = None
    
    # Section mapping
    section_map = {
        "单选题": "single",
        "单项选择": "single",
        "多选题": "multiple",
        "多项选择": "multiple",
        "判断题": "true_false",
        "材料分析": "material",
        "材料题分析": "material"
    }

    # Regex patterns
    question_start = re.compile(r"^\d+[\.\、]")
    option_start = re.compile(r"^([A-F])[\.\、]") # Added '、' as seen in file content example
    answer_start = re.compile(r"^答案.*[:](.*)") # Updated to match "答案要点：" etc.
    
    # Material analysis patterns
    material_start_pattern = re.compile(r"^材料分析题[\(（].*[\)）]")

    def finalize_question():
        nonlocal current_question
        if current_question:
             # Process multiple choice answer sorting
             if current_question["type"] == "multiple":
                 ans = current_question["answer"].upper().replace(" ", "")
                 ans = re.sub(r'[^A-F]', '', ans)
                 current_question["answer"] = "".join(sorted(ans))
             
             # Process boolean answers
             elif current_question["type"] == "true_false":
                 ans = current_question["answer"]
                 if any(k in ans for k in ["错", "F", "×"]): current_question["answer"] = "错误"
                 elif any(k in ans for k in ["对", "T", "√", "正"]): current_question["answer"] = "正确"
                 
             questions.append(current_question)
             current_question = None

    for line in lines:
        raw_line = line.strip()
        if not raw_line:
            continue
            
        clean_line = normalize_text(raw_line)
        
        # Check for Chapter Title (usually first line, but just in case)
        if clean_line.startswith("第一章") or clean_line.startswith("第二章") or \
           clean_line.startswith("第三章") or clean_line.startswith("第四章") or \
           clean_line.startswith("第五章") or clean_line.startswith("第六章") or \
           clean_line.startswith("第七章") or clean_line.startswith("第八章") or \
           clean_line.startswith("Chapter"):
            chapter_title = clean_line
            continue

        # Check for Section Header
        found_section = False
        for k, v in section_map.items():
            if k in clean_line and len(clean_line) < 20:
                # e.g. "一、单选题" or just "单选题"
                if re.match(r'^[一二三四IVX]+\W', clean_line) or clean_line.startswith(k):
                    finalize_question()
                    current_section = v
                    found_section = True
                    break
        if found_section:
            continue

        # Material Analysis logic is distinct
        if current_section == "material":
            m_ans = answer_start.match(clean_line)
            if m_ans:
                if current_question:
                    current_question["answer"] += m_ans.group(1) + "\n"
                    current_question["in_answer"] = True
                continue
                
            if material_start_pattern.match(clean_line):
                finalize_question()
                current_question = {
                    "type": "material",
                    "question": clean_line + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer": False
                }
            elif current_question:
                if current_question.get("in_answer"):
                     current_question["answer"] += clean_line + "\n"
                else:
                     current_question["question"] += clean_line + "\n"
            else:
                # Fallback start if regex missed
                 current_question = {
                    "type": "material",
                    "question": clean_line + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer": False
                }
            continue

        # Standard Questions (Single, Multiple, True/False)
        
        # Check for Answer line
        m_ans = answer_start.match(clean_line)
        if m_ans:
            if current_question:
                current_question["answer"] = m_ans.group(1).strip()
            continue

        # Check for Options (A. ...)
        m_opt = option_start.match(clean_line)
        if m_opt and current_section in ["single", "multiple"]:
            if current_question:
                # Sometimes options are on one line "A. ... B. ..."
                # normalize_text preserves spaces but we might want to split them if on same line?
                # The example showed "A. ... \n B. ..." structure mostly, but let's handle split if needed.
                # Actually, parse_docx_to_clean_text handled the splitting.
                # Here we assume the txt file has them one per line OR clearly separated.
                # If the user copied raw text, it might need splitting.
                
                # Check if multiple options on one line
                # Regex to find " B." or " C." preceded by space
                # But simple case first:
                current_question["options"].append(clean_line)
            continue
            
        # Check for Question Start
        m_q = question_start.match(clean_line)
        if m_q:
            finalize_question()
            current_question = {
                "type": current_section,
                "question": clean_line, 
                "options": [],
                "answer": ""
            }
        else:
            # Continuation of previous line (question or option)
            if current_question:
                if current_question["options"]:
                    current_question["options"][-1] += " " + clean_line
                else:
                    current_question["question"] += "\n" + clean_line

    finalize_question()
    
    return {
        "title": chapter_title,
        "questions": questions
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    data_dir = os.path.join(project_root, "data")
    source_dir = os.path.join(project_root, "source_data")
    
    manifest = []
    
    # Process Chapter 1 to 8
    for i in range(1, 9):
        txt_filename = f"chapter{i}.txt"
        txt_path = os.path.join(source_dir, txt_filename)
        
        if not os.path.exists(txt_path):
            print(f"Warning: {txt_filename} not found, skipping.")
            continue
            
        print(f"Processing {txt_filename}...")
        chapter_data = parse_chapter_file(txt_path)
        
        # Sort questions by type
        type_order = {"single": 0, "multiple": 1, "true_false": 2, "material": 3}
        chapter_data["questions"].sort(key=lambda q: type_order.get(q["type"], 99))
        
        # Output JS file
        js_filename = f"chapter_{i}.js"
        var_name = f"chapterData_{i-1}" # chapterData_0 for ch1
        
        js_content = f"window.{var_name} = " + json.dumps(chapter_data, ensure_ascii=False, indent=2) + ";"
        
        with open(os.path.join(data_dir, js_filename), 'w', encoding='utf-8') as f:
            f.write(js_content)
            
        manifest.append({
            "index": i-1,
            "title": chapter_data["title"],
            "file": f"data/{js_filename}",
            "globalVar": var_name
        })
        
    # Write manifest
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    manifest_content = f"const quizManifest = {manifest_json};"
    
    with open(os.path.join(data_dir, "manifest.js"), 'w', encoding='utf-8') as f:
        f.write(manifest_content)
        
    print("Done processing chapters.")

if __name__ == "__main__":
    main()
