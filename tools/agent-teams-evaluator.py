#!/usr/bin/env python3
"""
agent-teams-evaluator.py — Evaluates a draft script using a multi-agent consensus team.
Simulates HS-Agent, LS-Agent, AM-Agent, and a Manager Agent to score content.

Usage:
    python tools/agent-teams-evaluator.py --draft scripts/YYYY-MM-DD_id_short.md [--mode team]
"""

import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("agent-team")

# Domain Experts Definitions
ROLES = {
    "HS": {
        "name": "Hook & Emotion Expert",
        "primary": ["HP", "ER"],
        "system": (
            "你是一个‘钩子与情感专家’。你只关注稿件的前3秒与前30秒抓人程度（HP）和情感共鸣（ER）。"
            "你偏好具象的矛盾冲突、真实的痛点和让人微微不适的自我映射。你痛恨套路化的抒情和冰冷说教。"
        )
    },
    "LS": {
        "name": "Logic & Structure Expert",
        "primary": ["QL", "NA", "SAT", "LE"],
        "system": (
            "你是一个‘逻辑与结构专家’。你关注文章的起承转合（NA/LE）、金句能否独立存活（QL）以及讽刺/反讽嵌套深度（SAT）。"
            "你偏好精致的三幕剧结构、凝练深刻的警句和嵌套式的讽刺解构。你痛恨大白话口水歌和缺乏铺垫的强行总结。"
        )
    },
    "AM": {
        "name": "Audience & Market Expert",
        "primary": ["AB", "SR", "TS"],
        "system": (
            "你是一个‘受众与市场专家’。你关注大众共鸣点（AB/SR）和社交分享安全性与动力（TS）。"
            "你站在大盘视角看传播，评估转发动作对读者是社交负债还是社交货币。你痛恨自娱自乐的圈子自嗨和缺乏现实投射的内容。"
        )
    }
}

# Dimension Assignment Mapping for Double-Blind Consensus
DIMENSION_ROLES = {
    "HP": {"primary": "HS", "secondary": "AM"},
    "ER": {"primary": "HS", "secondary": "LS"},
    "QL": {"primary": "LS", "secondary": "HS"},
    "NA": {"primary": "LS", "secondary": "AM"},
    "LE": {"primary": "LS", "secondary": "AM"},
    "SAT": {"primary": "LS", "secondary": "HS"},
    "AB": {"primary": "AM", "secondary": "HS"},
    "TS": {"primary": "AM", "secondary": "HS"},
    "SR": {"primary": "AM", "secondary": "LS"}
}


def load_env(env_path: Path):
    """Simple parser to load .env variables without external packages."""
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ[key.strip()] = val.strip().strip("'\"")


def call_llm(system_instruction: str, prompt: str, json_mode: bool = False) -> str:
    """Wrapper to route to Gemini or OpenAI API based on env configuration."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
        
        contents = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        if system_instruction:
            contents["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if json_mode:
            contents["generationConfig"] = {"responseMimeType": "application/json"}

        req = urllib.request.Request(
            url,
            data=json.dumps(contents).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            logger.error(f"Gemini API 错误 {e.code}: {e.read().decode('utf-8')}")
            raise
    elif openai_key:
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        url = f"{base_url}/chat/completions"
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_key}"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            logger.error(f"OpenAI API 错误 {e.code}: {e.read().decode('utf-8')}")
            raise
    else:
        raise ValueError("未检测到 API 秘钥，请在 .env 中设置 GEMINI_API_KEY 或 OPENAI_API_KEY。")


def get_expert_evaluation(agent_key: str, draft_text: str, dimensions: list[str], rubric_definitions: str) -> dict:
    """Invokes a specific expert Agent to score designated dimensions."""
    role_info = ROLES[agent_key]
    dims_desc = ", ".join(dimensions)
    prompt = (
        f"请评估以下稿件。你只需评估你负责的维度: [{dims_desc}]。其他维度不要评估。\n"
        f"对于每个你评估的维度，请给出 0 至 5 的整数分（不允许小数分，要保守严格评分，尽量打低分而非高分，防止虚高）。\n"
        f"同时对每一项给出一句简洁理由（字数在1至30字以内，必须引用稿子里的具体句子或细节，极其直接犀利，不加高层废话）。\n\n"
        f"评分准则与维度定义如下:\n{rubric_definitions}\n\n"
        f"--- 稿件全文 ---\n{draft_text}\n\n"
        f"请输出如下 JSON 格式 (严格符合 JSON 标准):\n"
        f"{{\n"
        f"  \"evaluations\": {{\n"
        f"    \"维度简称\": {{\n"
        f"      \"score\": 整数值,\n"
        f"      \"reason\": \"犀利直接的理由 (≤30字)\"\n"
        f"    }}\n"
        f"  }}\n"
        f"}}"
    )
    
    try:
        response_text = call_llm(role_info["system"], prompt, json_mode=True)
        # Parse JSON
        result = json.loads(response_text)
        return result.get("evaluations", {})
    except Exception as e:
        logger.error(f"专家 {role_info['name']} 评估失败: {e}")
        return {}


def run_debate(dim: str, primary_role: str, secondary_role: str, val_p: int, val_s: int, reason_p: str, reason_s: str, draft_text: str, rubric_definitions: str) -> int:
    """Simulates 2-round debate when score difference is >= 2."""
    logger.info(f"触发 {dim} 维度共识辩论: 主审 {primary_role}({val_p}分) vs 备审 {secondary_role}({val_s}分)")

    # Round 1: Get Arguments
    p_arg_prompt = (
        f"针对稿件中的 {dim} 维度，你打了 {val_p} 分，而另一位专家打了 {val_s} 分。\n"
        f"请结合稿件文本与评分准则，提供不超过 100 字的自辩陈述，证明你的评分才是最客观正确的。\n"
        f"不要多说客套话，直接给出文本事实依据。\n\n"
        f"--- 稿件 ---\n{draft_text}\n"
    )
    s_arg_prompt = p_arg_prompt.replace(str(val_p), str(val_s)).replace(str(val_s), str(val_p))

    try:
        p_arg = call_llm(ROLES[primary_role]["system"], p_arg_prompt)
        s_arg = call_llm(ROLES[secondary_role]["system"], s_arg_prompt)
        
        logger.info(f"  [第一轮辩论陈述] {primary_role} 主张: {p_arg.strip()}")
        logger.info(f"  [第一轮辩论陈述] {secondary_role} 主张: {s_arg.strip()}")

        # Round 2: Rebuttal & Final Vote
        p_rebut_prompt = (
            f"针对稿件的 {dim} 维度，你打了 {val_p} 分，你的陈述是：'{p_arg.strip()}'。\n"
            f"另一位专家的打分是 {val_s}，其理由是：'{s_arg.strip()}'。\n"
            f"在阅读了对方理由后，请给出你的最终裁决。你是否坚持原判？若修改，请输入新分数（0-5 整数分）。\n"
            f"请以 JSON 格式返回:\n"
            f"{{\n"
            f"  \"final_score\": 整数值,\n"
            f"  \"reason\": \"简短说明是否改分及核心依据 (≤30字)\"\n"
            f"}}"
        )
        s_rebut_prompt = p_rebut_prompt.replace(str(val_p), str(val_s)).replace(str(val_s), str(val_p)).replace(p_arg.strip(), s_arg.strip()).replace(s_arg.strip(), p_arg.strip())

        p_res = json.loads(call_llm(ROLES[primary_role]["system"], p_rebut_prompt, json_mode=True))
        s_res = json.loads(call_llm(ROLES[secondary_role]["system"], s_rebut_prompt, json_mode=True))
        
        final_p = p_res.get("final_score", val_p)
        final_s = s_res.get("final_score", val_s)
        
        logger.info(f"  [第二轮投票] {primary_role}: {final_p}分 ({p_res.get('reason')})")
        logger.info(f"  [第二轮投票] {secondary_role}: {final_s}分 ({s_res.get('reason')})")

        if abs(final_p - final_s) <= 1:
            # Reached consensus
            val = round((final_p + final_s) / 2)
            logger.info(f"  [达成共识] 最终决定分数: {val}")
            return val
        else:
            # Manager intervention
            logger.info(f"  [分歧依旧] 启动 Manager 裁决，偏向主审 {primary_role} 的分数 {final_p}")
            return final_p
    except Exception as e:
        logger.error(f"辩论发生异常: {e}，回退为主审分数 {val_p}")
        return val_p


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Teams Evaluation tool for content drafts.")
    parser.add_argument("--draft", required=True, type=Path, help="Path to draft markdown file")
    parser.add_argument("--mode", default="team", choices=["team", "self"], help="Evaluation mode")
    args = parser.parse_args()

    # Load environment variables
    load_env(Path(".env"))

    if not args.draft.is_file():
        logger.error(f"稿件不存在: {args.draft}")
        return 1

    draft_content = args.draft.read_text(encoding="utf-8")
    
    # Locate rubric_notes.md
    rubric_path = Path("rubric_notes.md")
    if not rubric_path.is_file():
        logger.error("未找到 rubric_notes.md 文件，请在项目根目录下运行。")
        return 2
    
    rubric_notes = rubric_path.read_text(encoding="utf-8")

    # Extract active formula from rubric_notes.md
    formula_match = re.search(r"composite\s*=\s*(.+)$", rubric_notes, re.MULTILINE | re.IGNORECASE)
    if not formula_match:
        # Check starter rubric styles
        formula_match = re.search(r"```\s*\n\s*composite\s*=\s*(.+?)\n\s*```", rubric_notes, re.IGNORECASE)
    
    if not formula_match:
        logger.error("无法解析 rubric_notes.md 中的综合分公式。请确保包含 'composite = ...' 行")
        return 3

    formula_str = formula_match.group(1).strip()
    logger.info(f"找到公式: {formula_str}")

    # Determine dimensions based on active formula
    cleaned_formula = formula_str.replace("×", "*").replace("÷", "/")
    dimensions = sorted(list(set(re.findall(r"\b[A-Z]{2,3}\b", cleaned_formula))))
    logger.info(f"解析出需要打分的维度: {dimensions}")

    # Check API availability
    has_api = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not has_api:
        logger.warning(
            "未在环境或 .env 文件中发现 API Key。请在 .env 中填入 GEMINI_API_KEY 或 OPENAI_API_KEY。"
        )
        logger.info("此时推荐返回 IDE 会话由 Agent 进行角色扮演内生打分。")
        # Format the role prompt for inner simulation
        print("\n=== 内生模拟 Agent Teams 提示词 ===")
        print("请你在当前会话中扮演 Manager Agent，组建由 Hook & Emotion Expert, Logic & Structure Expert, Audience & Market Expert 组成的打分团队。")
        print(f"按以下维度打分: {dimensions}")
        print("===================================\n")
        return 5

    # Run Expert Agent evaluations
    logger.info("启动智能体专家打分流程...")
    expert_scores = {}
    
    for role_key, role_info in ROLES.items():
        # Get dimensions assigned to this role (either primary or secondary)
        assigned_dims = [
            dim for dim in dimensions 
            if DIMENSION_ROLES.get(dim, {}).get("primary") == role_key 
            or DIMENSION_ROLES.get(dim, {}).get("secondary") == role_key
        ]
        if not assigned_dims:
            continue
        
        logger.info(f"正在唤醒专家 {role_info['name']} 评估 {assigned_dims}...")
        evals = get_expert_evaluation(role_key, draft_content, assigned_dims, rubric_notes)
        expert_scores[role_key] = evals

    # Manager Consolidation
    logger.info("各专家评估完毕。Manager Agent 开始整合得分并判定冲突...")
    final_scores = {}
    final_reasons = {}

    for dim in dimensions:
        mapping = DIMENSION_ROLES.get(dim)
        if not mapping:
            # Fallback to general assignment if unknown dimension
            final_scores[dim] = 3
            final_reasons[dim] = "未知维度，给定中值分"
            continue
            
        p_role = mapping["primary"]
        s_role = mapping["secondary"]

        p_data = expert_scores.get(p_role, {}).get(dim, {})
        s_data = expert_scores.get(s_role, {}).get(dim, {})

        val_p = p_data.get("score", 3)
        reason_p = p_data.get("reason", "未提供理由")

        val_s = s_data.get("score", 3)
        reason_s = s_data.get("reason", "未提供理由")

        # Check for disagreement
        if abs(val_p - val_s) >= 2:
            final_val = run_debate(dim, p_role, s_role, val_p, val_s, reason_p, reason_s, draft_content, rubric_notes)
        else:
            final_val = round((val_p + val_s) / 2)

        final_scores[dim] = final_val
        final_reasons[dim] = reason_p if final_val == val_p else reason_s

    # Calculate final composite
    # Evaluate using the safe lambda evaluator we previously design
    expression = cleaned_formula
    for dim in dimensions:
        expression = re.sub(rf"\b{dim}\b", str(final_scores[dim]), expression)
    
    try:
        composite = round(eval(expression, {"__builtins__": None}), 2)
    except Exception as e:
        logger.error(f"公式求值失败: {expression}. 错误: {e}")
        composite = 0.0

    # Print final Markdown Matrix
    print("\n")
    print(f"📊 {args.draft.name} — Agent Teams 打分表")
    print("| 维度 | 分数 | 理由 | 决策专家分 (主/备) |")
    print("|---|---|---|---|")
    for dim in dimensions:
        mapping = DIMENSION_ROLES.get(dim, {})
        p_role = mapping.get("primary", "N/A")
        s_role = mapping.get("secondary", "N/A")
        p_val = expert_scores.get(p_role, {}).get(dim, {}).get("score", "-")
        s_val = expert_scores.get(s_role, {}).get(dim, {}).get("score", "-")
        
        print(f"| {dim:<3} | {final_scores[dim]:<4} | {final_reasons[dim]:<30} | {p_role}:{p_val} / {s_role}:{s_val} |")
    
    print(f"\n公式：{formula_str}")
    print(f"**composite = {composite}**")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
