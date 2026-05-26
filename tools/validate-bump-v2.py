#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate-bump-v2.py — Router/Proxy script forwarding invocation parameters
to '评估公式升级校验器_v2.0.py'.
"""

import sys
import subprocess
from pathlib import Path

def main():
  current_dir = Path(__file__).resolve().parent
  real_script = current_dir / "评估公式升级校验器_v2.0.py"
  
  if not real_script.is_file():
    print(f"ERROR: 升级校验器核心文件未找到: {real_script}", file=sys.stderr)
    sys.exit(1)
    
  # 参数平移转发
  cmd = [sys.executable, str(real_script)] + sys.argv[1:]
  
  result = subprocess.run(cmd)
  sys.exit(result.returncode)

if __name__ == "__main__":
  main()
