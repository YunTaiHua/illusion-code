"""
输出样式模块导出
============

本模块导出 output_styles 子目录中的公共接口。

导出内容：
    - OutputStyle: 输出样式数据类
    - get_output_styles_dir: 获取自定义输出样式目录
    - load_output_styles: 加载输出样式
"""

from illusion.output_styles.loader import OutputStyle, get_output_styles_dir, load_output_styles

__all__ = ["OutputStyle", "get_output_styles_dir", "load_output_styles"]