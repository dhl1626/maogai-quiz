import json
import os

file_path = '答题网页/data/chapter_3.js'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Strip JS variable assignment
        if 'window.chapterData_2 = ' in content:
            content = content.replace('window.chapterData_2 = ', '')
        if content.strip().endswith(';'):
            content = content.strip()[:-1]
            
        data = json.loads(content)
        
        print(f"Title: {data['title']}")
        print(f"Total questions: {len(data['questions'])}")
        
        counts = {}
        for q in data['questions']:
            counts[q['type']] = counts.get(q['type'], 0) + 1
            
        print("Counts by type:", counts)
        
        # Optional: Print question numbers to see gaps
        single_nums = []
        for q in data['questions']:
            if q['type'] == 'single':
                # Extract number from question text "1. ..."
                try:
                    num = int(q['question'].split('.')[0])
                    single_nums.append(num)
                except:
                    # try splitting by '、'
                    try:
                         num = int(q['question'].split('、')[0])
                         single_nums.append(num)
                    except:
                        pass
        print(f"Single choice IDs found: {sorted(single_nums)}")

except Exception as e:
    print(f"Error: {e}")
