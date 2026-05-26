#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
douyin-fetcher.py — Router/Proxy script forwarding invocation parameters
to '抖音视频解析器_v1.0.py'.
"""

import sys
import subprocess
from pathlib import Path

def main():
  current_dir = Path(__file__).resolve().parent
  real_script = current_dir / "抖音视频解析器_v1.0.py"
  
  if not real_script.is_file():
    print(f"ERROR: 抖音解析核心执行脚本未找到: {real_script}", file=sys.stderr)
    sys.exit(1)
    
  # 将当前脚本接收的所有参数转发给真实提取器
  cmd = [sys.executable, str(real_script)] + sys.argv[1:]
  
  result = subprocess.run(cmd)
  sys.exit(result.returncode)

if __name__ == "__main__":
  main()
