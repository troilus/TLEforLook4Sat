import requests    
import zipfile    
import io    
from collections import OrderedDict    
import json    
    
# 数据源定义 - 来自 Sources.kt [1](#2-0)     
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
    
def parse_csv_line(line):  
    """解析 CSV 行，返回 OrbitalData"""  
    values = line.split(",")  
    if len(values) < 18:  # CSV 实际有 18 个字段  
        return None  
        
    try:  
        name = values[0]  
        catnum = int(values[11])  
          
        # 从 CSV 字段构造正确的 TLE 格式  
        # EPOCH 格式: 2026-04-11T18:40:52.900320  
        epoch_str = values[2]  
        year = int(epoch_str[2:4])  # 26  
        day_of_year = get_day_of_year_from_iso(epoch_str[:10])  
        frac_day = get_fractional_day(epoch_str[11:])  
          
        # TLE Line 1: 1 25544U 98067A   26101.77953719  .00000000  00000-0  00000+0 0  0000  
        tle_line1 = f"1 {catnum:5d}U {values[1]} {year:02d}{day_of_year:03d}{frac_day:12.8f}  .00000000  00000-0  00000+0 0  0000"  
          
        # TLE Line 2: 2 25544  51.6325 268.2674 0006454 301.3432  58.6925 15.48877641392888  
        tle_line2 = f"2 {catnum:5d} {float(values[5]):8.4f} {float(values[6]):8.4f} {float(values[4]):7.7f} {float(values[7]):8.4f} {float(values[8]):8.4f} {float(values[3]):11.8f}00000"  
          
        return name, tle_line1, tle_line2  
    except Exception as e:  
        print(f"CSV解析错误: {e}")  
        return None  
  
def get_day_of_year_from_iso(date_str):  
    """从 ISO 日期获取年积日"""  
    from datetime import datetime  
    dt = datetime.strptime(date_str, "%Y-%m-%d")  
    return dt.timetuple().tm_yday  
  
def get_fractional_day(time_str):  
    """从时间字符串获取日的小数部分"""  
    h, m, s = time_str.split(':')  
    seconds = float(s)  
    total_seconds = int(h) * 3600 + int(m) * 60 + seconds  
    return total_seconds / 86400.0  
    
def parse_tle_lines(lines):    
    """解析 TLE 三行格式 - 参考 DataParser.parseTLE() [3](#2-2) """    
    tle_data = []    
    i = 0    
    while i < len(lines) - 2:    
        if lines[i].strip() and lines[i+1].startswith('1 ') and lines[i+2].startswith('2 '):    
            name = lines[i].strip()    
            line1 = lines[i+1].strip()    
            line2 = lines[i+2].strip()    
            tle_data.append((name, line1, line2))    
            i += 3    
        else:    
            i += 1    
    return tle_data    
    
def main():    
    # 使用 OrderedDict 保持插入顺序，后插入的会覆盖先插入的（模拟 REPLACE 策略）    
    satellites = OrderedDict()    
    source_stats = {}  # 记录每个源的卫星数量  
    total_before_dedup = 0  # 去重前的总数  
        
    print("开始下载卫星数据...")    
        
    for source_name, url in SATELLITE_URLS.items():    
        if not url:    
            continue    
                
        print(f"处理源: {source_name}")    
        source_count = 0  
            
        try:    
            response = requests.get(url, timeout=30)    
            response.raise_for_status()    
                
            if source_name in ["Classified", "McCants"]:    
                # 处理 ZIP 文件 - 参考 DatabaseRepo 中的 ZIP 处理 [4](#2-3)     
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:    
                    for file_name in zip_file.namelist():    
                        if file_name.endswith('.txt'):    
                            with zip_file.open(file_name) as f:    
                                content = f.read().decode('utf-8')    
                                lines = content.strip().split('\n')    
                                tle_data = parse_tle_lines(lines)    
                                for name, line1, line2 in tle_data:    
                                    catnum = int(line1[2:7])    
                                    satellites[catnum] = (name, line1, line2)    
                                    source_count += 1  
            elif source_name in ["Amsat", "R4UAB"]:    
                # 处理 TLE 文件    
                lines = response.text.strip().split('\n')    
                tle_data = parse_tle_lines(lines)    
                for name, line1, line2 in tle_data:    
                    catnum = int(line1[2:7])    
                    satellites[catnum] = (name, line1, line2)    
                    source_count += 1  
            else:    
                # 处理 CSV 文件    
                lines = response.text.strip().split('\n')    
                for line in lines[1:]:  # 跳过标题行    
                    parsed = parse_csv_line(line)    
                    if parsed:    
                        name, line1, line2 = parsed    
                        catnum = int(line1[2:7])    
                        satellites[catnum] = (name, line1, line2)    
                        source_count += 1  
                            
            # 记录该源的统计信息  
            if source_count > 0:  
                source_stats[source_name] = source_count  
                total_before_dedup += source_count  
                print(f"  -> 从 {source_name} 提取了 {source_count} 个卫星数据")  
                            
        except Exception as e:    
            print(f"处理 {source_name} 时出错: {e}")    
            continue    
      
    # 计算去重统计  
    final_count = len(satellites)  
    duplicates_removed = total_before_dedup - final_count  
      
    print("\n" + "="*50)  
    print("数据源统计汇总:")  
    print("="*50)  
    for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):  
        print(f"{source:15} : {count:5} 个卫星")  
      
    print("\n" + "-"*50)  
    print(f"去重前总卫星数: {total_before_dedup}")  
    print(f"重复卫星数量:   {duplicates_removed}")  
    print(f"最终剩余数量:   {final_count}")  
    print("-"*50)  
        
    # 写入 cn.txt 文件    
    print(f"\n写入 {final_count} 个卫星数据到 cn.txt")    
    with open('cn.txt', 'w', encoding='utf-8') as f:    
        for catnum, (name, line1, line2) in satellites.items():    
            f.write(f"{name}\n{line1}\n{line2}\n")    
        
    print("完成!")    
    
if __name__ == "__main__":    
    main()