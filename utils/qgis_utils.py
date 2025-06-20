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

import math

from PyQt6.QtCore import Qt, QBuffer, QIODevice, QVariant, QTimer, pyqtSignal, QEventLoop, QSize
from PyQt6.QtGui import QImage, QPainter, QColor, QFont
from PyQt6.QtWidgets import QTableWidgetItem, QMainWindow, QMessageBox
from qgis._core import QgsMapLayer, QgsExpression, QgsFeatureRequest, QgsVectorLayer, QgsField, QgsFeature, \
    QgsSimpleFillSymbolLayer, QgsFillSymbol, QgsSingleSymbolRenderer, QgsSpatialIndex, QgsCoordinateTransform, \
    QgsCoordinateReferenceSystem, QgsGeometry, QgsRectangle, QgsPointXY, QgsPalLayerSettings, QgsTextFormat, \
    QgsTextBufferSettings, QgsVectorLayerSimpleLabeling, QgsDistanceArea, QgsWkbTypes, QgsUnitTypes, QgsFields
from qgis._gui import QgsVertexMarker, QgsMapTool, QgsRubberBand, QgsMapToolEmitPoint, QgsMapToolPan, QgsMapToolIdentify

from utils.data_utils import DataUtils
from utils.sqlite_utils import SqliteUtils


class CustomAzimuthMeasurementTool(QgsMapTool):
    def __init__(self, mainWindow, qgsProjectInstance):
        super().__init__(mainWindow.mapCanvas)
        self.mainWindow = mainWindow
        self.mapCanvas = mainWindow.mapCanvas
        self.qgsProjectInstance = qgsProjectInstance

        self.point = None
        self.point_marker = None

        self.tempRubberBand = QgsRubberBand(self.mapCanvas, QgsWkbTypes.LineGeometry)
        self.tempRubberBand.setColor(QColor(255, 255, 0, 200))  # 稍深的半透明红色
        self.tempRubberBand.setWidth(3)
        self.north_angle = 0

    def drawPoint(self, point):
        """绘制点击的点"""
        if self.point_marker:
            self.reset()
        else:
            self.point_marker = QgsRubberBand(self.mapCanvas, QgsWkbTypes.PointGeometry)
            self.point_marker.setColor(QColor(0, 255, 0, 200))
            self.point_marker.setIconSize(8)
            self.point_marker.setIcon(QgsRubberBand.ICON_CIRCLE)
            self.point_marker.addPoint(point)
            self.north_line = self.drawNorthLine(point)

    def reset(self):
        if self.point_marker:
            self.point_marker.reset(QgsWkbTypes.PointGeometry)
            self.north_line.reset(QgsWkbTypes.LineGeometry)
            self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
            self.point = None
            self.point_marker = None
            self.mainWindow.statusbar_message_update("", -1, 'lightBlue')
            self.mainWindow.log_text_field_update(f"测量方位角: {self.north_angle:.2f} 度", 2)

    def deactivate(self):
        """工具停用处理"""
        self.reset()
        super().deactivate()


    def canvasPressEvent(self, e):
        """处理鼠标点击事件"""
        # 获取点击位置
        self.point = self.toMapCoordinates(e.pos())

        # 绘制点击的点
        self.drawPoint(self.point)

    def canvasMoveEvent(self, e):
        """处理鼠标移动事件"""
        self.current_point = self.toMapCoordinates(e.pos())
        if self.point:
            if self.point != self.current_point:
                self.calculateAzimuth()

            # 更新临时橡皮筋线，显示从最后一个固定点到当前鼠标位置的连线
            self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)

            self.tempRubberBand.addPoint(self.point)  # 最后一个固定点
            self.tempRubberBand.addPoint(self.current_point)  # 当前鼠标位置

    def drawNorthLine(self, point):
        """绘制以给定点为起点的正北方向参考线"""
        # 计算正北方向线上的另一个点（向上一定距离）
        # 使用与当前地图视图大致匹配的长度
        extent = self.mapCanvas.extent()
        length = (extent.height() + extent.width()) / 8  # 取地图范围的1/8作为长度
        # 正北方向：x不变，y增加
        north_point = QgsPointXY(point.x(), point.y() + length)

        north_line_color = QColor(0, 255, 0, 150)  # 绿色半透明
        self.north_line_style = {
            'color': north_line_color,
            'width': 3,
            'style': Qt.PenStyle.DashLine  # 虚线样式
        }
        # 创建虚线橡皮筋线
        north_line = QgsRubberBand(self.mapCanvas, QgsWkbTypes.LineGeometry)
        north_line.setColor(self.north_line_style['color'])
        north_line.setWidth(self.north_line_style['width'])
        # 设置虚线样式
        north_line.setLineStyle(Qt.PenStyle.DashLine)  # 修改此处
        # 添加线段点
        north_line.addPoint(point)
        north_line.addPoint(north_point)
        return north_line

    def calculateAzimuth(self):
        """计算并显示两点连线与正北方向的夹角"""

        # 计算线段方向（从p1到p2）
        dx = self.current_point.x() - self.point.x()
        dy = self.current_point.y() - self.point.y()

        # 计算与正东方向的夹角（弧度）
        angle_rad = math.atan2(dy, dx)

        # 转换为与正北方向的夹角（顺时针，0-360度）
        self.north_angle = 90 - math.degrees(angle_rad)
        if self.north_angle < 0:
            self.north_angle += 360

        # 保留两位小数
        self.north_angle = round(self.north_angle, 2)

        self.mainWindow.statusbar_message_update(f"测量方位角: {self.north_angle:.2f} 度", 0, 'yellow')

class CustomDistanceTool(QgsMapTool):
    """距离测量工具类，处理地图上的点击事件并计算距离"""

    def __init__(self, mainWindow, qgsProjectInstance):
        super().__init__(mainWindow.mapCanvas)
        self.mainWindow = mainWindow
        self.mapCanvas = mainWindow.mapCanvas
        self.qgsProjectInstance = qgsProjectInstance
        self.rubberBand = QgsRubberBand(self.mapCanvas, QgsWkbTypes.LineGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))  # 半透明红色
        self.rubberBand.setWidth(3)

        self.tempRubberBand = QgsRubberBand(self.mapCanvas, QgsWkbTypes.LineGeometry)
        self.tempRubberBand.setColor(QColor(255, 255, 0, 150))  # 稍深的半透明红色
        self.tempRubberBand.setWidth(3)

        self.reset()

        # 用于计算距离的对象
        self.distance = QgsDistanceArea()
        self.distance.setEllipsoid('WGS84')  # 设置为WGS84椭球体

        self.distance.setSourceCrs(
            self.mapCanvas.mapSettings().destinationCrs(),
            qgsProjectInstance.transformContext()
        )

    def reset(self):
        """重置测量工具状态"""
        self.points = []
        self.rubberBand.reset(QgsWkbTypes.LineGeometry)
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
        self.total_distance = 0

    def canvasPressEvent(self, e):
        """处理鼠标点击事件"""
        if e.button() == Qt.MouseButton.LeftButton:
            point = self.toMapCoordinates(e.pos())
            self.points.append(point)

            # 添加点到橡皮筋线
            self.rubberBand.addPoint(point, True)
            self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)

            # 计算并显示距离
            if len(self.points) > 1:
                # 计算两点之间的距离
                segment_distance = self.distance.measureLine(self.points[-2], self.points[-1])
                self.total_distance += segment_distance
                # 更新日志显示
                self.mainWindow.log_text_field_update(f"当前线段: {segment_distance:.2f} 米，总距离: {self.total_distance:.2f} 米", 2)
        else:
            self.finish_measure()

    def canvasMoveEvent(self, e):
        """处理鼠标移动事件"""
        if not self.points:
            return

        # 获取鼠标当前位置
        current_point = self.toMapCoordinates(e.pos())
        temp_distance = self.distance.measureLine(current_point, self.points[-1])
        self.mainWindow.statusbar_message_update(f"当前线段: {temp_distance:.2f} 米，总距离: {self.total_distance+temp_distance:.2f} 米", 0, 'yellow')

        # 更新临时橡皮筋线，显示从最后一个固定点到当前鼠标位置的连线
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)

        if self.points:
            self.tempRubberBand.addPoint(self.points[-1])  # 最后一个固定点
            self.tempRubberBand.addPoint(current_point)  # 当前鼠标位置

    def canvasDoubleClickEvent(self, e):
        """处理鼠标双击事件"""
        self.finish_measure()


    def deactivate(self):
        """工具停用处理"""
        # 清除所有橡皮筋线
        self.rubberBand.reset(QgsWkbTypes.LineGeometry)
        self.tempRubberBand.reset(QgsWkbTypes.LineGeometry)
        self.mainWindow.statusbar_message_update("", -1, 'lightBlue')
        super().deactivate()

    def finish_measure(self):
        if len(self.points) > 1:
            display_total = self.distance.convertLengthMeasurement(
                self.total_distance, QgsUnitTypes.DistanceMeters
            )
            self.mainWindow.statusbar_message_update(f"测量完成 - 总距离: {display_total:.2f} 米", 5000, 'lightBlue')
            self.mainWindow.log_text_field_update(f"测量完成 - 总距离: {display_total:.2f} 米",2)

        # 重置并停用工具
        self.reset()
        #self.mapCanvas.unsetMapTool(self)

# 定义子类，继承自 QgsMapToolIdentify
class CustomIdentifyTool(QgsMapToolIdentify):
    """
    QGIS查看信息工具，继承后重写该类的canvasPressEvent方法
    """
    def __init__(self, mainWindow, qgsProjectInstance):
        super().__init__(mainWindow.mapCanvas)  # 调用父类构造函数
        self.mainWindow = mainWindow
        self.mapCanvas = mainWindow.mapCanvas
        self.tableWidgetDetailTable = mainWindow.tableWidgetDetailTable
        self.projectTreeWidget = mainWindow.projectTreeWidget
        self.qgsProjectInstance = qgsProjectInstance

    # 重写 canvasReleaseEvent 方法
    def canvasPressEvent(self, event):
        # 清除之前的选择
        for layer in self.qgsProjectInstance.mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                layer.removeSelection()
        self.mapCanvas.refresh()
        layers_to_identify = []
        # 遍历所有图层，不提供行政区和卫星底图的查询功能
        for layer in self.mapCanvas.layers():
            if (layer.name() != '行政区') and ('底图' not in layer.name()) and ('临时1' not in layer.name()):
                layers_to_identify.append(layer)
        results = self.identify(event.x(), event.y(), layers_to_identify,QgsMapToolIdentify.LayerSelection)

        if len(results) > 0:

            identified_feature = results[0].mFeature
            layer = results[0].mLayer

            # 选中该要素
            layer.select(identified_feature.id())

            # 获取要素的属性
            attributes = identified_feature.attributes()
            fields = layer.fields()

            # 判断获取到的要素是否为项目图层，如果是改变flag，后面用于判断搜索
            identify_result_is_tob_project = False
            if "ToB项目图层" in str(results[0].mLayer.name()):
                identify_result_is_tob_project = True

            # 将要素的attr写入tableWidgetDetailTable，同时判断如果是项目图层，则同步点选对应tree中的item
            self.tableWidgetDetailTable.setRowCount(len(attributes))
            self.mainWindow.log_text_field_update(f"当前选择[{attributes[0]}]，已更新详情信息")
            for i, attr in enumerate(attributes):
                field_name = fields[i].name()
                if identify_result_is_tob_project and field_name == "项目名称":
                    root = self.projectTreeWidget.invisibleRootItem()
                    for j in range(root.childCount()):
                        item = root.child(j)  # 仅获取第一层子节点（直接子项）
                        if attr == item.text(0):
                            item.setSelected(True)  # 设置点选状态
                        else:
                            item.setSelected(False)
                table_cell_item = QTableWidgetItem(str(field_name))
                table_cell_item.setToolTip(str(field_name))
                self.tableWidgetDetailTable.setItem(i, 0, table_cell_item)
                table_cell_item = QTableWidgetItem(str(attr))
                table_cell_item.setToolTip(str(attr))
                self.tableWidgetDetailTable.setItem(i, 1, table_cell_item)

        else:
            self.mainWindow.statusbar_message_update('提示：未选中要素', 1000, 'lightBlue')



class CustomPolygonMapTool(QgsMapToolEmitPoint):
    """自定义多边形绘制工具"""
    def __init__(self, mapCanvas, layer):
        super().__init__(mapCanvas)
        self.mapCanvas = mapCanvas
        self.layer = layer
        self.points = []
        self.markers = []
        self.rubber_band = QgsRubberBand(mapCanvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 100))
        self.rubber_band.setWidth(2)
        self.reset()

    def reset(self):
        """重置工具状态"""
        self.points = []
        for marker in self.markers:
            self.mapCanvas.scene().removeItem(marker)
        self.markers = []
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, event):
        """处理鼠标按下事件"""
        point = self.toMapCoordinates(event.pos())

        if event.button() == Qt.LeftButton:
            # 添加顶点
            self.add_point(point)
        elif event.button() == Qt.RightButton:
            # 完成多边形
            if len(self.points) >= 3:
                self.create_polygon()
            else:
                QMessageBox.warning(None, "警告", "多边形至少需要3个顶点")
            self.reset()
            self.mapCanvas.unsetMapTool(self)

    def add_point(self, point):
        """添加点到多边形"""
        self.points.append(point)

        # 添加顶点标记
        marker = QgsVertexMarker(self.mapCanvas)
        marker.setCenter(point)
        marker.setColor(QColor(255, 0, 0))
        marker.setIconSize(5)
        marker.setIconType(QgsVertexMarker.ICON_CROSS)
        marker.setPenWidth(2)
        self.markers.append(marker)

        # 更新橡皮筋多边形
        self.update_rubber_band()

    def update_rubber_band(self):
        """更新橡皮筋多边形显示"""
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)

        for point in self.points:
            self.rubber_band.addPoint(point)

        # 如果有足够的点，闭合多边形
        if len(self.points) >= 2:
            self.rubber_band.addPoint(self.points[0])  # 闭合多边形

    def create_polygon(self):
        """创建多边形要素并添加到图层"""
        if len(self.points) < 3:
            return

        # 创建多边形几何
        polygon_geometry = QgsGeometry.fromPolygonXY([self.points])

        # 添加到图层
        feature = QgsFeature()
        feature.setGeometry(polygon_geometry)
        feature.setFields(self.layer.fields())

        field_names = [field.name() for field in self.layer.fields()]
        if "名称" in field_names:
            name_index = field_names.index("名称")
            attributes = [None] * len(field_names)
            attributes[name_index] = "评估项目边界"
            feature.setAttributes(attributes)

            # 开始编辑会话
        if not self.layer.isEditable():
            self.layer.startEditing()

        # 添加要素
        self.layer.addFeature(feature)

        # 提交更改
        self.layer.commitChanges()

        # 刷新地图
        self.mapCanvas.refresh()

        QMessageBox.information(None, "成功", "已完成项目图层绘制")

        self.toolPan = QgsMapToolPan(self.mapCanvas)
        self.mapCanvas.setMapTool(self.toolPan)


    def deactivate(self):
        """工具停用处理"""
        # 清除所有标记和橡皮筋
        self.reset()
        super().deactivate()


class QGISCanvasUtils(QMainWindow):

    # 因为气泡扩张算法用到了异步调用，需要配置信号与槽，用于接收方法结束后的数据
    bubble_expand_finished_signal = pyqtSignal(str, int, list, list)

    def __init__(self, mainWindow, qgsProjectInstance, conn):
        super().__init__(mainWindow)
        self.mainWindow = mainWindow
        self.mapCanvas = mainWindow.mapCanvas
        self.qgsProjectInstance = qgsProjectInstance
        self.conn = conn
        self.bubbleExpandTimer = QTimer(self.mainWindow)
        self.layerFlashTimer = QTimer(self)
        self.bubble_expand_finished_signal_connected = False
        self.data_util = DataUtils()
        self.sql_util = SqliteUtils()
        self.transformer_4326_to_3857 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                                          QgsCoordinateReferenceSystem("EPSG:3857"), self.qgsProjectInstance)
        self.transformer_3857_to_4326 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:3857"),
                                                          QgsCoordinateReferenceSystem("EPSG:4326"), self.qgsProjectInstance)
        self.transformer_3857_to_32650 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:3857"),
                                                               QgsCoordinateReferenceSystem("EPSG:32650"),
                                                               self.qgsProjectInstance)
        self.transformer_4326_to_32650 = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                                               QgsCoordinateReferenceSystem("EPSG:32650"),
                                                               self.qgsProjectInstance)

    # 基于给定的sector_cgi_list，搜索宏站和室分图层中所有的匹配元素，并进行高亮
    def add_temp_sector_layer_in_canvas(self, layer_name, sector_cgi_list, properties_fill, zoom_to_layer=False):
        """
        基于给定的sector_cgi_list，搜索宏站和室分图层中所有的匹配元素，并进行高亮
        :param layer_name: 临时图层名称
        :type layer_name: str
        :param sector_cgi_list:需要高亮的CGI列表
        :type sector_cgi_list: list[str]
        :param properties_fill: 扇区渲染样式表，形如properties_fill = {
                        "color": "235,200,0, 40",
                        "outline_color": "235,80,0,255",
                        "outline_style": "dash",
                        "outline_width": "0.1",
                        "outline_width_unit": "MM",
                        "style": "dense3",
                    }
        :param zoom_to_layer: 是否缩放至该图层所在区域
        :type zoom_to_layer: bool
        :return: None
        """
        self.del_layer_by_name(layer_name)

        layer_bts = self.qgsProjectInstance.mapLayersByName("宏站扇区图层")[0]
        layer_dbs = self.qgsProjectInstance.mapLayersByName("室分扇区图层")[0]

        temp_sector_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:3857", layer_name,
                                           "memory")
        temp_sector_layer.setCrs(layer_bts.crs())
        provider_cell = temp_sector_layer.dataProvider()

        symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
        symbol = QgsFillSymbol()
        quoted_cgi = [f"'{sector_cgi}'" for sector_cgi in sector_cgi_list]
        expression = QgsExpression(f'"唯一标识" IN ({", ".join(quoted_cgi)})')
        request = QgsFeatureRequest(expression)
        features_bts = list(layer_bts.getFeatures(request))
        features_dbs = list(layer_dbs.getFeatures(request))
        if features_bts:
            provider_cell.addFeatures(features_bts)
            temp_sector_layer.commitChanges()
        if features_dbs:
            provider_cell.addFeatures(features_dbs)
            temp_sector_layer.commitChanges()
        symbol.deleteSymbolLayer(0)
        symbol.appendSymbolLayer(symbol_layer.clone())
        renderer = QgsSingleSymbolRenderer(symbol)
        temp_sector_layer.setRenderer(renderer)
        self.qgsProjectInstance.addMapLayer(temp_sector_layer)
        if zoom_to_layer:
            self.mapCanvas.setExtent(self.get_expanded_extend_by_layer(layer_name))
            self.mapCanvas.refresh()

    # 出现一个标志，可以自定义样式，闪烁次数，持续时间
    def add_marker_in_canvas(self, lon, lat, interval=1000, blink_times=10, marker_type=QgsVertexMarker.ICON_X):
        """
        出现一个标志，可以自定义样式，闪烁次数，持续时间
        :param lon: 经度
        :type lon: flat
        :param lat: 纬度
        :type lat: flat
        :param interval: 闪烁间隔ms，默认1秒（1000）
        :type interval: int
        :param blink_times: 闪烁次数，想一次性显示可把blink_times设为1
        :type blink_times: int
        :param marker_type: ICON_CROSS、ICON_X、ICON_BOX、ICON_CIRCLE、ICON_DOUBLE_TRIANGLE、ICON_TRIANGLE、ICON_RHOMBUS..
        :type marker_type: enumerate
        :return: marker_to_add
        :rtype: QgsVertexMarker
        """
        marker_to_add = QgsVertexMarker(self.mapCanvas)
        point_4326 = QgsPointXY(lon, lat)
        point_3857 = self.transformer_4326_to_3857.transform(point_4326)
        # cord_trans = self.mainWindow.cord_trans_4326_to_3857(lon, lat)
        marker_to_add.setCenter(point_3857)
        marker_to_add.setColor(QColor(255, 0, 0))  # 红色
        marker_to_add.setIconSize(15)
        marker_to_add.setIconType(marker_type)
        marker_to_add.setPenWidth(2)  # 线条宽度
        marker_to_add.show()
        current_blink = 0
        visible = True

        def blink():
            nonlocal current_blink, visible
            current_blink += 1
            # 切换标记可见性
            visible = not visible
            marker_to_add.setVisible(visible)

            # 达到指定闪烁次数后停止并移除标记
            if current_blink >= blink_times * 2:  # 一次完整的闪烁包括显示和隐藏
                timer.stop()
                self.mapCanvas.scene().removeItem(marker_to_add)

        timer = QTimer(self.mainWindow)
        timer.timeout.connect(blink)
        timer.start(interval // 2)
        return marker_to_add

    # 气泡扩张算法主函数，根据输入的项目信息，通过气泡扩张获取区域内和区域周边的主服务小区列表
    def algorithm_bubble_expand(self, evaluate_project_name, new_project_flag, bubble_step=40, max_bubble_size=3000):
        """
        气泡扩张算法主函数，根据输入的项目信息，通过气泡扩张获取区域内和区域周边的主服务小区列表
        :param evaluate_project_name: 评估的项目名称，如果是新项目，则不起作用
        :type evaluate_project_name: str
        :param new_project_flag: 是否为新项目，如果是老项目从现有图层中获取形状，如果是新项目则从固定图层中获取形状
        :type new_project_flag: bool
        :param bubble_step: 气泡的扩张步长，米
        :type bubble_step: int
        :param max_bubble_size: 气泡的最大半径，米
        :type max_bubble_size: int
        :return: 通过信号与槽反馈，连接MainWindow类中的bubble_expand_finished_signal信号，返回最大气泡半径（米），内部cgi和外部cgi列表
        :rtype: int, list, list
        """
        # 测试现网项目的数据出场评估
        self.mainWindow.log_text_field_update("开始调用气泡扩散算法")
        intersects_cgi = []
        intersects_cellid_without_plmn = []
        outer_cgi = []
        outer_cellid_without_plmn = []
        outer_group_id = []
        layer_bts = self.qgsProjectInstance.mapLayersByName("宏站扇区图层")[0]
        # layer_dbs = self.qgsProjectInstance.mapLayersByName("室分扇区图层")[0]

        # 先获取区域内所有的小区列表(仅对面状场景）
        evaluate_project_type = self.sql_util.get_project_type(self.conn, evaluate_project_name)

        if evaluate_project_type == 2 or new_project_flag:
            if new_project_flag:
                polygon_intersects_bts = self.get_polygon_intersects_another_polygon('宏站扇区图层', '临时多边形图层_新项目评估',
                                                                                     '名称',
                                                                                     '评估项目边界')
                polygon_intersects_dbs = self.get_polygon_intersects_another_polygon('室分扇区图层', '临时多边形图层_新项目评估',
                                                                                     '名称',
                                                                                     '评估项目边界')
            else:
                polygon_intersects_bts = self.get_polygon_intersects_another_polygon('宏站扇区图层', 'ToB项目图层_面', '项目名称',
                                                                                     evaluate_project_name)
                polygon_intersects_dbs = self.get_polygon_intersects_another_polygon('室分扇区图层', 'ToB项目图层_面', '项目名称',
                                                                                     evaluate_project_name)
            for bts in polygon_intersects_bts:
                if self.data_util.cgi_remove_plmn(bts['唯一标识']) and not self.data_util.cgi_is_cbn(bts['唯一标识']):
                    intersects_cgi.append(bts['唯一标识'])
                    intersects_cellid_without_plmn.append(self.data_util.cgi_remove_plmn(bts['唯一标识']))
            for dbs in polygon_intersects_dbs:
                if self.data_util.cgi_remove_plmn(dbs['唯一标识']) and not self.data_util.cgi_is_cbn(dbs['唯一标识']):
                    intersects_cgi.append(dbs['唯一标识'])
                    intersects_cellid_without_plmn.append(self.data_util.cgi_remove_plmn(dbs['唯一标识']))
            # 在边界生成点
            if new_project_flag:
                points = self.get_discrete_points_from_polygon_border('临时多边形图层_新项目评估', '名称',
                                                                      '评估项目边界', 100)
            else:
                points = self.get_discrete_points_from_polygon_border('ToB项目图层_面', '项目名称', evaluate_project_name, 100)
            #layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_面")[0]
        elif evaluate_project_type == 1:
            # 在线上生成点
            points = self.get_discrete_points_from_line('ToB项目图层_线', '项目名称', evaluate_project_name, 100)
            #layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_线")[0]
        else:
            # 将点图层转化为标准点格式
            points = self.get_discrete_points_from_points('ToB项目图层_点', '项目名称', evaluate_project_name)
            #layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_点")[0]

        if new_project_flag or self.set_canvas_extend_to_project(evaluate_project_name):
            # 基于点生成圆，每生成一次进行一次判定
            if points:
                self.mainWindow.log_text_field_update("已完成离散化处理")
                bubble_size = 0

                # print("bubble_size")
                # print(bubble_size)
                def bubble_expand():
                    nonlocal bubble_size
                    # print("bubble_size_inside")
                    # print(bubble_size)
                    # nonlocal outer_cellid_without_plmn
                    # 步长可调
                    bubble_size += bubble_step * 1.3
                    self.mainWindow.statusbar_message_update(
                        f"正在使用气泡扩散法分析扇区覆盖关系，已扩展项目边界{int(bubble_size / 1.3)}米。",
                        10000, 'lightgreen')
                    # 切换图层可见性
                    self.del_layer_by_name('临时气泡图层')
                    temp_circle_layer = QgsVectorLayer("Polygon?crs=EPSG:3857", '临时气泡图层', "memory")
                    provider = temp_circle_layer.dataProvider()
                    provider.addAttributes([QgsField('num', QVariant.String)])
                    temp_circle_layer.updateFields()
                    temp_circle_layer.startEditing()
                    features_temp_circle = []
                    for i, point in enumerate(points):
                        # 创建圆几何
                        circle = point.buffer(bubble_size, 36)
                        feature = QgsFeature()
                        feature.setGeometry(circle)
                        feature.setAttributes([i])
                        features_temp_circle.append(feature)

                    # 添加特征到图层
                    provider.addFeatures(features_temp_circle)
                    temp_circle_layer.updateExtents()

                    # 样式可以再多尝试一些
                    properties_fill = {
                        "color": "235,200,0, 40",
                        "outline_color": "235,80,0,255",
                        "outline_style": "dash",
                        "outline_width": "0.1",
                        "outline_width_unit": "MM",
                        "style": "dense3",
                    }
                    symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
                    symbol = QgsFillSymbol()
                    symbol.deleteSymbolLayer(0)
                    symbol.appendSymbolLayer(symbol_layer.clone())
                    renderer = QgsSingleSymbolRenderer(symbol)
                    temp_circle_layer.setRenderer(renderer)

                    # 添加图层到项目
                    self.qgsProjectInstance.addMapLayer(temp_circle_layer)
                    self.mapCanvas.refresh()

                    # 新建一个方法，与polygon_intersects类似，但是返回一个key是相交的小区号，value是相交的bubble num的list
                    cellid_bubble_intersect_dict = self.get_sector_dict_intersects_bubble('宏站扇区图层', '临时气泡图层')

                    # 判断返回的列表里，不属于inner cellid的部分，删除对应的bubble，同时将该ci加入列表中
                    bubble_to_del_num = []
                    for cgi_group_id in cellid_bubble_intersect_dict:
                        cgi, group_id = cgi_group_id.split(',', 1)
                        cellid = self.data_util.cgi_remove_plmn(cgi)
                        if not self.data_util.cgi_is_cbn(cgi):
                            if cellid not in intersects_cellid_without_plmn:
                                if cellid not in outer_cellid_without_plmn:
                                    # ci不在列表中，将ci添加进列表，然后删除气泡
                                    outer_cellid_without_plmn.append(cellid)
                                    outer_cgi.append(cgi)
                                    if group_id not in outer_group_id:
                                        outer_group_id.append(group_id)
                            # 不论在不在外部列表中，气泡都要删除，开始整理删除气泡的list
                            for bubble_num in cellid_bubble_intersect_dict[cgi_group_id]:
                                if int(bubble_num) not in bubble_to_del_num:
                                    bubble_to_del_num.append(int(bubble_num))
                    # 删除bubble
                    bubble_del_indices = sorted([i for i in bubble_to_del_num], reverse=True)
                    for idx in bubble_del_indices:
                        if 0 <= idx < len(points):  # 确保索引有效
                            del points[idx]

                    if bubble_size >= (max_bubble_size * 1.3) or points == []:
                        # 寻找所有外部ci的同groupid小区，判定不在内ci后也纳入列表并高亮
                        quoted_group_id = [f"'{outer_group_id_innertext}'" for outer_group_id_innertext in
                                           outer_group_id if not isinstance(outer_group_id_innertext, (int, float)) or outer_group_id_innertext > 0]
                        expression = QgsExpression(f'"Group ID" IN ({", ".join(quoted_group_id)})')
                        request = QgsFeatureRequest(expression)
                        features_bts = list(layer_bts.getFeatures(request))
                        if features_bts:
                            for feature in features_bts:
                                group_cgi = feature['唯一标识']  # 获取指定字段的值
                                if (group_cgi not in intersects_cgi) and (group_cgi not in outer_cgi) and (
                                not self.data_util.cgi_is_cbn(group_cgi)):
                                    outer_cgi.append(group_cgi)
                                    outer_cellid_without_plmn.append(self.data_util.cgi_remove_plmn(group_cgi))
                                    # print(f"添加了{group_cgi}")

                    # 将所有cellid高亮（可选，看下效率）
                    self.del_layer_by_name('临时扇区图层')
                    if not (intersects_cgi == [] and outer_cgi == []):
                        plmn_replace_cgi_list = []
                        for cgi in intersects_cgi:
                            plmn_replace_cgi_list.append(cgi.replace('460-08', '460-00'))
                        for cgi in outer_cgi:
                            plmn_replace_cgi_list.append(cgi.replace('460-08', '460-00'))
                        self.add_temp_sector_layer_in_canvas("临时扇区图层", plmn_replace_cgi_list, {
                            "color": "255,242,1,255",
                            "outline_style": "no",
                            "style": "dense1",
                        })

                    # 达到指定次数后恢复初始状态并停止定时器
                    if bubble_size >= (max_bubble_size * 1.3) or points == []:
                        # print(bubble_size)
                        self.del_layer_by_name('临时气泡图层')
                        self.bubbleExpandTimer.stop()
                        self.mainWindow.statusbar_message_update('已完成气泡扩散分析', 20000,
                                                      'lightgreen')
                        self.mainWindow.log_text_field_update(f"已完成气泡扩散算法，最终扩散距离{int(bubble_size/1.3)}米")

                        # print(intersects_cellid_without_plmn)
                        # print(intersects_cgi)
                        # print(outer_cellid_without_plmn)
                        # print(outer_cgi)
                        # print(outer_group_id)
                        self.bubble_expand_finished_signal.emit(evaluate_project_name, int(bubble_size / 1.3), intersects_cgi, outer_cgi)

                # 创建定时器
                try:
                    self.bubbleExpandTimer.timeout.disconnect()
                except TypeError:
                    # 若未连接任何槽函数，会抛出TypeError
                    # print('err')
                    pass
                self.bubbleExpandTimer.timeout.connect(bubble_expand)
                self.bubbleExpandTimer.start(100)
        else:
            self.mainWindow.statusbar_message_update("该项目未完成地理化呈现，无法进行分析")
            self.mainWindow.log_text_field_update("该项目未完成地理化呈现，无法进行分析", 4)

    # 对于给定的wkt字典组成的列表，根据已知的wkt格式，生成对应图层
    def create_layer_from_wkt(self, wkt_dict_list, wkt_type, layer_name):
        """
        对于给定的wkt字典组成的列表，根据已知的wkt格式，生成对应图层
        :param wkt_dict_list: wkt字典组成的列表，列表内每个元素为一个dict，该dict至少包含一个key为wkt的键值对
        :type wkt_dict_list: list
        :param wkt_type: 1.Point,2.LineString,3.Polygon,4.MultiPoint,5.MultiLineString,6.MultiPolygon建议仅使用4,5,6，对于1,2,3将无条件转化
        :type wkt_type: int
        :param layer_name: 输出图层的名称
        :type layer_name: str
        :return: layer_create_success_flag,成功创建图层返回True，否则返回False
        :rtype: int
        """
        layer_create_success_flag = False
        try:
            if wkt_type == 4:
                layer = QgsVectorLayer("MultiPoint?crs=EPSG:3857", layer_name, "memory")
            elif wkt_type == 5:
                layer = QgsVectorLayer("MultiLineString?crs=EPSG:3857", layer_name, "memory")
            elif wkt_type == 6:
                layer = QgsVectorLayer("MultiPolygon?crs=EPSG:3857", layer_name, "memory")
            elif wkt_type == 1:
                layer = QgsVectorLayer("Point?crs=EPSG:3857", layer_name, "memory")
            elif wkt_type == 2:
                layer = QgsVectorLayer("LineString?crs=EPSG:3857", layer_name, "memory")
            elif wkt_type == 3:
                layer = QgsVectorLayer("Polygon?crs=EPSG:3857", layer_name, "memory")
            else:
                return False

            provider = layer.dataProvider()
            fields_to_add = []
            for field_name in wkt_dict_list[0].keys() :
                if field_name != 'wkt':
                    fields_to_add.append(QgsField(field_name, QVariant.String))
            provider.addAttributes(fields_to_add)
            layer.updateFields()
            layer.startEditing()

            for wkt_dict in wkt_dict_list :
                geometry = QgsGeometry.fromWkt(wkt_dict['wkt'])
                if geometry.isEmpty() or not geometry.isGeosValid():
                    #print(f'无效的WKT格式或几何形状{wkt_dict['项目名称']}')
                    self.log_text_field_update(f'项目[{wkt_dict['项目名称']}]无法生成有效的WKT几何形状',2)
                    continue
                geometry.transform(self.transformer_4326_to_3857)

                feature = QgsFeature()
                feature.setGeometry(geometry)

                attributes = []
                for key in wkt_dict.keys():
                    if key != 'wkt':
                        attributes.append(str(wkt_dict[key]))
                #print(attributes)
                feature.setAttributes(attributes)
                provider.addFeature(feature)
                layer_create_success_flag = True

            layer.commitChanges()
            self.qgsProjectInstance.addMapLayer(layer)

            # 缩放到图层范围
            self.mapCanvas.setExtent(layer.extent())
            self.mapCanvas.refresh()
            return layer_create_success_flag

        except Exception as e:
            # 这里可以添加错误处理，例如显示错误消息框
            print(f"Error: {str(e)}")
            return layer_create_success_flag

    def create_temp_polygon_layer_in_canvas(self, layer_name):
        self.del_layer_by_name(layer_name)
        temp_polygon_layer = QgsVectorLayer("MultiPolygon?crs=EPSG:3857", layer_name,
                                           "memory")
        provider_temp_polygon_layer = temp_polygon_layer.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("ID", QVariant.Int))
        fields.append(QgsField("名称", QVariant.String))
        provider_temp_polygon_layer.addAttributes(fields)
        temp_polygon_layer.updateFields()
        properties_fill = {
            "color": "235,200,0, 140",
            "outline_color": "235,80,0,255",
            "outline_style": "dash",
            "outline_width": "0.1",
            "outline_width_unit": "MM",
            "style": "dense3",
        }
        symbol_layer = QgsSimpleFillSymbolLayer.create(properties_fill)
        symbol = QgsFillSymbol()
        symbol.deleteSymbolLayer(0)
        symbol.appendSymbolLayer(symbol_layer.clone())
        renderer = QgsSingleSymbolRenderer(symbol)
        temp_polygon_layer.setRenderer(renderer)
        self.qgsProjectInstance.addMapLayer(temp_polygon_layer)
        self.mainWindow.active_layer = temp_polygon_layer



    # 删除指定名称的图层
    def del_layer_by_name(self, name):
        """
        删除指定名称的图层
        :param name: 图层名称
        :type name: str
        :return: None
        """
        existing_temp_layers = self.qgsProjectInstance.mapLayersByName(name)
        if existing_temp_layers:
            for existing_temp_layer in existing_temp_layers:
                self.qgsProjectInstance.removeMapLayer(existing_temp_layer.id())


    # 图层闪烁
    def flash_layer_in_canvas(self, layer, times=3, interval=500):
        """
        图层闪烁
        :param layer: 传入图层
        :type layer: QgsVectorLayer
        :param times: 闪烁次数
        :type times: int
        :param interval:闪烁间隔
        :type interval: int
        :return: 定时器
        :rtype: QTimer
        """
        node = self.qgsProjectInstance.instance().layerTreeRoot().findLayer(layer.id())
        # 已闪烁次数
        flash_count = 0
        current_visibility = True

        def toggle_visibility():
            nonlocal flash_count
            nonlocal current_visibility
            flash_count += 1
            # 切换图层可见性
            current_visibility = not current_visibility
            node.setItemVisibilityChecked(current_visibility)
            # 达到指定次数后恢复初始状态并停止定时器
            if flash_count >= times * 2:  # 每次闪烁包含显示和隐藏两次切换
                self.layerFlashTimer.stop()
                node.setItemVisibilityChecked(True)

        # 创建定时器
        self.layerFlashTimer = QTimer(self)
        self.layerFlashTimer.timeout.connect(toggle_visibility)
        self.layerFlashTimer.start(interval)

    @staticmethod
    def get_all_in_extend_by_two_extends(extend1, extend2):
        """
        对于输入的两个边界，取最大范围，确保两个边界内的内容均可以显示
        :param extend1: 边界1
        :type extend1: QgsRectangle
        :param extend2: 边界2
        :type extend2: QgsRectangle
        :return: 新边界
        :rtype: QgsRectangle
        """
        return_bbox = QgsRectangle(
            min(extend1.xMinimum(), extend2.xMinimum()),
            min(extend1.yMinimum(), extend2.yMinimum()),
            max(extend1.xMaximum(), extend2.xMaximum()),
            max(extend1.yMaximum(), extend2.yMaximum())
        )
        return return_bbox

    def get_project_geometry_by_name(self,project_name):
        """
        根据项目名称，从3个项目图层中返回项目geometry，如果未匹配则返回空
        :param project_name:项目名称
        :type project_name:str
        :return:项目地理信息
        :rtype:QgsGeometry
        """
        project_layer_name_list = ['ToB项目图层_面',"ToB项目图层_线","ToB项目图层_点"]
        for project_layer_name in project_layer_name_list:
            layer = self.qgsProjectInstance.mapLayersByName(project_layer_name)[0]
            if layer:
                expression = QgsExpression(f'"项目名称" = \'{project_name}\'')
                request = QgsFeatureRequest(expression)
                features = list(layer.getFeatures(request))
                if features:
                    geometry = features[0].geometry()
                    return geometry
                else:
                    continue
        return None


    # 判定两个图层的相交部分，将source_polygon中与compare_polygon中相交的多边形的feature封装为一个list返回
    def get_polygon_intersects_another_polygon(self, layer_name_of_source_polygon, layer_name_of_compare_polygon,
                                               compare_polygon_col_name,
                                               compare_polygon_name):
        """
        判定两个图层的相交部分，将source_polygon中与compare_polygon中相交的多边形的feature封装为一个list返回
        :param layer_name_of_source_polygon: 需要判断的多边形图层名，从该图层挑选返回多边形
        :type layer_name_of_source_polygon:str
        :param layer_name_of_compare_polygon: 用于匹配的多边形图层名
        :type layer_name_of_compare_polygon:str
        :param compare_polygon_col_name:用于匹配的多边形图层中，如需要匹配单个图形，索引名称
        :type compare_polygon_col_name:str
        :param compare_polygon_name:用于匹配的多边形图层中，如需要匹配单个图形，该图形索引下对应的实际名称
        :type compare_polygon_name:str
        :return:source_polygon中与compare_polygon中相交的多边形的feature封装为一个list
        :rtype:list[QgsFeature]
        """
        # 打开图层
        layer_source_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_source_polygon)[0]
        layer_compare_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_compare_polygon)[0]

        # crs_trans_flag:用于compare图层0:无需转换、1：4326-3857、 2:3857-4326，最终使compare图层与source的crs相同
        if layer_source_polygon.crs().authid() == 'EPSG:4326' and layer_compare_polygon.crs().authid() == 'EPSG:3857':
            crs_trans_flag = 2
        elif layer_source_polygon.crs().authid() == 'EPSG:3857' and layer_compare_polygon.crs().authid() == 'EPSG:4326':
            crs_trans_flag = 1
        else:
            crs_trans_flag = 0

        if compare_polygon_name:
            expression = QgsExpression(f'"{compare_polygon_col_name}" = \'{compare_polygon_name}\'')
            request = QgsFeatureRequest(expression)
            features_compare = list(layer_compare_polygon.getFeatures(request))
        else:
            features_compare = layer_compare_polygon.getFeatures()

        # 建立快速索引
        spatial_index_source = QgsSpatialIndex(layer_source_polygon.getFeatures())

        feature_source_intersect_return = []
        for i, feature_compare in enumerate(features_compare):
            geometry_compare = feature_compare.geometry()
            if crs_trans_flag == 2:
                geometry_compare.transform(self.transformer_3857_to_4326)
            elif crs_trans_flag == 1:
                geometry_compare.transform(self.transformer_4326_to_3857)
            intersecting_source_ids = spatial_index_source.intersects(geometry_compare.boundingBox())
            # print(intersecting_source_ids)
            for j, intersecting_source_id in enumerate(intersecting_source_ids):
                feature_source = layer_source_polygon.getFeature(intersecting_source_id)
                geom_source = feature_source.geometry()
                if geom_source.intersects(geometry_compare):
                    feature_source_intersect_return.append(feature_source)
        return feature_source_intersect_return

    def get_screenshot_from_map_canvas(self, dpi=300):
        """
        对QgsMapCanvas进行截图并保存至内存
        :param dpi: 输出图片的DPI值
        :type dpi: int
        :return:图片二进制数据
        :rtype:bytes
        """
        def wait_for_render(timeout=2000):  # 超时时间默认为2000毫秒（2秒）
            """阻塞当前线程，直到地图渲染完成或超时"""
            loop = QEventLoop()
            timeout_occurred = False

            # 连接渲染完成信号
            self.mapCanvas.renderComplete.connect(loop.quit)

            # 设置定时器，超时后强制退出循环
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: setattr(loop, 'timeout_occurred', True) or loop.quit())
            timer.start(timeout)

            # 启动事件循环，阻塞线程
            loop.exec_()

            # 清理资源
            self.mapCanvas.renderComplete.disconnect(loop.quit)
            timer.stop()
            timer.timeout.disconnect()

        wait_for_render()
        self.mapCanvas.refresh()
        wait_for_render()

        # 获取地图画布的尺寸
        #size = self.mapCanvas.size()
        size = QSize(
            int(self.mapCanvas.size().width() * 1.5),
            int(self.mapCanvas.size().height() * 1.5))

        # 创建与画布尺寸匹配的QImage
        image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)

        # 设置图像的DPI
        image.setDotsPerMeterX(int(dpi * 100 / 2.54))
        image.setDotsPerMeterY(int(dpi * 100 / 2.54))

        # 用白色填充图像背景
        image.fill(Qt.GlobalColor.white)

        # 创建QPainter用于绘制图像
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 渲染地图画布到QPainter
        self.mapCanvas.render(painter)

        # 结束绘制
        painter.end()

        # # 保存图像
        # image.save(output_path)
        # print(f"截图已保存至: {output_path}")

        # 使用QBuffer将图像保存到内存
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "JPG")  # 使用PNG格式避免透明度丢失
        buffer.close()

        self.mainWindow.log_text_field_update("已复制当前画布图像")

        # 获取字节数据
        return buffer.data().data()



    # 根据输入的多边形（或multiPolygon），返回边界上每隔一定距离的一组点（使用该图层对应坐标系，如3857）
    def get_discrete_points_from_polygon_border(self, layer_name_of_polygon, polygon_col_name, polygon_name, point_interval):
        """
        根据输入的多边形（或multiPolygon），返回边界上每隔一定距离的一组点（使用该图层对应坐标系，如3857）
        :param layer_name_of_polygon: 图层名称
        :type layer_name_of_polygon: str
        :param polygon_col_name: 图层搜索列名（用于搜索多边形名称）
        :type polygon_col_name: str
        :param polygon_name: 图层中多边形名称
        :type polygon_name: str
        :param point_interval: 每个点的间距（单位大约相当于0.8米，例如400大约相当于320米）
        :type point_interval: int
        :return: 一组QgsPointXY点转化为的QgsGeometry
        :rtype:list[QgsGeometry]
        """
        layer = self.qgsProjectInstance.mapLayersByName(layer_name_of_polygon)[0]
        expression = QgsExpression(f'"{polygon_col_name}" = \'{polygon_name}\'')
        request = QgsFeatureRequest(expression)
        features_project = list(layer.getFeatures(request))
        if features_project:
            geometry = features_project[0].geometry()
            if geometry.isMultipart():
                polygons = geometry.asMultiPolygon()
            else:
                polygons = [geometry.asPolygon()]
                #print(polygons)
            points = []
            for polygon in polygons:
                boundary = polygon[0]
                line_geom = QgsGeometry.fromPolylineXY(boundary)
                total_length = line_geom.length()
                distance = 0
                while distance < total_length:
                    # 在指定距离处获取点
                    point = line_geom.interpolate(distance)
                    points.append(point)
                    # 移动到下一个间隔
                    distance += point_interval
                # 添加最后一个点（确保包含终点）
                points.append(line_geom.interpolate(total_length))
            return points
        else:
            return None

    # 根据输入的线（或MultiLineString），返回线上每隔一定距离的一组点（使用该图层对应坐标系，如3857）
    def get_discrete_points_from_line(self, layer_name_of_line, line_col_name, line_name, point_interval):
        """
        根据输入的线（或MultiLineString），返回线上每隔一定距离的一组点（使用该图层对应坐标系，如3857）
        :param layer_name_of_line: 图层名称
        :type layer_name_of_line: str
        :param line_col_name: 图层搜索列名（用于搜索线名称）
        :type line_col_name: str
        :param line_name: 图层中线名称
        :type line_name: str
        :param point_interval: 每个点的间距（单位大约相当于0.8米，例如400大约相当于320米）
        :type point_interval: int
        :return: 一组QgsPointXY点转化为的QgsGeometry
        :rtype:list[QgsGeometry]
        """
        layer = self.qgsProjectInstance.mapLayersByName(layer_name_of_line)[0]
        expression = QgsExpression(f'"{line_col_name}" = \'{line_name}\'')
        request = QgsFeatureRequest(expression)
        features_project = list(layer.getFeatures(request))
        if features_project:
            line_geom = features_project[0].geometry()
            line_length = line_geom.length()
            points = []
            distance = 0
            while distance < line_length:
                point = line_geom.interpolate(distance)
                points.append(point)
                distance += 100  # 增加100米
            return points
        else:
            return None

    # 根据输入的点（或MultiPoint），返回对应名称的一组点（使用该图层对应坐标系，如3857）
    def get_discrete_points_from_points(self, layer_name_of_point, point_col_name, point_name):
        """
        根据输入的点（或MultiPoint），返回对应名称的一组点（使用该图层对应坐标系，如3857）
        :param layer_name_of_point: 图层名称
        :type layer_name_of_point: str
        :param point_col_name: 图层搜索列名（用于搜索点名称）
        :type point_col_name: str
        :param point_name: 图层中点名称
        :type point_name: str
        :return: 一组QgsPointXY点转化为的QgsGeometry
        :rtype:list[QgsGeometry]
        """
        layer = self.qgsProjectInstance.mapLayersByName(layer_name_of_point)[0]
        expression = QgsExpression(f'"{point_col_name}" = \'{point_name}\'')
        request = QgsFeatureRequest(expression)
        features_project = list(layer.getFeatures(request))
        if features_project:
            point_geom = features_project[0].geometry()
            if point_geom.type() == 0:
                points = point_geom.asMultiPoint()
                point_geom = []
                for point in points:
                    point_geom.append(QgsGeometry.fromPointXY(point))
            return point_geom
        else:
            return None

    def get_distance_from_polygon_to_project(self, geometry_polygon, project_name):
        geometry_project = self.get_project_geometry_by_name(project_name)
        if geometry_project:
            geometry_project.transform(self.transformer_3857_to_32650)
            return int(geometry_polygon.distance(geometry_project))
        else:
            return -1

    # 传入geometry，返回一个QgsRectangle，可以直接用于setextend方法，留出边框
    @staticmethod
    def get_expanded_extend_by_geometry(geometry):
        """
        传入geometry，返回一个QgsRectangle，可以直接用于setextend方法，留出边框
        :param geometry: 形状
        :type geometry: QgsGeometry
        :return: 显示边界
        :rtype: QgsRectangle
        """
        # 获取几何的边界框
        bounding_box = geometry.boundingBox()
        width = bounding_box.width()
        height = bounding_box.height()
        expanded_bbox = QgsRectangle(
            bounding_box.xMinimum() - width * 0.2,  # 左侧扩展20%
            bounding_box.yMinimum() - height * 0.2,  # 底部扩展20%
            bounding_box.xMaximum() + width * 0.2,  # 右侧扩展20%
            bounding_box.yMaximum() + height * 0.2  # 顶部扩展20%
        )
        return expanded_bbox

    def get_expanded_extend_by_layer(self, layer_name,extend_ratio=0.2):
        layer = self.qgsProjectInstance.mapLayersByName(layer_name)[0]
        if layer:
            width = layer.extent().width()
            height = layer.extent().height()
            expanded_bbox = QgsRectangle(
                layer.extent().xMinimum() - width * 0.2,  # 左侧扩展20%
                layer.extent().yMinimum() - height * 0.2,  # 底部扩展20%
                layer.extent().xMaximum() + width * 0.2,  # 右侧扩展20%
                layer.extent().yMaximum() + height * 0.2  # 顶部扩展20%
            )
            if layer.crs().authid() == 'EPSG:4326':
                expanded_bbox = self.transformer_4326_to_3857.transform(expanded_bbox)
            return expanded_bbox
        else:
            return None



    # 与polygon_intersects类似，专门用于判定气泡与扇区间的相交关系，是返回一个dict，key是相交的小区号，value是相交的bubble num的list
    def get_sector_dict_intersects_bubble(self, layer_name_of_sector_polygon, layer_name_of_bubble_polygon):
        """
        与polygon_intersects类似，专门用于判定气泡与扇区间的相交关系，是返回一个dict，key是相交的cgi和groupid（格式为cgi,groupid），value是相交的bubble num的list
        :param layer_name_of_sector_polygon: 扇区图层名称
        :type layer_name_of_sector_polygon: str
        :param layer_name_of_bubble_polygon: 气泡图层名称
        :type layer_name_of_bubble_polygon: str
        :return: 对应关系字典，key是相交的cgi和groupid（格式为cgi,groupid），value是相交的bubble num的list
        :rtype: dict{str:[str]}
        """
        # 打开图层
        layer_sector_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_sector_polygon)[0]
        layer_bubble_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_bubble_polygon)[0]

        # crs_trans_flag:用于bubble图层0:无需转换、1：4326-3857、 2:3857-4326，最终使bubble图层与扇区图层的crs相同
        if layer_sector_polygon.crs().authid() == 'EPSG:4326' and layer_bubble_polygon.crs().authid() == 'EPSG:3857':
            crs_trans_flag = 2
        elif layer_sector_polygon.crs().authid() == 'EPSG:3857' and layer_bubble_polygon.crs().authid() == 'EPSG:4326':
            crs_trans_flag = 1
        else:
            crs_trans_flag = 0

        features_bubble = layer_bubble_polygon.getFeatures()

        # 建立快速索引
        spatial_index_source = QgsSpatialIndex(layer_sector_polygon.getFeatures())

        cgi_bubble_intersect_dict_return = {}
        for i, feature_bubble in enumerate(features_bubble):
            geometry_bubble = feature_bubble.geometry()
            if crs_trans_flag == 2:
                geometry_bubble.transform(self.transformer_3857_to_4326)
            elif crs_trans_flag == 1:
                geometry_bubble.transform(self.transformer_4326_to_3857)
            intersecting_sector_ids = spatial_index_source.intersects(geometry_bubble.boundingBox())
            # print(intersecting_sector_ids)
            for j, intersecting_sector_id in enumerate(intersecting_sector_ids):
                feature_sector = layer_sector_polygon.getFeature(intersecting_sector_id)
                cgi = feature_sector['唯一标识']
                group_id = feature_sector['Group ID']
                if not group_id:
                    group_id = 0
                if isinstance(group_id, (int, float)) and group_id < 0:
                    group_id = 0
                dict_return_key = f'{cgi},{group_id}'
                geom_sector = feature_sector.geometry()
                if geom_sector.intersects(geometry_bubble):
                    if dict_return_key in cgi_bubble_intersect_dict_return:
                        if feature_bubble['num'] not in cgi_bubble_intersect_dict_return[dict_return_key]:
                            cgi_bubble_intersect_dict_return[dict_return_key].append(feature_bubble['num'])
                    else:
                        cgi_bubble_intersect_dict_return[dict_return_key] = [feature_bubble['num']]
        return cgi_bubble_intersect_dict_return

    def get_sector_feature_include_geometry_from_layer(self, layer_name_of_sector_polygon, cgi_list, plmn_normalization = False):
        layer_sector_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_sector_polygon)[0]
        if plmn_normalization:
            cgi_list_norm = [
                item.replace("460-08", "460-00").replace("460-15", "460-00")
                for item in cgi_list
            ]
        else:
            cgi_list_norm = cgi_list
        quoted_cgi = [f"'{cgi}'" for cgi in cgi_list_norm]
        expression = QgsExpression(f'"唯一标识" IN ({", ".join(quoted_cgi)})')
        request = QgsFeatureRequest(expression)
        features = list(layer_sector_polygon.getFeatures(request))
        return features

    def get_sector_info_from_layer(self, layer_name_of_sector_polygon, cgi_list):
        layer_sector_polygon = self.qgsProjectInstance.mapLayersByName(layer_name_of_sector_polygon)[0]
        match_info_list = []
        # unmatch_cgi_list = []
        quoted_cgi = [f"'{cgi}'" for cgi in cgi_list]
        expression = QgsExpression(f'"唯一标识" IN ({", ".join(quoted_cgi)})')
        request = QgsFeatureRequest(expression)
        features = list(layer_sector_polygon.getFeatures(request))
        for feature in features:
            match_info_list.append(
                {'唯一标识': str(feature["唯一标识"]),'基站号': str(feature["基站号"]),'小区名': str(feature["小区名"]),
                 '站型': str(feature["站型"]),'行政区': str(feature["行政区"]),'设备厂家': str(feature["设备厂家"]),
                 '频段': str(feature["频段"]),'带宽': str(feature["带宽"])})
        #
        # for cgi in cgi_list:
        #     expression = QgsExpression(f'"唯一标识" = \'{cgi}\'')
        #     request = QgsFeatureRequest(expression)
        #     features_bts = list(layer_sector_polygon.getFeatures(request))
        #     if features_bts:
        #         match_info_list.append([cgi,str(features_bts[0]["基站号"]),str(features_bts[0]["小区名"]),str(features_bts[0]["站型"]),str(features_bts[0]["行政区"]),str(features_bts[0]["设备厂家"]),str(features_bts[0]["频段"]),str(features_bts[0]["带宽"])])
        #     else:
        #         unmatch_cgi_list.append(cgi)
        return match_info_list

    def set_canvas_extend_to_project(self, project_name):
        """
        根据项目名称，查询数据库，获取边界并在mapcanvas居中显示
        :param project_name: 项目名称
        :type project_name: str
        :return: 是否成功显示该项目
        :rtype: bool
        """
        project_type = self.sql_util.get_project_type(self.conn, project_name)
        if project_type == 2:
            layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_面")[0]
        elif project_type == 1:
            layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_线")[0]
        else:
            layer = self.qgsProjectInstance.mapLayersByName("ToB项目图层_点")[0]

        expression = QgsExpression(f'"项目名称" = \'{project_name}\'')
        request = QgsFeatureRequest(expression)
        features = list(layer.getFeatures(request))
        if features:
            # 获取第一个匹配要素的几何
            geometry = features[0].geometry()
            # 设置Canvas显示范围为要素边界
            self.mapCanvas.setExtent(self.get_expanded_extend_by_geometry(geometry))
            # 刷新Canvas以显示新范围
            self.mapCanvas.refresh()
            return True
        else:
            self.mainWindow.log_text_field_update("该项目无地理化信息", 3)
            return False

    def set_canvas_extend_to_polygon(self, layer_name, polygon_col_name, polygon_name):
        layer = self.qgsProjectInstance.mapLayersByName(layer_name)[0]
        expression = QgsExpression(f'"{polygon_col_name}" = \'{polygon_name}\'')
        request = QgsFeatureRequest(expression)
        features = list(layer.getFeatures(request))
        if features:
            # 获取第一个匹配要素的几何
            geometry = features[0].geometry()
            # 设置Canvas显示范围为要素边界
            self.mapCanvas.setExtent(self.get_expanded_extend_by_geometry(geometry))
            # 刷新Canvas以显示新范围
            self.mapCanvas.refresh()
            return True
        else:
            return False

    # 将画布按照中心经纬度以及比例尺进行缩放
    def set_canvas_extend_to_cord(self, center_x, center_y, scale=10000):
        """
        将画布按照中心经纬度以及比例尺进行缩放
        :param center_x: 经度
        :type center_x: float
        :param center_y:纬度
        :type center_y: float
        :param scale:比例尺
        :type scale: int
        :return:None
        """
        canvas_width = self.mapCanvas.width()
        extent_width = scale * 0.00028 * canvas_width
        # 创建视图范围（中心点周围的矩形区域）
        half_width = extent_width / 2
        point_4326 = QgsPointXY(center_x, center_y)
        point_3857 = self.transformer_4326_to_3857.transform(point_4326)
        # center_3857_x, center_3857_y = cord_trans_4326_to_3857(center_x, center_y)
        extent = QgsRectangle(
            point_3857.x() - half_width,
            point_3857.y() - half_width * self.mapCanvas.height() / canvas_width,
            point_3857.x() + half_width,
            point_3857.y() + half_width * self.mapCanvas.height() / canvas_width
        )
        # 设置地图视图范围
        self.mapCanvas.setExtent(extent)
        self.mapCanvas.refresh()  # 刷新画布

    # 对传入的layer，让其完成标签的显示
    @staticmethod
    def show_layer_lable(layer, layer_type, fieldName, minimumScale):
        """
        对传入的layer，让其完成标签的显示
        :param layer: 传入图层
        :type layer: QgsVectorLayer
        :param layer_type: 图形类型（0:点，1:线，2:面）
        :type layer_type: int
        :param fieldName: 标签对应图层的列名
        :type fieldName: str
        :param minimumScale: 在该比例尺以上显示标签
        :type minimumScale: int
        :return: None
        """
        layer_settings = QgsPalLayerSettings()

        text_format = QgsTextFormat()

        text_format.setFont(QFont("等线", 10))
        text_format.setColor(QColor(120,100,100,255))
        text_format.setForcedBold(True)

        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(0.7)
        buffer_settings.setColor(QColor("lightGrey"))

        text_format.setBuffer(buffer_settings)
        layer_settings.setFormat(text_format)

        layer_settings.fieldName = fieldName
        if layer_type == 2:
            layer_settings.placement = QgsPalLayerSettings.Placement.AroundPoint
        elif layer_type == 1:
            layer_settings.placement = QgsPalLayerSettings.Placement.Curved
        else:
            layer_settings.placement = QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint
        layer_settings.scaleVisibility = True
        layer_settings.minimumScale = minimumScale
        labels = QgsVectorLayerSimpleLabeling(layer_settings)
        layer.setLabelsEnabled(True)
        layer.setLabeling(labels)
        layer.triggerRepaint()