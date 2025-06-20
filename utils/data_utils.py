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

import re

from qgis._core import QgsGeometry, QgsMultiPoint, QgsPoint


class DataUtils:
    # 从CGI中删除前面的PLMN
    @staticmethod
    def cgi_remove_plmn(cgi):
        """
        从CGI中删除前面的PLMN
        :param cgi: CGI
        :type cgi: str
        :return: 小区号
        :rtype: str
        """

        pattern = r'\d{3}-\d{2}-(\d{1,8}-\d{1,3})'

        # 执行正则表达式匹配
        match = re.search(pattern, cgi)

        # 提取并输出结果
        if match:
            result = match.group(1)
            return result  # 输出：1234567-123
        else:
            return None

    # 从一组CGI中删除前面的PLMN，仅返回删除后的list
    def cgi_list_remove_plmn_return_list(self, cgi_list):
        """
        从一组CGI中删除前面的PLMN，仅返回删除后的list
        :param cgi_list: 一组CGI
        :type cgi_list: list[str]
        :return: list[小区号]
        :rtype: list[str]
        """
        cgi_list_return = []
        for cgi in cgi_list:
            cgi_list_return.append(self.cgi_remove_plmn(cgi))
        return cgi_list_return

    # 从一组CGI中删除前面的PLMN，返回一对关系的list
    def cgi_list_remove_plmn_return_pair(self, cgi_list):
        """
        从一组CGI中删除前面的PLMN，返回一对关系的list
        :param cgi_list: 一组CGI
        :type cgi_list: list[str]
        :return: 一组[cgi,小区号]
        :rtype: list[str,str]
        """
        cgi_list_return = []
        for cgi in cgi_list:
            cgi_list_return.append([cgi,self.cgi_remove_plmn(cgi)])
        return cgi_list_return

    # 判断CGI是否为广电小区
    @staticmethod
    def cgi_is_cbn(cgi):
        """
        判断CGI是否为广电小区
        :param cgi: CGI
        :type cgi: str
        :return: 是/否
        :rtype: bool
        """
        pattern = r'^(\d{3})-(\d{2})-(\d{1,8})-(\d{1,3})$'
        match = re.match(pattern, cgi)
        if match:
            if 699 < int(match.group(4)) < 800:
                return True
            if int(match.group(2)) == 15:
                return True
            return False
        else:
            return False

    # 判断CGI是否为广电小区
    @staticmethod
    def cgi_replace_plmn_to_46000(cgi):
        """
        将cgi的plmn部分替换为46000
        :param cgi: CGI
        :type cgi: str
        :return: CGI
        :rtype: str
        """
        pattern = r'^(\d{3})-(\d{2})-(\d{1,8}-\d{1,3})$'
        match = re.match(pattern, cgi)
        if match:
            return f'{match.group(1)}-00-{match.group(3)}'
        else:
            return cgi

    # 对于给定的包含wkt的List（从sql中直接导出的），判断wkt是否合法，将单转化为多，然后对3类图层各返回一个wktlist
    @staticmethod
    def wkt_sort_processor(wkt_dict_list):
        """
        对于给定的包含wkt的List（从sql中直接导出的），判断wkt是否合法，将单转化为多，然后对3类图层各返回一个wktlist
        :param wkt_dict_list: sql导出的包含wkt的List
        :type wkt_dict_list: list
        :return: wkt_dict_list_point,wkt_dict_list_line,wkt_dict_list_polygon
        :rtype:list[3]
        """
        wkt_dict_list_point = []
        wkt_dict_list_line = []
        wkt_dict_list_polygon = []
        for wkt_dict in wkt_dict_list:
            geometry = QgsGeometry.fromWkt(wkt_dict['wkt'])
            if geometry.isEmpty() or not geometry.isGeosValid():
                # print(f'无效的WKT格式或几何形状{wkt_dict['项目名称']}')
                # self.log_text_field_update(f'项目[{wkt_dict['项目名称']}]无法生成有效的WKT几何形状', 3)
                continue
            geom_type = geometry.wkbType()
            if geom_type == 1:  # 点
                point_temp = geometry.asPoint()
                multi_point = QgsMultiPoint()
                multi_point.addGeometry(QgsPoint(point_temp.x(), point_temp.y()))
                wkt_dict['wkt'] = multi_point.asWkt()
                wkt_dict_list_point.append(wkt_dict)
            elif geom_type == 2:  # 线
                wkt_dict['wkt'] = wkt_dict['wkt'].replace("LINESTRING(", "MULTILINESTRING((").replace(")", "))")
                wkt_dict_list_line.append(wkt_dict)
            elif geom_type == 3:  # 面
                wkt_dict['wkt'] = wkt_dict['wkt'].replace("POLYGON(", "MULTIPOLYGON((").replace(")", "))")
                wkt_dict_list_polygon.append(wkt_dict)
            elif geom_type == 4:  # 多点
                wkt_dict_list_point.append(wkt_dict)
            elif geom_type == 5:  # 多线
                wkt_dict_list_line.append(wkt_dict)
            elif geom_type == 6:  # 多面
                wkt_dict_list_polygon.append(wkt_dict)
            else:
                continue
        return wkt_dict_list_point, wkt_dict_list_line, wkt_dict_list_polygon
