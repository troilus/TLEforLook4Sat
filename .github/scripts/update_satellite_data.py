#!/usr/bin/env python3
"""
卫星TLE数据获取和整合脚本
从多个数据源获取卫星数据，合并去重后生成cn.txt文件
同时从SatNOGS API获取活跃发射机数据保存为trans.json
"""

import requests
import csv
import zipfile
import io
import json
import re
from datetime import datetime
from collections import OrderedDict
from typing import Dict, List, Tuple, Set

# 数据源定义
SATELLITE_URLS = {
    "All": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=csv",
    "Amateur": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=csv",
    "Brightest": "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=csv",
    "Cubesat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cubesat&FORMAT=csv",
    "Education": "https://celestrak.org/NORAD/elements/gp.php?GROUP=education&FORMAT=csv",
    "Engineer": "https://celestrak.org/NORAD/elements/gp.php?GROUP=engineering&FORMAT=csv",
    "Geostationary": "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=csv",
    "Globalstar": "https://celestrak.org/NORAD/elements/gp.php?GROUP=globalstar&FORMAT=csv",
    "GNSS": "https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=csv",
    "Intelsat": "https://celestrak.org/NORAD/elements/gp.php?GROUP=intelsat&FORMAT=csv",
    "Iridium": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=csv",
    "Military": "https://celestrak.org/NORAD/elements/gp.php?GROUP=military&FORMAT=csv",
    "New": "https://celestrak.org/NORAD/elements/gp.php?GROUP=last-30-days&FORMAT=csv",
    "OneWeb": "https://celestrak.org/NORAD/elements/gp.php?GROUP=oneweb&FORMAT=csv",
    "Orbcomm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=orbcomm&FORMAT=csv",
    "Resource": "https://celestrak.org/NORAD/elements/gp.php?GROUP=resource&FORMAT=csv",
    "SatNOGS": "https://celestrak.org/NORAD/elements/gp.php?GROUP=satnogs&FORMAT=csv",
    "Science": "https://celestrak.org/NORAD/elements/gp.php?GROUP=science&FORMAT=csv",
    "Spire": "https://celestrak.org/NORAD/elements/gp.php?GROUP=spire&FORMAT=csv",
    "Starlink": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=csv",
    "Swarm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=swarm&FORMAT=csv",
    "Weather": "https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=csv",
    "X-Comm": "https://celestrak.org/NORAD/elements/gp.php?GROUP=x-comm&FORMAT=csv",
    "Amsat": "https://amsat.org/tle/current/nasabare.txt",
    "Classified": "https://www.mmccants.org/tles/classfd.zip",
    "McCants": "https://www.mmccants.org/tles/inttles.zip",
    "R4UAB": "https://r4uab.ru/satonline.txt"
}

# SatNOGS API URL
SATNOGS_API_URL = "https://db.satnogs.org/api/transmitters/?format=json&status=active"

def fetch_url(url: str, timeout: int = 30) -> str:
    """获取URL内容"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
    except Exception as e:
        print(f"  错误: 无法获取 {url}: {e}")
        return ""

def parse_tle_file(content: str) -> Dict[str, Tuple[str, str, str]]:
    """
    解析标准TLE格式文件（三行一组：第0行名称，第1行，第2行）
    返回 {norad_id: (name, line1, line2)}
    """
    tle_data = {}
    lines = content.strip().split('\n')
    i = 0
    
    while i < len(lines):
        # 跳过空行
        if not lines[i].strip():
            i += 1
            continue
        
        # 需要至少3行
        if i + 2 >= len(lines):
            break
        
        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()
        
        # 验证TLE格式
        if line1.startswith('1') and line2.startswith('2'):
            # 提取NORAD ID（第1行第3-7字符）
            norad_id = line1[2:7].strip()
            if norad_id:
                tle_data[norad_id] = (name, line1, line2)
            else:
                # 如果没有NORAD ID，使用名称的哈希作为key
                tle_data[name] = (name, line1, line2)
        
        i += 3
    
    return tle_data

def parse_celestrak_csv_to_tle(content: str) -> Dict[str, Tuple[str, str, str]]:
    """
    解析Celestrak的CSV格式数据，转换为标准TLE格式
    """
    tle_data = {}
    lines = content.strip().split('\n')
    if len(lines) <= 1:
        return tle_data
    
    try:
        reader = csv.DictReader(lines)
        for row in reader:
            try:
                norad_id = row.get('NORAD_CAT_ID', '').strip()
                if not norad_id or norad_id == '0':
                    continue
                
                name = row.get('OBJECT_NAME', '').strip()
                if not name:
                    continue
                
                # 获取TLE参数
                epoch = row.get('EPOCH', '').replace('T', '.').replace('-', '').replace(':', '')
                # 格式化为YYYYDDD.DDDDDDDD
                if len(epoch) >= 14:
                    epoch = epoch[:14]
                else:
                    epoch = epoch.ljust(14, '0')
                
                # 计算各项参数（转换为TLE格式需要的格式）
                mean_motion = float(row.get('MEAN_MOTION', 0))
                eccentricity = float(row.get('ECCENTRICITY', 0))
                inclination = float(row.get('INCLINATION', 0))
                ra_of_asc_node = float(row.get('RA_OF_ASC_NODE', 0))
                arg_of_pericenter = float(row.get('ARG_OF_PERICENTER', 0))
                mean_anomaly = float(row.get('MEAN_ANOMALY', 0))
                mean_motion_dot = float(row.get('MEAN_MOTION_DOT', 0)) / 1440.0  # 转换为每天
                bstar = float(row.get('BSTAR', 0))
                
                # 构建第1行
                # 格式: 1 NNNNNU YYNNNPPP YYYYDDD.DDDDDDDD +.DDDDDDDD +DDDDD-D +DDDDD-D D NNNNN
                line1 = f"1 {norad_id:>5}U {epoch:<14} {mean_motion_dot: .8e} {bstar: .8e} 0 0"
                # 简化版本，确保长度正确
                line1 = line1.ljust(69)[:69]
                
                # 构建第2行
                # 格式: 2 NNNNN DD.DDDD DD.DDDD DDDDDDD DDD.DDDD DDD.DDDD DD.DDDDDDDDDDDD
                line2 = f"2 {norad_id:>5} {inclination:8.4f} {ra_of_asc_node:8.4f} {eccentricity:7.0f} {arg_of_pericenter:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}"
                line2 = line2.ljust(69)[:69]
                
                tle_data[norad_id] = (name, line1, line2)
                
            except Exception as e:
                print(f"  解析CSV行时出错: {e}")
                continue
    except Exception as e:
        print(f"  解析CSV文件时出错: {e}")
    
    return tle_data

def process_celestrak_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理Celestrak CSV格式数据源"""
    print(f"  正在获取 {name}...")
    content = fetch_url(url)
    if not content:
        return 0
    
    satellites = parse_celestrak_csv_to_tle(content)
    count = 0
    for norad_id, tle_data in satellites.items():
        if norad_id not in all_satellites:
            all_satellites[norad_id] = tle_data
            count += 1
    
    print(f"    获取到 {len(satellites)} 颗卫星，新增: {count}")
    return len(satellites)

def process_tle_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理标准TLE格式数据源"""
    print(f"  正在获取 {name}...")
    content = fetch_url(url)
    if not content:
        return 0
    
    satellites = parse_tle_file(content)
    count = 0
    for sat_id, tle_data in satellites.items():
        if sat_id not in all_satellites:
            all_satellites[sat_id] = tle_data
            count += 1
    
    print(f"    获取到 {len(satellites)} 颗卫星，新增: {count}")
    return len(satellites)

def process_zip_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理ZIP压缩包格式的数据源"""
    print(f"  正在获取 {name}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        
        total_count = 0
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            for filename in z.namelist():
                if filename.endswith('.tle') or filename.endswith('.txt'):
                    try:
                        content = z.read(filename).decode('utf-8', errors='ignore')
                        satellites = parse_tle_file(content)
                        count = 0
                        for sat_id, tle_data in satellites.items():
                            if sat_id not in all_satellites:
                                all_satellites[sat_id] = tle_data
                                count += 1
                        total_count += count
                        if count > 0:
                            print(f"    从 {filename} 新增卫星: {count}")
                    except Exception as e:
                        print(f"    处理 {filename} 时出错: {e}")
        return total_count
    except Exception as e:
        print(f"  错误: 无法处理ZIP {url}: {e}")
        return 0

def download_satnogs_data(output_file: str = "trans.json") -> bool:
    """
    从 SatNOGS API 下载活跃的发射机数据，并保存为 JSON 文件。
    """
    print(f"\n正在从 SatNOGS API 获取数据...")
    print(f"API URL: {SATNOGS_API_URL}")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(SATNOGS_API_URL, timeout=30, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict):
            count = len(data.get('results', [])) if 'results' in data else len(data)
        else:
            count = "未知数量"
            
        print(f"✅ 成功保存 SatNOGS 数据到 {output_file}")
        print(f"   数据条目数量: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

def write_cn_txt(satellites: Dict, filename: str = "cn.txt"):
    """将卫星数据写入cn.txt文件（标准TLE格式，无空行）"""
    with open(filename, 'w', encoding='utf-8') as f:
        for sat_id, tle_data in satellites.items():
            if len(tle_data) == 3:
                name, line1, line2 = tle_data
                f.write(f"{name}\n")
                f.write(f"{line1}\n")
                f.write(f"{line2}\n")
            else:
                # 格式错误的数据，跳过
                print(f"警告: 卫星 {sat_id} 数据格式错误，跳过")
                continue

def main():
    print("=" * 60)
    print("卫星TLE数据获取和整合工具")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_satellites = OrderedDict()
    source_stats = {}
    
    # 处理所有卫星数据源
    for source_name, url in SATELLITE_URLS.items():
        print(f"\n处理数据源: {source_name}")
        
        if 'celestrak.org' in url and 'FORMAT=csv' in url:
            count = process_celestrak_source(source_name, url, all_satellites)
            source_stats[source_name] = count
        elif url.endswith('.zip'):
            count = process_zip_source(source_name, url, all_satellites)
            source_stats[source_name] = count
        else:
            count = process_tle_source(source_name, url, all_satellites)
            source_stats[source_name] = count
    
    # 下载 SatNOGS 数据
    download_satnogs_data("trans.json")
    
    print("\n" + "=" * 60)
    print("数据源统计:")
    print("=" * 60)
    total_raw = 0
    for source_name, count in source_stats.items():
        print(f"  {source_name:15} : {count:>6} 颗卫星")
        total_raw += count
    
    print("\n" + "=" * 60)
    print(f"合并统计:")
    print(f"  总共获取卫星数: {total_raw}")
    print(f"  去重后卫星数: {len(all_satellites)}")
    print(f"  去重数量: {total_raw - len(all_satellites)}")
    print("=" * 60)
    
    # 写入文件（无空行）
    write_cn_txt(all_satellites, "cn.txt")
    
    # 验证输出格式
    with open("cn.txt", 'r') as f:
        lines = f.readlines()
        print(f"\n✅ 成功生成 cn.txt 文件")
        print(f"   总行数: {len(lines)}")
        print(f"   卫星数: {len(all_satellites)}")
        if lines:
            print(f"   前几行预览:")
            for i in range(min(6, len(lines))):
                print(f"     {lines[i].rstrip()}")
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()