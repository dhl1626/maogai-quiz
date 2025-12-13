import json
import os

file_path = '答题网页/data/chapter_6.js'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Strip JS variable assignment
        if 'window.chapterData_5 = ' in content:
            content = content.replace('window.chapterData_5 = ', '')
        if content.strip().endswith(';'):
            content = content.strip()[:-1]
            
        data = json.loads(content)
        
        print(f"Title: {data['title']}")
        print(f"Total questions: {len(data['questions'])}")
        
        counts = {}
        for q in data['questions']:
            counts[q['type']] = counts.get(q['type'], 0) + 1
            
        print("Counts by type:", counts)

except Exception as e:
    print(f"Error: {e}")
