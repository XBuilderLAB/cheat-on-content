#!/usr/bin/env python3
"""
validate-bump.py — Validate rubric formula upgrade candidates by evaluating Spearman correlation
and pairwise no-regression on the historical calibration pool.

Usage:
    python tools/validate-bump.py --propose "新公式" [--predictions DIR] [--threshold THRESH] [--backfill "key=val"]

Example:
    python tools/validate-bump.py --propose "(ER*2.0 + HP*1.5 + MS*1.5 + QL + SR + TS + SAT) / 9.0 * 2.0" --backfill "MS=3,TS=3"
"""

import argparse
import logging
import re
import sys
from pathlib import Path

# Set up logging strictly adhering to user global rules
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("validate-bump")

# Patterns for parsing prediction markdowns
DIMENSION_ROW_RE = re.compile(
    r"^\|\s*([A-Z]{2,3})(?:\s*\([^)]*\))?\s*\|\s*(\d+)\s*\|", re.MULTILINE
)
ACTUAL_PLAYS_RE = re.compile(
    r"播放[：:]\s*\*?\*?(\d+(?:\.\d+)?)\s*w", re.IGNORECASE
)
COMPOSITE_HEADER_RE = re.compile(
    r"^[-*]?\s*\*\*?[Cc]omposite\*\*?:\s*`?(\d+(?:\.\d+)?)`?", re.MULTILINE
)


class Sample:
    def __init__(self, file_path: Path, scores: dict[str, int], actual_plays: float, old_composite: float):
        self.file_path = file_path
        self.name = file_path.name
        self.scores = scores
        self.actual_plays = actual_plays
        self.old_composite = old_composite
        self.new_composite = 0.0


def parse_formula_to_lambda(formula_str: str) -> tuple[callable, list[str]]:
    """
    Parses a formula string like '(ER*2.0 + HP*1.5 + MS*1.5 + QL) / 9.0 * 2.0'
    into a callable Python function and list of required dimensions.
    """
    # Clean formula math operators to python standard
    cleaned = formula_str.replace("×", "*").replace("÷", "/")
    
    # Extract all dimension tokens (2-3 letter uppercase words)
    dimensions = sorted(list(set(re.findall(r"\b[A-Z]{2,3}\b", cleaned))))
    
    # We will build a lambda that accepts a dict of scores
    # Replace dimension name with scores['NAME'] safely
    expression = cleaned
    for dim in dimensions:
        # Match word boundaries to prevent substring replacement issues (e.g. NA inside SAT)
        expression = re.sub(rf"\b{dim}\b", f"scores.get('{dim}', 0)", expression)
        
    try:
        # Simple syntax check by compiling
        code = compile(expression, "<formula>", "eval")
        func = lambda scores: eval(code, {"__builtins__": None}, {"scores": scores})
        return func, dimensions
    except Exception as e:
        logger.error(f"公式语法解析失败: {formula_str}. 详情: {e}")
        sys.exit(1)


def parse_prediction_file(path: Path) -> Sample | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning(f"无法读取文件 {path.name}: {e}")
        return None

    # Parse actual plays (only care about samples that have retrospective data)
    pred_section, _, retro_section = text.partition("## 复盘")
    if not retro_section.strip():
        return None

    plays_m = ACTUAL_PLAYS_RE.search(retro_section)
    if not plays_m:
        # Try searching header as fallback
        plays_m = ACTUAL_PLAYS_RE.search(pred_section)
        if not plays_m:
            return None
    actual_plays = float(plays_m.group(1))

    # Parse old composite
    comp_m = COMPOSITE_HEADER_RE.search(pred_section)
    old_composite = float(comp_m.group(1)) if comp_m else 0.0

    # Parse dimension scores
    scores = {}
    for m in DIMENSION_ROW_RE.finditer(pred_section):
        dim = m.group(1)
        val = int(m.group(2))
        scores[dim] = val

    # If no scores are parsed, check if they exist in retro section (unlikely but check)
    if not scores:
        for m in DIMENSION_ROW_RE.finditer(retro_section):
            dim = m.group(1)
            val = int(m.group(2))
            scores[dim] = val

    if not scores:
        logger.warning(f"文件 {path.name} 未解析到任何评分维度")
        return None

    return Sample(path, scores, actual_plays, old_composite)


def get_ranks(values: list[float], reverse: bool = True) -> list[float]:
    """Calculates average ranks for a list of values, handling ties."""
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
    n = len(ranks1)
    if n <= 1:
        return 1.0
    d_squared_sum = sum((r1 - r2) ** 2 for r1, r2 in zip(ranks1, ranks2))
    return 1.0 - (6.0 * d_squared_sum) / (n * (n**2 - 1))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rubric formula upgrades on calibration pool.")
    parser.add_argument("--propose", required=True, help="New formula string to validate")
    parser.add_argument("--predictions", type=Path, default=Path("predictions"), help="Predictions directory")
    parser.add_argument("--threshold", type=float, default=0.8, help="Rank match threshold (default: 0.8)")
    parser.add_argument("--backfill", default="", help="Comma separated key=value for missing dimensions")
    args = parser.parse_args()

    if not args.predictions.is_dir():
        logger.error(f"预测目录不存在: {args.predictions}")
        return 2

    # Parse backfill values
    backfill_dict = {}
    if args.backfill:
        for pair in args.backfill.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                backfill_dict[k.strip()] = int(v.strip())

    # Compile the formula
    formula_fn, required_dims = parse_formula_to_lambda(args.propose)
    logger.info(f"成功解析公式。需要维度: {required_dims}")

    # Load all valid calibration samples
    samples: list[Sample] = []
    for path in args.predictions.glob("*.md"):
        sample = parse_prediction_file(path)
        if sample:
            samples.append(sample)

    if not samples:
        logger.error("未找到任何含有复盘实绩的校准样本文件")
        return 1

    logger.info(f"加载了 {len(samples)} 个有复盘实绩的样本")

    # Evaluate new composites and handle missing dimensions
    for s in samples:
        # Backfill missing dimensions
        for dim in required_dims:
            if dim not in s.scores:
                if dim in backfill_dict:
                    s.scores[dim] = backfill_dict[dim]
                else:
                    logger.error(
                        f"样本 {s.name} 缺少维度 '{dim}'，且未提供 --backfill 补充打分值。"
                    )
                    return 3
        try:
            s.new_composite = round(formula_fn(s.scores), 2)
        except Exception as e:
            logger.error(f"计算样本 {s.name} 新综合分失败: {e}")
            return 4

    # Calculate ranks
    composites_old = [s.old_composite for s in samples]
    composites_new = [s.new_composite for s in samples]
    actual_plays = [s.actual_plays for s in samples]

    old_ranks = get_ranks(composites_old, reverse=True)
    new_ranks = get_ranks(composites_new, reverse=True)
    actual_ranks = get_ranks(actual_plays, reverse=True)

    # Compute Spearman correlation
    spearman_old = calculate_spearman(old_ranks, actual_ranks)
    spearman_new = calculate_spearman(new_ranks, actual_ranks)

    # Check pairwise no-regression:
    # A pair (i, j) is "correctly ordered" by old formula if:
    # (composites_old[i] > composites_old[j] and actual_plays[i] > actual_plays[j])
    # It regresses if under new formula: composites_new[i] < composites_new[j]
    regressions = []
    n = len(samples)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # Old formula ordered correctly
            old_correct = (composites_old[i] > composites_old[j] and actual_plays[i] > actual_plays[j])
            if old_correct:
                # New formula reversed the order
                new_reversed = (composites_new[i] < composites_new[j])
                if new_reversed:
                    regressions.append((samples[i], samples[j]))

    # Print comparison table
    logger.info("\n" + "=" * 80)
    logger.info(f"{'样本名称':<25} | {'旧分':<6} | {'新分':<6} | {'新Rank':<6} | {'实际播放':<8} | {'实际Rank':<8} | {'偏差':<4}")
    logger.info("-" * 80)
    
    samples_sorted = sorted(samples, key=lambda x: x.new_composite, reverse=True)
    ranks_map = {s.name: r for s, r in zip(samples, new_ranks)}
    act_ranks_map = {s.name: r for s, r in zip(samples, actual_ranks)}
    
    for s in samples_sorted:
        nr = ranks_map[s.name]
        ar = act_ranks_map[s.name]
        delta = abs(nr - ar)
        logger.info(
            f"{s.name[:25]:<25} | {s.old_composite:<6.2f} | {s.new_composite:<6.2f} | {nr:<6.1f} | {s.actual_plays:<7.2f}w | {ar:<8.1f} | {delta:<4.1f}"
        )
    logger.info("=" * 80)

    # Count rank matches (|delta| <= 1)
    matches = 0
    for s in samples:
        nr = ranks_map[s.name]
        ar = act_ranks_map[s.name]
        if abs(nr - ar) <= 1.0:
            matches += 1
    match_ratio = matches / n

    logger.info(f"旧公式 Spearman 秩相关系数: {spearman_old:.4f}")
    logger.info(f"新公式 Spearman 秩相关系数: {spearman_new:.4f}")
    logger.info(f"新公式排序一致性比例 (|delta| <= 1): {match_ratio*100:.1f}% ({matches}/{n})")
    logger.info(f"Pairwise 顺序倒挂回归对数: {len(regressions)}")

    for s1, s2 in regressions:
        logger.warning(
            f"  [倒挂回归] {s1.name} (新 {s1.new_composite} vs 实际 {s1.actual_plays}w) 被排在 "
            f"{s2.name} (新 {s2.new_composite} vs 实际 {s2.actual_plays}w) 之后"
        )

    # Final verdict
    success = True
    if match_ratio < args.threshold:
        logger.error(f"FAIL: 排序一致性比例 {match_ratio:.2f} 低于阈值 {args.threshold:.2f}")
        success = False
    
    if regressions:
        logger.error(f"FAIL: 检测到 {len(regressions)} 对旧公式正确的样本排序发生倒挂")
        success = False

    if spearman_new < spearman_old:
        logger.warning(f"WARN: 新公式的 Spearman 相关系数 ({spearman_new:.4f}) 低于旧公式 ({spearman_old:.4f})")

    if success:
        logger.info("PASS: 新公式通过了本地排序和无回归校验！")
        return 0
    else:
        logger.error("REJECT: 新公式未通过校验")
        return 5


if __name__ == "__main__":
    sys.exit(main())
