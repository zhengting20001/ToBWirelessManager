"""
 @file
 @brief
 @author T.Ding <zhengting20001@126.com>

 @section LICENSE

 Copyright (c) 2025 T.Ding

 ToB Wireless Manager is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 ToB Wireless Manager is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with ToB Wireless Manager.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import sys

# base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
# 设置PROJ_LIB为根目录下的lib文件夹

qt_bin_path = os.path.join(sys._MEIPASS, 'qgis')
os.environ['PATH'] = qt_bin_path + os.pathsep + os.environ['PATH']
os.environ['PROJ_LIB'] = os.path.join(qt_bin_path, 'proj')
# os.environ['PROJ_LIB'] = os.path.dirname(sys.argv[0])

# 打印调试信息（打包后运行时会显示）
print(f"[Hook] PyQt6路径已添加: {qt_bin_path}")

# 验证_core模块是否存在
if qt_bin_path and os.path.exists(os.path.join(qt_bin_path, "_core.pyd")):
    print(f"[Hook] 找到_core模块: {os.path.join(qt_bin_path, '_core.pyd')}")
else:
    print(f"[Hook] 未找到_core模块!")
    # 尝试其他可能的位置
    alt_location = os.path.join(sys._MEIPASS, "_core.pyd")
    if os.path.exists(alt_location):
        print(f"[Hook] 但在 {alt_location} 找到")