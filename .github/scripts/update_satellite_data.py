#!/usr/bin/env python3
"""
卫星TLE数据获取和整合脚本（改进版）
支持多个数据源，CSV格式数据转换为标准TLE
同时从SatNOGS API获取活跃发射机数据保存为trans.json
"""

import requests
import csv
import zipfile
import io
import json
from datetime import datetime
from collections import OrderedDict

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

def iso_to_tle_epoch(epoch_iso: str) -> str:
    """ISO时间转 TLE EPOCH YYDDD.DDDDDDDD"""
    dt = datetime.fromisoformat(epoch_iso)
    year = dt.year % 100
    day_of_year = dt.timetuple().tm_yday
    fraction = (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    return f"{year:02d}{day_of_year + fraction:012.8f}"

def format_tle_scientific(value: float) -> str:
    """格式化为TLE科学计数法 ±0.00000-0"""
    if value == 0:
        return " 00000-0"
    exponent = int(f"{value:e}".split('e')[1])
    mantissa = value / (10 ** exponent)
    mantissa_str = f"{mantissa: .5f}"[1:]  # 去掉前导空格
    return f"{mantissa_str}{exponent:+d}"

def parse_celestrak_csv_to_tle(content: str) -> dict:
    tle_data = {}
    lines = content.strip().splitlines()
    if len(lines) <= 1:
        return tle_data
    reader = csv.DictReader(lines)
    for row in reader:
        try:
            norad_id = row.get('NORAD_CAT_ID', '').strip()
            if not norad_id or norad_id == '0':
                continue
            name = row.get('OBJECT_NAME', '').strip()
            if not name:
                continue

            # 参数
            epoch_iso = row.get('EPOCH', '')
            mean_motion = float(row.get('MEAN_MOTION', 0))
            eccentricity = float(row.get('ECCENTRICITY', 0))
            inclination = float(row.get('INCLINATION', 0))
            ra_of_asc_node = float(row.get('RA_OF_ASC_NODE', 0))
            arg_of_pericenter = float(row.get('ARG_OF_PERICENTER', 0))
            mean_anomaly = float(row.get('MEAN_ANOMALY', 0))
            mean_motion_dot = float(row.get('MEAN_MOTION_DOT', 0))  # 每天
            bstar = float(row.get('BSTAR', 0))

            # 第1行
            epoch = iso_to_tle_epoch(epoch_iso)
            line1 = f"1 {int(norad_id):5d}U {epoch} {format_tle_scientific(mean_motion_dot):>10} {format_tle_scientific(bstar):>8} 0 0"
            line1 = line1.ljust(69)[:69]

            # 第2行
            ecc_str = f"{int(eccentricity * 1e7):07d}"  # 去掉小数点，7位
            line2 = f"2 {int(norad_id):5d} {inclination:8.4f} {ra_of_asc_node:8.4f} {ecc_str} {arg_of_pericenter:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}"
            line2 = line2.ljust(69)[:69]

            tle_data[norad_id] = (name, line1, line2)
        except Exception as e:
            print(f"  解析行出错: {e}")
    return tle_data

def process_celestrak_source(name: str, url: str, all_satellites: dict) -> int:
    print(f"  正在获取 {name}...")
    content = fetch_url(url)
    if not content:
        return 0
    satellites = parse_celestrak_csv_to_tle(content)
    count = 0
    for norad_id, tle in satellites.items():
        if norad_id not in all_satellites:
            all_satellites[norad_id] = tle
            count += 1
    print(f"    获取到 {len(satellites)} 颗卫星，新增: {count}")
    return len(satellites)

def download_satnogs_data(output_file: str = "trans.json") -> bool:
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

def write_cn_txt(satellites: dict, filename: str = "cn.txt"):
    with open(filename, 'w', encoding='utf-8') as f:
        for sat_id, tle in satellites.items():
            f.write(f"{tle[0]}\n{tle[1]}\n{tle[2]}\n")

def main():
    all_satellites = OrderedDict()
    for name, url in SATELLITE_URLS.items():
        process_celestrak_source(name, url, all_satellites)

    download_satnogs_data("trans.json")
    write_cn_txt(all_satellites, "cn.txt")
    print(f"\n✅ 完成, 共 {len(all_satellites)} 颗卫星, 保存到 cn.txt")

if __name__ == "__main__":
    main()