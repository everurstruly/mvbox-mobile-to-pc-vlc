from PySide6 import QtWidgets, QtCore, QtGui
import pythoncom

class MtpFolderPickerDialog(QtWidgets.QDialog):
    def __init__(self, parent, device_name, config):
        super().__init__(parent)
        self.device_name = device_name
        self.config = config
        self.selected_paths = []
        self.current_stack = [] # list of folder names
        
        self.setWindowTitle("Select Folders to Scan")
        self.resize(500, 600)
        self.setStyleSheet(parent.styleSheet() + """
            QDialog { background-color: #0e0e0e; }
            QListWidget { 
                background-color: #131313; 
                border-radius: 12px; 
                border: 1px solid rgba(255,255,255,0.05); 
                padding: 10px;
                color: white; 
                font-size: 14px;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.03); }
            QListWidget::item:selected { background-color: #20201f; color: #c59aff; }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        self.breadcrumb = QtWidgets.QLabel(f"Device: {device_name}")
        self.breadcrumb.setStyleSheet("color: #888; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.breadcrumb)
        
        title = QtWidgets.QLabel("Browse Device")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 24px; font-weight: 800;")
        layout.addWidget(title)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.drill_down)
        layout.addWidget(self.list_widget)
        
        btn_layout = QtWidgets.QHBoxLayout()
        self.back_btn = QtWidgets.QPushButton("Back")
        self.back_btn.setObjectName("secondary")
        self.back_btn.clicked.connect(self.drill_up)
        
        self.add_btn = QtWidgets.QPushButton("Select Current Folder")
        self.add_btn.setObjectName("secondary")
        self.add_btn.clicked.connect(self.select_current)
        
        btn_layout.addWidget(self.back_btn)
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)
        
        self.selection_label = QtWidgets.QLabel("No folders selected")
        self.selection_label.setStyleSheet("color: #c59aff; font-size: 12px;")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)
        
        final_layout = QtWidgets.QHBoxLayout()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        
        self.confirm_btn = QtWidgets.QPushButton("Confirm Selection")
        self.confirm_btn.setObjectName("primary")
        self.confirm_btn.clicked.connect(self.accept)
        
        final_layout.addWidget(cancel_btn)
        final_layout.addWidget(self.confirm_btn)
        layout.addLayout(final_layout)
        
        self.load_current_folder()
        
    def load_current_folder(self):
        self.list_widget.clear()
        pythoncom.CoInitialize()
        try:
            from ..devices.mtp_client import get_device_root, get_mtp_subfolder
            root_item = get_device_root(self.device_name)
            if not root_item: return
            
            path_str = "/".join(self.current_stack)
            target = get_mtp_subfolder(root_item.GetFolder, path_str)
            
            if target:
                items = target.Items()
                folder_names = []
                for i in items:
                    if i.IsFolder: folder_names.append(i.Name)
                
                folder_names.sort(key=str.lower)
                for name in folder_names:
                    item_widget = QtWidgets.QListWidgetItem("📁 " + name)
                    item_widget.setData(QtCore.Qt.UserRole, name)
                    self.list_widget.addItem(item_widget)
            
            self.breadcrumb.setText(" > ".join([self.device_name] + self.current_stack))
            self.back_btn.setEnabled(len(self.current_stack) > 0)
        finally:
            pythoncom.CoUninitialize()
            
    def drill_down(self, item):
        folder_name = item.data(QtCore.Qt.UserRole)
        self.current_stack.append(folder_name)
        self.load_current_folder()
        
    def drill_up(self):
        if self.current_stack:
            self.current_stack.pop()
            self.load_current_folder()
            
    def select_current(self):
        path = "/".join(self.current_stack)
        if not path: return
        if path not in self.selected_paths:
            self.selected_paths.append(path)
            self.update_selection_label()
            
    def update_selection_label(self):
        if not self.selected_paths:
            self.selection_label.setText("No folders selected")
        else:
            self.selection_label.setText("Selected: " + ", ".join(self.selected_paths))
