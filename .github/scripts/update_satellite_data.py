#!/usr/bin/env python3
"""
卫星TLE数据获取和整合脚本（TLE直接合并版）
直接下载TLE格式数据并合并，无需格式转换
同时从SatNOGS API获取活跃发射机数据保存为trans.json
"""

import requests
import zipfile
import io
import json
from collections import OrderedDict

SATELLITE_URLS = {
    "All": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
    "Amateur": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle",
    "Brightest": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle",
    "Cubesat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=tle",
    "Education": "https://celestrak.org/NORAD/elements/gp.php?GROUP=education&FORMAT=tle",
    "Engineer": "https://celestrak.org/NORAD/elements/gp.php?GROUP=engineering&FORMAT=tle",
    "Geostationary": "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=tle",
    "Globalstar": "https://celestrak.org/NORAD/elements/gp.php?GROUP=globalstar&FORMAT=tle",
    "GNSS": "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=tle",
    "Intelsat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=intelsat&FORMAT=tle",
    "Iridium": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=tle",
    "Military": "https://celestrak.org/NORAD/elements/gp.php?GROUP=military&FORMAT=tle",
    "New": "https://celestrak.org/NORAD/elements/gp.php?GROUP=last-30-days&FORMAT=tle",
    "OneWeb": "https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=tle",
    "Orbcomm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=orbcomm&FORMAT=tle",
    "Resource": "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=tle",
    "SatNOGS": "https://celestrak.org/NORAD/elements/gp.php?GROUP=satnogs&FORMAT=tle",
    "Science": "https://celestrak.org/NORAD/elements/gp.php?GROUP=science&FORMAT=tle",
    "Spire": "https://celestrak.org/NORAD/elements/gp.php?GROUP=spire&FORMAT=tle",
    "Starlink": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
    "Swarm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=swarm&FORMAT=tle",
    "Weather": "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle",
    "X-Comm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=x-comm&FORMAT=tle",
    "Amsat": "https://amsat.org/tle/current/nasabare.txt",
    "Classified": "https://www.mmccants.org/tles/classfd.zip",
    "McCants": "https://www.mmccants.org/tles/inttles.zip",
    "R4UAB": "https://r4uab.ru/satonline.txt"
}

SATNOGS_API_URL = "https://db.satnogs.org/api/transmitters/?format=json&status=active"

def fetch_url(url: str, timeout: int = 30) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"  错误: 无法获取 {url}: {e}")
        return ""

def fetch_zip_content(url: str) -> str:
    """下载并解压ZIP文件中的TLE内容"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # 获取第一个txt文件
            for filename in z.namelist():
                if filename.endswith('.txt') or filename.endswith('.tle'):
                    return z.read(filename).decode('utf-8', errors='ignore')
        return ""
    except Exception as e:
        print(f"  错误: 无法获取ZIP {url}: {e}")
        return ""

def parse_tle_content(content: str) -> dict:
    """解析TLE格式内容，返回 {norad_id: (name, line1, line2)}"""
    tle_data = {}
    lines = content.strip().splitlines()
    
    # 过滤空行
    lines = [line.rstrip() for line in lines if line.strip()]
    
    i = 0
    while i < len(lines):
        # 尝试查找TLE三元组（名称 + 两行数据）
        if i + 2 < len(lines):
            name = lines[i].strip()
            line1 = lines[i+1].strip()
            line2 = lines[i+2].strip()
            
            # 验证是否为TLE格式（第1行以"1 "开头，第2行以"2 "开头）
            if (line1.startswith('1 ') and line2.startswith('2 ')):
                # 提取NORAD ID
                try:
                    norad_id = line1[2:7].strip()
                    if norad_id and norad_id not in tle_data:
                        tle_data[norad_id] = (name, line1, line2)
                except:
                    pass
                i += 3
            else:
                i += 1
        else:
            i += 1
    
    return tle_data

def process_tle_source(name: str, url: str, all_satellites: dict) -> int:
    print(f"  正在获取 {name}...")
    
    # 特殊处理ZIP文件
    if url.endswith('.zip'):
        content = fetch_zip_content(url)
    else:
        content = fetch_url(url)
    
    if not content:
        return 0
    
    satellites = parse_tle_content(content)
    count = 0
    for norad_id, tle in satellites.items():
        if norad_id not in all_satellites:
            all_satellites[norad_id] = tle
            count += 1
    
    print(f"    获取到 {len(satellites)} 颗卫星，新增: {count}")
    return len(satellites)

def download_satnogs_data(output_file: str = "radio.json") -> bool:
    print(f"\n正在从 SatNOGS API 获取数据...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(SATNOGS_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 保存 SatNOGS 数据到 {output_file}, 条目: {len(data)}")
        return True
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return False

def write_cn_txt(satellites: dict, filename: str = "tle.txt"):
    with open(filename, 'w', encoding='utf-8') as f:
        for sat_id, tle in satellites.items():
            f.write(f"{tle[0]}\n{tle[1]}\n{tle[2]}\n")

def main():
    print("开始获取卫星TLE数据...")
    all_satellites = OrderedDict()
    
    for name, url in SATELLITE_URLS.items():
        process_tle_source(name, url, all_satellites)
    
    download_satnogs_data("radio.json")
    write_cn_txt(all_satellites, "tle.txt")
    print(f"\n✅ 完成，共合并 {len(all_satellites)} 颗卫星（去重后），保存到 tle.txt")

if __name__ == "__main__":
    main()
