from PySide2.QtCore import QSize
from PySide2.QtGui import QPixmap, QColor
from PySide2.QtWidgets import QLineEdit, QHBoxLayout, QFormLayout, QPushButton
from PySide6.QtCore import QFile
from PySide6.QtWidgets import QVBoxLayout, QTreeWidget, QTreeWidgetItem, QWidget, QLabel
from PySide6.QtGui import QIcon, Qt, QPalette, QBrush
from .utils import DockableWidget, ScriptJob
from maya import cmds


def get_image_path_from_type(object_type, default=':default.svg'):
    type_icon_path = f':{object_type}.svg'
    type_icon_file = QFile(type_icon_path)

    if type_icon_file.exists():
        image_path = type_icon_path
    else:
        image_path = default

    return image_path


class ReloadWidgetOnUndoScriptJob(ScriptJob):
    EVENT_NAME = 'Undo'

    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def run(self):
        self.widget.reload()


class ReloadWidgetOnRedoScriptJob(ScriptJob):
    EVENT_NAME = 'Redo'

    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def run(self):
        self.widget.reload()


class ReloadWidgetOnSceneOpenedScriptJob(ScriptJob):
    EVENT_NAME = 'SceneOpened'

    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def run(self):
        self.widget.reload()


class HighlightConstraintsOnSelectionChanged(ScriptJob):
    EVENT_NAME = 'SelectionChanged'

    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def run(self):
        selection = cmds.ls(sl=True, long=True)

        for constraint_item in self.widget.constraint_tree.constraint_items:
            # constraint_objects
            constraint = constraint_item.constraint
            parents = constraint.get_parents_paths()
            children = constraint.get_children_paths()

            constraint_objects = [constraint.path] + parents + children

            # selected_in_scene
            selected_in_scene = False

            for obj in constraint_objects:
                if obj in selection:
                    selected_in_scene = True
                    break

            constraint_item.selected_in_scene = selected_in_scene
            constraint_item.reload_color()


class Constraint:

    ignored_connections = (
        'MayaNodeEditorSavedTabsInfo'
    )

    def __init__(self):
        self.path = None

    def get_name(self):
        return self.path.split('|')[-1]

    def is_defective(self):
        defective = not self.get_parents() or not self.get_children()
        return defective

    def get_type(self):
        return cmds.objectType(self.path)

    def get_parents_paths(self):
        sources = cmds.listConnections(f'{self.path}.target', source=True, destination=False, fullNodeName=True) or list()

        parents = list()
        for source in sources:
            if source not in parents and source != self.path and source not in self.ignored_connections:
                parents.append(source)

        return parents

    def get_parents(self):
        return [x.split('|')[-1] for x in self.get_parents_paths()]

    def get_children_paths(self):
        destinations = cmds.listConnections(self.path, source=False, destination=True, fullNodeName=True) or list()

        children = list()
        for destination in destinations:
            if destination not in children and destination != self.path and destination not in self.ignored_connections:
                children.append(destination)

        return children

    def get_children(self):
        return [x.split('|')[-1] for x in self.get_children_paths()]

    def get_uuid(self):
        uuids = cmds.ls(self.path, uuid=True)
        if uuids:
            return uuids[0]
        else:
            return None

    @classmethod
    def get_all(cls):
        constraints = list()

        for constraint_path in cmds.ls(type='constraint', long=True):
            constraint = cls()
            constraint.path = constraint_path
            constraints.append(constraint)

        return constraints


class ConstraintItem(QTreeWidgetItem):
    def __init__(self):
        super().__init__()
        self.constraint = None

        self.defective = False
        self.selected_in_scene = False

        self.red_brush = QBrush(Qt.GlobalColor.red)
        self.blue_brush = QBrush(QColor(0, 255, 255))
        self.default_brush = self.foreground(0)

        self.setSizeHint(0, QSize(0, 25))

    def reload_color(self):
        if self.selected_in_scene:
            brush = self.blue_brush
        elif self.defective:
            brush = self.red_brush
        else:
            brush = self.default_brush

        self.setForeground(0, brush)

    def reload(self):
        self.setText(0, self.constraint.get_name())

        self.defective = self.constraint.is_defective()

        self.reload_color()

        icon_type_path = get_image_path_from_type(self.constraint.get_type())
        self.setIcon(0, QIcon(icon_type_path))


class ConstraintTree(QTreeWidget):
    def __init__(self):
        super().__init__()

        self.constraint_items = list()
        self.selection_memory = dict()

        self.setHeaderHidden(True)

        self.setSelectionMode(self.SelectionMode.ExtendedSelection)

    def get_selected_constraints(self):
        constraints = list()

        for constraint_item in self.selectedItems():
            if hasattr(constraint_item, 'constraint'):
                constraints.append(constraint_item.constraint)

        return constraints

    def clear(self):
        self.constraint_items = list()
        super().clear()

    def reload(self):
        # store selection
        for item in self.constraint_items:
            uuid = item.constraint.get_uuid()
            selected = item.isSelected()
            self.selection_memory[uuid] = selected

        # reload
        self.clear()

        for constraint in Constraint.get_all():
            constraint_item = ConstraintItem()
            constraint_item.constraint = constraint
            constraint_item.reload()
            self.addTopLevelItem(constraint_item)
            self.constraint_items.append(constraint_item)

        # restore selection
        for item in self.constraint_items:
            uuid = item.constraint.get_uuid()

            if uuid in self.selection_memory:
                selected = self.selection_memory[uuid]
                item.setSelected(selected)

        self.selection_memory = dict()


class ConstraintInfoWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.constraint_tree = None
        self.constraint = None

        self.default_pixmap = QPixmap(':mmEmpty.png')
        self.default_pixmap = self.default_pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        self.red_palette = QPalette()
        self.red_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.red)

        self.type_icon = QLabel()
        self.type_icon.setPixmap(self.default_pixmap)

        self.type_label = QLabel()

        type_info_layout = QHBoxLayout()
        type_info_layout.setContentsMargins(0, 0, 0, 0)
        type_info_layout.addSpacing(2)
        type_info_layout.addWidget(self.type_icon)
        type_info_layout.addWidget(self.type_label)

        type_info_layout_widget = QWidget()
        type_info_layout_widget.setLayout(type_info_layout)

        self.constraint_name_line = QLineEdit()
        self.constraint_name_line.editingFinished.connect(self.rename_constraint)

        self.parents_line = QLineEdit()
        self.parents_line.setReadOnly(True)

        self.parents_count_line = QLineEdit()
        self.parents_count_line.setMaximumWidth(25)
        self.parents_count_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.parents_count_line.setReadOnly(True)

        parents_layout = QHBoxLayout()
        parents_layout.setContentsMargins(0, 0, 0, 0)
        parents_layout.addWidget(self.parents_line)
        parents_layout.addWidget(self.parents_count_line)

        parents_layout_widget = QWidget()
        parents_layout_widget.setLayout(parents_layout)

        self.children_line = QLineEdit()
        self.children_line.setReadOnly(True)

        self.children_count_line = QLineEdit()
        self.children_count_line.setMaximumWidth(25)
        self.children_count_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.children_count_line.setReadOnly(True)

        children_layout = QHBoxLayout()
        children_layout.setContentsMargins(0, 0, 0, 0)
        children_layout.addWidget(self.children_line)
        children_layout.addWidget(self.children_count_line)

        children_layout_widget = QWidget()
        children_layout_widget.setLayout(children_layout)

        self.default_palette = self.children_line.palette()

        main_layout = QFormLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addRow('Name', self.constraint_name_line)
        main_layout.addRow('Type', type_info_layout_widget)
        main_layout.addRow('Parents', parents_layout_widget)
        main_layout.addRow('Children', children_layout_widget)

    def rename_constraint(self):
        if not self.constraint:
            return

        new_name = self.constraint_name_line.text()

        if self.constraint.get_name() == new_name:
            return

        new_path = cmds.rename(self.constraint.path, new_name)
        self.constraint.path = new_path

        self.constraint_tree.reload()

    def clear(self):
        self.type_icon.setPixmap(self.default_pixmap)

        self.constraint_name_line.setText('')
        self.type_label.setText('')

        self.parents_line.setText('')
        self.parents_line.setPalette(self.default_palette)

        self.parents_count_line.setText('')

        self.children_line.setText('')
        self.children_line.setPalette(self.default_palette)

        self.children_line.setText('')

        self.constraint_name_line.setReadOnly(True)

    def reload(self):
        self.clear()

        if self.constraint is None:
            return

        constraint_type = self.constraint.get_type()

        type_image_path = get_image_path_from_type(constraint_type)

        pixmap = QPixmap(type_image_path)
        pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        self.type_icon.setPixmap(pixmap)

        self.constraint_name_line.setText(self.constraint.get_name())
        self.constraint_name_line.setReadOnly(False)

        self.type_label.setText(constraint_type)

        parents = self.constraint.get_parents()
        if parents:
            parents_str = ', '.join(parents)
            self.parents_line.setText(parents_str)
        else:
            self.parents_line.setText('No parents found')
            self.parents_line.setPalette(self.red_palette)

        self.parents_count_line.setText(str(len(parents)))

        children = self.constraint.get_children()
        if children:
            children_str = ', '.join(children)
            self.children_line.setText(children_str)
        else:
            self.children_line.setText('No children found')
            self.children_line.setPalette(self.red_palette)

        self.children_count_line.setText(str(len(children)))


class ConstraintEditor(DockableWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Constraint Editor')
        self.resize(500, 700)

        self.scriptJobs = (
            ReloadWidgetOnUndoScriptJob(self),
            ReloadWidgetOnRedoScriptJob(self),
            ReloadWidgetOnSceneOpenedScriptJob(self),
            HighlightConstraintsOnSelectionChanged(self),
        )

        self.constraint_info_widget = ConstraintInfoWidget()

        select_constraints_btn = QPushButton()
        select_constraints_btn.setIcon(QIcon(':out_aimConstraint.png'))
        select_constraints_btn.clicked.connect(self.select_constraints)

        select_parents_btn = QPushButton()
        select_parents_btn.setIcon(QIcon(':input.png'))
        select_parents_btn.clicked.connect(self.select_parents)

        select_children_btn = QPushButton()
        select_children_btn.setIcon(QIcon(':output.png'))
        select_children_btn.clicked.connect(self.select_children)

        delete_constraints_btn = QPushButton()
        delete_constraints_btn.setIcon(QIcon(':trash.png'))
        delete_constraints_btn.clicked.connect(self.delete_constraints)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        btn_layout.addWidget(select_parents_btn)
        btn_layout.addWidget(select_constraints_btn)
        btn_layout.addWidget(select_children_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(delete_constraints_btn)

        self.constraint_tree = ConstraintTree()
        self.constraint_tree.itemSelectionChanged.connect(self.reload_constraint_info_widget)
        self.constraint_info_widget.constraint_tree = self.constraint_tree

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.constraint_tree)
        main_layout.addWidget(self.constraint_info_widget)

        self.reload()

    def hideEvent(self, event):
        for script_job in self.scriptJobs:
            script_job.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        for script_job in self.scriptJobs:
            script_job.start()
        super().showEvent(event)

    def delete_constraints(self):
        selected_constraints = self.constraint_tree.get_selected_constraints()
        existing_constraints = [x.path for x in selected_constraints if cmds.objExists(x.path)]
        cmds.delete(existing_constraints)

        self.constraint_tree.reload()

    def select_constraints(self):
        selected_constraints = self.constraint_tree.get_selected_constraints()

        constraint_names = list()
        for constraint in selected_constraints:
            constraint_names.append(constraint.path)

        cmds.select(constraint_names)

    def select_parents(self):
        selected_constraints = self.constraint_tree.get_selected_constraints()

        parents = list()
        for constraint in selected_constraints:
            for parent in constraint.get_parents():
                if parent not in parents:
                    parents.append(parent)

        cmds.select(parents)

    def select_children(self):
        selected_constraints = self.constraint_tree.get_selected_constraints()

        children = list()
        for constraint in selected_constraints:
            for child in constraint.get_children():
                if child not in children:
                    children.append(child)

        cmds.select(children)

    def reload(self):
        self.constraint_tree.reload()
        self.reload_constraint_info_widget()

    def reload_constraint_info_widget(self, *args, **kwargs):
        selected_constraints = self.constraint_tree.get_selected_constraints()

        if len(selected_constraints) == 1:
            selected_constraint = selected_constraints[0]
        else:
            selected_constraint = None

        self.constraint_info_widget.constraint = selected_constraint
        self.constraint_info_widget.reload()


def open_constraint_editor():
    ConstraintEditor.open_in_workspace()