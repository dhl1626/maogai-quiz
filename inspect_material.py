import docx
import os

def inspect_material(filename):
    if not os.path.exists(filename): return
    doc = docx.Document(filename)
    
    found = False
    count = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if "材料分析题" in text and len(text) < 20:
            found = True
            print(f"--- FOUND SECTION: {text} ---")
            count = 0
            continue
        
        if found:
            print(text)
            count += 1
            if count > 20:
                break

if __name__ == "__main__":
    inspect_material("毛概（2025-2026-1）期末练习题库.docx")
