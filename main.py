import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QScrollArea, QPushButton
from PyQt5.QtGui import QPixmap, QImage, QMovie
from PyQt5.QtCore import Qt, QTimer, QSize, QSettings, pyqtSignal, QThread, QObject
from PIL import Image
import io


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


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
        if self.original_pixmap and not self.original_pixmap.isNull():
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
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(QSize(60, 60), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumbnail.setPixmap(scaled_pixmap)
        else:
            thumbnail.setText("No Preview")
        thumbnail.setFixedSize(60, 60)
        thumbnail.setStyleSheet("QLabel { background-color: #333333; color: white; }")
        thumbnail.mousePressEvent = lambda event, i=index: self.thumbnailClicked.emit(i)
        self.layout.addWidget(thumbnail)
        self.thumbnails.append(thumbnail)

    def clear_thumbnails(self):
        for thumbnail in self.thumbnails:
            self.layout.removeWidget(thumbnail)
            thumbnail.deleteLater()
        self.thumbnails.clear()


class ImageLoader(QObject):
    loaded = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def load(self):
        try:
            image = Image.open(self.path)
            self.loaded.emit(image)
        except Exception as e:
            logging.error(f"Error loading image {self.path}: {str(e)}")
            self.error.emit(str(e))


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: black;")
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.image_area = QScrollArea()
        self.image_area.setWidgetResizable(True)
        self.image_area.setAlignment(Qt.AlignCenter)
        self.image_area.setStyleSheet("QScrollArea { border: none; background-color: black; }")
        
        self.label = APNGLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.image_area.setWidget(self.label)

        self.thumbnail_scroll_area = QScrollArea()
        self.thumbnail_scroll_area.setWidgetResizable(True)
        self.thumbnail_scroll_area.setFixedHeight(70)
        self.thumbnail_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumbnail_scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #111111; }")
        self.thumbnail_strip = ThumbnailStrip()
        self.thumbnail_strip.thumbnailClicked.connect(self.show_image)
        self.thumbnail_scroll_area.setWidget(self.thumbnail_strip)

        self.button_layout = QHBoxLayout()
        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_new_folder)
        self.button_layout.addWidget(self.select_folder_button)

        self.main_layout.addWidget(self.image_area, 1)
        self.main_layout.addLayout(self.button_layout)
        self.main_layout.addWidget(self.thumbnail_scroll_area)
        self.main_layout.setSpacing(5)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.current_image_index = 0
        self.image_list = []
        self.current_directory = ""
        self.current_image_path = ""

        
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self.handle_load_timeout)
        self.load_thread = None

        self.settings = QSettings("AZZA", "ImageViewer")
        self.select_new_folder(self.settings.value("last_directory", ""))

    def select_new_folder(self, default_path=""):
        directory = QFileDialog.getExistingDirectory(self, "Select Image Directory", default_path)
        if directory:
            self.load_images(directory)

    def load_images(self, directory):
        self.current_directory = directory
        self.settings.setValue("last_directory", self.current_directory)
        self.image_list = []
        for f in os.listdir(self.current_directory):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.apng')):
                try:
                    # Attempt to open the image to verify it's not corrupted
                    with Image.open(os.path.join(self.current_directory, f)) as img:
                        img.verify()
                    self.image_list.append(f)
                except Exception as e:
                    logging.warning(f"Skipping corrupted image {f}: {str(e)}")
        if self.image_list:
            self.load_thumbnails()
            self.show_image(0)
        else:
            self.label.setText("No valid images found in the selected directory")

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
            
            self.load_timer.start(5000)  # 5 second timeout
            self.load_thread = QThread()
            self.image_loader = ImageLoader(self.current_image_path)
            self.image_loader.moveToThread(self.load_thread)
            self.load_thread.started.connect(self.image_loader.load)
            self.image_loader.loaded.connect(self.on_image_loaded)
            self.image_loader.error.connect(self.on_image_error)
            self.load_thread.start()

    def on_image_loaded(self, image):
        self.load_timer.stop()
        self.load_thread.quit()
        self.load_thread.wait()

        if 'duration' in image.info:  # This is an APNG
            self.label.load_apng(self.current_image_path)
        elif getattr(image, "is_animated", False):  # This is a GIF
            self.show_animated_image()
        else:  # This is a static image
            self.show_static_image()

        self.adjustImageSize()

    def on_image_error(self, error):
        self.load_timer.stop()
        self.load_thread.quit()
        self.load_thread.wait()
        logging.error(f"Failed to load image: {error}")
        self.label.setText(f"Error loading image: {error}")

    def handle_load_timeout(self):
        self.load_thread.terminate()
        self.load_thread.wait()
        logging.error(f"Image loading timed out: {self.current_image_path}")
        self.label.setText("Image loading timed out")


    def show_png_image(self):
        try:
            image = Image.open(self.current_image_path)
            if 'duration' in image.info:  # This is an APNG
                self.label.load_apng(self.current_image_path)
            else:  # This is a static PNG
                self.show_static_image()
        except Exception as e:
            print(f"Error loading PNG: {e}")
            self.show_static_image()  # Fallback to static image loading

    def show_static_image(self):
        pixmap = QPixmap(self.current_image_path)
        if not pixmap.isNull():
            self.label.original_pixmap = pixmap
            self.label.setScaledPixmap()
        else:
            print(f"Failed to load image: {self.current_image_path}")

    def show_animated_image(self):
        movie = QMovie(self.current_image_path)
        if movie.isValid():
            self.label.setMovie(movie)
            movie.setScaledSize(self.label.size())
            movie.start()
        else:
            print(f"Failed to load animated image: {self.current_image_path}")

    def load_next_image(self):
        if len(self.image_list) > 0:
            self.show_image((self.current_image_index + 1) % len(self.image_list))

    def load_previous_image(self):
        if len(self.image_list) > 0:
            self.show_image((self.current_image_index - 1) % len(self.image_list))

    def scroll_thumbnails(self, direction):
        scrollbar = self.thumbnail_scroll_area.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() + direction * 100)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_6:
            self.scroll_thumbnails(1)
        elif event.key() == Qt.Key_4:
            self.scroll_thumbnails(-1)
        elif event.key() == Qt.Key_2:
            self.load_next_image()
        elif event.key() == Qt.Key_8:
            self.load_previous_image()
        elif event.key() == Qt.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif event.key() == Qt.Key_O:
            self.select_new_folder()

    def wheelEvent(self, event):
        if self.thumbnail_scroll_area.underMouse():
            self.thumbnail_scroll_area.horizontalScrollBar().setValue(
                self.thumbnail_scroll_area.horizontalScrollBar().value() - event.angleDelta().y())
        else:
            if event.angleDelta().y() < 0:  # down
                self.load_next_image()
            else:  # up
                self.load_previous_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjustImageSize()

    def adjustImageSize(self):
        if self.label.original_pixmap and not self.label.original_pixmap.isNull():
            available_size = self.image_area.size()
            scaled_pixmap = self.label.original_pixmap.scaled(available_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setPixmap(scaled_pixmap)
            self.label.setFixedSize(scaled_pixmap.size())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec_())