#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频生成压制器_v1.0.py — 调用 Xiaomi MiMo-V2.5-TTS 语音合成大模型 API 生成配音，
并利用本地 FFmpeg 混合指定的背景封面图片，全自动压制合成高清多模态成品短视频。
"""

import argparse
import base64
import json
import logging
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# 配置全局日志模块，符合规范 6.7
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("video-generator")

MIMO_API_URL = "https://api.xiaomimimo.com/v1/chat/completions"

def call_mimo_tts(text: str, apikey: str, voice: str, prompt: str) -> bytes:
  """
  调用 Xiaomi MiMo-V2.5-TTS 接口，生成高保真音频字节流。
  """
  payload = {
    "model": "mimo-v2.5-tts",
    "messages": [
      {"role": "user", "content": prompt},
      {"role": "assistant", "content": text}
    ],
    "audio": {
      "voice": voice,
      "format": "mp3"
    }
  }
  
  headers = {
    "Authorization": f"Bearer {apikey}",
    "Content-Type": "application/json"
  }
  
  logger.info(f"正在向 MiMo 发起语音合成请求，字数: {len(text)}...")
  req = urllib.request.Request(
    MIMO_API_URL,
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
    method="POST"
  )
  
  try:
    # 增加超时限制，防止连接挂起
    with urllib.request.urlopen(req, timeout=90) as response:
      res_data = json.loads(response.read().decode("utf-8"))
      # 解析 choices[0].message.audio.data 中的 Base64 音频
      audio_b64 = res_data["choices"][0]["message"]["audio"]["data"]
      return base64.b64decode(audio_b64)
  except urllib.error.HTTPError as e:
    err_msg = e.read().decode("utf-8", errors="ignore")
    logger.error(f"MiMo API 请求 HTTP 错误 (Code {e.code}): {err_msg}")
    raise RuntimeError(f"HTTP {e.code}: {err_msg}")
  except Exception as e:
    logger.error(f"访问 MiMo 接口时发生网络异常: {e}")
    raise

def generate_video(image_path: Path, audio_path: Path, output_path: Path):
  """
  调用 FFmpeg 压制静止图片与口播音轨为高清 MP4 视频。
  使用 libx264 编码，设置 yuv420p 色彩空间以确保移动端与各播放器完美兼容。
  """
  logger.info(f"正在启动 FFmpeg 压制流程...")
  logger.info(f"背景图: {image_path}")
  logger.info(f"音轨: {audio_path}")
  logger.info(f"输出视频: {output_path}")

  # 基础 FFmpeg 参数，确保静止图像完美循环匹配音频长度
  cmd = [
    "ffmpeg", "-y",
    "-loop", "1",
    "-i", str(image_path),
    "-i", str(audio_path),
    "-c:v", "libx264",
    "-tune", "stillimage",
    "-c:a", "aac",
    "-b:a", "192k",
    "-pix_fmt", "yuv420p",
    "-shortest",
    str(output_path)
  ]
  
  try:
    # 执行 FFmpeg 命令并捕获错误日志
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    logger.info("✅ FFmpeg 视频合成压制成功！")
  except subprocess.CalledProcessError as e:
    logger.error(f"FFmpeg 合成失败，命令退出码: {e.returncode}")
    logger.error(f"FFmpeg 错误详情:\n{e.stderr}")
    raise RuntimeError("FFmpeg execution failed")

def main():
  parser = argparse.ArgumentParser(description="一键多模态短视频生成压制工具")
  parser.add_argument("--apikey", default="", help="Xiaomi MiMo API Key，缺省时自动从环境变量读取")
  parser.add_argument("--text", default="", help="待口播的文本内容")
  parser.add_argument("--text_file", default="", help="从指定的 Markdown 文本文件中读取口播内容")
  parser.add_argument("--image", required=True, help="视频背景图片路径")
  parser.add_argument("--output", required=True, help="生成的 MP4 视频保存路径")
  parser.add_argument("--voice", default="苏打", help="MiMo 发音人音色，默认：苏打")
  parser.add_argument("--prompt", default="用激情昂扬的科技博主口吻，语速稍快，情绪饱满，音色响亮。", help="控制语音风格的 Prompt 指导词")
  args = parser.parse_args()

  # 1. 密钥加载逻辑，优先命令行参数，其次取环境变量，符合规范 6.6
  apikey = args.apikey or os.getenv("MIMO_API_KEY")
  if not apikey:
    logger.error("缺少 API Key。请使用 --apikey 参数传入，或配置 MIMO_API_KEY 环境变量。")
    sys.exit(1)

  # 2. 口播文本提取
  text = args.text
  if args.text_file:
    text_path = Path(args.text_file)
    if not text_path.is_file():
      logger.error(f"找不到指定的文本文件: {args.text_file}")
      sys.exit(1)
    # 自动解析 Markdown 文本，剥离 markdown 标题或非文本干扰（若有）
    raw_content = text_path.read_text(encoding="utf-8").strip()
    # 如果是 markdown 文件，可能含有 frontmatter 或 markdown 标题，这里做基本清洗，仅保留有效内容
    lines = [line.strip() for line in raw_content.splitlines()]
    cleaned_lines = [l for l in lines if l and not l.startswith("#") and not l.startswith("-")]
    text = " ".join(cleaned_lines)
    logger.info(f"已从文件中提取并清洗文本，共计 {len(text)} 字。")

  if not text:
    logger.error("口播文本不能为空。请指定 --text 或 --text_file 参数。")
    sys.exit(1)

  # 3. 校验图片路径与输出目录
  image_path = Path(args.image)
  if not image_path.is_file():
    logger.error(f"找不到指定的背景图片: {args.image}")
    sys.exit(1)

  output_path = Path(args.output)
  output_path.parent.mkdir(parents=True, exist_ok=True)

  # 临时音频存放路径（保存在同级目录下，防止污染项目根目录）
  temp_audio_path = output_path.parent / f"temp_{output_path.stem}.mp3"

  try:
    # 4. 执行语音合成
    audio_data = call_mimo_tts(text, apikey, args.voice, args.prompt)
    temp_audio_path.write_bytes(audio_data)
    logger.info(f"临时音轨已成功写出到: {temp_audio_path}")

    # 5. 执行 FFmpeg 压制
    generate_video(image_path, temp_audio_path, output_path)

  except Exception as e:
    logger.error(f"⚠️ 短视频生产流程异常终止: {e}")
    sys.exit(2)
  finally:
    # 清理临时音频文件，确保工作区整洁
    if temp_audio_path.is_file():
      temp_audio_path.unlink()
      logger.info("已清理临时音轨文件。")

  logger.info(f"🎉 恭喜！成品视频已交付至: {output_path.absolute()}")

if __name__ == "__main__":
  main()
