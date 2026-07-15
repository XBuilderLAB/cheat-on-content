"""Deterministic account-audit engine for productized creator diagnostics."""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


METRIC_ALIASES = {
    "views": ("views", "view_count", "play_count", "impressions", "exposure"),
    "likes": ("likes", "like_count", "liked_count"),
    "collects": ("collects", "collect_count", "favorite_count", "saves"),
    "comments": ("comment_count", "comments_count", "comments_total"),
    "shares": ("shares", "share_count", "shared_count"),
    "followers": ("followers", "fans_inc", "followers_gained"),
}


def _number(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    text = str(value).strip().lower().replace(",", "")
    if not text or text in {"-", "n/a", "none", "null"}:
        return None
    multiplier = 1
    if text.endswith("万"):
        multiplier, text = 10_000, text[:-1]
    elif text.endswith("k"):
        multiplier, text = 1_000, text[:-1]
    elif text.endswith("m"):
        multiplier, text = 1_000_000, text[:-1]
    try:
        return max(0, int(float(text) * multiplier))
    except ValueError:
        return None


def _first_metric(raw: dict[str, Any], aliases: Iterable[str]) -> int | None:
    for key in aliases:
        if key in raw:
            value = _number(raw.get(key))
            if value is not None:
                return value
    return None


def _comment_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = next(
                (str(item.get(k, "")) for k in ("content", "text", "body") if item.get(k)),
                "",
            )
        else:
            text = ""
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append(text[:500])
    return out


def _hook(text: str) -> str:
    first = re.split(r"[。！？!?\n]", text.strip(), maxsplit=1)[0]
    return first[:80]


def _hook_style(text: str) -> str:
    head = _hook(text)
    if not head:
        return "无正文"
    if "?" in head or "？" in head or re.search(r"为什么|怎么|是不是|有没有", head):
        return "问题"
    if re.search(r"\d|一二三四五六七八九十.+个", head):
        return "数字/清单"
    if re.search(r"但是|却|反而|不是.+而是|别再|真正", head):
        return "反差/纠偏"
    if re.search(r"我|我们|昨天|今天|刚刚|曾经", head):
        return "个人经历"
    return "直接陈述"


def _series(note: dict[str, Any]) -> str:
    if note["tags"]:
        return note["tags"][0]
    title = note["title"]
    words = re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,20}|[\u4e00-\u9fff]{2,6}", title)
    return words[0] if words else "其他"


def _structure(body: str) -> str:
    length = len(re.sub(r"\s+", "", body))
    if length < 200:
        return "短表达(<200字)"
    if length <= 600:
        return "中等展开(200–600字)"
    return "长论证(>600字)"


def normalize_notes(payload: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize adapter exports and remove duplicates by note id."""

    meta: dict[str, Any] = {}
    if isinstance(payload, dict):
        raw_notes = payload.get("notes", [])
        meta = {k: v for k, v in payload.items() if k != "notes"}
    elif isinstance(payload, list):
        raw_notes = payload
    else:
        raise ValueError("输入必须是 note 数组或包含 notes 数组的对象")
    if not isinstance(raw_notes, list):
        raise ValueError("notes 必须是数组")

    deduped: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_notes):
        if not isinstance(raw, dict):
            continue
        note_id = str(raw.get("note_id") or raw.get("id") or f"row-{index + 1}")
        body = str(raw.get("body") or raw.get("desc") or raw.get("text") or "").strip()
        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tags = [x.strip(" #") for x in re.split(r"[,，#]", tags) if x.strip(" #")]
        tags = [str(x).strip(" #") for x in tags if str(x).strip(" #")]
        note = {
            "note_id": note_id,
            "title": str(raw.get("title") or "(无标题)").strip(),
            "body": body,
            "tags": tags,
            "url": str(raw.get("url") or raw.get("platform_url") or f"https://www.xiaohongshu.com/explore/{note_id}"),
            "published_at": raw.get("published_at") or raw.get("post_time_str") or raw.get("create_time"),
            "comment_texts": _comment_texts(raw.get("comments") or raw.get("top_comments")),
            "fetch_warning": str(raw.get("audit_fetch_warning") or "").strip(),
        }
        for canonical, aliases in METRIC_ALIASES.items():
            note[canonical] = _first_metric(raw, aliases)
        note["hook"] = _hook(body or note["title"])
        note["hook_style"] = _hook_style(body or note["title"])
        note["series"] = _series(note)
        note["structure"] = _structure(body)
        views = note["views"] or 0
        for metric in ("likes", "collects", "comments", "shares", "followers"):
            value = note[metric]
            note[f"{metric}_rate"] = (value / views) if value is not None and views > 0 else None
        deduped[note_id] = note
    return list(deduped.values()), meta


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _summary(values: list[int | float]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return {"count": 0, "mean": None, "median": None, "p25": None, "p75": None, "min": None, "max": None}
    return {
        "count": len(clean),
        "mean": round(statistics.fmean(clean), 4),
        "median": round(statistics.median(clean), 4),
        "p25": round(_percentile(clean, 0.25) or 0, 4),
        "p75": round(_percentile(clean, 0.75) or 0, 4),
        "min": min(clean),
        "max": max(clean),
    }


def _evidence(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "note_id": note["note_id"],
        "title": note["title"],
        "url": note["url"],
        "views": note["views"],
        "collect_rate": note["collects_rate"],
        "comment_rate": note["comments_rate"],
    }


def _audience(notes: list[dict[str, Any]]) -> dict[str, Any]:
    categories = {
        "self_identification": re.compile(r"我也|同感|正在|刚好|本人|一样"),
        "questions": re.compile(r"怎么|如何|为什么|请问|哪里|能不能|吗[？?]?$"),
        "disagreement": re.compile(r"^(但是|不过)|不认同|不同意|不一定|反对|未必"),
    }
    result: dict[str, Any] = {"comment_count": 0, "signals": {}, "anti_persona": []}
    for note in notes:
        for text in note["comment_texts"]:
            result["comment_count"] += 1
            for name, pattern in categories.items():
                if pattern.search(text):
                    bucket = result["signals"].setdefault(name, {"count": 0, "examples": []})
                    bucket["count"] += 1
                    if len(bucket["examples"]) < 3:
                        bucket["examples"].append({"note_id": note["note_id"], "text": text[:120]})
    disagreement = result["signals"].get("disagreement", {})
    result["anti_persona"] = disagreement.get("examples", [])
    return result


def _group_pattern(notes: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for note in notes:
        groups[str(note[field])].append(note)
    rows = []
    for name, items in groups.items():
        views = [n["views"] for n in items if n["views"] is not None]
        rows.append({
            "name": name,
            "sample_size": len(items),
            "median_views": statistics.median(views) if views else None,
            "mean_views": statistics.fmean(views) if views else None,
            "evidence_note_ids": [n["note_id"] for n in sorted(items, key=lambda n: n["views"] or 0, reverse=True)[:3]],
        })
    return sorted(rows, key=lambda x: ((x["median_views"] or -1), x["sample_size"]), reverse=True)


def _hypotheses(notes: list[dict[str, Any]], baseline: float) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    topic_rows = [x for x in _group_pattern(notes, "series") if x["sample_size"] >= 2]
    if topic_rows:
        best = topic_rows[0]
        evidence = [n for n in notes if n["note_id"] in best["evidence_note_ids"]][:3]
        hypotheses.append({
            "id": "H1",
            "statement": f"“{best['name']}”系列可能是当前最稳的流量支点。",
            "confidence": "medium" if len(evidence) >= 2 else "low",
            "evidence": [_evidence(n) for n in evidence],
            "test": "保持题材不变，只替换开头结构，连续发布两次。",
        })

    hook_rows = [x for x in _group_pattern(notes, "hook_style") if x["sample_size"] >= 2]
    if hook_rows:
        best = hook_rows[0]
        evidence = [n for n in notes if n["note_id"] in best["evidence_note_ids"]][:3]
        hypotheses.append({
            "id": f"H{len(hypotheses) + 1}",
            "statement": f"“{best['name']}”开头与较高浏览表现相关。",
            "confidence": "medium" if len(evidence) >= 2 and (best["median_views"] or 0) > baseline else "low",
            "evidence": [_evidence(n) for n in evidence],
            "test": "同一选题写两个开头，只拍其中一个并在发布前写下选择理由。",
        })

    rate_candidates = [n for n in notes if n["collects_rate"] is not None]
    rate_candidates.sort(key=lambda n: n["collects_rate"], reverse=True)
    evidence = rate_candidates[:3]
    if evidence:
        common_tags = Counter(tag for n in evidence for tag in n["tags"])
        tag = common_tags.most_common(1)[0][0] if common_tags else "高收藏内容"
        hypotheses.append({
            "id": f"H{len(hypotheses) + 1}",
            "statement": f"“{tag}”相关内容可能更能驱动收藏，而不只是获得浏览。",
            "confidence": "medium" if len(evidence) >= 2 else "low",
            "evidence": [_evidence(n) for n in evidence],
            "test": "加入一个可保存的清单、步骤或判断框架，观察藏阅比是否高于账号中位数。",
        })

    fallbacks = [
        ("当前样本不足以确认稳定题材，先测试重复题材能否复现。", "连续两次使用同一题材结构。"),
        ("评论样本不足以确认争议驱动因素。", "在结尾加入一个具体、可反驳的问题。"),
        ("现有数据不能区分选题与表达结构的贡献。", "固定选题，只改变开头和论证顺序。"),
    ]
    while len(hypotheses) < 3:
        statement, test = fallbacks[len(hypotheses)]
        hypotheses.append({"id": f"H{len(hypotheses) + 1}", "statement": statement, "confidence": "low", "evidence": [], "test": test})
    for index, hypothesis in enumerate(hypotheses[:3], 1):
        hypothesis["id"] = f"H{index}"
        if len(hypothesis["evidence"]) < 2:
            hypothesis["confidence"] = "low"
    return hypotheses[:3]


def _engagement_drivers(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drivers: list[dict[str, Any]] = []
    for metric, label in (("collects_rate", "收藏"), ("comments_rate", "评论")):
        ranked = sorted(
            (note for note in notes if note[metric] is not None),
            key=lambda note: note[metric],
            reverse=True,
        )[:3]
        series = Counter(note["series"] for note in ranked).most_common(1)
        hook = Counter(note["hook_style"] for note in ranked).most_common(1)
        drivers.append({
            "metric": metric,
            "label": label,
            "confidence": "medium" if len(ranked) >= 2 else "low",
            "observed_pattern": (
                f"高{label}样本中最常见题材为“{series[0][0]}”，最常见开头为“{hook[0][0]}”。"
                if ranked else f"没有可用的{label}率数据。"
            ),
            "evidence": [_evidence(note) for note in ranked],
        })
    return drivers


def build_audit(
    payload: Any,
    *,
    account_name: str = "未命名账号",
    platform: str = "xiaohongshu",
    generated_at: str | None = None,
) -> dict[str, Any]:
    notes, meta = normalize_notes(payload)
    if not notes:
        raise ValueError("没有可分析的笔记")
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    metrics = {name: _summary([n[name] for n in notes if n[name] is not None]) for name in METRIC_ALIASES}
    rates = {name: _summary([n[f"{name}_rate"] for n in notes if n[f"{name}_rate"] is not None]) for name in ("likes", "collects", "comments", "shares", "followers")}
    with_views = [n for n in notes if (n["views"] or 0) > 0]
    ranked = sorted(with_views, key=lambda n: n["views"], reverse=True)
    baseline = float(metrics["views"]["median"] or 0)
    missing = {name: sum(1 for n in notes if n[name] is None) for name in METRIC_ALIASES}
    comments_covered = sum(1 for n in notes if n["comment_texts"])
    partial_fetch_failures = sum(1 for n in notes if n["fetch_warning"])
    limitations = []
    if len(notes) < 20:
        limitations.append("样本少于 20 篇；规律只能作为待验证假设。")
    if len(notes) > 50:
        limitations.append("输入超过 50 篇；报告仍使用全部样本，但商业版建议固定最近 20–50 篇。")
    if comments_covered < max(1, len(notes) // 3):
        limitations.append("评论覆盖不足三分之一；受众画像偏低置信。")
    if not with_views:
        limitations.append("没有正数浏览/曝光数据；无法比较流量表现。")
    if partial_fetch_failures:
        limitations.append(f"{partial_fetch_failures} 篇公开页或评论补全失败；已保留创作者中心主指标并降级分析。")
    resolved_name = account_name
    if not resolved_name or resolved_name == "未命名账号":
        resolved_name = str(meta.get("account_name") or "未命名账号")
    top_notes = ranked[:5]
    top_ids = {note["note_id"] for note in top_notes}
    bottom_notes = [note for note in reversed(ranked) if note["note_id"] not in top_ids][:5]
    audit = {
        "audit_version": "1.0",
        "source_classification": "reconstructed",
        "calibration_samples_increment": 0,
        "generated_at": generated_at,
        "account": {"name": resolved_name, "platform": platform, "source_meta": meta},
        "data_quality": {
            "sample_size": len(notes),
            "positive_view_samples": len(with_views),
            "comments_covered_notes": comments_covered,
            "partial_fetch_failures": partial_fetch_failures,
            "missing_metrics": missing,
            "limitations": limitations,
        },
        "baselines": {"metrics": metrics, "rates": rates},
        "top_content": [_evidence(n) | {"hook": n["hook"], "hook_style": n["hook_style"], "series": n["series"]} for n in top_notes],
        "bottom_content": [_evidence(n) | {"hook": n["hook"], "hook_style": n["hook_style"], "series": n["series"]} for n in bottom_notes],
        "topic_clusters": _group_pattern(notes, "series"),
        "hook_patterns": _group_pattern(notes, "hook_style"),
        "structure_patterns": _group_pattern(notes, "structure"),
        "engagement_drivers": _engagement_drivers(notes),
        "audience_signals": _audience(notes),
        "hypotheses": _hypotheses(notes, baseline),
        "disclaimer": "这是决策校准，不是爆款保证；历史分析不得伪装成盲预测。",
    }
    audit["experiments"] = [
        {"week": i, "stable": "保持当前表现最稳的题材与发布节奏。", "experiment": h["test"], "success_metric": "与账号浏览中位数及对应互动率中位数比较，不用单篇绝对爆款定输赢。"}
        for i, h in enumerate(audit["hypotheses"], 1)
    ]
    audit["experiments"].append({"week": 4, "stable": "复用前三周表现最稳的组合。", "experiment": "复盘三次实验，保留被数据支持的观察，删除被推翻的观察。", "success_metric": "至少形成一条有两篇以上证据支持、可进入后续 bump 候选的观察。"})
    return audit


def _fmt(value: Any, percent: bool = False) -> str:
    if value is None:
        return "—"
    if percent:
        return f"{float(value) * 100:.2f}%"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}"
    return f"{int(value):,}"


def _safe(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(audit: dict[str, Any]) -> str:
    q = audit["data_quality"]
    metrics = audit["baselines"]["metrics"]
    rates = audit["baselines"]["rates"]
    lines = [
        f"# {_safe(audit['account']['name'])}｜账号体检报告",
        "",
        f"- 平台：{audit['account']['platform']}",
        f"- 样本：{q['sample_size']} 篇（有正数曝光 {q['positive_view_samples']} 篇）",
        f"- 数据性质：`{audit['source_classification']}`；不会增加 calibration_samples",
        f"- 生成时间：{audit['generated_at']}",
        "",
        f"> {audit['disclaimer']}",
        "",
        "## 数据完整度和局限",
        "",
        f"- 有评论样本：{q['comments_covered_notes']} / {q['sample_size']}",
        f"- 缺失字段：{', '.join(f'{k}={v}' for k, v in q['missing_metrics'].items() if v) or '无'}",
    ]
    lines.extend(f"- ⚠️ {item}" for item in q["limitations"])
    lines.extend([
        "",
        "## 账号基线",
        "",
        "| 指标 | 均值 | 中位数 | P25 | P75 |",
        "|---|---:|---:|---:|---:|",
    ])
    for name in ("views", "likes", "collects", "comments", "shares", "followers"):
        row = metrics[name]
        lines.append(f"| {name} | {_fmt(row['mean'])} | {_fmt(row['median'])} | {_fmt(row['p25'])} | {_fmt(row['p75'])} |")
    lines.extend(["", "互动率中位数：" + "；".join(f"{k} {_fmt(v['median'], True)}" for k, v in rates.items()), ""])

    for heading, key in (("表现最高的内容", "top_content"), ("表现最低的内容", "bottom_content")):
        lines.extend([f"## {heading}", "", "| 内容 | 浏览 | 藏阅比 | 评阅比 | 开头类型 |", "|---|---:|---:|---:|---|"])
        for row in audit[key]:
            title = f"[{_safe(row['title'])}]({row['url']}) (`{row['note_id']}`)"
            lines.append(f"| {title} | {_fmt(row['views'])} | {_fmt(row['collect_rate'], True)} | {_fmt(row['comment_rate'], True)} | {_safe(row['hook_style'])} |")
        lines.append("")

    lines.extend(["## 选题与开头模式", "", "### 选题聚类", "", "| 聚类 | 样本 | 中位浏览 | 证据 ID |", "|---|---:|---:|---|"])
    for row in audit["topic_clusters"][:10]:
        lines.append(f"| {_safe(row['name'])} | {row['sample_size']} | {_fmt(row['median_views'])} | {', '.join(row['evidence_note_ids'])} |")
    lines.extend(["", "### 开头结构", "", "| 类型 | 样本 | 中位浏览 | 证据 ID |", "|---|---:|---:|---|"])
    for row in audit["hook_patterns"]:
        lines.append(f"| {_safe(row['name'])} | {row['sample_size']} | {_fmt(row['median_views'])} | {', '.join(row['evidence_note_ids'])} |")

    lines.extend(["", "### 表达结构", "", "| 结构 | 样本 | 中位浏览 | 证据 ID |", "|---|---:|---:|---|"])
    for row in audit["structure_patterns"]:
        lines.append(f"| {_safe(row['name'])} | {row['sample_size']} | {_fmt(row['median_views'])} | {', '.join(row['evidence_note_ids'])} |")

    lines.extend(["", "## 收藏与评论驱动信号", ""])
    for driver in audit["engagement_drivers"]:
        evidence = "、".join(f"[{e['note_id']}]({e['url']})" for e in driver["evidence"]) or "无"
        lines.append(f"- {driver['label']}（{driver['confidence']}）：{driver['observed_pattern']} 证据：{evidence}")

    audience = audit["audience_signals"]
    lines.extend(["", "## 受众信号与反画像", "", f"共分析 {audience['comment_count']} 条可用评论。"])
    if audience["signals"]:
        for name, value in audience["signals"].items():
            examples = "；".join(f"{x['note_id']}: {x['text']}" for x in value["examples"])
            lines.append(f"- {name}：{value['count']} 条。证据：{examples}")
    else:
        lines.append("- 评论证据不足，暂不构造受众画像。")
    if audience["anti_persona"]:
        lines.append("- 反画像：不要假设所有观众都赞同；反驳样本见上方 disagreement 证据。")

    lines.extend(["", "## 三个增长假设", ""])
    for h in audit["hypotheses"]:
        evidence = "、".join(f"[{e['note_id']}]({e['url']})" for e in h["evidence"]) or "无足够证据"
        lines.extend([f"### {h['id']}｜{h['statement']}", "", f"- 置信度：`{h['confidence']}`", f"- 证据：{evidence}", f"- 验证：{h['test']}", ""])
    lines.extend(["## 四周实验计划", "", "详见 `four-week-experiments.md`。", ""])
    return "\n".join(lines)


def render_experiments(audit: dict[str, Any]) -> str:
    lines = [
        "# 四周内容实验计划",
        "",
        "> 每周只改一个主要变量。稳定项用于控制变量，实验项用于证伪假设。",
        "",
        "| 周 | 稳定项 | 实验项 | 成功标准 |",
        "|---:|---|---|---|",
    ]
    for item in audit["experiments"]:
        lines.append(f"| {item['week']} | {_safe(item['stable'])} | {_safe(item['experiment'])} | {_safe(item['success_metric'])} |")
    lines.extend(["", "> 历史账号体检属于 reconstructed 分析；每篇新稿仍须在看到实绩前单独写盲预测。", ""])
    return "\n".join(lines)


def write_audit(audit: dict[str, Any], output_dir: Path | str) -> dict[str, Path]:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / "account-audit.json",
        "markdown": out / "account-audit.md",
        "experiments": out / "four-week-experiments.md",
    }
    paths["json"].write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["markdown"].write_text(render_markdown(audit), encoding="utf-8")
    paths["experiments"].write_text(render_experiments(audit), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 cheat-on-content 账号体检")
    parser.add_argument("--input", required=True, type=Path, help="xhs-explore 导出的 JSON")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--account-name", default="未命名账号")
    parser.add_argument("--platform", default="xiaohongshu")
    parser.add_argument("--as-of", help="固定 generated_at，便于可重复生成")
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    audit = build_audit(payload, account_name=args.account_name, platform=args.platform, generated_at=args.as_of)
    paths = write_audit(audit, args.output_dir)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
