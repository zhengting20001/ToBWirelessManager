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

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget
from cryptography.fernet import Fernet

from ui.tianditu_apikey_management_widget_qt_designer import Ui_Form


class TiandituApikeyManagementDialog(QWidget,Ui_Form):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.Window)

    def pushButtonUpdateKeyClicked(self):
        api_key = self.lineEditKey.text()
        secret_key_file_path = "data/tianditu_secret.key"
        # 判断文件是否存在
        if not os.path.exists(secret_key_file_path):
            key = Fernet.generate_key()
            with open('data/tianditu_secret.key', 'wb') as key_file:
                key_file.write(key)
        try:
            with open('data/tianditu_secret.key', 'rb') as key_file:
                key = key_file.read()
                cipher_suite = Fernet(key)
                encrypted_api_key = cipher_suite.encrypt(api_key.encode('utf-8'))
                with open('data/tianditu_api.ini', 'wb') as config_file:
                    config_file.write(encrypted_api_key)
                print(api_key)
        except FileNotFoundError:
            print("错误：未找到加密密钥文件!")
            exit(1)
        except Exception as e:
            print(f"错误：读取密钥文件时出错: {e}")
            exit(1)

        self.close()  # 关闭窗口
        python = sys.executable
        script = sys.argv[0]

        # 重启应用
        os.execl(python, python, script)