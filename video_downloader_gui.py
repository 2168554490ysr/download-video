import sys
import os
import yt_dlp
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QTextEdit, QFileDialog, QMessageBox, QCheckBox,
                             QComboBox, QGroupBox, QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal


class DownloadThread(QThread):
    progress_signal = pyqtSignal(str)
    progress_percent_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str, bool)

    def __init__(self, url, output_path, use_threading=False, threads=8):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.use_threading = use_threading
        self.threads = threads

    def run(self):
        ydl_opts = {
            'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'http_chunk_size': 10485760,
            'retries': 3,
            'fragment_retries': 3,
            'nocheckcertificate': True,
            'no_warnings': True,
            'progress_hooks': [self.progress_hook],
        }

        if self.use_threading:
            ydl_opts.update({
                'external_downloader': 'aria2c',
                'external_downloader_args': [
                    f'-x{self.threads}',
                    f'-s{self.threads}',
                    '-k', '10M',
                ],
            })

        try:
            self.progress_signal.emit('正在获取视频信息...')
            self.progress_percent_signal.emit(0)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                title = info.get('title', 'video')
                duration = info.get('duration', 0)
                self.progress_signal.emit(f'视频标题: {title}')
                self.progress_signal.emit(f'视频时长: {duration // 60}分{duration % 60}秒')
                if self.use_threading:
                    self.progress_signal.emit(f'多线程下载: {self.threads} 线程')
                self.progress_signal.emit('开始下载...')
                ydl.download([self.url])
            self.progress_percent_signal.emit(100)
            self.finished_signal.emit('下载完成!', True)
        except Exception as e:
            self.progress_percent_signal.emit(0)
            self.finished_signal.emit(f'下载失败: {str(e)}', False)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%')
            speed = d.get('_speed_str', '')
            eta = d.get('_eta_str', '')
            self.progress_signal.emit(f'下载进度: {percent} 速度: {speed} 剩余: {eta}')
            
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent_int = int(downloaded * 100 / total)
                self.progress_percent_signal.emit(percent_int)


class VideoDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.download_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('视频下载器 - yt-dlp GUI')
        self.setGeometry(100, 100, 650, 550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        url_layout = QHBoxLayout()
        url_label = QLabel('视频链接:')
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('请输入视频链接')
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        path_layout = QHBoxLayout()
        path_label = QLabel('保存路径:')
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText('默认保存在当前目录')
        self.path_input.setText(os.getcwd())
        self.browse_btn = QPushButton('浏览')
        self.browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)
        layout.addLayout(path_layout)

        settings_group = QGroupBox('下载设置')
        settings_layout = QVBoxLayout()

        self.thread_checkbox = QCheckBox('启用多线程下载 (推荐)')
        self.thread_checkbox.setChecked(True)
        settings_layout.addWidget(self.thread_checkbox)

        thread_setting_layout = QHBoxLayout()
        thread_setting_layout.addWidget(QLabel('线程数:'))
        self.thread_combo = QComboBox()
        self.thread_combo.addItems(['4', '8', '16', '32'])
        self.thread_combo.setCurrentText('8')
        thread_setting_layout.addWidget(self.thread_combo)
        thread_setting_layout.addStretch()
        settings_layout.addLayout(thread_setting_layout)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel('视频质量:'))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(['最高画质', '1080P', '720P', '480P', '仅音频'])
        self.quality_combo.currentTextChanged.connect(self.on_quality_changed)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        settings_layout.addLayout(quality_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('%p%')
        progress_layout.addWidget(self.progress_bar)
        layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton('开始下载')
        self.download_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton('取消')
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(120)
        layout.addWidget(self.log_display)

        self.statusBar().showMessage('就绪')

    def on_quality_changed(self, text):
        self.quality_selected = text

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择保存目录')
        if folder:
            self.path_input.setText(folder)

    def get_format(self):
        quality = self.quality_combo.currentText()
        if quality == '最高画质':
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif quality == '1080P':
            return 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best'
        elif quality == '720P':
            return 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best'
        elif quality == '480P':
            return 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best'
        elif quality == '仅音频':
            return 'bestaudio/best'
        return 'best'

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, '警告', '请输入视频链接')
            return

        output_path = self.path_input.text().strip()
        if not output_path:
            output_path = os.getcwd()

        use_threading = self.thread_checkbox.isChecked()
        threads = int(self.thread_combo.currentText())

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_display.clear()
        self.progress_bar.setValue(0)

        self.download_thread = DownloadThread(url, output_path, use_threading, threads)
        self.download_thread.progress_signal.connect(self.update_log)
        self.download_thread.progress_percent_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()
        self.statusBar().showMessage('下载中...')

    def update_progress(self, percent):
        self.progress_bar.setValue(percent)

    def cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.statusBar().showMessage('已取消')
            self.log_display.append('下载已取消')

    def update_log(self, message):
        self.log_display.append(message)

    def download_finished(self, message, success):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if success:
            self.progress_bar.setValue(100)
            self.statusBar().showMessage('下载完成')
            QMessageBox.information(self, '完成', message)
        else:
            self.progress_bar.setValue(0)
            self.statusBar().showMessage('下载失败')
            QMessageBox.critical(self, '错误', message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDownloader()
    window.show()
    sys.exit(app.exec_())
