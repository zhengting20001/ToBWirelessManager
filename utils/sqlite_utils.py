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

import sqlite3


class SqliteUtils:

    # 查询数据库取得项目、基站、小区数据，返回格式为数组嵌套
    # 项目list[项目，套餐级别，p（不显示，用于区分级别），基站列表list]
    # 基站列表list[基站名，区域，基站号（不显示，用于搜索），小区列表list]
    # 小区列表list[CGI,频段，c（不显示，用于区分级别）]

    @staticmethod
    def get_project_tree_inner_text(conn):
        """
        查询数据库取得项目、基站、小区数据，返回格式为数组嵌套
        :param conn:数据库连接
        :type conn:Connection
        :return:项目、基站、小区数据，返回格式为数组嵌套
        :rtype:项目list[项目，套餐级别，p（不显示，用于区分级别），基站列表list]
               基站列表list[基站名，区域，基站号（不显示，用于搜索），小区列表list]
               小区列表list[CGI,频段，c（不显示，用于区分级别）]
        """
        # # 打开SQLite数据库文件
        # conn = sqlite3.connect("data/toBDatabase.db")
        cursor = conn.cursor()
        # 查询数据
        cursor.execute("SELECT 项目名称,套餐级别,项目场景 FROM 项目明细")
        rows_project = cursor.fetchall()
        list_project = []
        for row_project in rows_project:
            cursor.execute(f"SELECT 基站号,基站名,行政区 FROM 基站明细 WHERE 项目名称='{row_project[0]}'")
            rows_gnb = cursor.fetchall()
            list_gnb = []
            for row_gnb in rows_gnb:
                cursor.execute(f"SELECT CGI,频段 FROM 小区明细 WHERE 基站号='{row_gnb[0]}'")
                rows_cell = cursor.fetchall()
                list_cell=[]
                for row_cell in rows_cell:
                    list_cell.append([row_cell[0],row_cell[1],'c'])
                list_gnb.append([row_gnb[1], row_gnb[2],str(row_gnb[0]),list_cell])
            list_project.append([row_project[0],row_project[1],row_project[2],list_gnb])
        return list_project

    def get_project_list(self,conn):
        cursor = conn.cursor()
        cursor.execute("SELECT 项目名称 FROM 项目明细")
        results = cursor.fetchall()
        project_list = []
        if not results:
            return None
        for result in results:
            project_list.append(result[0])
        return project_list

    def get_detail_table(self, conn, level, vlookup_field):
        cursor = conn.cursor()
        detail_title_and_data_return = []
        if level == 0:
            cursor.execute(f"SELECT * FROM 项目明细 WHERE 项目名称 = '{vlookup_field}' LIMIT 1")
            result = cursor.fetchall()
            if not result:
                return None
            detail_data = result[0]
        elif level == 1:
            cursor.execute(f"SELECT * FROM 基站明细 WHERE 基站号 = '{vlookup_field}' LIMIT 1")
            result = cursor.fetchall()
            if not result:
                return None
            detail_data = result[0]
        else:
            cursor.execute(f"SELECT * FROM 小区明细 WHERE CGI = '{vlookup_field}' LIMIT 1")
            result = cursor.fetchall()
            if not result:
                return None
            detail_data = result[0]
        for index, description in enumerate(cursor.description):
            if description[0] != '序号':
                detail_title_and_data_return.append([description[0], str(detail_data[index])])
        return detail_title_and_data_return

    # 从数据库获取项目明细表的全部内容并反馈，包括wkt，用于项目图层制作
    @staticmethod
    def get_project_full_data_include_wkt(conn,project_name=''):
        """
        从数据库获取项目明细表的全部内容并反馈，包括wkt，用于项目图层制作
        :param conn: 数据库连接
        :type conn: Connection
        :return: data_dict_list_return，一个列表，里面每个项目是一个dict，且wkt已被小写
        :rtype: list
        """
        cursor = conn.cursor()
        data_dict_list_return = []
        if project_name:
            cursor.execute(f"SELECT * FROM 项目明细 WHERE 项目名称='{project_name}'")
        else:
            cursor.execute(f"SELECT * FROM 项目明细")
        results = cursor.fetchall()
        if not results:
            return None
        for result in results:
            single_project_dict = {}
            for index, description in enumerate(cursor.description):
                if description[0] != '序号':
                    if str(description[0]).lower() == 'wkt':
                        single_project_dict['wkt'] = str(result[index])
                    else:
                        single_project_dict[description[0]]= result[index]
            data_dict_list_return.append(single_project_dict)
        return data_dict_list_return

    @staticmethod
    def get_project_cgi_list(conn, project_name):
        """
        获取一个项目的小区号（CGI）列表
        :param conn: 数据库连接
        :type conn: Connection
        :param project_name: 项目名称
        :type project_name: str
        :return: 小区号（CGI）列表
        :rtype: list[str]
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT CGI FROM 小区明细 WHERE 项目名称='{project_name}'")
        results = cursor.fetchall()
        cgi_return = []
        for result in results:
            cgi_return.append(result[0])
        return cgi_return

    @staticmethod
    def get_project_cell_detail(conn, project_name):
        """
        获取一个项目的小区详细信息
        :param conn: 数据库连接
        :type conn: Connection
        :param project_name: 项目名称
        :type project_name: str
        :return: 小区详细信息
        :rtype: list[dict]
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT CGI,基站号,小区名,站型,行政区,无线厂家,频段,带宽 FROM 小区明细 WHERE 项目名称='{project_name}'")
        results = cursor.fetchall()
        cell_detail_return = []
        for result in results:
            cell_detail_return.append({'唯一标识':result[0], '基站号':result[1],'小区名':result[2],'站型':result[3],'行政区':result[4],'设备厂家':result[5],'频段':result[6],'带宽':result[7],})
        return cell_detail_return

    @staticmethod
    def get_cell_detail_by_cgi(conn, cgi_list):

        cursor = conn.cursor()
        cgi_sql_token = ', '.join(['?'] * len(cgi_list))
        cursor.execute(
            f"SELECT CGI,基站号,小区名,站型,行政区,无线厂家,频段,带宽 FROM 小区明细 WHERE CGI IN ({cgi_sql_token})",cgi_list)
        results = cursor.fetchall()
        cell_detail_return = []
        for result in results:
            cell_detail_return.append(
                {'唯一标识': result[0], '基站号': result[1], '小区名': result[2], '站型': result[3],
                 '行政区': result[4], '设备厂家': result[5], '频段': result[6], '带宽': result[7], })
        return cell_detail_return

    @staticmethod
    def get_gnb_cgi_list(conn, gnbid):
        """
        获取一个基站的小区号（CGI）列表
        :param conn: 数据库连接
        :type conn: Connection
        :param gnbid: 基站号
        :type gnbid: str/int
        :return: 小区号（CGI）列表
        :rtype: list[str]
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT CGI FROM 小区明细 WHERE 基站号='{gnbid}'")
        results = cursor.fetchall()
        cgi_return = []
        for result in results:
            cgi_return.append(result[0])
        return cgi_return

    @staticmethod
    def get_project_type(conn, project_name):
        """
        获取一个项目的场景类型，0为点，1为线，2为面，-1为搜索失败
        :param conn: 数据库连接
        :type conn: Connection
        :param project_name: 项目名称
        :type project_name: str
        :return: 场景类型，0为点，1为线，2为面，-1为搜索失败
        :rtype: int
        """
        cursor = conn.cursor()
        cursor.execute(f"SELECT 项目场景 FROM 项目明细 WHERE 项目名称='{project_name}'")
        results = cursor.fetchall()
        if results:
            if results[0][0] == '园区':
                return 2
            elif results[0][0] == '线路':
                return 1
            else:
                return 0
        else:
            return -1


if __name__ == '__main__':
    su = SqliteUtils()
    conn = sqlite3.connect('../data/toBDatabase.db')
