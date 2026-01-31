#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

def fetch_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

url = "https://tushare.pro/document/2?doc_id=25"
print(f"正在获取: {url}\n")

html_content = fetch_page(url)
soup = BeautifulSoup(html_content, 'html.parser')

content_div = soup.find('div', class_='content')
if not content_div:
    print("未找到 content div")
    exit(1)

h2 = content_div.find('h2')
if h2:
    print(f"标题: {h2.get_text().strip()}\n")

print("=" * 60)
print("查找代码块中的接口名称:")
print("=" * 60)

code_blocks = content_div.find_all(['code', 'pre'])
print(f"找到 {len(code_blocks)} 个代码块\n")

for idx, block in enumerate(code_blocks[:10], 1):
    text = block.get_text().strip()
    if len(text) > 100:
        text = text[:100] + "..."
    print(f"\n代码块 {idx}:")
    print(f"标签: {block.name}")
    print(f"内容: {text}")
    
    matches = re.findall(r'(?:pro|ts)\.([a-z_]+)\s*\(', text)
    if matches:
        print(f"  → 匹配到: {matches}")

print("\n" + "=" * 60)
print("查找包含 '接口' 的段落:")
print("=" * 60)

paragraphs = content_div.find_all('p')
for p in paragraphs[:15]:
    text = p.get_text().strip()
    if '接口' in text or 'interface' in text.lower():
        print(f"\n{text[:200]}")
        
        match = re.search(r'接口[：:]\s*([a-z_]+)', text)
        if match:
            print(f"  → 匹配到: {match.group(1)}")
