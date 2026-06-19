#!/usr/bin/env python3
"""
火星基地多材料隔热墙优化竞赛 - 热设计工作室
启动脚本
"""

import sys
import os
import subprocess

def check_dependencies():
    """检查依赖项"""
    required_packages = ['numpy', 'matplotlib', 'tkinter']
    missing_packages = []

    for package in required_packages:
        try:
            if package == 'tkinter':
                import tkinter
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        print(f"缺少必要的Python包: {', '.join(missing_packages)}")
        print("请运行: pip install numpy matplotlib")
        return False

    return True

def main():
    """主函数"""
    print("火星基地多材料隔热墙优化竞赛 - 热设计工作室")
    print("=" * 50)

    if not check_dependencies():
        sys.exit(1)

    try:
        # 导入并运行主程序
        from thermal_design_studio import main as studio_main
        studio_main()
    except ImportError as e:
        print(f"导入模块失败: {e}")
        print("请确保 thermal_design_studio.py 文件在当前目录中")
        sys.exit(1)
    except Exception as e:
        print(f"程序运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()