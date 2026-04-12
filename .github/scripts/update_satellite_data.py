#!/usr/bin/env python3
"""
卫星TLE数据获取和整合脚本
从多个数据源获取卫星数据，合并去重后生成cn.txt文件
"""

import requests
import csv
import zipfile
import io
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

def parse_tle_line(line: str) -> Tuple[str, str, str]:
    """
    解析TLE格式的行
    返回 (卫星名称, 第1行, 第2行)
    """
    line = line.strip()
    if not line:
        return None, None, None
    return line

def parse_celestrak_csv(content: str) -> Dict[str, Tuple[str, str]]:
    """
    解析Celestrak的CSV格式数据，转换为TLE格式
    CSV格式: OBJECT_NAME,OBJECT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,
            RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY,EPHEMERIS_TYPE,
            CLASSIFICATION_TYPE,NORAD_CAT_ID,ELEMENT_SET_NO,REV_AT_EPOCH,
            BSTAR,MEAN_MOTION_DOT,MEAN_MOTION_DDOT
    """
    tle_data = {}
    lines = content.strip().split('\n')
    if len(lines) <= 1:
        return tle_data
    
    reader = csv.DictReader(lines)
    for row in reader:
        try:
            norad_id = row['NORAD_CAT_ID'].strip()
            name = row['OBJECT_NAME'].strip()
            
            # 构建TLE格式的两行数据
            # 第1行: 卫星名称
            line1 = name
            
            # 第2行: 标准TLE格式 (行号1)
            # 格式: 1 NNNNNU YYNNNPPP YYYYDDD.DDDDDDDD +.DDDDDDDD +DDDDD-D +DDDDD-D D NNNNN
            # 简化处理，构建基本格式
            epoch = row['EPOCH'].replace('T', '.').replace('-', '').replace(':', '')[:14]
            if len(epoch) < 14:
                epoch = epoch.ljust(14, '0')
            
            # 计算平均运动
            mean_motion = float(row['MEAN_MOTION'])
            # 计算BSTAR (已经是科学计数法格式)
            bstar = float(row['BSTAR']) if row['BSTAR'] else 0
            
            # 构建TLE第2行
            tle_line2 = f"1 {norad_id:>5}U {epoch:>14}  .{abs(mean_motion):08f}  {float(row['ECCENTRICITY']):.7f}  {float(row['INCLINATION']):>8f}  {float(row['RA_OF_ASC_NODE']):>8f}  {float(row['ARG_OF_PERICENTER']):>8f}  {float(row['MEAN_ANOMALY']):>8f}  {float(row['MEAN_MOTION_DOT']):>10} {bstar:>10}"
            
            # 简化版本：只存储名称和NORAD ID作为key
            tle_data[norad_id] = (line1, tle_line2)
            
        except Exception as e:
            print(f"  解析CSV行时出错: {e}")
            continue
    
    return tle_data

def parse_tle_file(content: str, source_name: str) -> Dict[str, Tuple[str, str, str]]:
    """
    解析标准TLE格式文件（三行一组：名称，第1行，第2行）
    """
    tle_data = {}
    lines = content.strip().split('\n')
    i = 0
    
    while i < len(lines):
        # 跳过空行
        if not lines[i].strip():
            i += 1
            continue
        
        # 获取卫星名称
        if i + 2 >= len(lines):
            break
        
        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()
        
        # 验证TLE格式（第1行应以1开头，第2行应以2开头）
        if line1.startswith('1') and line2.startswith('2'):
            # 提取NORAD ID（第1行第3-7字符）
            norad_id = line1[2:7].strip()
            if norad_id:
                tle_data[norad_id] = (name, line1, line2)
            else:
                # 如果没有NORAD ID，使用名称作为key
                tle_data[name] = (name, line1, line2)
        
        i += 3
    
    return tle_data

def fetch_url(url: str, timeout: int = 30) -> str:
    """获取URL内容"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  错误: 无法获取 {url}: {e}")
        return ""

def process_celestrak_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理Celestrak CSV格式数据源"""
    print(f"  正在获取 {name}...")
    content = fetch_url(url)
    if not content:
        return 0
    
    satellites = parse_celestrak_csv(content)
    count = 0
    for norad_id, tle_data in satellites.items():
        if norad_id not in all_satellites:
            all_satellites[norad_id] = tle_data
            count += 1
    
    print(f"    新增卫星: {count}")
    return len(satellites)

def process_tle_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理标准TLE格式数据源"""
    print(f"  正在获取 {name}...")
    content = fetch_url(url)
    if not content:
        return 0
    
    satellites = parse_tle_file(content, name)
    count = 0
    for sat_id, tle_data in satellites.items():
        if sat_id not in all_satellites:
            all_satellites[sat_id] = tle_data
            count += 1
    
    print(f"    新增卫星: {count}")
    return len(satellites)

def process_zip_source(name: str, url: str, all_satellites: Dict) -> int:
    """处理ZIP压缩包格式的数据源"""
    print(f"  正在获取 {name}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            total_count = 0
            for filename in z.namelist():
                if filename.endswith('.tle') or filename.endswith('.txt'):
                    content = z.read(filename).decode('utf-8', errors='ignore')
                    satellites = parse_tle_file(content, name)
                    count = 0
                    for sat_id, tle_data in satellites.items():
                        if sat_id not in all_satellites:
                            all_satellites[sat_id] = tle_data
                            count += 1
                    total_count += count
                    print(f"    从 {filename} 新增卫星: {count}")
            return total_count
    except Exception as e:
        print(f"  错误: 无法处理ZIP {url}: {e}")
        return 0

def write_cn_txt(satellites: Dict, filename: str = "cn.txt"):
    """将卫星数据写入cn.txt文件（TLE格式）"""
    with open(filename, 'w', encoding='utf-8') as f:
        for sat_id, tle_data in satellites.items():
            if len(tle_data) == 3:
                # 标准TLE格式
                name, line1, line2 = tle_data
                f.write(f"{name}\n")
                f.write(f"{line1}\n")
                f.write(f"{line2}\n")
            elif len(tle_data) == 2:
                # 简化格式
                name, line2 = tle_data
                f.write(f"{name}\n")
                f.write(f"{line2}\n")
                # 添加一个占位符第2行
                f.write(f"2 {sat_id:>5} 0   0   0   0   0   0   0 0   0\n")
            f.write("\n")

def main():
    print("=" * 60)
    print("卫星TLE数据获取和整合工具")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    all_satellites = OrderedDict()
    source_stats = {}
    
    for source_name, url in SATELLITE_URLS.items():
        print(f"\n处理数据源: {source_name}")
        
        # 根据URL类型选择处理方法
        if 'celestrak.org' in url and 'FORMAT=csv' in url:
            count = process_celestrak_source(source_name, url, all_satellites)
            source_stats[source_name] = count
        elif url.endswith('.zip'):
            count = process_zip_source(source_name, url, all_satellites)
            source_stats[source_name] = count
        else:
            count = process_tle_source(source_name, url, all_satellites)
            source_stats[source_name] = count
    
    print("\n" + "=" * 60)
    print("数据源统计:")
    print("=" * 60)
    for source_name, count in source_stats.items():
        print(f"  {source_name:15} : {count:>6} 颗卫星")
    
    print("\n" + "=" * 60)
    print(f"合并统计:")
    print(f"  总共获取卫星数: {sum(source_stats.values())}")
    print(f"  去重后卫星数: {len(all_satellites)}")
    print(f"  去重数量: {sum(source_stats.values()) - len(all_satellites)}")
    print("=" * 60)
    
    # 写入文件
    write_cn_txt(all_satellites, "cn.txt")
    
    print(f"\n✅ 成功生成 cn.txt 文件，包含 {len(all_satellites)} 颗卫星的TLE数据")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()