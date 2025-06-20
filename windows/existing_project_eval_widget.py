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

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget

from ui.existing_project_eval_widget_qt_designer import Ui_Form


class ExistingProjectEvalDialog(QWidget,Ui_Form):
    selection_made = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.Window)

    def push_putton_ok_clicked(self):
        selected_text = self.comboBoxProjectName.currentText()
        self.selection_made.emit(selected_text)  # 发送信号
        self.close()  # 关闭窗口