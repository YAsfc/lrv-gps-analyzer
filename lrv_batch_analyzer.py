#!/usr/bin/env python3
"""
LRVファイル一括GPS解析ツール
指定したフォルダ内のすべてのLRVファイルからGPSデータを抽出してCSVファイルに出力します。

使用方法:
    python lrv_batch_analyzer.py <フォルダパス> [出力CSVファイル名]

例:
    python lrv_batch_analyzer.py "/Volumes/GO 3S/DCIM/Camera01" gps_data.csv
"""

import os
import sys
import subprocess
import csv
import re
from datetime import datetime
from pathlib import Path

def parse_coordinate(coord_str):
    """座標文字列をデシマル度に変換"""
    # 例: "35 deg 37' 35.50\" N" -> 35.626528
    match = re.match(r'(\d+)\s*deg\s*(\d+)\'\s*([\d.]+)"\s*([NSEW])', coord_str)
    
    if match:
        degrees = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        direction = match.group(4)
        
        decimal = degrees + minutes / 60 + seconds / 3600
        
        if direction in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    
    return 0.0

def parse_gps_time(time_str):
    """GPS時刻をパース"""
    # 例: "2025:06:30 02:13:56.9Z" -> datetime
    try:
        clean_time = time_str.replace('Z', '').strip()
        if '.' in clean_time:
            # 秒の小数部分を削除
            clean_time = clean_time.split('.')[0]
        
        return datetime.strptime(clean_time, '%Y:%m:%d %H:%M:%S')
    except:
        return None

def extract_gps_data(lrv_file_path):
    """LRVファイルからGPSデータを抽出"""
    print(f"解析中: {os.path.basename(lrv_file_path)}")
    
    try:
        # exiftoolでGPSデータを抽出
        cmd = [
            'exiftool', '-ee', 
            lrv_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"エラー: {lrv_file_path} - {result.stderr}")
            return []
        
        # 出力をパース
        gps_data = []
        current_point = {}
        
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
                
            if 'GPS Date/Time' in line:
                # 前のポイントを保存
                if current_point and 'datetime' in current_point:
                    gps_data.append(current_point)
                
                # 新しいポイントを開始
                time_str = line.split(':', 1)[1].strip()
                parsed_time = parse_gps_time(time_str)
                if parsed_time:
                    current_point = {
                        'datetime': parsed_time,
                        'latitude': 0.0,
                        'longitude': 0.0,
                        'altitude': 0.0,
                        'speed': 0.0,
                        'track': 0.0
                    }
            elif 'GPS Latitude' in line:
                if current_point:
                    coord_str = line.split(':', 1)[1].strip()
                    current_point['latitude'] = parse_coordinate(coord_str)
            elif 'GPS Longitude' in line:
                if current_point:
                    coord_str = line.split(':', 1)[1].strip()
                    current_point['longitude'] = parse_coordinate(coord_str)
            elif 'GPS Altitude' in line:
                if current_point:
                    try:
                        alt_str = line.split(':', 1)[1].strip()
                        current_point['altitude'] = float(alt_str.split()[0])
                    except:
                        current_point['altitude'] = 0.0
            elif 'GPS Speed' in line:
                if current_point:
                    try:
                        speed_str = line.split(':', 1)[1].strip()
                        current_point['speed'] = float(speed_str)
                    except:
                        current_point['speed'] = 0.0
            elif 'GPS Track' in line:
                if current_point:
                    try:
                        track_str = line.split(':', 1)[1].strip()
                        current_point['track'] = float(track_str)
                    except:
                        current_point['track'] = 0.0
        
        # 最後のポイントを保存
        if current_point and 'datetime' in current_point:
            gps_data.append(current_point)
        
        print(f"  → {len(gps_data)} GPS ポイントを抽出")
        return gps_data
        
    except subprocess.TimeoutExpired:
        print(f"タイムアウト: {lrv_file_path}")
        return []
    except Exception as e:
        print(f"エラー: {lrv_file_path} - {str(e)}")
        return []

def find_lrv_files(folder_path):
    """フォルダ内のすべてのLRVファイルを検索"""
    lrv_files = []
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith('.lrv'):
                lrv_files.append(os.path.join(root, file))
    
    return sorted(lrv_files)

def write_csv(all_data, output_file):
    """CSVファイルに出力"""
    print(f"CSV出力: {output_file}")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'ファイル名',
            'タイムスタンプ',
            '緯度',
            '経度',
            '高度(m)',
            '速度(m/s)',
            '方向(度)'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        total_points = 0
        for file_data in all_data:
            filename = file_data['filename']
            for point in file_data['gps_points']:
                writer.writerow({
                    'ファイル名': filename,
                    'タイムスタンプ': point['datetime'].strftime('%Y-%m-%d %H:%M:%S'),
                    '緯度': f"{point['latitude']:.6f}",
                    '経度': f"{point['longitude']:.6f}",
                    '高度(m)': f"{point['altitude']:.1f}",
                    '速度(m/s)': f"{point['speed']:.3f}",
                    '方向(度)': f"{point['track']:.1f}"
                })
                total_points += 1
        
        print(f"総GPSポイント数: {total_points}")

def main():
    if len(sys.argv) < 2:
        print("使用方法: python lrv_batch_analyzer.py <フォルダパス> [出力CSVファイル名]")
        print("例: python lrv_batch_analyzer.py \"/Volumes/GO 3S/DCIM/Camera01\" gps_data.csv")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'lrv_gps_data.csv'
    
    # フォルダが存在するかチェック
    if not os.path.exists(folder_path):
        print(f"エラー: フォルダが見つかりません: {folder_path}")
        sys.exit(1)
    
    # exiftoolが利用可能かチェック
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("エラー: exiftoolがインストールされていません")
        print("macOSの場合: brew install exiftool")
        sys.exit(1)
    
    # 単一ファイルかフォルダかをチェック
    if os.path.isfile(folder_path) and folder_path.lower().endswith('.lrv'):
        print(f"単一ファイルを処理: {folder_path}")
        lrv_files = [folder_path]
    else:
        print(f"フォルダを検索中: {folder_path}")
        lrv_files = find_lrv_files(folder_path)
    
    if not lrv_files:
        print("LRVファイルが見つかりませんでした")
        sys.exit(1)
    
    print(f"発見したLRVファイル: {len(lrv_files)}個")
    
    all_data = []
    processed_files = 0
    
    for lrv_file in lrv_files:
        filename = os.path.basename(lrv_file)
        gps_points = extract_gps_data(lrv_file)
        
        if gps_points:
            all_data.append({
                'filename': filename,
                'gps_points': gps_points
            })
            processed_files += 1
    
    if all_data:
        write_csv(all_data, output_file)
        print(f"\n完了!")
        print(f"処理したファイル: {processed_files}/{len(lrv_files)}")
        print(f"出力ファイル: {output_file}")
    else:
        print("GPSデータを含むファイルが見つかりませんでした")

if __name__ == "__main__":
    main()