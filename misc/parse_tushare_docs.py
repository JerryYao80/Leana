#!/usr/bin/env python3
"""
Tushare API Documentation Parser - Final Version
解析 Tushare 文档页面，提取接口名称和输出参数
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time


def fetch_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def fetch_api_detail(doc_id):
    url = f"https://tushare.pro/document/2?doc_id={doc_id}"
    print(f"  获取: doc_id={doc_id}", end=" ... ")
    
    try:
        html_content = fetch_page(url)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        content_div = soup.find('div', class_='content')
        if not content_div:
            print("✗ 无内容")
            return None, None
        
        h2 = content_div.find('h2')
        if not h2:
            print("✗ 无标题")
            return None, None
        
        interface_name_cn = h2.get_text().strip()
        
        interface_name_en = None
        
        text_content = content_div.get_text()
        match = re.search(r'接口[：:]\s*([a-z_]+)', text_content)
        if match:
            interface_name_en = match.group(1)
        
        if not interface_name_en:
            code_blocks = content_div.find_all(['code', 'pre'])
            for block in code_blocks:
                text = block.get_text()
                match = re.search(r'pro\.([a-z_]+)\s*\(', text)
                if match:
                    candidate = match.group(1)
                    if candidate not in ['pro_api', 'pro_bar', 'query']:
                        interface_name_en = candidate
                        break
        
        if not interface_name_en:
            print(f"✗ {interface_name_cn} (无法提取英文接口名)")
            return None, None
        
        params = {}
        found_output_table = False
        
        for element in content_div.find_all(['p', 'table']):
            if element.name == 'p':
                text = element.get_text().strip()
                if '输出参数' in text:
                    found_output_table = True
                elif found_output_table:
                    found_output_table = False
            
            elif element.name == 'table' and found_output_table:
                rows = element.find_all('tr')
                if len(rows) < 2:
                    continue
                
                headers = [th.get_text().strip() for th in rows[0].find_all(['th', 'td'])]
                
                name_idx = 0
                desc_idx = 3 if len(headers) > 3 else 1
                
                for idx, header in enumerate(headers):
                    if '名称' in header or '字段' in header:
                        name_idx = idx
                    elif '描述' in header or '说明' in header:
                        desc_idx = idx
                
                for row in rows[1:]:
                    cols = row.find_all(['td', 'th'])
                    if len(cols) > max(name_idx, desc_idx):
                        param_name = cols[name_idx].get_text().strip()
                        param_desc = cols[desc_idx].get_text().strip()
                        
                        if param_name:
                            params[param_name] = param_desc
                
                if params:
                    break
        
        if params:
            print(f"✓ {interface_name_en} / {interface_name_cn} ({len(params)} 参数)")
            return interface_name_en, params
        else:
            print(f"✗ {interface_name_en} / {interface_name_cn} (无输出参数)")
            return None, None
            
    except Exception as e:
        print(f"✗ 错误: {e}")
        return None, None


def extract_doc_ids(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    doc_ids = set()
    
    links = soup.find_all('a', href=True)
    for link in links:
        href = link.get('href', '')
        if not isinstance(href, str):
            continue
        match = re.search(r'doc_id=(\d+)', href)
        if match:
            doc_ids.add(int(match.group(1)))
    
    return sorted(doc_ids)


def parse_tushare_api(main_url, limit=None):
    print(f"正在获取主页面: {main_url}")
    html_content = fetch_page(main_url)
    
    print("正在提取文档ID列表...")
    doc_ids = extract_doc_ids(html_content)
    print(f"找到 {len(doc_ids)} 个文档ID")
    
    if limit:
        print(f"限制解析前 {limit} 个接口（测试模式）\n")
        doc_ids = doc_ids[:limit]
    else:
        print(f"准备解析所有接口\n")
    
    result = {}
    
    print("开始解析接口详情:")
    for idx, doc_id in enumerate(doc_ids, 1):
        print(f"[{idx}/{len(doc_ids)}] ", end="")
        
        name, params = fetch_api_detail(doc_id)
        if name and params:
            result[name] = params
        
        if idx < len(doc_ids):
            time.sleep(0.5)
   
    output_file = "tushare-net.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✓ 成功解析 {len(result)} 个接口")
    
    #return result


def main():
    test_url = "https://tushare.pro/document/2"
    
    try:
        test_doc_ids = [25, 26, 27, 32, 33]
        api_data = {}
        
        print(f"测试模式: 解析指定的 {len(test_doc_ids)} 个接口\n")
        print("开始解析接口详情:")
        
        for idx, doc_id in enumerate(test_doc_ids, 1):
            print(f"[{idx}/{len(test_doc_ids)}] ", end="")
            name, params = fetch_api_detail(doc_id)
            if name and params:
                api_data[name] = params
            if idx < len(test_doc_ids):
                time.sleep(0.5)
        
        output_file = "tushare-net.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"✓ 成功解析 {len(api_data)} 个接口")
        print(f"✓ 数据已保存到: {output_file}")
        
        if api_data:
            print(f"\n示例数据:")
            first_interface = list(api_data.keys())[0]
            print(f"\n接口名称: {first_interface}")
            print(f"输出参数:")
            for param_name, param_desc in list(api_data[first_interface].items())[:8]:
                print(f"  • {param_name}: {param_desc}")
            if len(api_data[first_interface]) > 8:
                print(f"  ... (共 {len(api_data[first_interface])} 个参数)")
    
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_url = "https://tushare.pro/document/2"
    parse_tushare_api(test_url)

    #main()
