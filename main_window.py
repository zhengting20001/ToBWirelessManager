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

import datetime
import sqlite3,re
from io import BytesIO

import docxtpl
import qdarkstyle
from PyQt6.QtCore import QMimeData, Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QAction, QTextCharFormat, QTextCursor, QIcon, QPixmap, QActionGroup
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox, QLabel, QComboBox, QTreeWidgetItem, \
    QTableWidgetItem, QHeaderView, QToolTip, QTableWidget, QMenu, QToolButton
from docx.shared import Mm
from docxtpl import DocxTemplate
from qgis.PyQt.QtWidgets import QMainWindow
from qgis._core import QgsPointXY, QgsCoordinateTransform,\
    QgsSimpleFillSymbolLayer, \
    QgsFillSymbol, QgsSingleSymbolRenderer, QgsSimpleLineSymbolLayer, QgsLineSymbol, \
    QgsRendererCategory, QgsCategorizedSymbolRenderer, \
    QgsSimpleMarkerSymbolLayer, QgsMarkerSymbol, QgsExpression, QgsFeatureRequest, \
    QgsMapLayer, QgsLayerTreeModel, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCoordinateReferenceSystem,QgsApplication,QgsMapSettings
from qgis._gui import QgsVertexMarker, QgsMapToolPan, QgsMapCanvas,QgsLayerTreeMapCanvasBridge

import os.path

from ui.main_frame_qt_designer import Ui_MainWindow
from ui.about_dialog_qt_designer import Ui_Dialog as UiDialogAbout
from utils.data_utils import DataUtils
from utils.io_utils import IOUtils
from utils.qgis_utils import CustomIdentifyTool, QGISCanvasUtils, CustomDistanceTool, CustomAzimuthMeasurementTool, \
    CustomPolygonMapTool
from utils.sqlite_utils import SqliteUtils
from windows.existing_project_eval_widget import ExistingProjectEvalDialog
from windows.tianditu_apikey_management_widget import TiandituApikeyManagementDialog

"""
正常开发计划
数据库文件加密，是否可以后期与图层文件整合，变成可以直接拖入窗口进行项目更新
图层可拖动更换顺序
天地图多种类型地图一键转换
可以在mapcanvas右上角增加频段和制式选择

后续计划完善的内容
1.tianditu_token需要加密，用其他方式存储于某个文件中，并支持替换
2.ico和各项资源，如何通过路径方法引用（目前因为ui文件位于单独文件夹内，引用后相对路径变化导致ico无法显示）
完善树形图层结构和canvas的关系，如何拖动图层顺序

存在的bug
1.在init过程中打开的图层无法使用mapCanvas.setExtent指定显示范围，目前采用了1秒钟的timer延迟实现，需要确认各电脑是否兼容，是否可以用欢迎屏幕进一步增加时长并稳定效果
"""
database_path = 'data/toBDatabase.db'

PROJECT = QgsProject.instance()
transformer_4326_to_3857 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                                  QgsCoordinateReferenceSystem("EPSG:3857"), PROJECT)
transformer_3857_to_4326 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:3857"),
                                                  QgsCoordinateReferenceSystem("EPSG:4326"), PROJECT)

class MainWindow(QMainWindow, Ui_MainWindow):

    # 整体窗体启动函数，建立主画布和SQLite链接
    def __init__(self):
        """
        整体初始化方法
        """
        super(MainWindow, self).__init__()
        self.setupUi(self)
        self.mapCanvas = QgsMapCanvas(self)
        # 画布并行渲染，防止黑屏
        self.mapCanvas.setParallelRenderingEnabled(True)
        self.conn = sqlite3.connect(database_path)
        self.statusMessageTimer = QTimer(self)
        self.statusMessageBlinkTimer = QTimer(self)
        #self.layerFlashTimer = QTimer(self)
        #self.bubbleExpandTimer = QTimer(self)
        #self.bubble_expand_finished_signal_connected = False
        self.sql_util = SqliteUtils()
        self.qgs_canvas_util = QGISCanvasUtils(self, PROJECT, self.conn)
        self.data_util = DataUtils()
        self.io_util = IOUtils()
        self.existing_project_eval_docx_save_path = '/'



    # MainWindow初始化完成后，对于使用QT Designer无法添加的组件，通过本方法添加，并进行绑定
    def post_init_no_pyqt_widget(self):
        """
        MainWindow初始化完成后，对于使用QT Designer无法添加的组件，通过本方法添加，并进行绑定
        :return: None
        """

        """
        主画布初始化
        """
        # 添加主画布
        self.mapFrameLayout.addWidget(self.mapCanvas)
        # 初始化主画布CRS为EPSG4326
        self.mapCanvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        self.log_text_field_update("当前坐标系为EPSG:3857",2)
        # 设置背景为黑色
        self.mapCanvas.setCanvasColor(Qt.GlobalColor.black)

        """
        左侧dockWidget初始化
        """
        # 图层
        # 开始进行图层Tree结构和主画布的绑定
        self.model = QgsLayerTreeModel(PROJECT.layerTreeRoot())
        self.model.setFlag(QgsLayerTreeModel.AllowNodeChangeVisibility)  # 允许改变图层节点可视性
        self.model.setFlag(QgsLayerTreeModel.AllowNodeReorder)
        self.model.setFlag(QgsLayerTreeModel.ShowLegend)
        self.layerTreeView.setModel(self.model)
        self.layerTreeView.setHeaderHidden(True)
        # 建立图层树与地图画布的桥接
        self.layerTreeBridge = QgsLayerTreeMapCanvasBridge(PROJECT.layerTreeRoot(), self.mapCanvas)

        # 调整左侧dockWidget比例
        self.resizeDocks([self.dockWidgetProjectTree, self.dockWidgetLayerTree, self.dockWidgetLog], [5, 2, 3], Qt.Orientation.Vertical)
        # 将图层和日志窗口整合
        self.tabifyDockWidget(self.dockWidgetLayerTree, self.dockWidgetLog)

        """
        右侧dockWidget初始化
        """
        pixmap = QPixmap("resources/logo/workshop_logo.png")
        scaled_pixmap = pixmap.scaled(
            250, 35,  # 目标尺寸
            Qt.AspectRatioMode.KeepAspectRatio,  # 保持宽高比
            Qt.TransformationMode.SmoothTransformation  # 平滑缩放（高质量）
        )
        self.labelWelcomeBanner.setPixmap(scaled_pixmap)
        self.dockWidgetDetail.setWindowTitle("欢迎")

        def hide_welcome():
            self.dockWidgetDetail.setWindowTitle("详细信息")
            self.labelWelcomeBanner.hide()
            self.labelWelcomeText.hide()
        QTimer.singleShot(5000, hide_welcome)

        # 详细信息
        self.tableWidgetDetailTable.setHorizontalHeaderLabels(["要素", "值"])
        self.tableWidgetDetailTable.verticalHeader().setVisible(False)
        self.tableWidgetDetailTable.horizontalHeader().setVisible(False)
        self.tableWidgetDetailTable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tableWidgetDetailTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tableWidgetDetailTable.setColumnWidth(0, 80)
        self.tableWidgetDetailTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        """
        下方dockWidget初始化
        """
        self.dockWidgetNewProjectEval.hide()

        """
        状态栏初始化
        """
        # 添加状态栏中的显示内容
        self.statusMessageBox = QLabel('')
        self.statusbar.addWidget(self.statusMessageBox, 1)
        self.statusXY = QLabel('{:<40}'.format(''))  # x y 坐标状态
        self.statusbar.addWidget(self.statusXY, 1)
        self.statusXY.setFixedWidth(200)
        self.statusScaleLabel = QLabel('比例尺')
        self.statusScaleComboBox = QComboBox(self)
        self.statusScaleComboBox.setFixedWidth(120)
        # self.statusScaleComboBox.addItems(
        #     ["1:500", "1:1000", "1:2500", "1:5000", "1:10000", "1:25000", "1:100000", "1:500000", "1:1000000"])
        self.statusScaleComboBox.setEditable(True)
        self.statusbar.addWidget(self.statusScaleLabel)
        self.statusbar.addWidget(self.statusScaleComboBox)
        self.statusCrsLabel = QLabel(
            f"坐标系: {self.mapCanvas.mapSettings().destinationCrs().description()}-"
            f"{self.mapCanvas.mapSettings().destinationCrs().authid()}")
        self.statusbar.addWidget(self.statusCrsLabel)
        # 对状态栏中显示的内容连接槽函数，进行实时更新
        self.mapCanvas.xyCoordinates.connect(self.statusbar_update_cord)
        self.mapCanvas.scaleChanged.connect(self.statusbar_show_scale)
        self.mapCanvas.destinationCrsChanged.connect(self.statusbar_show_crs)

        """
        菜单初始化
        """
        # 将显示菜单中的各组件关闭事件与菜单中的勾选情况建立信号连接
        self.dockWidgetDetail.visibilityChanged.connect(lambda visible: self.m2_view_detail.setChecked(visible))
        self.dockWidgetLog.visibilityChanged.connect(lambda visible: self.m2_view_log.setChecked(visible))
        self.dockWidgetLayerTree.visibilityChanged.connect(lambda visible: self.m2_view_layer_tree.setChecked(visible))
        self.dockWidgetGPSCord.visibilityChanged.connect(lambda visible: self.m2_view_gpscord.setChecked(visible))
        self.dockWidgetProjectTree.visibilityChanged.connect(lambda visible: self.m2_view_project_tree.setChecked(visible))

        self.m2_tool_pan.setIcon(QIcon("resources/svg/pan.svg"))
        self.m2_tool_info.setIcon(QIcon("resources/svg/info.svg"))
        self.m2_tool_distance.setIcon(QIcon("resources/svg/distance.svg"))
        self.m2_tool_azimuth.setIcon(QIcon("resources/svg/azimuth.svg"))
        self.m2_about.setIcon(QIcon("resources/svg/about.svg"))
        self.toolBarMapTool.setIconSize(QSize(20, 20))
        self.m2_open_layer.setIcon(QIcon("resources/svg/open_layer.svg"))
        self.m2_open_project.setIcon(QIcon("resources/svg/open_project.svg"))
        self.toolBarFile.setIconSize(QSize(20, 20))
        self.m2_new_project_eval.setIcon(QIcon("resources/svg/new_project_eval.svg"))
        self.m2_existing_project_eval.setIcon(QIcon("resources/svg/existing_project_eval.svg"))
        self.toolBarEval.setIconSize(QSize(20, 20))
        self.m2_tianditu_key_management.setIcon(QIcon("resources/svg/key_management.svg"))
        self.toolBarMap.setIconSize(QSize(20, 20))

        """
        工具初始化
        """
        # 增加action组，确保不会取消选择所有工具
        self.action_group_map_tools = QActionGroup(self)
        self.action_group_map_tools.setExclusive(True)
        # 添加手型工具
        self.toolPan = QgsMapToolPan(self.mapCanvas)
        self.toolPan.setAction(self.m2_tool_pan)
        self.m2_tool_pan_toggled(True)
        self.action_group_map_tools.addAction(self.m2_tool_pan)
        # 添加自定义信息获取工具
        self.toolInfo = CustomIdentifyTool(self, PROJECT)
        self.toolInfo.setAction(self.m2_tool_info)
        self.action_group_map_tools.addAction(self.m2_tool_info)
        # 添加自定义距离测量工具
        self.toolDistance = CustomDistanceTool(self, PROJECT)
        self.toolDistance.setAction(self.m2_tool_distance)
        self.action_group_map_tools.addAction(self.m2_tool_distance)
        # 添加自定义方位角测量工具
        self.toolAzimuth = CustomAzimuthMeasurementTool(self, PROJECT)
        self.toolAzimuth.setAction(self.m2_tool_azimuth)
        self.action_group_map_tools.addAction(self.m2_tool_azimuth)

        # 作为action组勾选变化信号的槽函数，确保不会取消选择所有工具
        def on_action_map_tools_triggered(action):
            # 记录最后一个被选中的动作
            if action.isChecked():
                self.last_checked_action = action
            # 如果所有动作都未被选中，恢复最后一个选中的动作
            elif not any(a.isChecked() for a in self.action_group_map_tools.actions()):
                if self.last_checked_action:
                    self.last_checked_action.setChecked(True)
        # 发射action组勾选变化信号
        self.action_group_map_tools.triggered.connect(on_action_map_tools_triggered)

        self.menubar_about_button = QToolButton()
        self.menubar_about_button.setIcon(QIcon("resources/svg/about.svg"))  # 替换为实际图标路径
        self.menubar_about_button.setToolTip("关于")
        self.menubar_about_button.clicked.connect(self.m2_about_triggered)
        self.menubar.setCornerWidget(self.menubar_about_button, Qt.Corner.TopRightCorner)

        """
        完成初始化
        """
        self.log_text_field_update("已完成主窗口初始化")

    # 加载默认图层，包括天地图底图
    def load_init_layer(self):
        """
        加载默认图层，包括天地图底图、行政区图层、基站扇区、tob项目图层
        :return: None
        """

        self.log_text_field_update("开始地理化信息加载流程，正在初始化数据库接口")

        tianditu_token = self.io_util.get_tianditu_api_key()
        if not tianditu_token:
            self.m2_tianditu_key_management_triggered()

        layer_to_add = QgsRasterLayer(
            f"crs=EPSG:3857&format&type=xyz&url=https://t4.tianditu.gov.cn/img_w/wmts?SERVICE%3DWMTS%26"
            f"REQUEST%3DGetTile%26VERSION%3D1.0.0%26LAYER%3Dimg%26STYLE%3Ddefault%26TILEMATRIXSET%3Dw%26"
            f"FORMAT%3Dtiles%26TileCol%3D%7Bx%7D%26TileRow%3D%7By%7D%26TileMatrix%3D%7Bz%7D%26tk%3D{tianditu_token}"
            f"&zmax=18&zmin=1&http-header:referer=https://www.tianditu.gov.cn/",
            # uri
            "卫星影像底图",
            "wms"
        )
        layer_to_add.setCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        PROJECT.addMapLayer(layer_to_add)

        # 加载行政区图层
        shp = r"resources\layer\行政区.shp"
        layer_to_add = QgsVectorLayer(shp, os.path.splitext(os.path.basename(shp))[0], "ogr")
        PROJECT.addMapLayer(layer_to_add)
        properties_fill = {
            "color": "130, 170, 75, 0",
            "joinstyle": "round",
            "outline_color": "190,190,190,220",
            "outline_style": "dot",
            "outline_width": "0.6",
            "outline_width_unit": "MM",
            "style": "dense2",
        }
        symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
        symbol = QgsFillSymbol()
        symbol.deleteSymbolLayer(0)
        symbol.appendSymbolLayer(symbol_layer.clone())
        renderer = QgsSingleSymbolRenderer(symbol)
        layer_to_add.setRenderer(renderer)

        # 加载宏站图层
        shp = self.io_util.find_latest_para_file('宏站扇区图层')[0]
        if shp:
            layer_to_add = QgsVectorLayer(shp, '宏站扇区图层', "ogr")
            PROJECT.addMapLayer(layer_to_add)
            lfi = layer_to_add.fields().indexFromName('频段')
            unique_bands = layer_to_add.uniqueValues(lfi)
            categories = []
            for unique_band in unique_bands:
                if unique_band == '2.6G':
                    properties_fill = {
                        "color": "130, 170, 75, 160",
                        "outline_style": "no",
                        "style": "dense2",
                    }
                elif unique_band == '700M':
                    properties_fill = {
                        "color": "253, 129, 111, 160",
                        "outline_style": "no",
                        "style": "dense2",
                    }
                else:
                    properties_fill = {
                        "color": "189, 143, 83, 160",
                        "outline_style": "no",
                        "style": "dense2",
                    }
                fill_symbol = QgsFillSymbol.createSimple(properties_fill)
                category = QgsRendererCategory(unique_band, fill_symbol.clone(), str(unique_band))
                categories.append(category)
            renderer = QgsCategorizedSymbolRenderer('频段', categories)
            layer_to_add.setRenderer(renderer)
            layer_to_add.triggerRepaint()
        else:
            self.statusbar_message_update('未找到宏站图层', 3000)
            self.log_text_field_update("未找到宏站图层", 3)


        # 加载室分图层
        shp, latest_date = self.io_util.find_latest_para_file('室分扇区图层')
        if shp:
            #shp = r"resources\layer\室分扇区图层20250519_2034.shp"
            layer_to_add = QgsVectorLayer(shp, '室分扇区图层', "ogr")
            PROJECT.addMapLayer(layer_to_add)
            properties_fill = {
                "color": "130, 170, 75, 160",
                "outline_style": "no",
                "style": "dense2",
            }
            symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(symbol_layer.clone())
            renderer = QgsSingleSymbolRenderer(symbol)
            layer_to_add.setRenderer(renderer)
        else:
            self.statusbar_message_update('未找到室分图层', 3000)
            self.log_text_field_update("未找到室分图层",3)

        self.log_text_field_update(f"数据库工参日期为{latest_date}")
        self.log_text_field_update("已完成工参数据加载")

        # 加载ToB项目图层
        project_data_dict_from_db = self.sql_util.get_project_full_data_include_wkt(self.conn)
        project_data_dict_sorted = self.data_util.wkt_sort_processor(project_data_dict_from_db)
        if project_data_dict_sorted[2]:
            self.qgs_canvas_util.create_layer_from_wkt(project_data_dict_sorted[2], 6, 'ToB项目图层_面')
            layer = QgsProject.instance().mapLayersByName("ToB项目图层_面")[0]
            properties_fill = {
                "color": "166, 206, 227, 130",
                "outline_color": "235,80,0,255",
                "outline_style": "dash",
                "outline_width": "0.6",
                "outline_width_unit": "MM",
                "style": "dense5",
            }
            symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(symbol_layer.clone())
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            self.qgs_canvas_util.show_layer_lable(layer, 2, "项目名称", 20000000)

        if project_data_dict_sorted[1]:
            self.qgs_canvas_util.create_layer_from_wkt(project_data_dict_sorted[1], 5, 'ToB项目图层_线')
            layer = QgsProject.instance().mapLayersByName("ToB项目图层_线")[0]
            properties_line = {
                "line_color": "235,80,0,255",
                "line_width": "250",
                "line_width_unit": "RenderMetersInMapUnits",
                "capstyle": "round"
            }
            symbol_layer = QgsSimpleLineSymbolLayer.create(properties_line)
            symbol = QgsLineSymbol()
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(symbol_layer.clone())
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.setOpacity(0.5)
            self.qgs_canvas_util.show_layer_lable(layer, 1, "项目名称", 30000000)

        if project_data_dict_sorted[0]:
            self.qgs_canvas_util.create_layer_from_wkt(project_data_dict_sorted[0], 4, 'ToB项目图层_点')
            layer = QgsProject.instance().mapLayersByName("ToB项目图层_点")[0]
            properties_marker = {
                "color": "235,80,0,255",
                "size": "2",
            }
            symbol_layer = QgsSimpleMarkerSymbolLayer.create(properties_marker)
            symbol = QgsMarkerSymbol()
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(symbol_layer.clone())
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            self.qgs_canvas_util.show_layer_lable(layer, 0, "项目名称", 30000000)

        QTimer.singleShot(300, lambda: self.qgs_canvas_util.set_canvas_extend_to_cord(117.296584, 39.144797, 80000))

        self.log_text_field_update("已完成项目地理信息加载")

    #左侧项目树初始化
    def init_project_tree_widget(self):
        """
        左侧项目树初始化，调用SqliteUtils函数获取全量项目信息和基站小区列表
        :return: None
        """
        self.projectTreeWidget.setColumnCount(3)
        self.projectTreeWidget.setColumnHidden(2, True)
        self.projectTreeWidget.setHeaderHidden(True)
        self.projectTreeWidget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.list_projects = self.sql_util.get_project_tree_inner_text(self.conn)
        project_tree_items = []
        for list_project in self.list_projects:
            project_item = QTreeWidgetItem([list_project[0], list_project[1], list_project[2]])
            project_item.setToolTip(0, list_project[0])
            project_item.setToolTip(1, list_project[1])
            for list_gnb in list_project[3]:
                gnb_item =  QTreeWidgetItem([list_gnb[0], list_gnb[1], list_gnb[2]])
                gnb_item.setToolTip(0,list_gnb[0])
                gnb_item.setToolTip(1, list_gnb[1])
                for list_cell in list_gnb[3]:
                    cell_item = QTreeWidgetItem([list_cell[0], list_cell[1], list_cell[2]])
                    cell_item.setToolTip(0,list_cell[0])
                    cell_item.setToolTip(1, list_cell[1])
                    gnb_item.addChild(cell_item)
                project_item.addChild(gnb_item)
            project_tree_items.append(project_item)

        self.projectTreeWidget.insertTopLevelItems(0, project_tree_items)

        projectTreeWidgetWidth = self.projectTreeWidget.viewport().width()
        self.projectTreeWidget.setColumnWidth(0, int(projectTreeWidgetWidth * 0.80))
        self.projectTreeWidget.setColumnWidth(1, int(projectTreeWidgetWidth * 0.10))
        self.projectTreeWidget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

        self.projectTreeWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # 启用自定义右键菜单
        self.projectTreeWidget.customContextMenuRequested.connect(self.showProjectTreeContextMenu)  # 连接菜单显示方法
        self.log_text_field_update("已完成项目列表数据结构初始化并配置右键菜单")

    """
    右键菜单区域
    """

    def showProjectTreeContextMenu(self, position):
        # 获取鼠标点击处的项
        item = self.projectTreeWidget.itemAt(position)
        if item.text(2) in ['园区','线路','散点']:
            menu = QMenu()
            # 创建菜单项
            assess_action = QAction("定位项目", self)
            assess_action.triggered.connect(lambda: self.project_tree_item_clicked(item,0,True))  # 连接方法并传递当前项
            menu.addAction(assess_action)
            assess_action = QAction("项目评估", self)
            assess_action.triggered.connect(lambda: self.existing_project_eval_menu_clicked(item))  # 连接方法并传递当前项
            menu.addAction(assess_action)
            menu.exec(self.projectTreeWidget.mapToGlobal(position))  # 在鼠标位置显示菜单

    def existing_project_eval_menu_clicked(self,item):
        self.project_tree_item_clicked(item, 0, False)
        self.existing_project_eval(item.text(0))



    """
    菜单按钮槽函数区域
    """

    # 按钮名称：关于
    def m2_about_triggered(self):
        self.log_text_field_update(
            '\n_/﹋\\_\n (҂`_´)                      Coded by T.Ding\n<, ︻╦╤─ ҉ - -      Live Long And Prosper\n_/﹋\\_\n\n',
            0)
        #self.mapCanvas.setMapTool(QgsMapToolPan(self.mapCanvas))
        dialog = QDialog(self)
        about_window = UiDialogAbout()
        about_window.setupUi(dialog)
        pixmap = QPixmap("resources/logo/workshop_logo.png")
        scaled_pixmap = pixmap.scaled(
            250, 45,  # 目标尺寸
            Qt.AspectRatioMode.KeepAspectRatio,  # 保持宽高比
            Qt.TransformationMode.SmoothTransformation  # 平滑缩放（高质量）
        )
        about_window.label_LOGO.setPixmap(scaled_pixmap)
        about_window.label_LOGO.setFixedHeight(50)
        dialog.exec()


    def m2_open_layer_triggered(self):
        file_dialog = QFileDialog()
        layer_filepath, _ = file_dialog.getOpenFileName(self, "选择图层文件", "",
                                                                "Layer Files (*.shp *.tab)")
        if layer_filepath:
            layer_to_add = QgsVectorLayer(layer_filepath, os.path.basename(layer_filepath), "ogr")
            PROJECT.addMapLayer(layer_to_add)
            self.mapCanvas.setExtent(self.qgs_canvas_util.transformer_4326_to_3857.transform(layer_to_add.extent()))
            self.log_text_field_update(f"已打开{layer_filepath}")

    def m2_open_project_triggered(self):
        self.log_text_field_update(f"暂不支持工程的保存和打开功能",2)
        self.statusbar_message_update(f"暂不支持工程的保存和打开功能")

    def m2_tool_pan_toggled(self, toggled):
        if toggled:
            self.mapCanvas.setMapTool(self.toolPan)
            self.log_text_field_update("已启用拖动工具")
        else:
            self.mapCanvas.unsetMapTool(self.toolPan)
            #self.log_text_field_update("已停用手型工具")

    def m2_tool_info_toggled(self, toggled):
        if toggled:
            self.mapCanvas.setMapTool(self.toolInfo)
            self.log_text_field_update("已启用信息查询工具")
        else:
            self.mapCanvas.unsetMapTool(self.toolInfo)
            #self.log_text_field_update("已停用信息查询工具")

    def m2_tool_distance_toggled(self, toggled):
        if toggled:
            self.mapCanvas.setMapTool(self.toolDistance)
            self.log_text_field_update("已启用测距工具")
        else:
            self.mapCanvas.unsetMapTool(self.toolDistance)
            #self.log_text_field_update("已停用信息查询工具")

    def m2_tool_azimuth_toggled(self, toggled):
        if toggled:
            self.mapCanvas.setMapTool(self.toolAzimuth)
            self.log_text_field_update("已启用角度测量工具")
        else:
            self.mapCanvas.unsetMapTool(self.toolAzimuth)
            #self.log_text_field_update("已停用信息查询工具")

    def m2_view_detail_triggered(self, toggled):
        if toggled:
            self.dockWidgetDetail.show()
            self.log_text_field_update("已显示详细信息窗口")
        else:
            self.dockWidgetDetail.hide()
            self.log_text_field_update("已关闭详细信息窗口")

    def m2_view_project_tree_triggered(self, toggled):
        if toggled:
            self.dockWidgetProjectTree.show()
            self.log_text_field_update("已显示项目树窗口")
        else:
            self.dockWidgetProjectTree.hide()
            self.log_text_field_update("已关闭项目树窗口")

    def m2_view_layer_tree_triggered(self, toggled):
        if toggled:
            self.dockWidgetLayerTree.show()
            self.log_text_field_update("已显示图层窗口")
        else:
            self.dockWidgetLayerTree.hide()
            self.log_text_field_update("已关闭图层窗口")

    def m2_view_gpscord_triggered(self, toggled):
        if toggled:
            self.dockWidgetGPSCord.show()
            self.log_text_field_update("已显示坐标定位窗口")
        else:
            self.dockWidgetGPSCord.hide()
            self.log_text_field_update("已关闭坐标定位窗口")

    def m2_view_log_triggered(self, toggled):
        if toggled:
            self.dockWidgetLog.show()
            self.log_text_field_update("已显示日志窗口")
        else:
            self.dockWidgetLog.hide()
            self.log_text_field_update("已关闭日志窗口")

    def m2_existing_project_eval_triggered(self):
        dialog = ExistingProjectEvalDialog(self)
        dialog.selection_made.connect(self.m2_existing_project_eval_selection_result_handler)
        # 模态对话框：阻塞主窗口交互
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        options = self.sql_util.get_project_list(self.conn)
        dialog.comboBoxProjectName.addItems(options)
        dialog.show()

    def m2_existing_project_eval_selection_result_handler(self, selected_text):
        self.existing_project_eval(selected_text)

    def m2_new_project_eval_triggered(self):
        if self.dockWidgetNewProjectEval.isHidden():
            self.dockWidgetNewProjectEval.show()
            if hasattr(self, 'comboBoxPorjectLevel'):
                combo = getattr(self, 'comboBoxPorjectLevel')
                combo.addItems(["优享", "专享", "尊享"])
            if hasattr(self, 'comboBoxUPF'):
                combo = getattr(self, 'comboBoxUPF')
                combo.addItems(["是", "否"])
                combo.setCurrentText("否")
            if hasattr(self, 'comboBoxAMF'):
                combo = getattr(self, 'comboBoxAMF')
                combo.addItems(["是", "否"])
                combo.setCurrentText("否")
            for i in range(1, 4):
                combo_name = f"comboBoxUseCase{i}"
                # 检查对象是否存在
                if hasattr(self, combo_name):
                    combo = getattr(self, combo_name)
                    combo.addItems(["", "摄像头", "AGV车", "扫码枪", "手持终端", "信息采集", "其他"])
                    #combo.setCurrentText("AGV车")
                combo_name = f"comboBoxLatency{i}"
                # 检查对象是否存在
                if hasattr(self, combo_name):
                    combo = getattr(self, combo_name)
                    combo.addItems([">30", "30", "20", "10"])
                    #combo.setCurrentText("20")
                combo_name = f"comboBoxReliability{i}"
                # 检查对象是否存在
                if hasattr(self, combo_name):
                    combo = getattr(self, combo_name)
                    combo.addItems(["<99%", "99%", "99.9%", "99.99%"])
                    #combo.setCurrentText("99.9%")
                text_name = f"lineEditULSpeed{i}"
                # if hasattr(self, combo_name):
                #     combo = getattr(self, text_name)
                #     combo.setText('20')
                # text_name = f"lineEditDLSpeed{i}"
                # if hasattr(self, combo_name):
                #     combo = getattr(self, text_name)
                #     combo.setText('200')
                # text_name = f"lineEditUECount{i}"
                # if hasattr(self, combo_name):
                #     combo = getattr(self, text_name)
                #     combo.setText('30')
                # text_name = f"lineEditUEIntercurrent{i}"
                # if hasattr(self, combo_name):
                #     combo = getattr(self, text_name)
                #     combo.setText('50')
        else:
            self.dockWidgetNewProjectEval.hide()

    def m2_tianditu_key_management_triggered(self):
        dialog = TiandituApikeyManagementDialog(self)
        # 模态对话框：阻塞主窗口交互
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.show()

    def m2_test_triggered(self):
        """

        :return:
        :rtype:
        '临时多边形图层_新项目评估','名称','评估项目边界'
        """

        self.log_text_field_update("别点我，我害羞",2)


    """
    组件槽函数区域
    """

    # 槽函数：用于用户点选某个站点或项目后显示其详细信息并平移缩放地图
    def project_tree_item_clicked(self, item, column, blink=True):
        """
        槽函数
        用于用户点选某个站点或项目后显示其详细信息并平移缩放地图，对于点选的项目将项目和小区高亮，对于点选的小区高亮

        当用户点击项目列表树结构中的某个item后将该item传入该槽函数，
        item自带一个隐藏字段text(2)用于判断级别，'园区''线路''散点'为project父节点，c为cell孙节点，其余为gnbid对应gnb子节点
        对点选的子节点和孙节点，调用set_canvas_extend_to_cord方法平移画布，并调用add_marker增加一个闪烁10次的红圈

        对点选的父节点，计划首先在图层中搜索项目图层并平移至项目，如果没有图层则平移至所有站点对应的最大和最小经纬度区域（尚未开发完成）

        完成后调用tableWidgetDetailTable.setItem更新右侧表格

        组件：projectTreeWidget
        组件位置：左上
        信号：itemClicked(QTreeWidgetItem*,int)

        :param item: 自动传入，projectTreeWidget组件中当前点击的QTreeWidgetItem
        :type item: QTreeWidgetItem
        :return: None
        """
        detail_title_and_data_return = []
        # 删除一切临时图层
        self.qgs_canvas_util.del_layer_by_name('临时项目图层')
        self.qgs_canvas_util.del_layer_by_name('临时扇区图层')

        for layer in PROJECT.mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                layer.removeSelection()

        if self.qgs_canvas_util.layerFlashTimer:
            self.qgs_canvas_util.layerFlashTimer.stop()

        # 用于对没有shp图层的项目，以扇区分布进行定位
        project_shp_valid_flag = True

        # 点击的是项目节点
        if item.text(2) in ['园区','线路','散点']:
            detail_title_and_data_return = self.sql_util.get_detail_table(self.conn, 0, item.text(0))

            self.log_text_field_update(f"已选择项目:[{item.text(0)}]")

            #高亮显示项目
            if item.text(2) == '园区':
                layer = PROJECT.mapLayersByName("ToB项目图层_面")[0]
            elif item.text(2) == '线路':
                layer = PROJECT.mapLayersByName("ToB项目图层_线")[0]
            else:
                layer = PROJECT.mapLayersByName("ToB项目图层_点")[0]
            expression = QgsExpression(f'"项目名称" = \'{item.text(0)}\'')
            request = QgsFeatureRequest(expression)
            features = list(layer.getFeatures(request))
            if features:
                # 创建临时内存图层存储选中的要素
                if item.text(2) == '园区':
                    temp_project_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:3857", "临时项目图层", "memory")
                    properties = {
                        "color": "255, 206, 227, 130",
                        "outline_color": "255,242,1,255",
                        "outline_style": "dash",
                        "outline_width": "2.6",
                        "outline_width_unit": "MM",
                        "style": "dense5",
                    }
                    symbol_layer = QgsSimpleFillSymbolLayer.create(properties)
                    symbol = QgsFillSymbol()
                elif item.text(2) == '线路':
                    temp_project_layer = QgsVectorLayer("MultiLineString?crs=EPSG:3857", "临时项目图层", "memory")
                    properties = {
                        "line_color": "255,242,1,255",
                        "line_width": "250",
                        "line_width_unit": "RenderMetersInMapUnits",
                        "capstyle": "round"
                    }
                    symbol_layer = QgsSimpleLineSymbolLayer.create(properties)
                    symbol = QgsLineSymbol()
                    temp_project_layer.setOpacity(0.3)
                else:
                    temp_project_layer = QgsVectorLayer("MultiPoint?crs=EPSG:3857", "临时项目图层", "memory")
                    properties = {
                        "color": "255,80,0,255",
                        "size": "4",
                    }
                    symbol_layer = QgsSimpleMarkerSymbolLayer.create(properties)
                    symbol = QgsMarkerSymbol()
                temp_project_layer.setCrs(layer.crs())
                provider = temp_project_layer.dataProvider()

                # 添加选中的要素
                provider.addFeatures(features)
                temp_project_layer.commitChanges()

                symbol.deleteSymbolLayer(0)
                symbol.appendSymbolLayer(symbol_layer.clone())
                renderer = QgsSingleSymbolRenderer(symbol)
                temp_project_layer.setRenderer(renderer)
                PROJECT.addMapLayer(temp_project_layer)
                # 获取第一个匹配要素的几何
                geometry = features[0].geometry()
                # 设置Canvas显示范围为要素边界
                self.mapCanvas.setExtent(self.qgs_canvas_util.get_expanded_extend_by_geometry(geometry))
                # 刷新Canvas以显示新范围
                self.mapCanvas.refresh()

                #图层闪烁（比例尺过大的就不闪烁了）
                if self.mapCanvas.scale() < 50000 and blink:
                    self.qgs_canvas_util.flash_layer_in_canvas(temp_project_layer)
            else:
                self.statusbar_message_update(f"项目[{item.text(0)}]为零星散点项目，且未提供终端分布，无法进行项目地理化边界呈现")
                project_shp_valid_flag = False

            # 获取高亮小区列表
            highlight_cgi_list = self.sql_util.get_project_cgi_list(self.conn, item.text(0))

        # 点击的是小区节点
        elif item.text(2) == 'c':
            self.log_text_field_update(f"已选择小区:[{item.text(0)}]")
            # print(item.parent().parent().text(0))
            highlight_cgi_list = [item.text(0)]
            detail_title_and_data_return = self.sql_util.get_detail_table(self.conn, 2, item.text(0))
            detail_title_and_data_return_dict = {item[0]: item[1] for item in detail_title_and_data_return}
            try:
                lon = float(detail_title_and_data_return_dict.get('经度'))
                lat = float(detail_title_and_data_return_dict.get('纬度'))
                if 116 < lon < 119 and 37 < lat < 42:
                    self.qgs_canvas_util.set_canvas_extend_to_cord(lon, lat, 20000)
                    self.qgs_canvas_util.add_marker_in_canvas(lon, lat, 1000, 10, QgsVertexMarker.ICON_CIRCLE)
            except ValueError:
                print('该站点经纬度有误')
        # 点击的是基站节点
        else:
            self.log_text_field_update(f"已选择基站:[{item.text(0)}]")
            detail_title_and_data_return = self.sql_util.get_detail_table(self.conn, 1, item.text(2))
            detail_title_and_data_return_dict = {item[0]: item[1] for item in detail_title_and_data_return}
            highlight_cgi_list = self.sql_util.get_gnb_cgi_list(self.conn, item.text(2))
            try:
                lon = float(detail_title_and_data_return_dict.get('经度'))
                lat = float(detail_title_and_data_return_dict.get('纬度'))
                if 116<lon<119 and 37<lat<42:
                    self.qgs_canvas_util.set_canvas_extend_to_cord(lon, lat, 20000)
                    self.qgs_canvas_util.add_marker_in_canvas(lon, lat, 1000, 10, QgsVertexMarker.ICON_CIRCLE)
            except ValueError:
                print('该站点经纬度有误')

        # 高亮小区
        if highlight_cgi_list:
            plmn_replace_cgi_list = []
            for highlight_cgi in highlight_cgi_list:
                plmn_replace_cgi_list.append(highlight_cgi.replace('460-08', '460-00'))
            layer_bts = PROJECT.mapLayersByName("宏站扇区图层")[0]
            layer_dbs = PROJECT.mapLayersByName("室分扇区图层")[0]
            temp_highlight_cell_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:3857", "临时扇区图层", "memory")
            temp_highlight_cell_layer.setCrs(layer_bts.crs())
            provider_cell = temp_highlight_cell_layer.dataProvider()
            properties_fill = {
                "color": "255,242,1,255",
                "outline_style": "no",
                "style": "dense1",
            }
            symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
            symbol = QgsFillSymbol()
            quoted_cgi = [f"'{highlight_cgi}'" for highlight_cgi in plmn_replace_cgi_list]
            expression = QgsExpression(f'"唯一标识" IN ({", ".join(quoted_cgi)})')
            request = QgsFeatureRequest(expression)
            features_bts = list(layer_bts.getFeatures(request))
            features_dbs = list(layer_dbs.getFeatures(request))
            if features_bts:
                provider_cell.addFeatures(features_bts)
                temp_highlight_cell_layer.commitChanges()
            if features_dbs:
                provider_cell.addFeatures(features_dbs)
                temp_highlight_cell_layer.commitChanges()
            symbol.deleteSymbolLayer(0)
            symbol.appendSymbolLayer(symbol_layer.clone())
            renderer = QgsSingleSymbolRenderer(symbol)
            temp_highlight_cell_layer.setRenderer(renderer)
            PROJECT.addMapLayer(temp_highlight_cell_layer)

            # 对未按照项目边界进行画布缩放的，以扇区图层进行缩放
            if not project_shp_valid_flag:
                self.mapCanvas.setExtent(self.qgs_canvas_util.transformer_4326_to_3857.transform(temp_highlight_cell_layer.extent()))


        # 更新右侧表格数据
        self.tableWidgetDetailTable.setRowCount(len(detail_title_and_data_return))
        row_wkt_del = -1
        for row, row_data in enumerate(detail_title_and_data_return):
            for col, text in enumerate(row_data):
                if str(text).lower() == 'wkt':
                    row_wkt_del = row
                if text != 'None':
                    table_cell_item = QTableWidgetItem(text)
                    table_cell_item.setToolTip(text)
                    self.tableWidgetDetailTable.setItem(row, col, table_cell_item)
                else:
                    table_cell_item = QTableWidgetItem('')
                    self.tableWidgetDetailTable.setItem(row, col, table_cell_item)
        if row_wkt_del != -1:
            self.tableWidgetDetailTable.removeRow(row_wkt_del)


    # 槽函数：在项目列表上方搜索框输入文字触发事件，实时筛选项目树中匹配的行
    def project_search_lineedit_text_changed(self, text):
        """
        槽函数

        在项目列表上方搜索框输入文字触发事件，实时筛选项目树中匹配的行
        对于项目类型匹配的，不展开树结构，对于基站和小区列表匹配的展开树结构

        组件：projectSearchLineEdit
        组件位置：左上
        信号：textChanged(QString)

        :param text: 自动传入，projectSearchLineEdit组件中当前的文字
        :type text: str
        :return: None
        """
        project_tree_items = []
        #判断命中第几层，1为项目，2为基站，3为小区
        match_layer = 0
        for list_project in self.list_projects:
            project_not_del_flag = False
            project_item = QTreeWidgetItem([list_project[0], list_project[1], list_project[2]])
            project_item.setToolTip(0, list_project[0])
            project_item.setToolTip(1, list_project[1])
            # 匹配项目信息
            if text in list_project[0] or text in list_project[1]:
                match_layer = 1
                for list_gnb in list_project[3]:
                    gnb_item =  QTreeWidgetItem([list_gnb[0], list_gnb[1], list_gnb[2]])
                    gnb_item.setToolTip(0,list_gnb[0])
                    gnb_item.setToolTip(1, list_gnb[1])
                    for list_cell in list_gnb[3]:
                        cell_item = QTreeWidgetItem([list_cell[0], list_cell[1], list_cell[2]])
                        cell_item.setToolTip(0,list_cell[0])
                        cell_item.setToolTip(1, list_cell[1])
                        gnb_item.addChild(cell_item)
                    project_item.addChild(gnb_item)
                project_tree_items.append(project_item)
            else:
                #非匹配项目信息
                for list_gnb in list_project[3]:
                    gnb_not_del_flag = False
                    gnb_item =  QTreeWidgetItem([list_gnb[0], list_gnb[1], list_gnb[2]])
                    gnb_item.setToolTip(0,list_gnb[0])
                    gnb_item.setToolTip(1, list_gnb[1])
                    #匹配GNB信息
                    if text in list_gnb[0] or text in list_gnb[1] or text in list_gnb[2]:
                        project_not_del_flag = True
                        if match_layer == 0:
                            match_layer = 2
                        for list_cell in list_gnb[3]:
                            cell_item = QTreeWidgetItem([list_cell[0], list_cell[1], list_cell[2]])
                            cell_item.setToolTip(0,list_cell[0])
                            cell_item.setToolTip(1, list_cell[1])
                            gnb_item.addChild(cell_item)
                        project_item.addChild(gnb_item)
                    else:
                    # 不匹配GNB信息
                        for list_cell in list_gnb[3]:
                            cell_item = QTreeWidgetItem([list_cell[0], list_cell[1], list_cell[2]])
                            cell_item.setToolTip(0,list_cell[0])
                            cell_item.setToolTip(1, list_cell[1])
                            #匹配小区信息
                            if text in list_cell[0] or text in list_cell[1]:
                                if match_layer == 0:
                                    match_layer = 3
                                gnb_item.addChild(cell_item)
                                gnb_not_del_flag = True
                                project_not_del_flag = True
                        if gnb_not_del_flag:
                            project_item.addChild(gnb_item)
                if project_not_del_flag:
                    project_tree_items.append(project_item)

        self.projectTreeWidget.clear()
        self.projectTreeWidget.insertTopLevelItems(0, project_tree_items)
        if text != '' and match_layer != 1:
            self.projectTreeWidget.expandAll()

    def pushButtonNewProjectDrawBorder_clicked(self):
        self.qgs_canvas_util.create_temp_polygon_layer_in_canvas('临时多边形图层_新项目评估')
        self.polygon_tool = CustomPolygonMapTool(self.mapCanvas, self.active_layer)
        # 设置为当前地图工具
        self.mapCanvas.setMapTool(self.polygon_tool)

    def pushButtonNewProjectEval_clicked(self):
        dialog = QFileDialog(self, "选择报告保存路径", "./")
        dialog.setOption(QFileDialog.Option.ShowDirsOnly)  # 只显示目录
        dialog.setOption(QFileDialog.Option.ReadOnly)  # 只读模式
        dialog.setFileMode(QFileDialog.FileMode.Directory)  # PyQt6 中的正确用法

        # 设置对话框大小
        dialog.setFixedSize(340, 250)
        self.log_text_field_update(f"开始进行新业务需求评估，请选择报告保存路径", 2)

        if dialog.exec():
            self.new_project_eval_docx_save_path = dialog.selectedFiles()[0]

            if self.new_project_eval_docx_save_path:
                self.log_text_field_update(f"报告将输出至{self.new_project_eval_docx_save_path}")

                self.qgs_canvas_util.bubble_expand_finished_signal.connect(
                    self.new_project_eval_post_bubble_expand)
                self.qgs_canvas_util.algorithm_bubble_expand('', True)

    def new_project_eval_post_bubble_expand(self, evaluate_project_name, max_bubble_size, intersects_cgi_list, outer_cgi_list):

        docx_template = DocxTemplate('resources/template/template_new_project_eval.docx')
        docx_template_render_context = {'project_name': self.lineEditProjectName.text(),
                                        'eval_date': datetime.date.today().isoformat()}

        #概述部分
        docx_template_render_context["project_summary"] = [
                f'本次对{self.lineEditProjectName.text()}项目的新增业务需求进行评估，该项目为{self.comboBoxPorjectLevel.currentText()}项目，'
                f'使用{"华北大区共享2B AMF" if self.comboBoxAMF.currentText() == '否' else "专属下沉AMF"}和'
                f'{"天津共享2B UPF" if self.comboBoxUPF.currentText() == '否' else "园区下沉MEC"}。','项目所在地理位置如下图所示：']

        self.qgs_canvas_util.set_canvas_extend_to_polygon('临时多边形图层_新项目评估','名称','评估项目边界')
        self.mapCanvas.refresh()
        image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
        docx_template_render_context["project_image"] = docxtpl.InlineImage(docx_template,
                                                                                       BytesIO(image_data),
                                                                                       width=Mm(140))

        #用例部分
        usecase_count = 0
        use_case_table_data = []
        for i in range(1, 4):
            attr_name = [f"comboBoxUseCase{i}",f"comboBoxLatency{i}",f"comboBoxReliability{i}",f"lineEditULSpeed{i}",f"lineEditDLSpeed{i}",f"lineEditUECount{i}",f"lineEditUEIntercurrent{i}"]
            # 检查对象是否存在
            if hasattr(self, attr_name[0]):
                combo = getattr(self, attr_name[0])
                if combo.currentText():
                    usecase_count += 1
                    use_case_table_data.append(
                        {'业务用例': combo.currentText(), '上行业务速率': getattr(self, attr_name[3]).text(), '下行业务速率': getattr(self, attr_name[4]).text(),
                         '时延': getattr(self, attr_name[1]).currentText(), '可靠性': getattr(self, attr_name[2]).currentText(), '终端数量': getattr(self, attr_name[5]).text(),
                         '并发概率': getattr(self, attr_name[6]).text()})

        docx_template_render_context["use_case_table"] = use_case_table_data
        docx_template_render_context["project_use_case_summary"] = [f'本项目共有用例{usecase_count}个，详表如下：']

        #需求对应小区评估
        if intersects_cgi_list:
            high_risk_bts_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('宏站扇区图层', intersects_cgi_list)
            high_risk_dbs_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('室分扇区图层', intersects_cgi_list)

            # 存在高风险小区，在日志中打印小区信息，更新word context
            if high_risk_bts_cell_info_list or high_risk_dbs_cell_info_list:
                docx_template_render_context["eval_result_high_pri_summary"] = [f'经过评估，高优先纳入项目小区共计{len(high_risk_bts_cell_info_list)+len(high_risk_dbs_cell_info_list)}个，其中宏站（含小微站）{len(high_risk_bts_cell_info_list)}个，室分{len(high_risk_dbs_cell_info_list)}个。','涉及小区详表如下:']
                docx_template_render_context["eval_result_high_pri_conclusion"] = []

                if high_risk_bts_cell_info_list:
                    bts_cell_26 = [item["小区名"] for item in high_risk_bts_cell_info_list if item["频段"] == "2.6G"]
                    bts_cell_other = [item["小区名"] for item in high_risk_bts_cell_info_list if
                                        item["频段"] != "2.6G"]
                    if bts_cell_26:
                        bts_cell_text_26 = ", ".join([f"{item}" for item in bts_cell_26])
                        docx_template_render_context["eval_result_high_pri_conclusion"].append(
                            f'对于高优先宏站2.6G小区：{bts_cell_text_26}，建议直接将以上小区纳入项目。')
                    if bts_cell_other:
                        bts_cell_text_other = ", ".join([f"{item}" for item in bts_cell_other])
                        docx_template_render_context["eval_result_high_pri_conclusion"].append(
                            f'对于高优先宏站700M或4.9G小区：{bts_cell_text_other}，请基于该项目投放终端的频段支持情况，按需接将以上小区纳入项目。')

                if high_risk_dbs_cell_info_list:
                    dbs_cell_text = ", ".join(
                        [f"{high_risk_dbs_cell_info['小区名']}" for high_risk_dbs_cell_info in
                         high_risk_dbs_cell_info_list])
                    docx_template_render_context["eval_result_high_pri_conclusion"].append(f'对于高优先室分小区：{dbs_cell_text}，如项目终端存在进入室分覆盖区域的可能性，建议直接将以上小区纳入项目')
                docx_template_render_context[
                        "eval_result_high_pri_table"] = high_risk_bts_cell_info_list + high_risk_dbs_cell_info_list

            #基于高风险CGI list生成图层，并截图放入word
            self.qgs_canvas_util.add_temp_sector_layer_in_canvas('临时扇区图层',intersects_cgi_list, {
                            "color": "255,0,0,255",
                            "outline_color": "255,255,0,255",
                            "outline_style": "solid",
                            "outline_width": "0.5",
                            "outline_width_unit": "MM",
                            "style": "solid",
                        })
            docx_template_render_context["eval_result_high_pri_conclusion"].append(
                f'高优先小区分布图如下：')
            image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
            docx_template_render_context["high_pri_sector_image"] = docxtpl.InlineImage(docx_template, BytesIO(image_data), width=Mm(140))
        else:
        # 不存在高风险小区，在日志中打印小区信息，更新word context
            docx_template_render_context["eval_result_high_pri_summary"] = [f'经过评估，本项目无高优先小区。']


        if outer_cgi_list:
            middle_risk_bts_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('宏站扇区图层',
                                                                                           outer_cgi_list)
            middle_risk_dbs_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('室分扇区图层',
                                                                                           outer_cgi_list)

            # 存在中风险小区，在日志中打印小区信息，更新word context
            if middle_risk_bts_cell_info_list or middle_risk_dbs_cell_info_list:
                docx_template_render_context["eval_result_middle_pri_summary"] = [f'经过评估，中优先纳入项目小区共计{len(middle_risk_bts_cell_info_list)+len(middle_risk_dbs_cell_info_list)}个，其中宏站（含小微站）{len(middle_risk_bts_cell_info_list)}个，室分{len(middle_risk_dbs_cell_info_list)}个。','涉及小区详表如下:']
                docx_template_render_context["eval_result_middle_pri_conclusion"] = []
                if middle_risk_dbs_cell_info_list:
                    dbs_cell_text = ", ".join(
                        [f"{middle_risk_dbs_cell_info['小区名']}" for middle_risk_dbs_cell_info in
                         middle_risk_dbs_cell_info_list])
                    docx_template_render_context["eval_result_middle_pri_conclusion"].append(
                        f'对于中优先室分小区：{dbs_cell_text}，如项目终端存在进入室分覆盖区域的可能性，建议直接将以上小区纳入项目')
                if middle_risk_bts_cell_info_list:
                    bts_cell_26 = [item["小区名"] for item in middle_risk_bts_cell_info_list if item["频段"] == "2.6G"]
                    bts_cell_other = [item["小区名"] for item in middle_risk_bts_cell_info_list if
                                      item["频段"] != "2.6G"]
                    if bts_cell_26:
                        bts_cell_text_26 = ", ".join([f"{item}" for item in bts_cell_26])
                        docx_template_render_context["eval_result_middle_pri_conclusion"].append(
                            f'对于中优先宏站2.6G小区：{bts_cell_text_26}，建议基于该小区的实际覆盖区域，以及终端的运行路线/摆放位置，按需将以上小区纳入项目。')

                    if bts_cell_other:
                        bts_cell_text_other = ", ".join([f"{item}" for item in bts_cell_other])
                        docx_template_render_context["eval_result_middle_pri_conclusion"].append(
                            f'对于中优先宏站700M或4.9G小区：{bts_cell_text_other}，在基于该小区的实际覆盖区域，以及终端的运行路线/摆放位置的基础上，同时考虑该项目投放终端的频段支持情况，按需接将以上小区纳入项目。')


                docx_template_render_context[
                    "eval_result_middle_pri_table"] = middle_risk_bts_cell_info_list + middle_risk_dbs_cell_info_list

            # 基于中风险CGI list生成图层，并截图放入word
            self.qgs_canvas_util.add_temp_sector_layer_in_canvas('临时扇区图层', outer_cgi_list, {
                "color": "125,255,0,255",
                "outline_color": "255,255,0,255",
                "outline_style": "solid",
                "outline_width": "0.5",
                "outline_width_unit": "MM",
                "style": "solid",
            })
            self.mapCanvas.setExtent(self.qgs_canvas_util.get_all_in_extend_by_two_extends(self.mapCanvas.extent(),self.qgs_canvas_util.get_expanded_extend_by_layer('临时扇区图层')))
            self.mapCanvas.refresh()
            docx_template_render_context["eval_result_middle_pri_conclusion"].append(
                f'中优先小区分布图如下：')
            image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
            docx_template_render_context["middle_pri_sector_image"] = docxtpl.InlineImage(docx_template,
                                                                                         BytesIO(image_data),
                                                                                         width=Mm(140))
        else:
            docx_template_render_context["eval_result_middle_risk_summary"] = [
                f'本项目无中优先小区。']

        #容量计算
        docx_template_render_context["eval_result_network_cap_summary"] = []
        ul_speed_sum = 0
        dl_speed_sum = 0
        for i, use_case in enumerate(use_case_table_data):
            ul_speed = float(use_case['上行业务速率'])*int(use_case['终端数量'])*float(use_case['并发概率'])/100
            dl_speed = float(use_case['下行业务速率']) * int(use_case['终端数量']) * float(use_case['并发概率']) / 100

            #print(f'UL:{float(use_case['上行业务速率'])*int(use_case['终端数量'])*float(use_case['并发概率'])/100}')
            if use_case['时延'] == '10':
                if use_case['可靠性'] == '99.99%':
                    ratio_num = 0.39
                elif use_case['可靠性'] == '99.9%':
                    ratio_num = 0.51
                else:
                    ratio_num = 0.68
            elif use_case['时延'] == '20':
                if use_case['可靠性'] == '99.99%':
                    ratio_num = 0.51
                elif use_case['可靠性'] == '99.9%':
                    ratio_num = 0.67
                else:
                    ratio_num = 0.87
            else:
                if use_case['可靠性'] == '99.99%':
                    ratio_num = 0.66
                elif use_case['可靠性'] == '99.9%':
                    ratio_num = 0.81
                else:
                    ratio_num = 1
            docx_template_render_context["eval_result_network_cap_summary"].append(f'对于业务用例{i+1}，'
                f'该业务需要上行基础带宽{ul_speed:.2f}Mbps，下行基础带宽{dl_speed:.2f}Mbps，根据集团公司时延/可靠性折算标准，'
                f'该业务等效系数为{ratio_num}，基于折算后，项目需要实际上行带宽{ul_speed/ratio_num:.2f}Mbps，实际下行带宽{dl_speed/ratio_num:.2f}Mbps。')
            ul_speed_sum += ul_speed / ratio_num
            dl_speed_sum += dl_speed / ratio_num
        docx_template_render_context["eval_result_network_cap_summary"].insert(0, f"经评估，该项目共需要上行带宽{ul_speed_sum:.2f}Mbps，下行带宽{dl_speed_sum:.2f}Mbps，需要基于实际项目用例和小区关系，合理规划整体容量。每个用例的详情如下：")

        #项目冲突评估
        layer_temp_polygon = PROJECT.mapLayersByName('临时多边形图层_新项目评估')[0]
        temp_name = '评估项目边界'
        expression = QgsExpression(f'"名称" = \'{temp_name}\'')
        request = QgsFeatureRequest(expression)
        features_layer_temp_polygon = list(layer_temp_polygon.getFeatures(request))
        project_list_middle_risk = []
        project_list_high_risk = []
        if features_layer_temp_polygon:
            geom_temp = features_layer_temp_polygon[0].geometry()
            geom_temp.transform(self.qgs_canvas_util.transformer_3857_to_32650)

            project_list = self.sql_util.get_project_list(self.conn)

            for project_name in project_list:
                distance = self.qgs_canvas_util.get_distance_from_polygon_to_project(geom_temp, project_name)
                if distance == 0:
                    project_list_high_risk.append(project_name)
                elif 0< distance < max_bubble_size * 3:
                    project_list_middle_risk.append([project_name,distance])
        if project_list_middle_risk or project_list_high_risk:
            project_dict = self.sql_util.get_project_full_data_include_wkt(self.conn)
            docx_template_render_context["eval_project_cli_summary"] = [
                f'经过评估，本次新增需求可能与{len(project_list_middle_risk) + len(project_list_high_risk)}个现网项目产生冲突或资源抢占情况，需要结合对应项目的业务内容、资源占用以及核心网下沉方式，综合评估两个项目之间的冲突问题，合理制定解决方案（如独立PLMN，独立切片RB预留等）。']
            if project_list_high_risk:
                project_table_data_high_risk = []
                docx_template_render_context["eval_project_cli_summary"].append(f'高风险冲突项目共计{len(project_list_high_risk)}个，详表如下：')
                for project_high_risk in project_list_high_risk:
                    for project_dict_item in project_dict:
                        if project_dict_item['项目名称'] == project_high_risk:
                            project_table_data_high_risk.append({'项目名称':project_high_risk, '套餐级别':project_dict_item['套餐级别'],'项目场景':project_dict_item['项目场景'],'AMF下沉':project_dict_item['AMF下沉'],'UPF下沉':project_dict_item['UPF下沉'],'项目距离':'存在交叠'})
                            break
                docx_template_render_context["eval_project_cli_high_risk_table"] = project_table_data_high_risk
            if project_list_middle_risk:
                project_table_data_middle_risk = []
                docx_template_render_context["eval_project_cli_middle_risk_summary"]=[f'中风险冲突项目共计{len(project_list_middle_risk)}个，详表如下：']
                for project_middle_risk in project_list_middle_risk:
                    for project_dict_item in project_dict:
                        if project_dict_item['项目名称'] == project_middle_risk[0]:
                            project_table_data_middle_risk.append({'项目名称':project_middle_risk[0], '套餐级别':project_dict_item['套餐级别'],'项目场景':project_dict_item['项目场景'],'AMF下沉':project_dict_item['AMF下沉'],'UPF下沉':project_dict_item['UPF下沉'],'项目距离':project_middle_risk[1]})
                            break
                docx_template_render_context["eval_project_cli_middle_risk_table"] = project_table_data_middle_risk

        else:
            docx_template_render_context["eval_project_cli_summary"] = ['经评估，本次新增需求与现网项目不存在冲突或资源抢占情况']

        # 文件输出
        return_val = self.io_util.docxtpl_docx_output_handler(docx_template,
                                                     docx_template_render_context,
                                                     self.new_project_eval_docx_save_path,
                                                     f'ToB项目评估报告-{self.lineEditProjectName.text()}')
        if not return_val:
            self.log_text_field_update(f"已完成项目评估报告输出")
        else:
            self.log_text_field_update(return_val, 4)


    # 槽函数：用户在坐标定位栏输入经纬度后平移缩放地图
    def gps_cord_input_line_edit_key_pressed(self):
        """
        槽函数
        用户在坐标定位栏输入经纬度后平移缩放地图

        组件：gpsCordInputLineEdit
        组件位置：右下
        信号：returnPressed()

        :return: None
        """
        text = self.gpsCordInputLineEdit.text()
        # 定义灵活的分隔符模式：中文逗号、英文逗号、一个或多个空格
        separator = r'[\s,，]+'  # 匹配空格、英文逗号、中文逗号及其组合
        # 完整的正则表达式：经度 + 分隔符 + 纬度
        pattern = rf'^\s*(-?\d+(\.\d+)?){separator}(-?\d+(\.\d+)?)\s*$'
        match = re.match(pattern, text)
        cord_error_flag = False
        if match:
            try:
                # 提取经纬度并验证范围
                lon = float(match.group(1))  # 经度
                lat = float(match.group(3))  # 纬度
                # 检查范围：经度[-180, 180]，纬度[-90, 90]
                if -180 <= lon <= 180 and -90 <= lat <= 90 :
                    self.qgs_canvas_util.add_marker_in_canvas(lon, lat)
                    self.qgs_canvas_util.set_canvas_extend_to_cord(lon, lat)
                    self.log_text_field_update(f"已定位:[{lon},{lat}]")
                else:
                    cord_error_flag = True
            except ValueError:
                cord_error_flag = True
        else:
            cord_error_flag = True

        if cord_error_flag:
            QToolTip.showText(
                self.gpsCordInputLineEdit.mapToGlobal(self.gpsCordInputLineEdit.rect().bottomLeft()),
                "请输入有效的经纬度！",
                self.gpsCordInputLineEdit,
                self.gpsCordInputLineEdit.rect(),
                3000
            )
            self.statusbar_message_update("请输入有效的经纬度！")
            self.log_text_field_update(f"经纬度输入有误",3)


    """
    状态栏槽函数区域
    """
    # 槽函数：用于实时更新状态栏左下角的经纬度信息
    def statusbar_update_cord(self, point):
        """
        槽函数
        用于实时更新状态栏左下角的经纬度信息
        在post_init_no_pyqt_widget方法中连接，非QT Designer中定义
        组件：mapCanvas
        :param point: 自动传入，mapCanvas当前鼠标坐标
        :type point: QgsPointXY
        :return: None
        """
        # x, y = cord_trans_3857_to_4326(point.x(),point.y())
        point_4326 = self.qgs_canvas_util.transformer_3857_to_4326.transform(point)
        #transformer_3857_to_4326
        self.statusXY.setText(f'经纬度：{point_4326.x():.6f}, {point_4326.y():.6f}')

    # 槽函数：用于实时更新状态栏右下角的比例尺
    def statusbar_show_scale(self, scale):
        """
        槽函数
        用于实时更新状态栏右下角的比例尺
        组件：mapCanvas
        :param scale: 自动传入，mapCanvas当前比例尺
        :type scale: float
        :return: None
        """
        self.statusScaleComboBox.setEditText(f"1:{int(scale)}")

    # 槽函数：用于实时更新状态栏右下角的坐标系
    def statusbar_show_crs(self):
        """
        槽函数
        用于实时更新状态栏右下角的坐标系
        组件：mapCanvas
        :return: None
        """
        mapSetting: QgsMapSettings = self.mapCanvas.mapSettings()
        self.statusCrsLabel.setText(
            f"坐标系: {mapSetting.destinationCrs().description()}-{mapSetting.destinationCrs().authid()}")

    # 在状态栏左下角显示通知、提示或告警内容，可设置文字存在时间和文字颜色
    def statusbar_message_update(self, message, interval=5000, color = 'red'):
        """
        在状态栏左下角显示通知、提示或告警内容，可设置文字存在时间和文字颜色
        :param message: 通知、提示或告警内容
        :type message: str
        :param interval: 存在时间（ms），0为长期，-1为清空
        :type interval: int
        :param color: 文字颜色
        :type color: str
        :return: None
        """
        if interval == -1:
            self.statusMessageBox.setText("")
        elif interval == 0:
            self.statusMessageBox.setText(f"[{message}]")
            self.statusMessageBox.setStyleSheet(f"color: {color};")
        else:
            if self.statusMessageBox.text():
                self.statusMessageTimer.stop()
                self.statusMessageBlinkTimer.stop()
            self.statusMessageBox.setText(f"[{message}]")
            self.statusMessageBox.setStyleSheet(f"color: {color};")
            def hide_label():
                self.statusMessageBox.setText("")
                self.statusMessageTimer.stop()
                self.statusMessageBlinkTimer.stop()
            def change_color():
                nonlocal color
                if color == 'red':
                    color = 'yellow'
                else:
                    color = 'red'
                self.statusMessageBox.setStyleSheet(f"color: {color};")
                self.statusMessageBox.setText(f"[{message}]")

            #self.statusMessageTimer = QTimer(self)
            self.statusMessageTimer.timeout.connect(hide_label)
            self.statusMessageTimer.start(interval)
            #self.statusMessageBlinkTimer = QTimer(self)
            if color == 'red':
                self.statusMessageBlinkTimer.timeout.connect(change_color)
                self.statusMessageBlinkTimer.start(500)

    def log_text_field_update(self, message, message_level=1):
        """
        在日志窗口中更新信息，并区分优先级
        :param message: 日志信息
        :type message: str
        :param message_level: 日志信息等级，默认为1（正常），2为提示，3为警告，4为重要警告，其他（例如0）为黄色不加时间用于出EMO图
        :type message_level:int
        :return:
        :rtype:
        """
        # 获取当前时间
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        # 创建一个新的文本格式
        text_format = QTextCharFormat()

        # 移动光标到文档末尾
        cursor = self.logTextEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # 插入时间戳和消息
        if message_level == 1 :
            text_format.setForeground(QColor('white'))
            cursor.insertText(f"[{current_time}]  {message}\n", text_format)
        elif message_level == 2 :
            text_format.setForeground(QColor('lightblue'))
            cursor.insertText(f"[{current_time}]  {message}\n", text_format)
        elif message_level == 3 :
            text_format.setForeground(QColor('orange'))
            cursor.insertText(f"[{current_time}]  {message}\n", text_format)
        elif message_level == 4:
            text_format.setForeground(QColor('red'))
            cursor.insertText(f"[{current_time}]  (警告) {message}\n", text_format)
        else:
            text_format.setForeground(QColor('yellow'))
            cursor.insertText(message, text_format)
        # 更新文本编辑控件
        self.logTextEdit.setTextCursor(cursor)
        self.logTextEdit.ensureCursorVisible()  # 确保新添加的内容可见

    """
    重写方法，开启图层拖拽功能
    """
    def dragEnterEvent(self, fileData):
        if fileData.mimeData().hasUrls():
            fileData.accept()
        else:
            fileData.ignore()
    # 重写方法，开启图层拖拽功能
    def dropEvent(self, fileData):
        mimeData: QMimeData = fileData.mimeData()
        filePathList = [u.path()[1:] for u in mimeData.urls()]
        for filePath in filePathList:
            filePath: str = filePath.replace("/", "//")
            if filePath.split(".")[-1].lower() in ["shp", "gpkg", "geojson", "kml", "tab"]:
                layer_to_add = QgsVectorLayer(filePath, os.path.basename(filePath), "ogr")
                PROJECT.addMapLayer(layer_to_add)
                self.mapCanvas.setExtent(self.qgs_canvas_util.transformer_4326_to_3857.transform(layer_to_add.extent()))

            elif filePath == "":
                pass
            else:
                QMessageBox.about(self, '警告', f'{filePath}为不支持的文件类型，请拖拽矢量图层(shp,tab等)')

    """
    MainWindow下属方法，实现各类功能
    """
    def existing_project_eval(self, project_name):

        try:
            self.qgs_canvas_util.bubble_expand_finished_signal.disconnect()
        except TypeError:
        # 若未连接任何槽函数，会抛出TypeError
            pass
        #
        # self.existing_project_eval_docx_save_path = QFileDialog.getExistingDirectory(self, '选择报告保存路径', './',
        #                                                            options=QFileDialog.Option.ReadOnly | QFileDialog.Option.ShowDirsOnly)
        dialog = QFileDialog(self, "选择报告保存路径", "./")
        dialog.setOption(QFileDialog.Option.ShowDirsOnly)  # 只显示目录
        dialog.setOption(QFileDialog.Option.ReadOnly)  # 只读模式
        dialog.setFileMode(QFileDialog.FileMode.Directory)  # PyQt6 中的正确用法

        # 设置对话框大小
        dialog.setFixedSize(340, 250)
        self.log_text_field_update(f"开始进行[{project_name}]项目分析，请选择报告保存路径", 2)

        if dialog.exec():
            self.existing_project_eval_docx_save_path = dialog.selectedFiles()[0]

            if self.existing_project_eval_docx_save_path:
                self.log_text_field_update(f"报告将输出至{self.existing_project_eval_docx_save_path}")

                self.qgs_canvas_util.bubble_expand_finished_signal.connect(self.existing_project_eval_post_bubble_expand)
                self.qgs_canvas_util.algorithm_bubble_expand(project_name, False)

    def existing_project_eval_post_bubble_expand(self, evaluate_project_name, max_bubble_size, intersects_cgi_list, outer_cgi_list):
        self.log_text_field_update(f"开始进行项目数据出场风险及冗余度分析")

        docx_template = DocxTemplate('resources/template/template_existing_project_eval.docx')
        docx_template_render_context = {'project_name': evaluate_project_name, 'eval_date': datetime.date.today().isoformat()}

        # 获取项目的全部CGI，并整理成元素为[CGI,CellID]的list对(evaluate_project_cgi_remove_plmn_list_pair)，以及一个用于匹配的，仅包含cellid的list(evaluate_project_cgi_remove_plmn_list)
        evaluate_project_cgi_list = self.sql_util.get_project_cgi_list(self.conn, evaluate_project_name)
        evaluate_project_cgi_remove_plmn_list_pair = self.data_util.cgi_list_remove_plmn_return_pair(evaluate_project_cgi_list)
        evaluate_project_cgi_remove_plmn_list = [item[1] for item in evaluate_project_cgi_remove_plmn_list_pair]

        # 处理docx模板中，项目简介的部分
        project_detail = self.sql_util.get_project_full_data_include_wkt(self.conn, evaluate_project_name)
        if project_detail:
            docx_template_render_context["project_summary"] = [
                f'{evaluate_project_name}为天津移动当前在网运行的ToB项目，'
                f'项目落地行政区为{project_detail[0]["行政区"] if project_detail[0]["行政区"] != '/' else "多区域"}，'
                f'{project_detail[0]["项目场景"]}类场景，使用{project_detail[0]["无线厂家"]}无线设备，'
                f'项目套餐级别为{project_detail[0]["套餐级别"]}。',
                f'核心网数据方面，本项目使用{"大区共享ToB AMF" if project_detail[0]["AMF下沉"] == '否' else "专属下沉AMF"}和'
                f'{"天津本地共享ToB UPF" if project_detail[0]["UPF下沉"] == '否' else "专属下沉MEC"}，'
                f'使用{'专有PLMN：'+ str(project_detail[0]["PLMN"]) if project_detail[0]["PLMN"] != '46000' else '默认PLMN（46000）'}，'
                f'{'配置专属切片ID：'+ str(project_detail[0]["专属切片ID"]) if project_detail[0]["专属切片ID"] != '无' else '未配置专属切片'}',
                f'管理级别方面，该项目{'按照ToB级别管理，全量站点纳入OMC ToB管理域，日常参数修改需要经过客响中心审批后进行。' if project_detail[0]["OMC管理级别"] == 'ToB' else '经政企侧和客响中心确认，以ToC级别进行管理。'}',
                f'项目共下挂基站{project_detail[0]["基站个数"]}个，小区{project_detail[0]["小区个数"]}个，地理位置及周边站点分布如下:']
        tree_item = self.find_project_item_in_project_tree_by_name(evaluate_project_name)
        if tree_item:
            self.project_tree_item_clicked(tree_item, 0,False)
        image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
        docx_template_render_context["project_image"] = docxtpl.InlineImage(docx_template,
                                                                                       BytesIO(image_data),
                                                                                       width=Mm(140))

        # 处理docx模板中，项目现有小区列表的部分
        docx_template_render_context[
            "project_cell_table"] = self.sql_util.get_project_cell_detail(self.conn, evaluate_project_name)

        # 正向评估，看intersects_cgi和outer_cgi中哪些小区不在2B总表中，分别归入数据出场风险中的高风险小区和中风险小区，获取这些小区的基本信息，生成表格
        # 定义高中风险小区列表
        high_risk_cgi_list = []
        middle_risk_cgi_list = []
        intersects_cgi_remove_plmn_list_pair = []
        outer_cgi_remove_plmn_list_pair = []

        # 高风险-位于项目区域内但不在2B总表里的小区
        # 将项目区域内包含的所有CGI转化为[CGI,CellID]的list对
        if intersects_cgi_list:
            intersects_cgi_remove_plmn_list_pair = self.data_util.cgi_list_remove_plmn_return_pair(intersects_cgi_list)

            for intersects_cgi_remove_plmn_pair in intersects_cgi_remove_plmn_list_pair:
                if intersects_cgi_remove_plmn_pair[1] not in evaluate_project_cgi_remove_plmn_list:
                    high_risk_cgi_list.append(intersects_cgi_remove_plmn_pair[0])

        # 基于高风险小区列表获取小区信息
        if high_risk_cgi_list:
            high_risk_bts_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('宏站扇区图层', high_risk_cgi_list)
            high_risk_dbs_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('室分扇区图层', high_risk_cgi_list)

            # 存在高风险小区，在日志中打印小区信息，更新word context
            if high_risk_bts_cell_info_list or high_risk_dbs_cell_info_list:
                self.log_text_field_update(f"已完成项目[{evaluate_project_name}]数据出场高风险小区评估")
                self.log_text_field_update(f"共识别高风险小区{len(high_risk_bts_cell_info_list)+len(high_risk_dbs_cell_info_list)}个，建议加入该项目小区总表：",3)
                docx_template_render_context["eval_result_high_risk_summary"] = [f'经过评估，本项目（{evaluate_project_name}）存在数据出场高风险小区，其中宏站（含小微站）{len(high_risk_bts_cell_info_list)}个，室分{len(high_risk_dbs_cell_info_list)}个。','涉及小区详表如下:']
                docx_template_render_context["eval_result_high_risk_conclusion"] = []
                if high_risk_dbs_cell_info_list:
                    dbs_cell_text = ", ".join(
                        [f"{high_risk_dbs_cell_info['小区名']}" for high_risk_dbs_cell_info in
                         high_risk_dbs_cell_info_list])
                    self.log_text_field_update(dbs_cell_text ,3)
                    docx_template_render_context["eval_result_high_risk_conclusion"].append(f'对于高风险室分小区：{dbs_cell_text}，如项目终端存在进入室分覆盖区域的可能性，建议直接将以上小区纳入项目')
                if high_risk_bts_cell_info_list:
                    bts_cell_26 = [item["小区名"] for item in high_risk_bts_cell_info_list if item["频段"] == "2.6G"]
                    bts_cell_other = [item["小区名"] for item in high_risk_bts_cell_info_list if
                                        item["频段"] != "2.6G"]
                    if bts_cell_26:
                        bts_cell_text_26 = ", ".join([f"{item}" for item in bts_cell_26])
                        docx_template_render_context["eval_result_high_risk_conclusion"].append(
                            f'对于高风险宏站2.6G小区：{bts_cell_text_26}，建议直接将以上小区纳入项目。')
                    else: bts_cell_text_26 = ''
                    if bts_cell_other:
                        bts_cell_text_other = ", ".join([f"{item}" for item in bts_cell_other])
                        docx_template_render_context["eval_result_high_risk_conclusion"].append(
                            f'对于高风险宏站700M或4.9G小区：{bts_cell_text_other}，请基于该项目投放终端的频段支持情况，按需接将以上小区纳入项目。')
                    else:bts_cell_text_other = ''
                    self.log_text_field_update(bts_cell_text_26 + bts_cell_text_other,3)

                docx_template_render_context[
                        "eval_result_high_risk_table"] = high_risk_bts_cell_info_list + high_risk_dbs_cell_info_list

            #基于高风险CGI list生成图层，并截图放入word
            self.qgs_canvas_util.add_temp_sector_layer_in_canvas('临时扇区图层',high_risk_cgi_list, {
                            "color": "255,0,0,255",
                            "outline_color": "255,255,0,255",
                            "outline_style": "solid",
                            "outline_width": "0.5",
                            "outline_width_unit": "MM",
                            "style": "solid",
                        })
            docx_template_render_context["eval_result_high_risk_conclusion"].append(
                f'高风险小区分布图如下：')
            image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
            docx_template_render_context["high_risk_sector_image"] = docxtpl.InlineImage(docx_template, BytesIO(image_data), width=Mm(140))
        else:
        # 不存在高风险小区，在日志中打印小区信息，更新word context
            self.log_text_field_update(f"已完成项目[{evaluate_project_name}]数据出场高风险小区评估，未发现高风险小区。")
            docx_template_render_context["eval_result_high_risk_summary"] = [f'经过评估，本项目（{evaluate_project_name}）不存在数据出场高风险小区。']


        if outer_cgi_list:
            outer_cgi_remove_plmn_list_pair = self.data_util.cgi_list_remove_plmn_return_pair(outer_cgi_list)

            for outer_cgi_remove_plmn_pair in outer_cgi_remove_plmn_list_pair:
                if outer_cgi_remove_plmn_pair[1] not in evaluate_project_cgi_remove_plmn_list:
                    middle_risk_cgi_list.append(outer_cgi_remove_plmn_pair[0])

        # 基于中风险小区列表获取小区信息
        if middle_risk_cgi_list:
            middle_risk_bts_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('宏站扇区图层',
                                                                                           middle_risk_cgi_list)
            middle_risk_dbs_cell_info_list = self.qgs_canvas_util.get_sector_info_from_layer('室分扇区图层',
                                                                                           middle_risk_cgi_list)

            # 存在中风险小区，在日志中打印小区信息，更新word context
            if middle_risk_bts_cell_info_list or middle_risk_dbs_cell_info_list:
                self.log_text_field_update(f"已完成项目[{evaluate_project_name}]数据出场中风险小区评估")
                self.log_text_field_update(
                    f"共识别中风险小区{len(middle_risk_bts_cell_info_list) + len(middle_risk_dbs_cell_info_list)}个，建议加入该项目小区总表：",
                    2)
                docx_template_render_context["eval_result_middle_risk_summary"] = [
                    f'经过评估，本项目（{evaluate_project_name}）存在数据出场中风险小区，其中宏站（含小微站）{len(middle_risk_bts_cell_info_list)}个，室分{len(middle_risk_dbs_cell_info_list)}个。',
                    '涉及小区详表如下:']
                docx_template_render_context["eval_result_middle_risk_conclusion"] = []
                if middle_risk_dbs_cell_info_list:
                    dbs_cell_text = ", ".join(
                        [f"{middle_risk_dbs_cell_info['小区名']}" for middle_risk_dbs_cell_info in
                         middle_risk_dbs_cell_info_list])
                    self.log_text_field_update(dbs_cell_text, 2)
                    docx_template_render_context["eval_result_middle_risk_conclusion"].append(
                        f'对于中风险室分小区：{dbs_cell_text}，如项目终端存在进入室分覆盖区域的可能性，建议直接将以上小区纳入项目')
                if middle_risk_bts_cell_info_list:
                    bts_cell_26 = [item["小区名"] for item in middle_risk_bts_cell_info_list if item["频段"] == "2.6G"]
                    bts_cell_other = [item["小区名"] for item in middle_risk_bts_cell_info_list if
                                      item["频段"] != "2.6G"]
                    if bts_cell_26:
                        bts_cell_text_26 = ", ".join([f"{item}" for item in bts_cell_26])
                        docx_template_render_context["eval_result_middle_risk_conclusion"].append(
                            f'对于中风险宏站2.6G小区：{bts_cell_text_26}，建议基于该小区的实际覆盖区域，以及终端的运行路线/摆放位置，按需将以上小区纳入项目。')
                    else:
                        bts_cell_text_26 = ''
                    if bts_cell_other:
                        bts_cell_text_other = ", ".join([f"{item}" for item in bts_cell_other])
                        docx_template_render_context["eval_result_middle_risk_conclusion"].append(
                            f'对于中风险宏站700M或4.9G小区：{bts_cell_text_other}，在基于该小区的实际覆盖区域，以及终端的运行路线/摆放位置的基础上，同时考虑该项目投放终端的频段支持情况，按需接将以上小区纳入项目。')
                    else:
                        bts_cell_text_other = ''
                    self.log_text_field_update(bts_cell_text_26 + bts_cell_text_other, 2)

                docx_template_render_context[
                    "eval_result_middle_risk_table"] = middle_risk_bts_cell_info_list + middle_risk_dbs_cell_info_list

            # 基于中风险CGI list生成图层，并截图放入word
            self.qgs_canvas_util.add_temp_sector_layer_in_canvas('临时扇区图层', middle_risk_cgi_list, {
                "color": "125,255,0,255",
                "outline_color": "255,255,0,255",
                "outline_style": "solid",
                "outline_width": "0.5",
                "outline_width_unit": "MM",
                "style": "solid",
            })
            self.mapCanvas.setExtent(self.qgs_canvas_util.get_all_in_extend_by_two_extends(self.mapCanvas.extent(),self.qgs_canvas_util.get_expanded_extend_by_layer('临时扇区图层')))
            self.mapCanvas.refresh()
            docx_template_render_context["eval_result_middle_risk_conclusion"].append(
                f'中风险小区分布图如下：')
            image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
            docx_template_render_context["middle_risk_sector_image"] = docxtpl.InlineImage(docx_template,
                                                                                         BytesIO(image_data),
                                                                                         width=Mm(140))
        else:
            # 不存在中风险小区，在日志中打印小区信息，更新word context
            self.log_text_field_update(f"已完成项目[{evaluate_project_name}]数据出场中风险小区评估，未发现中风险小区。")
            docx_template_render_context["eval_result_middle_risk_summary"] = [
                f'经过评估，本项目（{evaluate_project_name}）不存在数据出场中风险小区。']

        # 反向评估，看项目2B总表中的小区哪些距离项目超过3倍最大气泡半径，纳入置信度中的冗余小区，超过5倍的纳入高冗余，将这些小区再生成一个蓝色图层，放入地图中，截图，做成表格，把距离也放进去
        intersects_cgi_remove_plmn_list = []
        outer_cgi_remove_plmn_list = []
        if intersects_cgi_remove_plmn_list_pair:
            intersects_cgi_remove_plmn_list = [item[1] for item in intersects_cgi_remove_plmn_list_pair]
        if outer_cgi_remove_plmn_list_pair:
            outer_cgi_remove_plmn_list = [item[1] for item in outer_cgi_remove_plmn_list_pair]

        project_redundancy_possible_cgi_list_pair = []

        for evaluate_project_cgi_remove_plmn_pair in evaluate_project_cgi_remove_plmn_list_pair:
            if evaluate_project_cgi_remove_plmn_pair[1] not in intersects_cgi_remove_plmn_list and evaluate_project_cgi_remove_plmn_pair[1] not in outer_cgi_remove_plmn_list:
                project_redundancy_possible_cgi_list_pair.append(evaluate_project_cgi_remove_plmn_pair)

        # 存在冗余小区可能性
        if project_redundancy_possible_cgi_list_pair:
            project_redundancy_possible_cgi_list = [item[0] for item in project_redundancy_possible_cgi_list_pair]
            features_bts = self.qgs_canvas_util.get_sector_feature_include_geometry_from_layer('宏站扇区图层', project_redundancy_possible_cgi_list,True)
            features_dbs = self.qgs_canvas_util.get_sector_feature_include_geometry_from_layer('室分扇区图层',
                                                                                               project_redundancy_possible_cgi_list,
                                                                                               True)
            features = features_bts + features_dbs
            
            # 先将小区与工参对比，看是否有退网的
            project_redundancy_cgi_already_deleted = []
            match_cgi_list = [feature['唯一标识'] for feature in features]
            match_cgi_list_remove_plmn = self.data_util.cgi_list_remove_plmn_return_list(match_cgi_list)
            for project_redundancy_possible_cgi_pair in project_redundancy_possible_cgi_list_pair:
                if project_redundancy_possible_cgi_pair[1] not in match_cgi_list_remove_plmn:
                    project_redundancy_cgi_already_deleted.append(project_redundancy_possible_cgi_pair[0])
            if project_redundancy_cgi_already_deleted:
                docx_template_render_context[
                    "eval_cgi_already_deleted_table"] = self.sql_util.get_cell_detail_by_cgi(self.conn,project_redundancy_cgi_already_deleted)
                docx_template_render_context["eval_cgi_already_deleted_summary"] = [
                    f'经过评估，本项目（{evaluate_project_name}）下属的{len(project_redundancy_cgi_already_deleted)}个小区中存在疑似退网情况，需要根军改小区实际在网情况评估是否调出该项目。',
                    '涉及小区详表如下:']
            else:
                # 不存在已退网小区，在日志中打印小区信息，更新word context
                docx_template_render_context["eval_cgi_already_deleted_summary"] = [
                    f'经过评估，本项目（{evaluate_project_name}）当前下属小区均正常在网，不存在已退网情况。']


            #feature_redundancy_sector = []
            eval_result_redundancy_table_data = []
            eval_result_redundancy_cgi_list = []
            for feature in features:
                geom = feature.geometry()
                geom.transform(self.qgs_canvas_util.transformer_4326_to_32650)
                distance = self.qgs_canvas_util.get_distance_from_polygon_to_project(geom,evaluate_project_name)
                if distance > (max_bubble_size*3):
                    #feature_redundancy_sector.append(feature)
                    eval_result_redundancy_table_data.append({'唯一标识':feature['唯一标识'],'基站号':feature['基站号'],'小区名':feature['小区名'],'站型':feature['站型'],'行政区':feature['行政区'],'频段':feature['频段'],'带宽':feature['带宽'],'距离':format(distance/1000, '.2f')})
                    eval_result_redundancy_cgi_list.append(feature['唯一标识'])

            if eval_result_redundancy_table_data:
                docx_template_render_context["eval_result_redundancy_summary"] = [
                    f'经过评估，本项目（{evaluate_project_name}）存在{len(eval_result_redundancy_table_data)}个冗余小区',
                    '涉及小区详表如下:']
                docx_template_render_context["eval_result_redundancy_conclusion"] = [f'对于以上小区，请基于周边网络覆盖情况、当前项目所属终端的实际小区占用以及项目合同的条款明细评估是否可调出该项目。']
                docx_template_render_context[
                    "eval_result_redundancy_table"] = eval_result_redundancy_table_data
                # 基于中风险CGI list生成图层，并截图放入word
                self.qgs_canvas_util.add_temp_sector_layer_in_canvas('临时扇区图层', eval_result_redundancy_cgi_list, {
                    "color": "255,0,0,255",
                    "outline_color": "255,0,0,255",
                    "outline_style": "solid",
                    "outline_width": "0.5",
                    "outline_width_unit": "MM",
                    "style": "solid",
                })
                self.mapCanvas.setExtent(self.qgs_canvas_util.get_all_in_extend_by_two_extends(self.mapCanvas.extent(),
                                                                                               self.qgs_canvas_util.get_expanded_extend_by_layer(
                                                                                                   '临时扇区图层')))
                self.mapCanvas.refresh()
                docx_template_render_context["eval_result_redundancy_conclusion"].append(
                    f'冗余小区分布图如下：')
                image_data = self.qgs_canvas_util.get_screenshot_from_map_canvas(300)
                docx_template_render_context["redundancy_sector_image"] = docxtpl.InlineImage(docx_template,
                                                                                               BytesIO(image_data),
                                                                                               width=Mm(140))

            else:
                docx_template_render_context["eval_result_redundancy_summary"] = [
                    f'经过评估，本项目（{evaluate_project_name}）不存在冗余风险小区。']

        else:
            docx_template_render_context["eval_cgi_already_deleted_summary"] = [
                f'经过评估，本项目（{evaluate_project_name}）当前下属小区均正常在网，不存在已退网情况。']
            docx_template_render_context["eval_result_redundancy_summary"] = [
                f'经过评估，本项目（{evaluate_project_name}）不存在冗余风险小区。']

        # 做一个word模板，将项目情况，正反向评估结果进行输出
        existing_project_eval_docx_return_val = self.io_util.docxtpl_docx_output_handler(docx_template, docx_template_render_context,
                                                               self.existing_project_eval_docx_save_path,
                                                               f'ToB项目评估报告-{evaluate_project_name}')
        if not existing_project_eval_docx_return_val:
            self.log_text_field_update(f"已完成项目评估报告输出")
        else:
            self.log_text_field_update(existing_project_eval_docx_return_val,4)

    def find_project_item_in_project_tree_by_name(self,project_name):
        root = self.projectTreeWidget.invisibleRootItem()
        for j in range(root.childCount()):
            item = root.child(j)  # 仅获取第一层子节点（直接子项）
            if project_name == item.text(0):
                return item  # 设置点选状态
        return None




if __name__ == '__main__':
    """
    主函数
    """
    QgsApplication.setPrefixPath('qgis', True)
    app = QgsApplication([], True)
    app.initQgis()
    mainWindow = MainWindow()
    mainWindow.post_init_no_pyqt_widget()
    mainWindow.show()
    mainWindow.load_init_layer()
    mainWindow.init_project_tree_widget()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
    app.setWindowIcon(QIcon("resources/logo/LOGO.png"))
    app.exec()
    app.exitQgis()