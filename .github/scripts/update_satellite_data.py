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
    """解析 CSV 行，返回 OrbitalData - 参考 DataParser.parseCSV() [2](#2-1) """  
    values = line.split(",")  
    if len(values) < 15:  
        return None  
      
    try:  
        name = values[0]  
        catnum = int(values[11])  
        # 提取 TLE 行信息  
        tle_line1 = f"1 {catnum:5d}U {values[1]} {values[2][:8]}{values[2][9:16].replace('.', '')}  .00000000  00000-0  00000+0 0  0000"  
        tle_line2 = f"2 {catnum:5d} {values[5]:8.4f} {values[6]:8.4f} {values[4]:7.7f} {values[7]:8.4f} {values[8]:8.4f} {values[3]:11.8f}00000"  
        return name, tle_line1, tle_line2  
    except:  
        return None  
  
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
      
    print("开始下载卫星数据...")  
      
    for source_name, url in SATELLITE_URLS.items():  
        if not url:  
            continue  
              
        print(f"处理源: {source_name}")  
          
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
            elif source_name in ["Amsat", "R4UAB"]:  
                # 处理 TLE 文件  
                lines = response.text.strip().split('\n')  
                tle_data = parse_tle_lines(lines)  
                for name, line1, line2 in tle_data:  
                    catnum = int(line1[2:7])  
                    satellites[catnum] = (name, line1, line2)  
            else:  
                # 处理 CSV 文件  
                lines = response.text.strip().split('\n')  
                for line in lines[1:]:  # 跳过标题行  
                    parsed = parse_csv_line(line)  
                    if parsed:  
                        name, line1, line2 = parsed  
                        catnum = int(line1[2:7])  
                        satellites[catnum] = (name, line1, line2)  
                          
        except Exception as e:  
            print(f"处理 {source_name} 时出错: {e}")  
            continue  
      
    # 写入 cn.txt 文件  
    print(f"写入 {len(satellites)} 个卫星数据到 cn.txt")  
    with open('cn.txt', 'w', encoding='utf-8') as f:  
        for catnum, (name, line1, line2) in satellites.items():  
            f.write(f"{name}\n{line1}\n{line2}\n")  
      
    print("完成!")  
  
if __name__ == "__main__":  
    main()