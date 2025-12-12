import docx
import re
import os
import glob
import json

def normalize_text(text):
    text = text.replace('（', '(').replace('）', ')').replace('：', ':').replace('．', '.')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_docx_to_clean_text(docx_path, output_txt_path):
    doc = docx.Document(docx_path)
    lines = []
    chapter_pattern = re.compile(r"^\s*(第[一二三四五六七八九十]+章|Chapter\s*\d+)")
    section_map = {
        "单选题": "SINGLE",
        "单项选择": "SINGLE",
        "多选题": "MULTIPLE",
        "多项选择": "MULTIPLE",
        "判断题": "TRUE_FALSE",
        "材料分析": "MATERIAL"
    }
    option_split_pattern = re.compile(r'(\s[A-F][\. .])')
    current_chapter = "Unknown Chapter"
    current_section = "SINGLE" 
    
    for para in doc.paragraphs:
        raw_text = para.text.strip()
        if not raw_text:
            continue
            
        clean_line = normalize_text(raw_text)
        
        if chapter_pattern.match(clean_line):
            lines.append(f"\n=== CHAPTER: {clean_line} ===\n")
            current_chapter = clean_line
            current_section = "SINGLE" 
            continue
            
        found_section = False
        for k, v in section_map.items():
            if k in clean_line and len(clean_line) < 20:
                if re.match(r'^[一二三四IVX]+\W', clean_line) or clean_line.startswith(k):
                    lines.append(f"\n--- SECTION: {v} ---\n")
                    current_section = v
                    found_section = True
                    break
        if found_section:
            continue
            
        if re.match(r'^答案[:]', clean_line):
            lines.append(clean_line)
            continue
            
        if current_section == "TRUE_FALSE":
            lines.append(clean_line)
            continue
            
        if current_section == "MATERIAL":
            lines.append(clean_line)
            continue

        if re.match(r'^[A-F][\.]', clean_line):
            parts = option_split_pattern.split(clean_line)
            final_str = parts[0]
            for i in range(1, len(parts), 2):
                sep = parts[i].strip() 
                content = parts[i+1] if i+1 < len(parts) else ""
                final_str += "\n" + sep + " " + content
            
            lines.append(final_str)
            continue

        if re.match(r'^\d+[\.]', clean_line):
             lines.append("\n" + clean_line)
        else:
             lines.append(clean_line)

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Cleaned text written to {output_txt_path}")

def parse_clean_text_to_js(txt_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    chapters = []
    current_chapter = None
    current_section = "single" 
    current_question = None
    
    chapter_marker = re.compile(r"^=== CHAPTER: (.*) ===")
    section_marker = re.compile(r"^--- SECTION: (.*) ---")
    
    question_start = re.compile(r"^\d+[\.]")
    option_start = re.compile(r"^([A-F])[\.]")
    answer_start = re.compile(r"^答案[:](.*)")
    
    material_start_pattern = re.compile(r"^材料分析题[\(（].*[\)）]")

    def finalize_question():
        nonlocal current_question
        if current_question and current_chapter:
             if current_question["type"] == "multiple":
                 ans = current_question["answer"].upper().replace(" ", "")
                 ans = re.sub(r'[^A-F]', '', ans)
                 current_question["answer"] = "".join(sorted(ans))
             
             elif current_question["type"] == "true_false":
                 ans = current_question["answer"]
                 if any(k in ans for k in ["错", "F", "×"]): current_question["answer"] = "错误"
                 elif any(k in ans for k in ["对", "T", "√", "正"]): current_question["answer"] = "正确"
                 
             current_chapter["questions"].append(current_question)
             current_question = None

    for line in lines:
        line = line.strip()
        if not line: continue
        
        m_chap = chapter_marker.match(line)
        if m_chap:
            finalize_question()
            if current_chapter: chapters.append(current_chapter)
            current_chapter = {"title": m_chap.group(1), "questions": []}
            current_section = "single"
            continue
            
        if not current_chapter:
             current_chapter = {"title": "绪论/未分类", "questions": []}
             chapters.append(current_chapter)

        m_sec = section_marker.match(line)
        if m_sec:
            finalize_question()
            sec_type = m_sec.group(1)
            if sec_type == "SINGLE": current_section = "single"
            elif sec_type == "MULTIPLE": current_section = "multiple"
            elif sec_type == "TRUE_FALSE": current_section = "true_false"
            elif sec_type == "MATERIAL": current_section = "material"
            continue
            
        if current_section == "material":
            m_ans = answer_start.match(line)
            if m_ans:
                if current_question:
                    current_question["answer"] += m_ans.group(1) + "\n"
                    current_question["in_answer"] = True
                continue
                
            if material_start_pattern.match(line):
                finalize_question()
                current_question = {
                    "type": "material",
                    "question": line + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer": False
                }
            elif current_question:
                if current_question.get("in_answer"):
                     current_question["answer"] += line + "\n"
                else:
                     current_question["question"] += line + "\n"
            else:
                 current_question = {
                    "type": "material",
                    "question": line + "\n",
                    "answer": "",
                    "options": [],
                    "in_answer": False
                }
            
        else: 
            m_ans = answer_start.match(line)
            if m_ans:
                if current_question:
                    current_question["answer"] = m_ans.group(1).strip()
                continue
                
            # SAFE REGEX CHECK
            m_opt = option_start.match(line)
            if m_opt and current_section in ["single", "multiple"]:
                if current_question:
                    try:
                        # Ensure we have groups
                        if len(m_opt.groups()) >= 2:
                            current_question["options"].append(m_opt.group(2).strip())
                        else:
                            # Fallback if regex matched but weirdly
                            current_question["options"].append(line)
                    except Exception as e:
                        print(f"Error parsing option line: {line} - {e}")
                continue
            
            m_q = question_start.match(line)
            if m_q:
                finalize_question()
                current_question = {
                    "type": current_section,
                    "question": line, 
                    "options": [],
                    "answer": ""
                }
            else:
                if current_question:
                    if current_question["options"]:
                        current_question["options"][-1] += " " + line
                    else:
                        current_question["question"] += "\n" + line

    finalize_question()
    if current_chapter: chapters.append(current_chapter)
    
    chapters = [ch for ch in chapters if ch["questions"]]
    
    manifest = []
    type_order = {"single": 0, "multiple": 1, "true_false": 2, "material": 3}
    
    for i, ch in enumerate(chapters):
        ch["questions"].sort(key=lambda q: type_order.get(q["type"], 99))
        
        file_name = f"chapter_{i+1}.js"
        var_name = f"chapterData_{i}"
        
        content = f"window.{var_name} = " + json.dumps(ch, ensure_ascii=False, indent=2) + ";"
        
        out_path = os.path.join(output_dir, file_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        manifest.append({
            "index": i,
            "title": ch["title"],
            "file": f"data/{file_name}",
            "globalVar": var_name
        })
        
    with open(os.path.join(os.path.dirname(output_dir), "manifest.js"), "w", encoding="utf-8") as f:
        f.write("const quizManifest = " + json.dumps(manifest, ensure_ascii=False, indent=2) + ";")
        
    print(f"Generated {len(chapters)} JS files.")

if __name__ == "__main__":
    files = glob.glob("*.docx") + glob.glob("../*.docx")
    docx_file = ""
    for f in files:
        if "毛概" in f and "期末" in f and not "~$ " in f:
            docx_file = f
            break
            
    if not docx_file:
        print("DOCX not found")
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        clean_txt = os.path.join(script_dir, "cleaned_questions.txt")
        
        parse_docx_to_clean_text(docx_file, clean_txt)
        
        data_dir = os.path.join(script_dir, "data")
        parse_clean_text_to_js(clean_txt, data_dir)