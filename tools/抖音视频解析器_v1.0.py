#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音视频解析器_v1.0.py — 一键拉取抖音单视频或用户主页最近视频、自动下载音频、跑 ASR 提取台词文案并执行 Agent Teams 初始打分。
"""

import argparse
import json
import logging
import re
import sys
import subprocess
import urllib.parse
from pathlib import Path

# 设置 logging 模块，遵守 Rule 6.7
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("douyin-fetcher")

# 公共 API 端点配置
WTF_BASE_URL = "https://api.douyin.wtf"

def fetch_api_json(endpoint: str, params: dict) -> dict | None:
  """
  使用系统内置 curl 发送 GET 请求，完美绕过 Python urllib 代理拦截风控。
  """
  query_string = urllib.parse.urlencode(params)
  url = f"{WTF_BASE_URL}{endpoint}?{query_string}"
  
  # 使用 curl 模拟真实 Chrome 请求
  cmd = [
    "curl", "-s", "-L",
    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    url
  ]
  try:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:
      res_data = json.loads(result.stdout)
      # 兼容 detail code 与直接 code 两种返回结构
      code = res_data.get("code") or res_data.get("detail", {}).get("code")
      if code == 200:
        return res_data
      else:
        msg = res_data.get("msg") or res_data.get("detail", {}).get("message")
        logger.error(f"API 返回异常 (Code {code}): {msg}")
        return None
    else:
      logger.error(f"curl 执行失败: {result.stderr}")
      return None
  except Exception as e:
    logger.error(f"API 请求失败 {url}: {e}")
    return None

def download_file(url: str, dest_path: Path):
  """
  使用 curl 命令行工具下载大文件，提供高吞吐和高兼容性。
  """
  cmd = [
    "curl", "-s", "-L",
    "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "-o", str(dest_path),
    url
  ]
  try:
    subprocess.run(cmd, check=True)
    logger.info(f"成功下载文件到: {dest_path}")
  except Exception as e:
    logger.error(f"下载文件失败 {url}: {e}")
    raise

def main():
  parser = argparse.ArgumentParser(description="抖音无水印全自动解析与文案提取工具")
  parser.add_argument("--url", required=True, help="抖音视频链接或用户主页链接")
  parser.add_argument("--count", type=int, default=3, help="若是主页链接，抓取最近的作品篇数")
  parser.add_argument("--account-name", default="", help="自定义保存的账号文件夹名，缺省时自动使用博主昵称")
  args = parser.parse_args()

  logger.info(f"开始解析链接: {args.url}")

  # 1. 第一步：解析链接类型
  logger.info("正在探查链接类型，检测是否为主页链接...")
  res_sec_user = fetch_api_json("/api/douyin/web/get_sec_user_id", {"url": args.url})
  
  sec_user_id = None
  if res_sec_user and res_sec_user.get("code") == 200:
    sec_user_id = res_sec_user.get("data")
    
  aweme_list = []
  nickname = args.account_name or "未命名账号"
  
  if sec_user_id:
    # 情况 A：这是一个博主主页链接
    logger.info(f"检测到主页分享链接 (sec_uid: {sec_user_id})")
    logger.info(f"正在拉取该博主最近的 {args.count} 个作品列表...")
    
    res_posts = fetch_api_json("/api/douyin/web/fetch_user_post_videos", {
      "sec_user_id": sec_user_id,
      "count": args.count
    })
    
    post_data = res_posts.get("data", {}) if res_posts else {}
    if post_data and post_data.get("aweme_list"):
      aweme_list = post_data["aweme_list"]
      # 从最近的作品中尝试获取博主姓名以覆盖未命名状态
      for aweme in aweme_list:
        author = aweme.get("author", {})
        if author and author.get("nickname"):
          nickname = author.get("nickname")
          break
    else:
      logger.error("拉取用户主页作品失败")
      sys.exit(3)
  else:
    # 情况 B：这是一个单个视频链接
    logger.info("未检测到主页特征，按单视频分享链接进行本地免 Cookie HTML 解密...")
    
    # 模拟重定向获取真实的 video_id
    cmd_redirect = [
      "curl", "-s", "-I", "-L",
      "-H", "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1",
      args.url
    ]
    try:
      res = subprocess.run(cmd_redirect, capture_output=True, text=True, encoding="utf-8")
      locations = re.findall(r'[lL]ocation:\s*([^\r\n]+)', res.stdout)
      final_url = locations[-1] if locations else args.url
      
      video_id_match = re.search(r'video/(\d+)', final_url)
      if not video_id_match:
        video_id_match = re.search(r'/(\d+)(?:\?|$)', final_url)
        
      if not video_id_match:
        logger.error(f"无法从最终重定向链接中提取出 19 位数字的视频 ID: {final_url}")
        sys.exit(1)
        
      video_id = video_id_match.group(1)
      logger.info(f"成功提取视频 ID: {video_id}。开始向 iesdouyin 发起免 Cookie 安全数据爬取...")
      
      ies_url = f"https://www.iesdouyin.com/share/video/{video_id}"
      cmd_fetch = [
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1",
        ies_url
      ]
      result = subprocess.run(cmd_fetch, capture_output=True, text=True, encoding="utf-8")
      
      pattern = re.compile(pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", flags=re.DOTALL)
      find_res = pattern.search(result.stdout)
      if not find_res:
        logger.error("在网页 HTML 源码中未匹配到 window._ROUTER_DATA 数据盾，视频可能已被删除或风控限制。")
        sys.exit(2)
        
      json_str = find_res.group(1).strip()
      if json_str.endswith(';'):
        json_str = json_str[:-1]
        
      json_data = json.loads(json_str)
      loader_data = json_data.get("loaderData", {})
      VIDEO_ID_PAGE_KEY = "video_(id)/page"
      NOTE_ID_PAGE_KEY = "note_(id)/page"
      
      original_video_info = None
      if VIDEO_ID_PAGE_KEY in loader_data:
        original_video_info = loader_data[VIDEO_ID_PAGE_KEY].get("videoInfoRes")
      elif NOTE_ID_PAGE_KEY in loader_data:
        original_video_info = loader_data[NOTE_ID_PAGE_KEY].get("videoInfoRes")
        
      if not original_video_info or not original_video_info.get("item_list"):
        logger.error("iesdouyin 解析成功但未匹配到 item_list 作品列表")
        sys.exit(3)
        
      data = original_video_info["item_list"][0]
      nickname = data.get("author", {}).get("nickname") or data.get("nickname") or "未命名账号"
      aweme_list = [data]
    except Exception as e:
      logger.error(f"本地解密单视频网页数据失败: {e}")
      sys.exit(4)
 
  if not aweme_list:
    logger.error("未获取到任何有效的视频信息")
    sys.exit(4)
 
  # 文件夹及命名清洗，遵守 Rule 6.5
  account_folder = args.account_name if args.account_name else nickname
  account_folder = re.sub(r'[\\/:*?"<>| ]', "_", account_folder)
 
  logger.info(f"共获取到 {len(aweme_list)} 个待处理视频。开始批量执行下载与文案提取流程...")
 
  samples_base = Path("samples")
 
  for i, aweme in enumerate(aweme_list):
    aweme_id = aweme.get("aweme_id") or aweme.get("video_id")
    desc = aweme.get("desc") or "无标题"
    stats = aweme.get("statistics", {})
    
    # 优先提取无水印音频地址
    audio_url = ""
    music_info = aweme.get("music", {})
    if music_info and music_info.get("play_url"):
      play_url_obj = music_info["play_url"]
      url_list = play_url_obj.get("url_list")
      if url_list and len(url_list) > 0:
        audio_url = url_list[0]
      elif play_url_obj.get("uri"):
        audio_url = play_url_obj["uri"]
        
    # 若无直接音频（如网页单视频数据），则提取无水印视频地址并提取音轨
    video_url = ""
    video_info = aweme.get("video", {})
    if video_info and video_info.get("play_addr"):
      v_url_list = video_info["play_addr"].get("url_list")
      if v_url_list and len(v_url_list) > 0:
        video_url = v_url_list[0].replace("playwm", "play")
        
    if not audio_url and not video_url:
      logger.warning(f"视频 {aweme_id} 未找到任何有效的音频或视频播放地址，跳过")
      continue
 
    logger.info(f"[{i+1}/{len(aweme_list)}] 处理视频 ID: {aweme_id} | 描述: {desc[:20]}...")
 
    # 创建目标样本存放文件夹
    video_dir = samples_base / account_folder / aweme_id
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_path = video_dir / "audio.mp3"
 
    # 自适应音频下载与提取
    if audio_url:
      logger.info("检测到无水印直接音频链接，正在极速下载...")
      try:
        download_file(audio_url, audio_path)
      except Exception:
        logger.error(f"视频 {aweme_id} 音频下载失败")
        continue
    else:
      logger.info("未检测到直接音频。正在下载无水印视频并转码提取音轨...")
      video_path = video_dir / "temp_video.mp4"
      try:
        download_file(video_url, video_path)
        logger.info("正在使用 ffmpeg 转换 MP4 为 MP3 格式...")
        # 调用 ffmpeg 命令行提取音频
        cmd_ffmpeg = [
          "ffmpeg", "-y", "-i", str(video_path),
          "-vn", "-acodec", "libmp3lame", "-q:a", "2",
          str(audio_path)
        ]
        subprocess.run(cmd_ffmpeg, check=True, capture_output=True)
        logger.info("FFmpeg 音轨提取转换成功！")
      except Exception as e:
        logger.error(f"视频 {aweme_id} 音视频下载转换失败: {e}")
        continue
      finally:
        if video_path.is_file():
          video_path.unlink()
 
    # 生成 meta.md 头部元数据
    # 计算播放量转化为 w 单位，便于 validate-bump 解析
    raw_play = stats.get("play_count", 0)
    play_w = round(raw_play / 10000.0, 2) if raw_play > 0 else 0.0
    
    meta_text = (
      f"## 视频信息\n"
      f"标题：{desc}\n"
      f"作者：{nickname}\n"
      f"视频ID：{aweme_id}\n\n"
      f"## 数据\n"
      f"播放：{play_w}w\n"
      f"点赞：{stats.get('digg_count', 0)}\n"
      f"评论数：{stats.get('comment_count', 0)}\n"
      f"转发数：{stats.get('share_count', 0)}\n\n"
      f"## 印象\n"
      f"高/中/低表现：中\n"
      f"印象理由：对标自动导入样本\n\n"
    )
    
    meta_path = video_dir / "meta.md"
    meta_path.write_text(meta_text, encoding="utf-8")

    # 2. 第二步：调用 Whisper 执行 ASR 提取台词
    whisper_script = Path("adapters/script-extraction/whisper/run.sh")
    if whisper_script.is_file():
      logger.info(f"正在唤醒 Whisper 提取台词 ASR。样本目录: {video_dir}")
      # 用 zsh 或 bash 执行本地转录脚本，遵守 Rule 6.8 / 6.1
      cmd_whisper = ["bash", str(whisper_script), str(audio_path), str(video_dir)]
      try:
        # 使用 check=True 使得错误立即可控
        subprocess.run(cmd_whisper, check=True)
        logger.info(f"Whisper ASR 提取成功！生成 transcript.md")
      except subprocess.CalledProcessError as e:
        logger.error(f"Whisper ASR 转录失败: {e}")
        # 如果转录失败，写入一个 N/A 占位 transcript 确保格式完整
        (video_dir / "transcript.md").write_text("N/A", encoding="utf-8")
    else:
      logger.warning("未检测到 adapters/script-extraction/whisper/run.sh，无法自动执行 ASR 转录")
      (video_dir / "transcript.md").write_text("N/A", encoding="utf-8")

    # 3. 第三步：调用 Agent Teams 对转写文案执行初始自动打分
    evaluator_script = Path("tools/agent-teams-evaluator.py")
    transcript_path = video_dir / "transcript.md"
    
    if evaluator_script.is_file() and transcript_path.is_file() and transcript_path.read_text(encoding="utf-8").strip() != "N/A":
      logger.info(f"正在唤醒 Agent Teams 进行冷启动初评分...")
      cmd_eval = [sys.executable, str(evaluator_script), "--draft", str(transcript_path)]
      try:
        # 执行打分并截获 stdout
        eval_result = subprocess.run(cmd_eval, capture_output=True, text=True, encoding="utf-8", check=True)
        # 将打分矩阵表格追加写入 meta.md
        with open(meta_path, "a", encoding="utf-8") as f_meta:
          f_meta.write("## 初始打分\n")
          f_meta.write(eval_result.stdout)
        logger.info(f"Agent Teams 初评分已追加写入 meta.md")
      except subprocess.CalledProcessError as e:
        logger.error(f"Agent Teams 评分失败: {e.stderr if e.stderr else e}")
        
  logger.info("全自动导入及打分流程执行完毕！")

if __name__ == "__main__":
  main()
