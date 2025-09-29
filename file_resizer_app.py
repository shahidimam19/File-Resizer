import sys, os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QLineEdit, QFrame, QFileDialog, QSizePolicy, QSpacerItem)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QPixmap, QImage, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QFontMetrics
import shutil
import atexit
import fitz # Import the PyMuPDF library to handle PDF previews

# This import assumes a file named 'file_resizer_backend.py' exists in the same directory.
from file_resizer_backend import resize_image, resize_pdf

class ResizerWorker(QThread):
    """Worker thread to perform file resizing in the background."""
    finished = pyqtSignal(bool, str)

    def __init__(self, file_path, file_type, target_kb, aspect_ratio=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_type = file_type
        self.target_kb = target_kb
        self.aspect_ratio = aspect_ratio
    
    def run(self):
        """The main function that runs in the new thread."""
        success = False
        output_path = None
        
        # 1. Determine the output path in the code file's location (temp file location)
        temp_dir = os.path.dirname(os.path.abspath(__file__))
        base_filename = os.path.splitext(os.path.basename(self.file_path))[0]
        
        try:
            if self.file_type == "image":
                # Ensure the output is always .jpg for maximum compression
                output_path = os.path.join(temp_dir, f"{base_filename}_resized.jpg")
                success = resize_image(self.file_path, output_path, self.target_kb, self.aspect_ratio)
            elif self.file_type == "pdf":
                # Ensure the output is always .pdf
                output_path = os.path.join(temp_dir, f"{base_filename}_resized.pdf")
                success = resize_pdf(self.file_path, output_path, self.target_kb)
        except Exception as e:
            print(f"An error occurred during resizing: {e}")
            self.finished.emit(False, str(e))
            return
            
        self.finished.emit(success, output_path)

class FileResizerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Resizer")
        self.set_dark_theme()
        
        self.current_file_path = None
        self.resized_file_path = None
        self.current_file_type = "image"
        
        self.initUI()
        self.showMaximized()
        
        # Register cleanup function to run on application exit
        atexit.register(self.clean_temp_file)

    def set_dark_theme(self):
        """Applies a dark theme to the application."""
        self.setStyleSheet("""
            QWidget {
                background-color: #2c2f33;
                color: #ffffff;
                font-family: Arial;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #7289da;
                color: #ffffff;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5b6eae;
            }
            QPushButton#selected_btn {
                background-color: #5b6eae;
                border: 2px solid #ffffff;
            }
            QPushButton#unselected_btn {
                background-color: #23272a;
                color: #ffffff;
                border: 2px solid #5b6eae;
            }
            QLineEdit {
                background-color: #40444b;
                border: 1px solid #7289da;
                border-radius: 5px;
                padding: 8px;
                color: #ffffff;
            }
            QFrame {
                border: none;
                border-radius: 10px;
                padding: 20px;
            }
        """)

    def initUI(self):
        """Initializes the main UI layout and widgets."""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(20)

        # Title
        title_label = QLabel("File Resizer")
        title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(title_label)
        
        # Status Label (moved here, above the main content)
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Main content layout (side-by-side)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Left section (Upload Frame)
        self.upload_frame = QFrame()
        self.upload_frame.setStyleSheet("QFrame { border: 2px solid #4f545c; }")
        upload_layout = QVBoxLayout()
        upload_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_frame.setFixedSize(QSize(450, 500))
        
        # --- DRAG-AND-DROP CHANGES START HERE ---
        self.upload_frame.setAcceptDrops(True)
        # We override the methods from QFrame to add our logic
        self.upload_frame.dragEnterEvent = self.dragEnterEvent
        self.upload_frame.dragLeaveEvent = self.dragLeaveEvent
        self.upload_frame.dropEvent = self.dropEvent
        # --- DRAG-AND-DROP CHANGES END HERE ---
        
        # Drag and drop section
        self.drag_drop_text = QLabel("Drag and drop image here")
        self.drag_drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.upload_preview_label = QLabel()
        self.upload_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_preview_label.setScaledContents(True)
        self.upload_preview_label.setMaximumSize(400, 400)
        self.upload_preview_label.hide() # Initially hide the preview label

        self.file_name_label = QLabel("No file selected")
        self.file_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_name_label.setWordWrap(False) # Keep this as False

        browse_button = QPushButton("Browse Files")
        browse_button.clicked.connect(self.open_file_dialog)
        
        upload_layout.addWidget(self.drag_drop_text, alignment=Qt.AlignmentFlag.AlignCenter)
        upload_layout.addWidget(self.upload_preview_label, alignment=Qt.AlignmentFlag.AlignCenter)
        upload_layout.addWidget(self.file_name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        upload_layout.addWidget(browse_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.upload_frame.setLayout(upload_layout)

        # Right section (Options and buttons)
        options_frame = QFrame()
        options_frame.setStyleSheet("QFrame { border: 2px solid #4f545c; background-color: #23272a; border-radius: 10px; padding: 15px; }")
        options_layout = QVBoxLayout()
        options_layout.setSpacing(20)
        options_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        options_frame.setFixedSize(QSize(450, 500))

        # File type selection
        file_type_layout = QHBoxLayout()
        file_type_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_type_layout.setSpacing(15)
        self.image_btn = QPushButton("Image")
        self.image_btn.setObjectName("selected_btn")
        self.image_btn.setFixedSize(120, 50)
        
        self.pdf_btn = QPushButton("PDF")
        self.pdf_btn.setObjectName("unselected_btn")
        self.pdf_btn.setFixedSize(120, 50)
        
        file_type_layout.addWidget(self.image_btn)
        file_type_layout.addWidget(self.pdf_btn)
        options_layout.addLayout(file_type_layout)

        target_size_layout = QVBoxLayout()
        target_size_layout.addWidget(QLabel("Target Size (KB)"))
        self.target_input = QLineEdit("100")
        target_size_layout.addWidget(self.target_input)
        options_layout.addLayout(target_size_layout)
        
        self.aspect_ratio_widget = QWidget()
        self.aspect_ratio_layout = QVBoxLayout(self.aspect_ratio_widget)
        self.aspect_ratio_layout.addWidget(QLabel("Aspect Ratio (W:H)"))
        aspect_input_layout = QHBoxLayout()
        self.aspect_w = QLineEdit("")
        self.aspect_h = QLineEdit("")
        aspect_input_layout.addWidget(self.aspect_w)
        aspect_input_layout.addWidget(QLabel(":"))
        aspect_input_layout.addWidget(self.aspect_h)
        self.aspect_ratio_layout.addLayout(aspect_input_layout)
        options_layout.addWidget(self.aspect_ratio_widget)
        
        # Action buttons (Resize, Download, Reset)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.resize_btn = QPushButton("Resize")
        self.resize_btn.clicked.connect(self.resize_file)
        
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download_file)
        self.download_btn.setEnabled(False) # Initially disabled
        
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_ui)
        
        button_layout.addWidget(self.resize_btn)
        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.reset_btn)
        options_layout.addLayout(button_layout)
        
        self.resized_info_label = QLabel("")
        self.resized_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resized_info_label.setWordWrap(True)
        options_layout.addWidget(self.resized_info_label)
        
        options_frame.setLayout(options_layout)
        
        content_layout.addWidget(self.upload_frame, 1)
        content_layout.addWidget(options_frame, 1)
        main_layout.addLayout(content_layout)
        
        # Add a vertical spacer to push content up
        spacer_item = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addItem(spacer_item)

        final_layout = QVBoxLayout(self)
        final_layout.addWidget(main_widget)
        self.setLayout(final_layout)
        
        self.image_btn.clicked.connect(lambda: self.on_file_type_selected("image"))
        self.pdf_btn.clicked.connect(lambda: self.on_file_type_selected("pdf"))
        self.on_file_type_selected("image")

    # --- DRAG-AND-DROP EVENT HANDLERS ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        Handles the drag-enter event.
        Changes the border color to provide visual feedback.
        """
        if event.mimeData().hasUrls():
            self.upload_frame.setStyleSheet("QFrame { border: 2px solid #7289da; }")
            self.status_label.setText("Drop file here")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """
        Handles the drag-leave event.
        Resets the border color and status text.
        """
        self.upload_frame.setStyleSheet("QFrame { border: 2px solid #4f545c; }")
        self.status_label.setText("")
        event.accept()

    def dropEvent(self, event: QDropEvent):
        """
        Handles the drop event.
        Processes the dropped file and resets the UI state.
        """
        self.upload_frame.setStyleSheet("QFrame { border: 2px solid #4f545c; }")
        self.status_label.setText("")
        
        urls = event.mimeData().urls()
        if urls and len(urls) > 0:
            file_path = urls[0].toLocalFile()
            self.handle_file_selected(file_path)
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def handle_file_selected(self, file_path):
        """
        A helper method to process a newly selected file from either
        the browse button or a drag-and-drop action.
        """
        self.clean_temp_file()
        self.current_file_path = file_path
        
        original_size_kb = os.path.getsize(file_path) / 1024
        file_name = os.path.basename(file_path)
        
        # Create a full string including the size
        full_text = f"{file_name} ({original_size_kb:.2f} KB)"
        
        # Get font metrics for the label
        metrics = QFontMetrics(self.file_name_label.font())
        
        # Get the maximum width of the label
        max_width = self.file_name_label.width()
        
        # Elide the text from the middle if it's too long
        elided_text = metrics.elidedText(full_text, Qt.TextElideMode.ElideMiddle, max_width)

        self.file_name_label.setText(elided_text)
        self.resized_info_label.setText("") # Clear previous results

        # Show a preview of the original file
        if self.current_file_type == "image":
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(self.upload_preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.upload_preview_label.setPixmap(scaled_pixmap)
            self.upload_preview_label.show()
            self.drag_drop_text.hide()
        elif self.current_file_type == "pdf":
            try:
                # Open the PDF file and get the first page
                doc = fitz.open(file_path)
                page = doc.load_page(0)
                
                # Render the page to a pixmap
                pix = page.get_pixmap()
                
                # Convert the PyMuPDF pixmap to a PyQt6 QImage
                qt_image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                
                # Convert the QImage to a QPixmap for the label
                pixmap = QPixmap.fromImage(qt_image)
                
                scaled_pixmap = pixmap.scaled(self.upload_preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.upload_preview_label.setPixmap(scaled_pixmap)
                self.upload_preview_label.show()
                self.drag_drop_text.hide()
                
                doc.close()
            except Exception as e:
                # Handle cases where the PDF can't be rendered
                print(f"Error rendering PDF preview: {e}")
                self.status_label.setText("Error: Could not render PDF preview.")
                self.upload_preview_label.hide()
                self.drag_drop_text.show()
        else:
            self.upload_preview_label.hide()
            self.drag_drop_text.show()
        
        self.status_label.setText("")

    def on_file_type_selected(self, file_type):
        """Updates the UI based on the selected file type (image/pdf)."""
        self.current_file_type = file_type
        
        if file_type == "image":
            self.image_btn.setObjectName("selected_btn")
            self.pdf_btn.setObjectName("unselected_btn")
            self.file_name_label.setText("No file selected")
            self.aspect_ratio_widget.setHidden(False)
            self.upload_preview_label.hide()
            self.drag_drop_text.show()
            self.drag_drop_text.setText("Drag and drop image here")
        else:
            self.image_btn.setObjectName("unselected_btn")
            self.pdf_btn.setObjectName("selected_btn")
            self.file_name_label.setText("No file selected")
            self.aspect_ratio_widget.setHidden(True)
            self.upload_preview_label.hide()
            self.drag_drop_text.show()
            self.drag_drop_text.setText("Drag and drop PDF here")
            
        self.image_btn.setStyleSheet(self.styleSheet())
        self.pdf_btn.setStyleSheet(self.styleSheet())

    def open_file_dialog(self):
        """Opens a file dialog to select an image or PDF file."""
        filter_text = ""
        if self.current_file_type == "image":
            filter_text = "Images (*.png *.jpg *.jpeg)"
        else:
            filter_text = "PDF Files (*.pdf)"
            
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", filter_text)
        
        if file_path:
            self.handle_file_selected(file_path)
            
    def resize_file(self):
        """Starts the resizing process in a separate thread."""
        if not self.current_file_path:
            self.status_label.setText("Please select a file first!")
            return
        
        self.status_label.setText("Resizing...")
        self.resize_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.resized_info_label.setText("")
        
        # Clean up any previous resized file before starting a new one
        self.clean_temp_file()

        try:
            target_kb = int(self.target_input.text())
        except ValueError:
            self.status_label.setText("Invalid target size. Please enter a number.")
            self.resize_btn.setEnabled(True)
            return

        aspect_ratio = None
        if self.current_file_type == "image":
            try:
                # Only use aspect ratio if both fields are filled
                if self.aspect_w.text() and self.aspect_h.text():
                    aspect_ratio = (int(self.aspect_w.text()), int(self.aspect_h.text()))
            except ValueError:
                self.status_label.setText("Invalid aspect ratio. Using original.")
                aspect_ratio = None
        
        # Create and start the worker thread
        self.worker = ResizerWorker(self.current_file_path, self.current_file_type, target_kb, aspect_ratio)
        self.worker.finished.connect(self.on_resizing_finished)
        self.worker.start()

    def on_resizing_finished(self, success, output):
        """Handles the result from the worker thread."""
        self.resize_btn.setEnabled(True)
        self.download_btn.setEnabled(success) # Enable download only on success

        if success:
            self.resized_file_path = output
            file_name = os.path.basename(output)
            file_size_kb = os.path.getsize(output) / 1024
            self.resized_info_label.setText(f"SUCCESS: {file_name} ({file_size_kb:.2f} KB)")
            self.status_label.setText("File resized successfully! Ready to download.")
        else:
            self.status_label.setText(f"Resizing failed: {output}")
            # If resizing fails, the path is invalid, so clear it.
            self.resized_file_path = None

    def download_file(self):
        """
        Opens a save file dialog to let the user save the resized file,
        then deletes the temporary file afterward.
        """
        if not self.resized_file_path or not os.path.exists(self.resized_file_path):
            self.status_label.setText("Please resize a file first!")
            return
        
        file_name = os.path.basename(self.resized_file_path)
        
        # Determine the file filter and default extension
        extension = os.path.splitext(file_name)[1]
        if extension.lower() in ['.jpg', '.jpeg']:
            filter_text = "JPEG Files (*.jpg *.jpeg)"
        else:
            filter_text = "PDF Files (*.pdf)"
        
        # Open the save file dialog
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Resized File", file_name, filter_text)
        
        if save_path:
            try:
                # Copy the temporary file to the user-selected location
                shutil.copy(self.resized_file_path, save_path)
                self.status_label.setText(f"File saved to: {save_path}")
                
                # 3. Delete the temporary file after successful copy/download
                self.clean_temp_file()
                self.download_btn.setEnabled(False)
                self.resized_info_label.setText(f"Download complete. Temporary file deleted.")
            except Exception as e:
                self.status_label.setText(f"Error saving file: {e}")
        else:
            self.status_label.setText("File download canceled. Temp file remains.")

    def reset_ui(self):
        """Resets the UI to its initial state and cleans up temp files."""
        # Clean up any temporary file
        self.clean_temp_file()
        
        self.current_file_path = None
        self.resized_file_path = None
        
        # Reset the border style explicitly
        self.upload_frame.setStyleSheet("QFrame { border: 2px solid #4f545c; }")
        
        self.on_file_type_selected("image")
        self.target_input.setText("100")
        self.aspect_w.setText("")
        self.aspect_h.setText("")
        self.file_name_label.setText("No file selected")
        self.resize_btn.setEnabled(True)
        self.download_btn.setEnabled(False)
        self.upload_preview_label.hide()
        self.resized_info_label.setText("")
        self.status_label.setText("")
        self.drag_drop_text.show()
        
    def clean_temp_file(self):
        """Deletes the temporary resized file if it exists."""
        if self.resized_file_path and os.path.exists(self.resized_file_path):
            try:
                os.remove(self.resized_file_path)
                print(f"Temporary file deleted: {self.resized_file_path}")
            except Exception as e:
                # Log error, but continue app execution
                print(f"Error deleting temporary file: {e}")
        # Crucially, clear the path reference after attempting deletion
        self.resized_file_path = None
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileResizerApp()
    window.show()
    sys.exit(app.exec())