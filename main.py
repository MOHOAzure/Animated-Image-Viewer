import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QScrollArea
from PyQt5.QtGui import QPixmap, QImage, QMovie
from PyQt5.QtCore import Qt, QTimer, QSize, QRectF, pyqtSignal
from PIL import Image
import io


class APNGLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.movie = None
        self.current_frame = 0
        self.frames = []
        self.durations = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.show_next_frame)
        self.original_pixmap = None

    def load_apng(self, path):
        self.timer.stop()
        self.frames = []
        self.durations = []
        im = Image.open(path)
        try:
            while True:
                buffer = io.BytesIO()
                im.save(buffer, format="PNG")
                qimage = QImage()
                qimage.loadFromData(buffer.getvalue())
                self.frames.append(qimage)
                self.durations.append(im.info.get('duration', 100))
                im.seek(im.tell() + 1)
        except EOFError:
            pass

        if self.frames:
            self.original_pixmap = QPixmap.fromImage(self.frames[0])
            self.setPixmap(self.original_pixmap)
            self.current_frame = 0
            self.start_animation()

    def start_animation(self):
        if self.frames:
            self.timer.start(int(self.durations[self.current_frame]))

    def show_next_frame(self):
        if self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.original_pixmap = QPixmap.fromImage(self.frames[self.current_frame])
            self.setPixmap(self.original_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.timer.start(int(self.durations[self.current_frame]))

    def setScaledPixmap(self):
        if self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setScaledPixmap()
class ThumbnailStrip(QWidget):
    thumbnailClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(5)
        self.thumbnails = []

    def add_thumbnail(self, pixmap, index):
        thumbnail = QLabel()
        scaled_pixmap = pixmap.scaled(QSize(80, 80), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumbnail.setPixmap(scaled_pixmap)
        thumbnail.setFixedSize(80, 80)
        thumbnail.mousePressEvent = lambda event, i=index: self.thumbnailClicked.emit(i)
        self.layout.addWidget(thumbnail)
        self.thumbnails.append(thumbnail)

    def clear_thumbnails(self):
        for thumbnail in self.thumbnails:
            self.layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Img Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: black;")
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.image_area = QWidget()
        self.image_layout = QVBoxLayout(self.image_area)
        self.label = APNGLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.image_layout.addWidget(self.label)

        self.thumbnail_scroll_area = QScrollArea()
        self.thumbnail_scroll_area.setWidgetResizable(True)
        self.thumbnail_scroll_area.setFixedHeight(100)
        self.thumbnail_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll_area.setStyleSheet("QScrollArea { border: none; background-color: black; }")
        self.thumbnail_strip = ThumbnailStrip()
        self.thumbnail_strip.thumbnailClicked.connect(self.show_image)
        self.thumbnail_scroll_area.setWidget(self.thumbnail_strip)

        self.main_layout.addWidget(self.image_area, 1)
        self.main_layout.addWidget(self.thumbnail_scroll_area)
        self.main_layout.setContentsMargins(0, 0, 0, 10)

        self.current_image_index = 0
        self.image_list = []
        self.current_directory = ""
        self.current_image_path = ""

        self.load_images()

    def load_images(self):
        self.current_directory = QFileDialog.getExistingDirectory(self, "Select img dir")
        if self.current_directory:
            self.image_list = [f for f in os.listdir(self.current_directory)
                               if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.apng'))]
            if self.image_list:
                self.load_thumbnails()
                self.show_image(0)

    def load_thumbnails(self):
        self.thumbnail_strip.clear_thumbnails()
        for i, image_name in enumerate(self.image_list):
            image_path = os.path.join(self.current_directory, image_name)
            pixmap = QPixmap(image_path)
            self.thumbnail_strip.add_thumbnail(pixmap, i)

    def show_image(self, index):
        if 0 <= index < len(self.image_list):
            self.current_image_index = index
            self.current_image_path = os.path.join(self.current_directory, self.image_list[index])
            if self.current_image_path.lower().endswith(('.png', '.apng')):
                self.label.load_apng(self.current_image_path)
            elif self.current_image_path.lower().endswith('.gif'):
                self.show_gif()
            else:
                pixmap = QPixmap(self.current_image_path)
                self.label.original_pixmap = pixmap
                self.label.setScaledPixmap()

    def show_gif(self):
        movie = QMovie(self.current_image_path)
        self.label.setMovie(movie)
        movie.setScaledSize(self.label.size())
        movie.start()

    def load_next_image(self):
        if len(self.image_list) > 0:
            self.show_image((self.current_image_index + 1) % len(self.image_list))

    def load_previous_image(self):
        if len(self.image_list) > 0:
            self.show_image((self.current_image_index - 1) % len(self.image_list))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.load_next_image()
        elif event.key() == Qt.Key_Left:
            self.load_previous_image()
        elif event.key() == Qt.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()

    def wheelEvent(self, event):
        if self.thumbnail_scroll_area.underMouse():
            # 如果滑鼠在縮圖區域，則滾動縮圖列表
            self.thumbnail_scroll_area.horizontalScrollBar().setValue(
                self.thumbnail_scroll_area.horizontalScrollBar().value() - event.angleDelta().y())
        else:
            # 否則，切換圖片
            if event.angleDelta().y() < 0:  # down
                self.load_next_image()
            else:  # up
                self.load_previous_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.label.setScaledPixmap()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())