#!/bin/bash
# 自动激活虚拟环境并启动桌面端编辑器
cd "$(dirname "$0")"
source venv/bin/activate
python main.py 