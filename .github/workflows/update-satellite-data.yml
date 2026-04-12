import requests  
import zipfile  
import io  
from collections import OrderedDict  
import json  
  
SATELLITE_URLS = {  
    "All": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=csv",  
    # ... 其他 URL 保持不变  
}  
  
def parse_csv_line(line):  
    """解析 CSV 行"""  
    values = line.split(",")  
    if len(values) < 18:  
        return None  
      
    try:  
        name = values[0].strip()  
        catnum = int(values[11])  
        return name, catnum  
    except Exception as e:  
        print(f"CSV解析错误: {e}")  
        return None  
  
def parse_tle_lines(lines):  
    """解析 TLE 三行格式"""  
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
    satellites = OrderedDict()  
    source_stats = {}  
    total_before_dedup = 0  
      
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
                # ZIP 文件处理  
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
                # TLE 文件处理  
                lines = response.text.strip().split('\n')  
                tle_data = parse_tle_lines(lines)  
                for name, line1, line2 in tle_data:  
                    catnum = int(line1[2:7])  
                    satellites[catnum] = (name, line1, line2)  
                    source_count += 1  
            else:  
                # CSV 文件处理 - 简化版本  
                lines = response.text.strip().split('\n')  
                if len(lines) > 1:  # 确保有数据  
                    for line in lines[1:]:  # 跳过标题行  
                        parsed = parse_csv_line(line)  
                        if parsed:  
                            name, catnum = parsed  
                            # 存储简化标记，实际使用时需要转换  
                            satellites[catnum] = (name, f"CSV_DATA_{catnum}", f"CSV_DATA_{catnum}")  
                            source_count += 1  
                  
            if source_count > 0:  
                source_stats[source_name] = source_count  
                total_before_dedup += source_count  
                print(f"  -> 从 {source_name} 提取了 {source_count} 个卫星数据")  
                          
        except Exception as e:  
            print(f"处理 {source_name} 时出错: {e}")  
            continue  
      
    # 统计输出  
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
      
    # 写入文件  
    print(f"\n写入 {final_count} 个卫星数据到 cn.txt")  
    with open('cn.txt', 'w', encoding='utf-8') as f:  
        for catnum, (name, line1, line2) in satellites.items():  
            f.write(f"{name}\n{line1}\n{line2}\n")  
      
    print("完成!")  
  
if __name__ == "__main__":  
    main()