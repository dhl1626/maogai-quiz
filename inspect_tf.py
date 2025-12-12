import docx
import os
import re

def inspect_tf(filename):
    if not os.path.exists(filename): return
    doc = docx.Document(filename)
    
    # Find a "判断题" section and print next few lines
    found = False
    count = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if "判断题" in text and len(text) < 20:
            found = True
            print(f"--- FOUND SECTION: {text} ---")
            count = 0
            continue
        
        if found:
            print(text)
            count += 1
            if count > 10:
                break
                
if __name__ == "__main__":
    inspect_tf("毛概（2025-2026-1）期末练习题库.docx")
