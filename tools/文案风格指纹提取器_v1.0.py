#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文案风格指纹提取器_v1.0.py — 量化分析对标文案的句长、标点密度、过渡连词以及评论区高频 Meme 词。
"""

import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

# 设置 logging 模块，遵守 Rule 6.7
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("style-extractor")

# 常见中文停用词，用于过滤 Meme 词分析中的虚词
STOP_WORDS = {
  "的", "了", "是", "我", "你", "他", "在", "有", "个", "这", "不", "也", "都", "要", "和",
  "与", "就", "说", "去", "到", "很", "会", "着", "让", "给", "但", "把", "那", "这", "吧",
  "吗", "呢", "啊", "呀", "哈", "拉", "吧", "被", "自己", "一个", "我们", "你们", "他们",
  "这个", "那个", "这样", "那样", "什么", "怎么", "如何", "因为", "所以", "虽然", "但是"
}

# 常见过渡连词/语气转折词列表，用于文案连词特征统计
TRANSITION_WORDS = [
  "其实", "也就是说", "但是", "所以", "不过", "当然", "甚至", "而且", "换句话说", "最后",
  "首先", "也就是说", "其实我", "然而", "突然", "不过", "居然", "竟然", "结果", "因此",
  "所以说", "说实话", "讲道理", "那么", "接着", "然后"
]

def analyze_script(script_text: str) -> dict:
  """
  分析单篇文案的句长、标点、换行等风格指标。
  """
  # 用正则匹配中文和英文的断句标点，包括：。 ！ ？ ! ? \n 还有省略号 (…… / ...)
  # 这样可以精准切分出独立语义句，避免由于标点不同导致句长统计失真。
  sentences_raw = re.split(r"[。！？!?\n]|(?:……)|(?:\.\.\.)", script_text)
  
  # 清理并过滤空句子
  sentences = [s.strip() for s in sentences_raw if s.strip()]
  
  if not sentences:
    return {
      "avg_length": 0.0,
      "variance": 0.0,
      "punc_excl_rate": 0.0,
      "punc_ques_rate": 0.0,
      "punc_ellip_rate": 0.0,
      "newline_rate": 0.0,
      "transitions": {}
    }
  
  # 计算每句的字符长度
  lengths = [len(s) for s in sentences]
  avg_length = sum(lengths) / len(lengths)
  # 计算句长方差，用于衡量节奏波动（高方差代表长短句交错剧烈）
  variance = sum((x - avg_length) ** 2 for x in lengths) / len(lengths)
  
  # 统计各标点符号绝对出现频次
  excl_count = len(re.findall(r"[！!]", script_text))
  ques_count = len(re.findall(r"[？?]", script_text))
  ellip_count = len(re.findall(r"(?:……)|(?:\.\.\.)", script_text))
  newline_count = script_text.count("\n")
  
  # 计算标点占总句数的比例
  punc_excl_rate = excl_count / len(sentences)
  punc_ques_rate = ques_count / len(sentences)
  punc_ellip_rate = ellip_count / len(sentences)
  
  # 换行率：每百字换行数（反映分段紧凑度）
  char_count = len(script_text)
  newline_rate = (newline_count / char_count * 100) if char_count > 0 else 0.0
  
  # 统计过渡连词出现频次
  transitions_found = {}
  for word in TRANSITION_WORDS:
    count = len(re.findall(re.escape(word), script_text))
    if count > 0:
      transitions_found[word] = count

  return {
    "avg_length": round(avg_length, 2),
    "variance": round(variance, 2),
    "punc_excl_rate": round(punc_excl_rate, 3),
    "punc_ques_rate": round(punc_ques_rate, 3),
    "punc_ellip_rate": round(punc_ellip_rate, 3),
    "newline_rate": round(newline_rate, 3),
    "transitions": transitions_found
  }

def extract_comments_memes(meta_text: str) -> list[tuple[str, int]]:
  """
  解析 meta.md，提取评论区高频词汇作为受众敏感的 Meme 候选词。
  """
  # 使用正则匹配评论区段落
  # 通常评论保存在含有“## 评论”或“top_comments”标志的后方
  comments_section = ""
  lines = meta_text.splitlines()
  in_comments = False
  for line in lines:
    if "## 评论" in line or "top_comments" in line.lower() or "评论数" in line:
      in_comments = True
      continue
    if in_comments and line.strip().startswith("## "):
      # 遇到了下一个二级标题，退出评论区匹配
      break
    if in_comments:
      comments_section += line + "\n"
      
  if not comments_section.strip():
    # 兜底：如果没找到 ## 评论 标题，就对整个 meta_text 扫描
    comments_section = meta_text

  # 使用正则匹配出所有 2 到 4 个字的中文字符串
  chinese_words = re.findall(r"[\u4e00-\u9fa5]{2,4}", comments_section)
  
  # 过滤停用词
  filtered_words = [w for w in chinese_words if w not in STOP_WORDS]
  
  # 统计词频并返回前 10 个高频词
  counter = Counter(filtered_words)
  return counter.most_common(10)

def main():
  """
  主入口程序。
  """
  parser = argparse = __import__("argparse").ArgumentParser(
    description="对标账号文案风格指纹提取工具"
  )
  parser.add_argument("--samples-dir", required=True, type=Path, help="对标账号样本目录")
  parser.add_argument("--output-json", required=True, type=Path, help="生成的指纹 JSON 输出路径")
  args = parser.parse_args()

  samples_dir = args.samples_dir
  if not samples_dir.is_dir():
    logger.error(f"样本目录不存在: {samples_dir}")
    sys.exit(1)

  all_metrics = []
  all_memes = Counter()

  # 使用 pathlib 扫描子目录下所有的 transcript.md 和 meta.md 文件（Rule 6.5）
  for sub_dir in samples_dir.iterdir():
    if not sub_dir.is_dir() or sub_dir.name.startswith("."):
      continue
    
    transcript_path = sub_dir / "transcript.md"
    meta_path = sub_dir / "meta.md"
    
    # 提取文案特征
    if transcript_path.is_file():
      try:
        script_content = transcript_path.read_text(encoding="utf-8")
        metrics = analyze_script(script_content)
        all_metrics.append(metrics)
        logger.info(f"成功解析样本文案: {transcript_path.name}")
      except Exception as e:
        logger.error(f"读取文案失败 {transcript_path}: {e}")

    # 提取评论 Meme 特征
    if meta_path.is_file():
      try:
        meta_content = meta_path.read_text(encoding="utf-8")
        memes = extract_comments_memes(meta_content)
        for word, freq in memes:
          all_memes[word] += freq
        logger.info(f"成功解析样本评论: {meta_path.name}")
      except Exception as e:
        logger.error(f"读取 meta 失败 {meta_path}: {e}")

  if not all_metrics:
    logger.error("未找到任何有效的 transcript.md 样本，无法生成指纹。")
    sys.exit(2)

  # 聚合多篇样本的风格指标（计算算术平均值）
  num_samples = len(all_metrics)
  avg_sentence_len = sum(m["avg_length"] for m in all_metrics) / num_samples
  avg_variance = sum(m["variance"] for m in all_metrics) / num_samples
  avg_excl = sum(m["punc_excl_rate"] for m in all_metrics) / num_samples
  avg_ques = sum(m["punc_ques_rate"] for m in all_metrics) / num_samples
  avg_ellip = sum(m["punc_ellip_rate"] for m in all_metrics) / num_samples
  avg_newline = sum(m["newline_rate"] for m in all_metrics) / num_samples
  
  # 整合过渡词频次
  merged_transitions = Counter()
  for m in all_metrics:
    for word, count in m["transitions"].items():
      merged_transitions[word] += count
  
  # 取前 5 个最常用过渡连词
  top_transitions = [w for w, _ in merged_transitions.most_common(5)]
  # 取前 8 个评论高赞 Meme 词
  top_memes = [w for w, _ in all_memes.most_common(8)]

  fingerprint = {
    "sample_count": num_samples,
    "style_metrics": {
      "average_sentence_length": round(avg_sentence_len, 2),
      "sentence_length_variance": round(avg_variance, 2),
      "exclamation_mark_ratio": round(avg_excl, 3),
      "question_mark_ratio": round(avg_ques, 3),
      "ellipsis_ratio": round(avg_ellip, 3),
      "newline_ratio_per_100_chars": round(avg_newline, 3)
    },
    "signature_transitions": top_transitions,
    "audience_memes": top_memes
  }

  # 写入输出 JSON 文件
  try:
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(fingerprint, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"风格指纹文件成功落盘: {args.output_json}")
  except Exception as e:
    logger.error(f"写入指纹 JSON 失败: {e}")
    sys.exit(3)

if __name__ == "__main__":
  main()
