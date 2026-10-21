import os
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import (QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QPixmap, QImage)
from PyQt6.QtCore import (Qt, QRectF, QPointF, pyqtSignal)
from app.common.config_manager import load_config, save_config

class VideoCanvasWidget(QWidget):
    configChanged = pyqtSignal(dict)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.current_image = None
        self.native_vw = 0
        self.native_vh = 0
        self.snap_x = None
        self.snap_y = None
        self.config = load_config()
        self.selected_item = None
        self.drag_action = None
        self.drag_offset = None
        self.masks_rel = self.config.get('mask_logos', [])
        self.sub_rel_x = self.config.get('sub_rel_x', 0.5)
        self.sub_rel_y = self.config.get('sub_rel_y', 0.9)
        self.sub_scale = self.config.get('sub_scale', 1.0)
        self.sub_text = 'Vị trí hiển thị phụ đề.'
        self.sub_visible = self.config.get('show_subtitle', True)
        self.wm_rel_x = self.config.get('wm_rel_x', 0.8)
        self.wm_rel_y = self.config.get('wm_rel_y', 0.1)
        self.wm_scale = self.config.get('wm_scale', 1.0)
        self.wm_text = self.config.get('wm_text', '')
        self.wm_visible = True if self.wm_text else False
        self.logo_path = self.config.get('logo_path', '')
        self.logo_rel_x = self.config.get('logo_rel_x', 0.1)
        self.logo_rel_y = self.config.get('logo_rel_y', 0.1)
        self.logo_scale = self.config.get('logo_scale', 1.0)
        self.logo_pixmap = None
        self._loadLogo()
        self.bg_frame_path = self.config.get('bg_frame_path', '')
        self.bg_frame_rel_x = self.config.get('bg_frame_rel_x', 0.5)
        self.bg_frame_rel_y = self.config.get('bg_frame_rel_y', 0.5)
        self.bg_frame_scale = self.config.get('bg_frame_scale', 1.0)
        self.bg_frame_pixmap = None
        self._loadBgFrame()
        self.sub_font_name = self.config.get('sub_font_name', 'Arial')
        self.sub_font_color = self.config.get('sub_font_color', '#FFFFFF')
        self.sub_border_color = self.config.get('sub_border_color', '#000000')
        self.sub_border_style = self.config.get('sub_border_style', 'outline')
        self.wm_font_name = self.config.get('wm_font_name', 'Arial')
        self.wm_font_color = self.config.get('wm_font_color', '#FFFFFF')
        self.wm_border_color = self.config.get('wm_border_color', '#000000')
        self.wm_border_style = self.config.get('wm_border_style', 'box')
        self.ocr_rel = self.config.get('ocr_bbox_rel', [0.2, 0.7, 0.6, 0.2])

    def _loadLogo(self):
        if self.logo_path and os.path.exists(self.logo_path):
            self.logo_pixmap = QPixmap(self.logo_path)
            return
        self.logo_pixmap = None
        self.logo_path = ''

    def _loadBgFrame(self):
        if self.bg_frame_path and os.path.exists(self.bg_frame_path):
            self.bg_frame_pixmap = QPixmap(self.bg_frame_path)
            return
        self.bg_frame_pixmap = None
        self.bg_frame_path = ''

    def applyConfig(self, config_dict):
        self.config = config_dict
        self.masks_rel = self.config.get('mask_logos', [])
        self.sub_rel_x = self.config.get('sub_rel_x', 0.5)
        self.sub_rel_y = self.config.get('sub_rel_y', 0.9)
        self.sub_scale = self.config.get('sub_scale', 1.0)
        self.sub_visible = self.config.get('show_subtitle', True)
        self.wm_rel_x = self.config.get('wm_rel_x', 0.8)
        self.wm_rel_y = self.config.get('wm_rel_y', 0.1)
        self.wm_scale = self.config.get('wm_scale', 1.0)
        self.wm_text = self.config.get('wm_text', '')
        self.wm_visible = True if self.wm_text else False
        self.logo_path = self.config.get('logo_path', '')
        self.logo_rel_x = self.config.get('logo_rel_x', 0.1)
        self.logo_rel_y = self.config.get('logo_rel_y', 0.1)
        self.logo_scale = self.config.get('logo_scale', 1.0)
        self._loadLogo()
        self.bg_frame_path = self.config.get('bg_frame_path', '')
        self.bg_frame_rel_x = self.config.get('bg_frame_rel_x', 0.5)
        self.bg_frame_rel_y = self.config.get('bg_frame_rel_y', 0.5)
        self.bg_frame_scale = self.config.get('bg_frame_scale', 1.0)
        self._loadBgFrame()
        self.sub_font_name = self.config.get('sub_font_name', 'Arial')
        self.sub_font_color = self.config.get('sub_font_color', '#FFFFFF')
        self.sub_border_color = self.config.get('sub_border_color', '#000000')
        self.sub_border_style = self.config.get('sub_border_style', 'outline')
        self.wm_font_name = self.config.get('wm_font_name', 'Arial')
        self.wm_font_color = self.config.get('wm_font_color', '#FFFFFF')
        self.wm_border_color = self.config.get('wm_border_color', '#000000')
        self.wm_border_style = self.config.get('wm_border_style', 'box')
        self.ocr_rel = self.config.get('ocr_bbox_rel', [0.2, 0.7, 0.6, 0.2])
        self.update()

    def setVideoFrame(self, frame):
        import time
        now = time.time()
        if hasattr(self, '_last_frame_time') and now - self._last_frame_time < 0.033:
            return
        self._last_frame_time = now
        if not frame.isValid():
            return
        img = frame.toImage()
        if not img.isNull():
            self.native_vw = img.width()
            self.native_vh = img.height()
            if img.width() > 960:
                img = img.scaledToWidth(960, Qt.TransformationMode.FastTransformation)
            self.current_image = img
            self.update()

    def setOCRVisible(self, visible):
        self.ocr_visible = visible
        self.update()

    def addMask(self):
        offset = len(self.masks_rel) * 0.05
        new_x = min(0.6, 0.3 + offset)
        new_y = min(0.6, 0.3 + offset)
        self.masks_rel.append([new_x, new_y, 0.4, 0.4])
        self.selected_item = f'mask_{len(self.masks_rel) - 1}'
        self.saveConfig()
        self.update()

    def removeSelectedItem(self):
        if not self.selected_item:
            return False
        if self.selected_item.startswith('mask_'):
            idx = int(self.selected_item.split('_')[1])
            if 0 <= idx < len(self.masks_rel):
                self.masks_rel.pop(idx)
                self.selected_item = None
                self.saveConfig()
                self.update()
                return True
            return False
        if self.selected_item == 'logo':
            self.logo_path = ''
            self.logo_pixmap = None
            self.selected_item = None
            self.saveConfig()
            self.update()
            return True
        if self.selected_item == 'bg_frame':
            self.bg_frame_path = ''
            self.bg_frame_pixmap = None
            self.selected_item = None
            self.saveConfig()
            self.update()
            return True
        return False

    def setWatermarkText(self, text):
        self.wm_text = text
        self.wm_visible = len(text.strip()) > 0
        self.config = load_config()
        self.config['wm_text'] = text
        save_config(self.config)
        self.update()

    def setLogoPath(self, path):
        self.logo_path = path
        self.config['logo_path'] = path
        self.saveConfig()
        self._loadLogo()
        self.update()

    def setBgFramePath(self, path):
        self.bg_frame_path = path
        self.config['bg_frame_path'] = path
        self.saveConfig()
        self._loadBgFrame()
        self.update()

    def saveConfig(self):
        self.config['mask_logos'] = self.masks_rel
        self.config['ocr_bbox_rel'] = self.ocr_rel
        self.config['sub_rel_x'] = self.sub_rel_x
        self.config['sub_rel_y'] = self.sub_rel_y
        self.config['sub_scale'] = self.sub_scale
        self.config['wm_rel_x'] = self.wm_rel_x
        self.config['wm_rel_y'] = self.wm_rel_y
        self.config['wm_scale'] = self.wm_scale
        self.config['logo_path'] = self.logo_path
        self.config['logo_rel_x'] = self.logo_rel_x
        self.config['logo_rel_y'] = self.logo_rel_y
        self.config['logo_scale'] = self.logo_scale
        self.config['bg_frame_path'] = self.bg_frame_path
        self.config['bg_frame_rel_x'] = self.bg_frame_rel_x
        self.config['bg_frame_rel_y'] = self.bg_frame_rel_y
        self.config['bg_frame_scale'] = self.bg_frame_scale
        self.configChanged.emit(self.config)

    def _getVideoRect(self):
        w = self.width()
        h = self.height()
        if self.native_vw <= 0 or self.native_vh <= 0:
            return 0.0, 0.0, float(w), float(h)
        widget_ratio = w / float(h)
        video_ratio = self.native_vw / float(self.native_vh)
        if widget_ratio > video_ratio:
            vh_drawn = h
            vw_drawn = h * video_ratio
            return (w - vw_drawn) / 2.0, 0.0, vw_drawn, float(vh_drawn)
        vw_drawn = w
        vh_drawn = w / video_ratio
        return 0.0, (h - vh_drawn) / 2.0, float(vw_drawn), vh_drawn

    def _getMaskRect(self, vx, vy, vw, vh, idx):
        if idx >= len(self.masks_rel):
            return QRectF()
        rx, ry, rw, rh = self.masks_rel[idx]
        return QRectF(vx + rx * vw, vy + ry * vh, rw * vw, rh * vh)

    def _getOCRRect(self, vx, vy, vw, vh):
        if hasattr(self, 'ocr_abs_bbox') and self.ocr_abs_bbox and self.native_vw > 0:
            ax, ay, aw, ah = self.ocr_abs_bbox
            rx = ax / self.native_vw
            ry = ay / self.native_vh
            rw = aw / self.native_vw
            rh = ah / self.native_vh
            return QRectF(vx + rx * vw, vy + ry * vh, rw * vw, rh * vh)
        rx, ry, rw, rh = self.ocr_rel
        return QRectF(vx + rx * vw, vy + ry * vh, rw * vw, rh * vh)

    def _getSubRect(self, vx, vy, vw, vh):
        native_w = self.native_vw if self.native_vw > 0 else 1080
        font_pt = (18 if native_w < 1280 else 24) * self.sub_scale * (vw / 640.0)
        font_pt = max(1, font_pt)
        real_family = self.sub_font_name
        try:
            from app.common.font_manager import get_font_family
            real_family = get_font_family(self.sub_font_name)
        except:
            pass
        f_lower = self.sub_font_name.lower()
        weight = QFont.Weight.Normal
        if 'black' in f_lower:
            weight = QFont.Weight.Black
        elif 'extrabold' in f_lower:
            weight = QFont.Weight.ExtraBold
        elif 'bold' in f_lower:
            weight = QFont.Weight.Bold
        elif 'semibold' in f_lower:
            weight = QFont.Weight.DemiBold
        elif 'medium' in f_lower:
            weight = QFont.Weight.Medium
        elif 'extralight' in f_lower:
            weight = QFont.Weight.ExtraLight
        elif 'light' in f_lower:
            weight = QFont.Weight.Light
        elif 'thin' in f_lower:
            weight = QFont.Weight.Thin
        font = QFont(real_family, int(font_pt), weight)
        if 'italic' in f_lower:
            font.setItalic(True)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.sub_text)
        th = fm.height()
        cx = vx + self.sub_rel_x * vw
        cy = vy + self.sub_rel_y * vh
        return QRectF(cx - tw / 2, cy - th / 2, tw, th), font

    def _getWMRect(self, vx, vy, vw, vh):
        if not self.wm_text:
            return QRectF(), None
        native_w = self.native_vw if self.native_vw > 0 else 1080
        font_pt = (20 if native_w < 1280 else 30) * self.wm_scale * (vw / 640.0)
        font_pt = max(1, font_pt)
        real_family = self.wm_font_name
        try:
            from app.common.font_manager import get_font_family
            real_family = get_font_family(self.wm_font_name)
        except:
            pass
        f_lower = self.wm_font_name.lower()
        weight = QFont.Weight.Normal
        if 'black' in f_lower:
            weight = QFont.Weight.Black
        elif 'extrabold' in f_lower:
            weight = QFont.Weight.ExtraBold
        elif 'bold' in f_lower:
            weight = QFont.Weight.Bold
        elif 'semibold' in f_lower:
            weight = QFont.Weight.DemiBold
        elif 'medium' in f_lower:
            weight = QFont.Weight.Medium
        elif 'extralight' in f_lower:
            weight = QFont.Weight.ExtraLight
        elif 'light' in f_lower:
            weight = QFont.Weight.Light
        elif 'thin' in f_lower:
            weight = QFont.Weight.Thin
        font = QFont(real_family, int(font_pt), weight)
        if 'italic' in f_lower:
            font.setItalic(True)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.wm_text)
        th = fm.height()
        cx = vx + self.wm_rel_x * vw
        cy = vy + self.wm_rel_y * vh
        return QRectF(cx - tw / 2, cy - th / 2, tw, th), font

    def _getLogoRect(self, vx, vy, vw, vh):
        if not self.logo_pixmap:
            return QRectF()
        target_w = vw * 0.25 * self.logo_scale
        ratio = self.logo_pixmap.height() / float(self.logo_pixmap.width())
        target_h = target_w * ratio
        cx = vx + self.logo_rel_x * vw
        cy = vy + self.logo_rel_y * vh
        return QRectF(cx - target_w / 2, cy - target_h / 2, target_w, target_h)

    def _getBgFrameRect(self, vx, vy, vw, vh):
        if not self.bg_frame_pixmap:
            return QRectF()
        target_w = vw * self.bg_frame_scale
        ratio = self.bg_frame_pixmap.height() / float(self.bg_frame_pixmap.width())
        target_h = target_w * ratio
        cx = vx + self.bg_frame_rel_x * vw
        cy = vy + self.bg_frame_rel_y * vh
        return QRectF(cx - target_w / 2, cy - target_h / 2, target_w, target_h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        vx, vy, vw, vh = self._getVideoRect()
        if vw <= 0 or vh <= 0:
            return
        if self.current_image and not self.current_image.isNull():
            target_rect = QRectF(vx, vy, vw, vh)
            painter.drawImage(target_rect, self.current_image)
        for i in range(len(self.masks_rel)):
            mask_rect = self._getMaskRect(vx, vy, vw, vh, i)
            pen = QPen(QColor(255, 0, 0), 2)
            if self.selected_item == f'mask_{i}':
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(mask_rect)
            if self.selected_item == f'mask_{i}':
                self._drawHandles(painter, mask_rect, QColor(255, 0, 0))
        def _drawLogo(self, painter, vx, vy, vw, vh):
            rect = self._getLogoRect(vx, vy, vw, vh)
            painter.save()
            logo_op = self.config.get('logo_opacity', 100) / 100.0
            painter.setOpacity(logo_op)
            painter.drawPixmap(rect.toRect(), self.logo_pixmap)
            painter.restore()

        def _drawBgFrame(self, painter, vx, vy, vw, vh):
            rect = self._getBgFrameRect(vx, vy, vw, vh)
            painter.drawPixmap(rect.toRect(), self.bg_frame_pixmap)

        if self.bg_frame_pixmap:
            _drawBgFrame(self, painter, vx, vy, vw, vh)
            if self.selected_item == 'bg_frame':
                bg_rect = self._getBgFrameRect(vx, vy, vw, vh)
                painter.setPen(QPen(QColor('#14B8A6'), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pad = 4
                padded_rect = bg_rect.adjusted(-pad, -pad, pad, pad)
                painter.drawRect(padded_rect)
                self._drawHandles(painter, padded_rect, QColor('#14B8A6'))
        if self.logo_pixmap:
            _drawLogo(self, painter, vx, vy, vw, vh)
            if self.selected_item == 'logo':
                painter.setPen(QPen(QColor('#8B5CF6'), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pad = 2
                logo_rect = self._getLogoRect(vx, vy, vw, vh)
                padded_rect = logo_rect.adjusted(-pad, -pad, pad, pad)
                painter.drawRect(padded_rect)
                self._drawHandles(painter, padded_rect, QColor('#8B5CF6'))
        if getattr(self, 'ocr_visible', False):
            ocr_rect = self._getOCRRect(vx, vy, vw, vh)
            pen = QPen(QColor(0, 255, 0), 2)
            if self.selected_item == 'ocr':
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ocr_rect)
            if self.selected_item == 'ocr':
                self._drawHandles(painter, ocr_rect, QColor(0, 255, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        def get_fade_color(base_hex, base_alpha, opacity):
            c = QColor(base_hex)
            c.setAlpha(int(base_alpha * opacity))
            return c

        def draw_styled_text(rect, text, font, font_color, border_color, border_style, sel_color, is_selected, opacity=1.0):
            painter.setFont(font)
            fm = QFontMetrics(font)
            text_x = rect.left()
            text_y = rect.bottom() - fm.descent()
            if border_style == 'box':
                box_rect = rect.adjusted(-10, -5, 10, 5)
                painter.fillRect(box_rect, get_fade_color(border_color, 255, opacity))
            elif border_style == 'outline':
                painter.setPen(QPen(get_fade_color(border_color, 255, opacity), 2))
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        painter.drawText(QPointF(text_x + dx, text_y + dy), text)
            elif border_style == 'glow':
                painter.setPen(get_fade_color(border_color, 40, opacity))
                for dx in (-3, 0, 3):
                    for dy in (-3, 0, 3):
                        if dx != 0 or dy != 0:
                            painter.drawText(QPointF(text_x + dx, text_y + dy), text)
                painter.setPen(get_fade_color(border_color, 120, opacity))
                for dx in (-1, 1):
                    for dy in (-1, 1):
                        painter.drawText(QPointF(text_x + dx, text_y + dy), text)
            painter.setPen(get_fade_color(font_color, 255, opacity))
            painter.drawText(QPointF(text_x, text_y), text)
            if is_selected:
                painter.setPen(QPen(QColor(sel_color), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                pad = 4
                padded_rect = rect.adjusted(-pad, -pad, pad, pad)
                painter.drawRect(padded_rect)
                self._drawHandles(painter, padded_rect, QColor(sel_color))

        if self.sub_visible:
            sub_rect, font = self._getSubRect(vx, vy, vw, vh)
            draw_styled_text(sub_rect, self.sub_text, font, self.sub_font_color, self.sub_border_color, self.sub_border_style, '#FBBF24', self.selected_item == 'sub')
        if self.wm_visible and self.wm_text:
            wm_rect, font = self._getWMRect(vx, vy, vw, vh)
            wm_op = self.config.get('wm_opacity', 100) / 100.0
            draw_styled_text(wm_rect, self.wm_text, font, self.wm_font_color, self.wm_border_color, self.wm_border_style, '#10B981', self.selected_item == 'wm', wm_op)
        if getattr(self, 'snap_x', None) is not None:
            painter.setPen(QPen(QColor('#F59E0B'), 2, Qt.PenStyle.DashLine))
            line_x = vx + self.snap_x * vw
            painter.drawLine(QPointF(line_x, vy), QPointF(line_x, vy + vh))
        if getattr(self, 'snap_y', None) is not None:
            painter.setPen(QPen(QColor('#F59E0B'), 2, Qt.PenStyle.DashLine))
            line_y = vy + self.snap_y * vh
            painter.drawLine(QPointF(vx, line_y), QPointF(vx + vw, line_y))

    def _drawHandles(self, painter, rect, color):
        painter.setBrush(QColor('white'))
        painter.setPen(QPen(color, 2))
        h_size = 6
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        vx, vy, vw, vh = self._getVideoRect()
        min_x = vx
        max_x = vx + vw - h_size * 2
        min_y = vy
        max_y = vy + vh - h_size * 2
        def clamp_point(px, py):
            cx = max(min_x, min(max_x, px))
            cy = max(min_y, min(max_y, py))
            return cx, cy

        tl_x, tl_y = clamp_point(x - h_size, y - h_size)
        tr_x, tr_y = clamp_point(x + w - h_size, y - h_size)
        bl_x, bl_y = clamp_point(x - h_size, y + h - h_size)
        br_x, br_y = clamp_point(x + w - h_size, y + h - h_size)
        painter.drawRect(QRectF(tl_x, tl_y, h_size * 2, h_size * 2))
        painter.drawRect(QRectF(tr_x, tr_y, h_size * 2, h_size * 2))
        painter.drawRect(QRectF(bl_x, bl_y, h_size * 2, h_size * 2))
        painter.drawRect(QRectF(br_x, br_y, h_size * 2, h_size * 2))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        vx, vy, vw, vh = self._getVideoRect()
        if vw <= 0 or vh <= 0:
            return
        rects = {}
        if getattr(self, 'ocr_visible', False) and (not hasattr(self, 'ocr_abs_bbox') or not self.ocr_abs_bbox):
            rects['ocr'] = self._getOCRRect(vx, vy, vw, vh)
        if self.wm_visible and self.wm_text:
            rects['wm'] = self._getWMRect(vx, vy, vw, vh)[0].adjusted(-4, -4, 4, 4)
        if self.sub_visible:
            rects['sub'] = self._getSubRect(vx, vy, vw, vh)[0].adjusted(-4, -4, 4, 4)
        if self.logo_pixmap:
            rects['logo'] = self._getLogoRect(vx, vy, vw, vh)
        if self.bg_frame_pixmap:
            rects['bg_frame'] = self._getBgFrameRect(vx, vy, vw, vh)
        for i in range(len(self.masks_rel)):
            rects[f'mask_{i}'] = self._getMaskRect(vx, vy, vw, vh, i)
        clicked_item = None
        if self.selected_item in rects:
            rect = rects[self.selected_item]
            h_action = self._checkHandles(pos, rect)
            if h_action:
                self.drag_action = h_action
                self.drag_offset = pos
                self.drag_start_center = rect.center()
                self.drag_start_dist = ((pos.x() - rect.center().x()) ** 2 + (pos.y() - rect.center().y()) ** 2) ** 0.5
                if self.selected_item == 'sub':
                    self.drag_start_scale = self.sub_scale
                    return
                if self.selected_item == 'wm':
                    self.drag_start_scale = self.wm_scale
                    return
                if self.selected_item == 'logo':
                    self.drag_start_scale = self.logo_scale
                    return
                if self.selected_item == 'bg_frame':
                    self.drag_start_scale = self.bg_frame_scale
                return
        order = ['sub', 'wm', 'logo', 'bg_frame'] + [f'mask_{i}' for i in range(len(self.masks_rel) - 1, -1, -1)] + ['ocr']
        for key in order:
            if key in rects and rects[key].contains(pos):
                clicked_item = key
                break
        if clicked_item:
            self.selected_item = clicked_item
            self.drag_action = 'move'
            self.drag_offset = pos
            self.drag_start_pos = pos
            if clicked_item.startswith('mask_'):
                idx = int(clicked_item.split('_')[1])
                self.start_item_rel = list(self.masks_rel[idx])
            elif clicked_item == 'ocr':
                self.start_item_rel = list(self.ocr_rel)
            elif clicked_item == 'sub':
                self.start_item_rel = self.sub_rel_x, self.sub_rel_y
            elif clicked_item == 'wm':
                self.start_item_rel = self.wm_rel_x, self.wm_rel_y
            elif clicked_item == 'logo':
                self.start_item_rel = self.logo_rel_x, self.logo_rel_y
            elif clicked_item == 'bg_frame':
                self.start_item_rel = self.bg_frame_rel_x, self.bg_frame_rel_y
        else:
            self.selected_item = None
            self.drag_action = None
        self.update()

    def _checkHandles(self, pos, rect):
        margin = 15
        h_size = 6
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        vx, vy, vw, vh = self._getVideoRect()
        min_x = vx
        max_x = vx + vw - h_size * 2
        min_y = vy
        max_y = vy + vh - h_size * 2
        def clamp_point(px, py):
            cx = max(min_x, min(max_x, px))
            cy = max(min_y, min(max_y, py))
            return cx, cy

        tl_x, tl_y = clamp_point(x - h_size, y - h_size)
        tr_x, tr_y = clamp_point(x + w - h_size, y - h_size)
        bl_x, bl_y = clamp_point(x - h_size, y + h - h_size)
        br_x, br_y = clamp_point(x + w - h_size, y + h - h_size)
        tl_c = QPointF(tl_x + h_size, tl_y + h_size)
        tr_c = QPointF(tr_x + h_size, tr_y + h_size)
        bl_c = QPointF(bl_x + h_size, bl_y + h_size)
        br_c = QPointF(br_x + h_size, br_y + h_size)
        if abs(pos.x() - tl_c.x()) <= margin and abs(pos.y() - tl_c.y()) <= margin:
            return 'tl'
        if abs(pos.x() - tr_c.x()) <= margin and abs(pos.y() - tr_c.y()) <= margin:
            return 'tr'
        if abs(pos.x() - bl_c.x()) <= margin and abs(pos.y() - bl_c.y()) <= margin:
            return 'bl'
        if abs(pos.x() - br_c.x()) <= margin and abs(pos.y() - br_c.y()) <= margin:
            return 'br'

    def mouseMoveEvent(self, event):
        pos = event.position()
        vx, vy, vw, vh = self._getVideoRect()
        if vw <= 0 or vh <= 0:
            return
        if self.selected_item and self.drag_action:
            snap_margin = 0.03
            self.snap_x = None
            self.snap_y = None
            if self.drag_action == 'move':
                dx_total = pos.x() - self.drag_start_pos.x()
                dy_total = pos.y() - self.drag_start_pos.y()
                new_x = self.start_item_rel[0] + dx_total / vw
                new_y = self.start_item_rel[1] + dy_total / vh
                if self.selected_item.startswith('mask_'):
                    rw, rh = self.start_item_rel[2], self.start_item_rel[3]
                    cx = new_x + rw / 2
                    cy = new_y + rh / 2
                    if abs(cx - 0.5) < snap_margin:
                        self.snap_x, new_x = 0.5, 0.5 - rw / 2
                    if abs(cy - 0.5) < snap_margin:
                        self.snap_y, new_y = 0.5, 0.5 - rh / 2
                    new_x = max(0.0, min(1.0 - rw, new_x))
                    new_y = max(0.0, min(1.0 - rh, new_y))
                    idx = int(self.selected_item.split('_')[1])
                    self.masks_rel[idx] = [new_x, new_y, rw, rh]
                elif self.selected_item == 'ocr':
                    if hasattr(self, 'ocr_abs_bbox') and self.ocr_abs_bbox:
                        pass
                    else:
                        rw, rh = self.start_item_rel[2], self.start_item_rel[3]
                        cx = new_x + rw / 2
                        cy = new_y + rh / 2
                        if abs(cx - 0.5) < snap_margin:
                            self.snap_x, new_x = 0.5, 0.5 - rw / 2
                        if abs(cy - 0.5) < snap_margin:
                            self.snap_y, new_y = 0.5, 0.5 - rh / 2
                        new_x = max(0.0, min(1.0 - rw, new_x))
                        new_y = max(0.0, min(1.0 - rh, new_y))
                        self.ocr_rel = [new_x, new_y, rw, rh]
                else:
                    if abs(new_x - 0.5) < snap_margin:
                        new_x = self.snap_x = 0.5
                    if abs(new_y - 0.5) < snap_margin:
                        new_y = self.snap_y = 0.5
                    if self.selected_item == 'sub':
                        self.sub_rel_x, self.sub_rel_y = new_x, new_y
                    elif self.selected_item == 'wm':
                        self.wm_rel_x, self.wm_rel_y = new_x, new_y
                    elif self.selected_item == 'logo':
                        self.logo_rel_x, self.logo_rel_y = new_x, new_y
                    elif self.selected_item == 'bg_frame':
                        self.bg_frame_rel_x, self.bg_frame_rel_y = new_x, new_y
            else:
                dx = pos.x() - self.drag_offset.x()
                dy = pos.y() - self.drag_offset.y()
                self.drag_offset = pos
                if self.selected_item.startswith('mask_'):
                    idx = int(self.selected_item.split('_')[1])
                    rx, ry, rw, rh = self.masks_rel[idx]
                    cx, cy, cw, ch = rx * vw + vx, ry * vh + vy, rw * vw, rh * vh
                    if 'l' in self.drag_action:
                        cx += dx
                        cw -= dx
                    if 'r' in self.drag_action:
                        cw += dx
                    if 't' in self.drag_action:
                        cy += dy
                        ch -= dy
                    if 'b' in self.drag_action:
                        ch += dy
                    cx = max(vx, min(vx + vw - cw, cx))
                    cy = max(vy, min(vy + vh - ch, cy))
                    if cw < 20:
                        cw = 20
                    if ch < 20:
                        ch = 20
                    self.masks_rel[idx] = [(cx - vx) / vw, (cy - vy) / vh, cw / vw, ch / vh]
                elif self.selected_item == 'ocr':
                    if hasattr(self, 'ocr_abs_bbox') and self.ocr_abs_bbox:
                        pass
                    else:
                        rx, ry, rw, rh = self.ocr_rel
                        cx, cy, cw, ch = rx * vw + vx, ry * vh + vy, rw * vw, rh * vh
                        if 'l' in self.drag_action:
                            cx += dx
                            cw -= dx
                        if 'r' in self.drag_action:
                            cw += dx
                        if 't' in self.drag_action:
                            cy += dy
                            ch -= dy
                        if 'b' in self.drag_action:
                            ch += dy
                        cx = max(vx, min(vx + vw - cw, cx))
                        cy = max(vy, min(vy + vh - ch, cy))
                        if cw < 20:
                            cw = 20
                        if ch < 20:
                            ch = 20
                        self.ocr_rel = [(cx - vx) / vw, (cy - vy) / vh, cw / vw, ch / vh]
                elif hasattr(self, 'drag_start_dist') and self.drag_start_dist > 0:
                    current_dist = ((pos.x() - self.drag_start_center.x()) ** 2 + (pos.y() - self.drag_start_center.y()) ** 2) ** 0.5
                    scale_factor = current_dist / self.drag_start_dist
                    new_scale = self.drag_start_scale * scale_factor
                    if self.selected_item == 'sub':
                        self.sub_scale = max(0.5, min(3.0, new_scale))
                    elif self.selected_item == 'wm':
                        self.wm_scale = max(0.5, min(3.0, new_scale))
                    elif self.selected_item == 'logo':
                        self.logo_scale = max(0.2, min(5.0, new_scale))
                    elif self.selected_item == 'bg_frame':
                        self.bg_frame_scale = max(0.2, min(5.0, new_scale))
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_action = None
            self.snap_x = None
            self.snap_y = None
            self.saveConfig()
            self.update()


