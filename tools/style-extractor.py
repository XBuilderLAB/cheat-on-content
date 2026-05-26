#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style-extractor.py — Router/Proxy script routing execution to '文案风格指纹提取器_v1.0.py'
to comply with coding style and project tool architecture.
"""

import sys
import subprocess
from pathlib import Path

def main():
  # 获取当前文件的同级目录下的真实提取器脚本路径
  current_dir = Path(__file__).resolve().parent
  real_script = current_dir / "文案风格指纹提取器_v1.0.py"
  
  if not real_script.is_file():
    print(f"ERROR: 真实执行脚本未找到: {real_script}", file=sys.stderr)
    sys.exit(1)
    
  # 将当前脚本接收的所有参数平移转发给真实提取器
  cmd = [sys.executable, str(real_script)] + sys.argv[1:]
  
  result = subprocess.run(cmd)
  sys.exit(result.returncode)

if __name__ == "__main__":
  main()
