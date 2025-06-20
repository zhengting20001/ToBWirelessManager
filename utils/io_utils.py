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
import re

from cryptography.fernet import Fernet


class IOUtils:
    # 用于搜索工参文件夹中最新的一个工参
    @staticmethod
    def find_latest_para_file(prefix):
        """
        用于搜索工参文件夹中最新的一个工参
        :param prefix: 前缀，例如‘宏站扇区图层’
        :type prefix: str
        :return:最新日期的文件对应路径
        :rtype:str
        """
        find_dir = 'resources/layer'  # Linux/macOS 根目录，Windows 需改为 'C:\\' 等
        pattern = r'^' + prefix + r'(\d{8})_(\d{0,4}).shp$'
        max_number = -1
        latest_file = None
        latest_date = None
        try:
            for entry in os.scandir(find_dir):
                if entry.is_file():
                    match = re.match(pattern, entry.name)
                    if match:
                        latest_date = match.group(1)
                        file_number = int(match.group(1)) * 10000 + int(match.group(2))
                        if file_number > max_number:
                            max_number = file_number
                            latest_file = entry.path
        except PermissionError:
            print(f"权限不足，无法访问 {find_dir}")
            return ''

        return latest_file, latest_date

    @staticmethod
    def docxtpl_docx_output_handler(docxtpl_instance, docx_template_render_context,output_path,output_filename):
        try:
            # 渲染模板
            docxtpl_instance.render(docx_template_render_context)

            # 保存结果
            docxtpl_instance.save(f"{output_path}{output_filename}.docx")

            return ''


        except Exception as e:
            return f"处理过程中发生错误: {e}"

    def get_tianditu_api_key(self):
        try:
            with open('data/tianditu_secret.key', 'rb') as key_file:
                key = key_file.read()

            cipher_suite = Fernet(key)

            with open('data/tianditu_api.ini', 'rb') as config_file:
                encrypted_api_key = config_file.read()

            return cipher_suite.decrypt(encrypted_api_key).decode()
        except Exception as e:
            return None
