import json
import argparse
import re
import yt_dlp
import whisper
import os

def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|watch\?v=|\/v\/|\/e\/|youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("无法提取视频ID")

def get_subtitle_or_audio(video_id):
    audio_file = "temp_audio.wav"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_cookies': True,
        'extractor_args': 'youtube:player_client=web',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': audio_file,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        return audio_file
    except Exception as e:
        raise Exception(f"下载音频失败: {str(e)}")

def audio_to_text(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="zh", fp16=False)
    return result["text"].strip()

def extract_info(text):
    password_patterns = [
        r'密码[:：\s]*([a-zA-Z0-9]{4,16})',
        r'口令[:：\s]*([a-zA-Z0-9]{4,16})',
        r'密钥[:：\s]*([a-zA-Z0-9]{4,32})',
    ]
    passwords = []
    for p in password_patterns:
        passwords += re.findall(p, text, re.I)
    
    urls = re.findall(r'https?://[^\s]+', text)
    nodes = re.findall(r'(vmess|vless|trojan|ss|ssr)://[^\s]+', text, re.I)
    
    return {
        "passwords": list(set(passwords)) or ["未找到"],
        "urls": list(set(urls)) or ["未找到"],
        "nodes": list(set(nodes)) or ["未找到"]
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    args = parser.parse_args()

    try:
        video_id = extract_video_id(args.url)
        print(f"✅ 视频ID: {video_id}")

        audio_path = get_subtitle_or_audio(video_id)
        full_text = audio_to_text(audio_path)
        os.remove(audio_path)

        info = extract_info(full_text)

        result = {
            "url": args.url,
            "video_id": video_id,
            "info": info,
            "full_text": full_text
        }

        with open(f"result_{video_id}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print("📊 提取结果：")
        print(f"密码: {info['passwords']}")
        print(f"链接: {info['urls']}")
        print(f"节点: {info['nodes']}")
        print("✅ 完成！")

    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    main()
