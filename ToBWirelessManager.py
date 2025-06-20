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

import qdarkstyle
from PyQt6.QtCore import Qt, QPropertyAnimation, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from qgis._core import QgsApplication

from main_window import MainWindow

#QgsApplication.setPrefixPath('qgis', True)

'''
打包流程：
1.使用OSGeo4W Shell
2.打包命令： "C:/OSGeo4W/bin/python-qgis-qt6.bat" -m PyInstaller ToBWirelessManager.spec
3.将工程根目录下的data和resources文件夹复制到根目录下，删除data中的秘钥
4.将工程根目录下的qgis文件夹复制到根目录下，将其中的proj文件夹单独剪切到_internal/qgis下

'''
class SplashScreen(QWidget):
    def __init__(self, image_path):
        super().__init__()
        # 设置窗口无边框
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.SplashScreen |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # 设置窗口大小
        self.setFixedSize(750, 105)
        # 加载图片
        pixmap = QPixmap(image_path)
        # 等比例缩放图片
        scaled_pixmap = pixmap.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        # 创建标签用于显示图片
        label = QLabel(self)
        label.setPixmap(scaled_pixmap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

        # 屏幕居中
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)

        # 显示窗口
        self.show()

    def fade_out(self):
        # 创建透明度动画
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000)  # 动画时长 1 秒
        self.animation.setStartValue(1.0)  # 初始透明度为 1
        self.animation.setEndValue(0.0)  # 最终透明度为 0
        self.animation.finished.connect(self.close)  # 动画结束后关闭窗口
        self.animation.start()

QgsApplication.setPrefixPath('qgis', True)





app = QgsApplication([], True)
app.initQgis()
splash = SplashScreen("resources/logo/workshop_logo.png")
mainWindow = MainWindow()
def close_splash_and_show_main():
    splash.fade_out()
    mainWindow.post_init_no_pyqt_widget()
    mainWindow.show()
    mainWindow.load_init_layer()
    mainWindow.init_project_tree_widget()


QTimer.singleShot(1000, close_splash_and_show_main)

app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
app.setWindowIcon(QIcon("resources/logo/LOGO.png"))
app.exec()
app.exitQgis()