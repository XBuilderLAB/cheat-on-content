#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评估公式升级校验器_v2.0.py — 校验 Rubric 公式升级，支持混合读取已复盘和对标样本，并加入冷启动保护。
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# 设置日志格式，遵循 Rule 6.7
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("validate-bump-v2")

# 解析文件所用正则匹配
DIMENSION_ROW_RE = re.compile(
  r"^\|\s*([A-Z]{2,3})(?:\s*\([^)]*\))?\s*\|\s*(\d+)\s*\|", re.MULTILINE
)
ACTUAL_PLAYS_RE = re.compile(
  r"播放[量：:]*\s*\*?\*?(\d+(?:\.\d+)?)\s*w", re.IGNORECASE
)
COMPOSITE_HEADER_RE = re.compile(
  r"^[-*]?\s*\*\*?[Cc]omposite\*\*?:\s*`?(\d+(?:\.\d+)?)`?", re.MULTILINE
)
COMPOSITE_META_RE = re.compile(
  r"\*\*composite\*\*?\s*[=：:]\s*`?(\d+(?:\.\d+)?)`?", re.IGNORECASE
)

class Sample:
  def __init__(self, file_path: Path, scores: dict[str, int], actual_plays: float, old_composite: float, is_benchmark: bool = False):
    self.file_path = file_path
    self.name = file_path.name if not is_benchmark else f"[对标] {file_path.parent.name}"
    self.scores = scores
    self.actual_plays = actual_plays
    self.old_composite = old_composite
    self.new_composite = 0.0
    self.is_benchmark = is_benchmark

def parse_formula_to_lambda(formula_str: str) -> tuple[callable, list[str]]:
  """
  解析公式字符串为 lambda 表达式及所需维度列表。
  """
  cleaned = formula_str.replace("×", "*").replace("÷", "/")
  dimensions = sorted(list(set(re.findall(r"\b[A-Z]{2,3}\b", cleaned))))
  
  expression = cleaned
  for dim in dimensions:
    expression = re.sub(rf"\b{dim}\b", f"scores.get('{dim}', 0)", expression)
      
  try:
    code = compile(expression, "<formula>", "eval")
    func = lambda scores: eval(code, {"__builtins__": None}, {"scores": scores})
    return func, dimensions
  except Exception as e:
    logger.error(f"公式语法解析失败: {formula_str}. 详情: {e}")
    sys.exit(1)

def parse_prediction_file(path: Path) -> Sample | None:
  """
  解析正式 predictions/ 目录下的复盘日志样本。
  """
  try:
    text = path.read_text(encoding="utf-8")
  except OSError as e:
    logger.warning(f"无法读取文件 {path.name}: {e}")
    return None

  # 必须包含复盘模块才视为已复盘有效样本
  pred_section, _, retro_section = text.partition("## 复盘")
  if not retro_section.strip():
    return None

  plays_m = ACTUAL_PLAYS_RE.search(retro_section)
  if not plays_m:
    plays_m = ACTUAL_PLAYS_RE.search(pred_section)
    if not plays_m:
      return None
  actual_plays = float(plays_m.group(1))

  comp_m = COMPOSITE_HEADER_RE.search(pred_section)
  old_composite = float(comp_m.group(1)) if comp_m else 0.0

  scores = {}
  for m in DIMENSION_ROW_RE.finditer(pred_section):
    dim = m.group(1)
    val = int(m.group(2))
    scores[dim] = val

  if not scores:
    # 尝试在复盘段中再找一次
    for m in DIMENSION_ROW_RE.finditer(retro_section):
      dim = m.group(1)
      val = int(m.group(2))
      scores[dim] = val

  if not scores:
    logger.warning(f"文件 {path.name} 未解析到任何评分维度")
    return None

  return Sample(path, scores, actual_plays, old_composite, is_benchmark=False)

def parse_benchmark_meta_file(path: Path) -> Sample | None:
  """
  解析 samples/ 对标样本目录下的 meta.md。
  """
  try:
    text = path.read_text(encoding="utf-8")
  except OSError as e:
    logger.warning(f"无法读取对标文件 {path}: {e}")
    return None

  # 提取播放量
  plays_m = ACTUAL_PLAYS_RE.search(text)
  if not plays_m:
    return None
  actual_plays = float(plays_m.group(1))

  # 提取可能已保存的旧 composite
  comp_m = COMPOSITE_META_RE.search(text)
  old_composite = float(comp_m.group(1)) if comp_m else 0.0

  # 提取各维度初评分（由 agent-teams-evaluator 打分落盘）
  scores = {}
  for m in DIMENSION_ROW_RE.finditer(text):
    dim = m.group(1)
    val = int(m.group(2))
    scores[dim] = val

  # 若对标样本中没有评分，则无法用于 Spearman 重计算，忽略它
  if not scores:
    return None

  return Sample(path, scores, actual_plays, old_composite, is_benchmark=True)

def get_ranks(values: list[float], reverse: bool = True) -> list[float]:
  """
  计算序列秩次，平分处理平分结。
  """
  indexed = sorted(enumerate(values), key=lambda x: x[1], reverse=reverse)
  ranks = [0.0] * len(values)
  
  i = 0
  while i < len(indexed):
    j = i
    while j < len(indexed) and indexed[j][1] == indexed[i][1]:
      j += 1
    mean_rank = sum(range(i + 1, j + 1)) / (j - i)
    for k in range(i, j):
      ranks[indexed[k][0]] = mean_rank
    i = j
  return ranks

def calculate_spearman(ranks1: list[float], ranks2: list[float]) -> float:
  """
  计算 Spearman 秩相关系数。
  """
  n = len(ranks1)
  if n <= 1:
    return 1.0
  d_squared_sum = sum((r1 - r2) ** 2 for r1, r2 in zip(ranks1, ranks2))
  return 1.0 - (6.0 * d_squared_sum) / (n * (n**2 - 1))

def main() -> int:
  parser = argparse.ArgumentParser(description="评估公式升级校验器 v2.0")
  parser.add_argument("--propose", required=True, help="拟提议的新 Rubric 综合分公式")
  parser.add_argument("--predictions", type=Path, default=Path("predictions"), help="已复盘预测日志目录")
  parser.add_argument("--samples", type=Path, default=Path("samples"), help="对标样本目录")
  parser.add_argument("--threshold", type=float, default=0.8, help="Spearman 秩排序一致性比例阈值")
  parser.add_argument("--backfill", default="", help="回填字段, 格式如: AB=3,SR=2")
  args = parser.parse_args()

  # 解析回填值
  backfill_dict = {}
  if args.backfill:
    for pair in args.backfill.split(","):
      if "=" in pair:
        k, v = pair.split("=", 1)
        backfill_dict[k.strip()] = int(v.strip())

  # 解析拟提议公式
  formula_fn, required_dims = parse_formula_to_lambda(args.propose)
  logger.info(f"成功解析公式。包含维度: {required_dims}")

  samples: list[Sample] = []

  # 1. 扫描已发表并复盘的文件
  if args.predictions.is_dir():
    for path in args.predictions.glob("*.md"):
      s = parse_prediction_file(path)
      if s:
        samples.append(s)

  # 2. 扫描已导入的对标样本文件（samples/<账号名>/<id>/meta.md）
  if args.samples.is_dir():
    # 递归查找子目录下的 meta.md
    for path in args.samples.rglob("meta.md"):
      s = parse_benchmark_meta_file(path)
      if s:
        samples.append(s)

  if not samples:
    logger.error("在 predictions 目录与 samples 目录中未找到任何含有打分与实绩的样本")
    return 1

  logger.info(f"加载了 {len(samples)} 个包含实绩的标定样本 (包含对标与自产已复盘样本)")

  # 计算新公式下的 composite 并补齐维度
  for s in samples:
    for dim in required_dims:
      if dim not in s.scores:
        if dim in backfill_dict:
          s.scores[dim] = backfill_dict[dim]
        else:
          logger.error(f"样本 '{s.name}' 缺少拟提议公式的必需维度 '{dim}'，请在 --backfill 中指定默认补齐分。")
          return 3
    try:
      s.new_composite = round(formula_fn(s.scores), 2)
    except Exception as e:
      logger.error(f"计算样本 {s.name} 新综合分失败: {e}")
      return 4

  # 计算排序并比对 Spearman 相关系数
  n = len(samples)
  composites_old = [s.old_composite for s in samples]
  composites_new = [s.new_composite for s in samples]
  actual_plays = [s.actual_plays for s in samples]

  old_ranks = get_ranks(composites_old, reverse=True)
  new_ranks = get_ranks(composites_new, reverse=True)
  actual_ranks = get_ranks(actual_plays, reverse=True)

  spearman_old = calculate_spearman(old_ranks, actual_ranks)
  spearman_new = calculate_spearman(new_ranks, actual_ranks)

  # 计算倒挂回归对 (Pairwise rank regression)
  regressions = []
  for i in range(n):
    for j in range(n):
      if i == j:
        continue
      old_correct = (composites_old[i] > composites_old[j] and actual_plays[i] > actual_plays[j])
      if old_correct:
        new_reversed = (composites_new[i] < composites_new[j])
        if new_reversed:
          regressions.append((samples[i], samples[j]))

  # 输出校验比对结果表
  logger.info("\n" + "=" * 80)
  logger.info(f"{'样本名称':<30} | {'旧分':<6} | {'新分':<6} | {'新Rank':<6} | {'实际播放':<8} | {'实际Rank':<8} | {'偏差':<4}")
  logger.info("-" * 80)
  
  samples_sorted = sorted(samples, key=lambda x: x.new_composite, reverse=True)
  ranks_map = {s.name: r for s, r in zip(samples, new_ranks)}
  act_ranks_map = {s.name: r for s, r in zip(samples, actual_ranks)}
  
  for s in samples_sorted:
    nr = ranks_map[s.name]
    ar = act_ranks_map[s.name]
    delta = abs(nr - ar)
    logger.info(
      f"{s.name[:30]:<30} | {s.old_composite:<6.2f} | {s.new_composite:<6.2f} | {nr:<6.1f} | {s.actual_plays:<7.2f}w | {ar:<8.1f} | {delta:<4.1f}"
    )
  logger.info("=" * 80)

  # 统计排序偏差在合理区间内的比例 (|delta| <= 1.0)
  matches = sum(1 for s in samples if abs(ranks_map[s.name] - act_ranks_map[s.name]) <= 1.0)
  match_ratio = matches / n

  logger.info(f"旧公式 Spearman 秩序相关系数: {spearman_old:.4f}")
  logger.info(f"新公式 Spearman 秩序相关系数: {spearman_new:.4f}")
  logger.info(f"新公式排序一致性比例 (|delta| <= 1): {match_ratio*100:.1f}% ({matches}/{n})")
  logger.info(f"Pairwise 顺序倒挂回归对数: {len(regressions)}")

  for s1, s2 in regressions:
    logger.warning(
      f"  [倒挂回归] {s1.name} (新 {s1.new_composite} vs 实际 {s1.actual_plays}w) 被排在了 "
      f"{s2.name} (新 {s2.new_composite} vs 实际 {s2.actual_plays}w) 后面。"
    )

  # 最终判定 (引入冷启动防拦截机制)
  success = True
  is_cold_start = (n < 5)

  if match_ratio < args.threshold:
    logger.error(f"校验判定: 排序一致性比例 {match_ratio:.2f} 低于阈值 {args.threshold:.2f}")
    if not is_cold_start:
      success = False
    else:
      logger.warning("由于当前处于冷启动阶段 (样本数 < 5 篇)，一致性比例不作强拦截限流限制。")

  if regressions:
    logger.error(f"校验判定: 检测到 {len(regressions)} 对样本发生了排序秩序倒挂回归")
    if not is_cold_start:
      success = False
    else:
      logger.warning("由于当前处于冷启动阶段 (样本数 < 5 篇)，倒挂回归不作强拦截限制。")

  if spearman_new < spearman_old:
    logger.warning(f"WARN: 新公式的 Spearman 指数 ({spearman_new:.4f}) 低于旧公式的 ({spearman_old:.4f})")

  if success:
    if is_cold_start:
      logger.info("PASS: 校验通过！(当前为冷启动防震荡弱化拦截模式)")
    else:
      logger.info("PASS: 新公式成功通过排序一致性与无回归验证！")
    return 0
  else:
    logger.error("REJECT: 新公式验证未通过，被系统强制拦截。")
    return 5

if __name__ == "__main__":
  sys.exit(main())
