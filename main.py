# VideoConverter
#
# Copyright (c) 2024 led-mirage
# このソースコードは MITライセンス の下でライセンスされています。
# ライセンスの詳細については、このプロジェクトのLICENSEファイルを参照してください。

import os
import shutil
import subprocess
import sys
import argparse

APP_NAME = "動画変換ツール"
APP_VERSION = "1.0.0"
COPYRIGHT = "Copyright 2024 led-mirage"
APP_DESCRIPTION_RESOLUTION_CONVERT = "指定の解像度に動画を変換します。コーデックは H264/AAC となります。"
APP_DESCRIPTION_AUDIO_EXTRACT = "動画から音声を抽出します。コーデックは mp3 となります。"
BIN_FFMPEG_PATH = os.path.join("bin", "ffmpeg.exe")
SYSTEM_FFMPEG_PATH = "ffmpeg.exe"
INPUT_FOLDER = "01.入力"
OUTPUT_FOLDER = "02.出力"
SUPPORTED_FORMATS = [".mp4", ".avi", ".mkv", ".flv", ".mov", ".wmv"]

# プログラム引数を解析する
def parse_argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["convert", "extract"], default="convert", help="動作モード（convert: 解像度変更, extract: 音声抽出）")
    args = parser.parse_args()

    if args.mode == "convert":
        description = APP_DESCRIPTION_RESOLUTION_CONVERT
    elif args.mode == "extract":
        description = APP_DESCRIPTION_AUDIO_EXTRACT

    return args.mode, description

# 使用するFFmpegのパスを取得する
def find_ffmpeg():
    if os.path.isfile(BIN_FFMPEG_PATH):
        return BIN_FFMPEG_PATH
    if subprocess.run([SYSTEM_FFMPEG_PATH, "-version"], capture_output=True).returncode == 0:
        return SYSTEM_FFMPEG_PATH
    return None

# FFmpegのバージョンを取得する
def get_ffmpeg_version(ffmpeg_path):
    try:
        result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            # バージョン情報の最初の一行を取得
            version_info = result.stdout.split('\n')[0]
            return version_info
    except Exception as e:
        print(f"Error retrieving FFmpeg version: {e}")
    return "不明"

# NVIDIAのGPUが利用可能かを確認する
def is_nvenc_available(ffmpeg_path):
    try:
        result = subprocess.run([ffmpeg_path, "-encoders"], capture_output=True, text=True)
        return "h264_nvenc" in result.stdout
    except Exception as e:
        print(f"Error checking NVENC availability: {e}")
        return False

# 出力フォルダをクリアする
def clear_output_folder():
    if os.path.exists(OUTPUT_FOLDER):
        shutil.rmtree(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER)

# 入力ファイルを取得する
def get_input_files():
    # 入力フォルダにあるすべてのファイルを取得（多階層対応）
    input_files = []
    for root, _, files in os.walk(INPUT_FOLDER):
        for file in files:
            if os.path.splitext(file)[1].lower() in SUPPORTED_FORMATS:
                input_files.append(os.path.join(root, file))
    return input_files

# 出力ファイルのパスを取得する
def get_output_path(input_path, input_folder, output_folder, target_height=None, is_audio_only=False):
    # 入力フォルダの相対パスを取得する
    relative_path = os.path.relpath(input_path, input_folder)
    # 新しい出力ファイルのパスを生成する
    base, ext = os.path.splitext(relative_path)
    if is_audio_only:
        output_relative_path = f"{base}.mp3"
    else:
        output_relative_path = f"{base}_{target_height}p{ext}"
    return os.path.join(output_folder, output_relative_path)

# 動画を指定の解像度とコーデックで再エンコードする（FFmpegを使用）
def convert_video(input_path, output_path, target_height, video_codec, audio_codec, ffmpeg_path):
    command = [
        ffmpeg_path, "-y", "-i", input_path, 
        "-vf", f"scale=-1:{target_height}",  # 指定された高さでアスペクト比を保ちながら解像度変更
        "-c:v", video_codec,
        "-c:a", audio_codec
    ]
    
    # AACエンコーディングを使用する場合のオプション
    if audio_codec == "aac":
        command.extend(["-strict", "experimental"])

    # 出力パス
    command.append(output_path)

    # FFmpegを実行、出力を非表示にする
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 動画から音声を抽出する（FFmpegを使用）
def extract_audio(input_path, output_path, audio_codec, audio_bitrate, ffmpeg_path):
    command = [
        ffmpeg_path, "-y", "-i", input_path,
        "-vn",
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 解像度の高さをユーザーから取得する
def get_target_height():
    while True:
        try:
            print("変換後の動画の高さを入力してください（例：480）")
            target_height = int(input("> "))
            print()
            return target_height
        except ValueError:
            print("数値を入力してください。")
            print()

# 解像度変更モードのメイン処理
def process_convert_resolution(ffmpeg_path, input_files):
    # ユーザーに解像度の高さを入力させる
    target_height = get_target_height()

    # 動画コーデック
    if is_nvenc_available(ffmpeg_path):
        video_codec = "h264_nvenc"  # NVIDIAのGPUを使う
        print("GPUを使用して動画のエンコーディングを行います。")
        print()
    else:
        video_codec = "libx264"  # CPUを使う

    # 音声コーデック
    audio_codec = "aac"

    # 出力フォルダをクリアする
    clear_output_folder()

    # 各ファイルを指定された高さに変換しつつコーデックを変更
    print("動画の変換を開始します。")
    total_files = len(input_files)
    for i, input_file in enumerate(input_files):
        print(f"・({i+1}/{total_files}) {input_file}...", end="")
        sys.stdout.flush()

        # 出力パスの取得
        output_path = get_output_path(input_file, INPUT_FOLDER, OUTPUT_FOLDER, target_height)

        # 必要な出力フォルダを作成
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 動画を再エンコードする
        convert_video(input_file, output_path, target_height, video_codec, audio_codec, ffmpeg_path)
        
        print("変換完了！")
        sys.stdout.flush()

# 音声抽出モードのメイン処理
def process_extract_audio(ffmpeg_path, input_files):
    user_input = input("音声抽出を開始しますか？ (y/n): ").strip().lower()
    if user_input != "y":
        return
    print()

    # 音声コーデック
    audio_codec = "mp3"
    audio_bitrate = "192k"

    # 出力フォルダをクリアする
    clear_output_folder()

    # 各ファイルを指定された高さに変換しつつコーデックを変更
    print("音声の抽出を開始します。")
    total_files = len(input_files)
    for i, input_file in enumerate(input_files):
        print(f"・({i+1}/{total_files}) {input_file}...", end="")
        sys.stdout.flush()

        # 出力パスの取得
        output_path = get_output_path(input_file, INPUT_FOLDER, OUTPUT_FOLDER, is_audio_only=True)

        # 必要な出力フォルダを作成
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # 動画を再エンコードする
        extract_audio(input_file, output_path, audio_codec, audio_bitrate, ffmpeg_path)
        
        print("抽出完了！")
        sys.stdout.flush()

# メイン
def main():
    # プログラム引数を解析する
    mode, description = parse_argument()

    print("----------------------------------------------------------------------")
    print(f" {APP_NAME} {APP_VERSION}")
    print()
    print(f" {description}")
    print()
    print(f" {COPYRIGHT}")
    print("----------------------------------------------------------------------")
    print()

    ## 使用するFFmpegのパスを取得する
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path is None:
        print("エラー: FFmpeg が見つかりません。binフォルダに配置するか、システムパスに追加してください。")
        sys.exit(1)
    else:
        print("このツールは以下のFFmpegを使用して動画を変換します。")
        print(get_ffmpeg_version(ffmpeg_path))
        print()

    # 入出力フォルダが存在しなければ作成する
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # 入力フォルダにあるすべての動画ファイルを取得する
    input_files = get_input_files()
    if len(input_files) == 0:
        print(f"{INPUT_FOLDER}フォルダに変換元のファイルを保存してから実行してください。")
        return

    # 変換処理実行
    if mode == "convert":
        process_convert_resolution(ffmpeg_path, input_files)
    elif mode == "extract":
        process_extract_audio(ffmpeg_path, input_files)

if __name__ == "__main__":
    main()
