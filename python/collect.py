import json
import argparse
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
import yt_dlp
import whisper
import re

def extract_video_id(url):
    """从YouTube链接中提取video_id"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|watch\?v=|\/v\/|\/e\/|youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("无法从链接中提取YouTube视频ID")

def get_transcript(video_id):
    """优先获取字幕，无字幕则返回None"""
    try:
        # 尝试获取所有可用字幕，优先选中文/英文
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        for transcript in transcripts:
            if transcript.language in ['zh', 'en', 'zh-CN', 'zh-TW']:
                return transcript.fetch()
        # 没有中文/英文，选第一个可用字幕
        first_transcript = next(transcripts)
        return first_transcript.fetch()
    except TranscriptsDisabled:
        print("⚠️  该视频无字幕，将下载音频转文字...")
        return None
    except Exception as e:
        print(f"⚠️  获取字幕失败：{e}")
        return None

def download_audio(video_id, output_path="temp_audio.wav"):
    """下载YouTube音频（仅用于转文字，用完自动删除）"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    return output_path

def audio_to_text(audio_path):
    """用Whisper将音频转文字"""
    model = whisper.load_model("base")  # 可选：small/medium（更准但更慢）
    result = model.transcribe(audio_path, language=None)  # 自动检测语言
    return result["text"]

def extract_target_info(full_text):
    """提取密码、链接等目标信息"""
    # 正则规则：匹配密码（数字/字母组合，带"密码"关键词）、URL、节点链接
    password_patterns = [
        r'密码[:：\s]*([0-9A-Za-z]{4,16})',
        r'口令[:：\s]*([0-9A-Za-z]{4,16})',
        r'密钥[:：\s]*([0-9A-Za-z]{8,32})',
        r'pass(?:word)?[:\s]*([0-9A-Za-z]{4,16})'
    ]
    url_pattern = r'(https?:\/\/[^\s]+)'  # 匹配所有URL
    node_pattern = r'(vmess|vless|trojan|ss|ssr)[:：][^\s]+'  # 匹配节点链接

    passwords = []
    for pattern in password_patterns:
        matches = re.findall(pattern, full_text, re.IGNORECASE)
        passwords.extend(matches)
    
    urls = re.findall(url_pattern, full_text)
    nodes = re.findall(node_pattern, full_text, re.IGNORECASE)

    # 去重
    passwords = list(set(passwords))
    urls = list(set(urls))
    nodes = list(set(nodes))

    return {
        "passwords": passwords if passwords else ["未找到"],
        "urls": urls if urls else ["未找到"],
        "nodes": nodes if nodes else ["未找到"]
    }

def main():
    # 解析命令行参数（输入YouTube链接）
    parser = argparse.ArgumentParser(description="提取YouTube视频中的密码和链接")
    parser.add_argument("--url", required=True, help="YouTube视频链接（例：https://www.youtube.com/watch?v=xxxx）")
    args = parser.parse_args()

    try:
        # 1. 提取视频ID
        video_id = extract_video_id(args.url)
        print(f"✅ 提取视频ID成功：{video_id}")

        # 2. 获取字幕/音频转文字
        transcript = get_transcript(video_id)
        if transcript:
            # 字幕转完整文本
            full_text = "\n".join([item["text"] for item in transcript])
        else:
            # 下载音频转文字
            audio_path = download_audio(video_id)
            full_text = audio_to_text(audio_path)
            import os
            os.remove(audio_path)  # 删除临时音频文件

        print("✅ 文本提取成功，正在分析目标信息...")

        # 3. 提取密码、链接等
        target_info = extract_target_info(full_text)

        # 4. 输出结果（JSON文件+控制台打印）
        result = {
            "video_url": args.url,
            "video_id": video_id,
            "extracted_info": target_info,
            "full_text": full_text  # 完整文本（可用于二次分析）
        }

        # 保存为JSON文件
        output_file = f"youtube_extract_result_{video_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 控制台打印结果
        print("\n" + "="*50)
        print("📊 提取结果：")
        print(f"密码/口令：{target_info['passwords']}")
        print(f"URL链接：{target_info['urls']}")
        print(f"节点链接：{target_info['nodes']}")
        print(f"\n✅ 完整结果已保存到：{output_file}")
        print("="*50)

    except Exception as e:
        print(f"\n❌ 运行失败：{str(e)}")

if __name__ == "__main__":
    main()
