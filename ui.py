from PySide2.QtCore import QSize
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QLineEdit, QHBoxLayout, QFormLayout
from PySide6.QtWidgets import QVBoxLayout, QTreeWidget, QTreeWidgetItem, QWidget, QLabel
from PySide6.QtGui import QIcon, Qt, QPalette, QBrush
from .utils import DockableWidget
from maya import cmds


class Constraint:

    def __init__(self):
        self.name = None

    def is_defective(self):
        has_parents = bool(self.get_parents())
        has_children = bool(self.get_children())
        defective = not has_parents and not has_children
        return defective

    def get_type(self):
        return cmds.objectType(self.name)

    def get_parents(self):
        sources = cmds.listConnections(f'{self.name}.target', source=True, destination=False) or list()

        parents = list()
        for source in sources:
            if source not in parents and source != self.name:
                parents.append(source)

        return parents

    def get_children(self):
        destinations = cmds.listConnections(self.name, source=False, destination=True) or list()

        children = list()
        for destination in destinations:
            if destination not in children and destination != self.name:
                children.append(destination)

        return children

    @classmethod
    def get_all(cls):
        constraints = list()

        for constraint_name in cmds.ls(type='constraint'):
            constraint = cls()
            constraint.name = constraint_name
            constraints.append(constraint)

        return constraints


class ConstraintItem(QTreeWidgetItem):
    def __init__(self):
        super().__init__()
        self.constraint = None

        self.red_brush = QBrush(Qt.GlobalColor.red)
        self.default_brush = self.foreground(0)

        self.setSizeHint(0, QSize(0, 25))

    def reload(self):
        self.setText(0, self.constraint.name)

        if self.constraint.is_defective():
            brush = self.red_brush
        else:
            brush = self.default_brush

        self.setForeground(0, brush)

        self.setIcon(0, QIcon(f':{self.constraint.get_type()}.svg'))


class ConstraintTree(QTreeWidget):
    def __init__(self):
        super().__init__()

        self.setHeaderHidden(True)

    def get_selected_constraints(self):
        constraints = list()

        for constraint_item in self.selectedItems():
            if hasattr(constraint_item, 'constraint'):
                constraints.append(constraint_item.constraint)

        return constraints

    def reload(self):
        self.clear()

        for constraint in Constraint.get_all():
            constraint_item = ConstraintItem()
            constraint_item.constraint = constraint
            constraint_item.reload()
            self.addTopLevelItem(constraint_item)


class ConstraintInfoWidget(QWidget):
    def __init__(self):
        super().__init__()

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

        self.constraint_name = QLineEdit()
        self.constraint_name.setPlaceholderText('Name')

        self.parents_line = QLineEdit()
        self.parents_line.setReadOnly(True)
        self.parents_line.setPlaceholderText('Parents')

        self.children_line = QLineEdit()
        self.children_line.setReadOnly(True)
        self.children_line.setPlaceholderText('Children')

        self.default_palette = self.children_line.palette()

        main_layout = QFormLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addRow('Name', self.constraint_name)
        main_layout.addRow('Type', type_info_layout_widget)
        main_layout.addRow('Parents', self.parents_line)
        main_layout.addRow('Children', self.children_line)

    def clear(self):
        self.type_icon.setPixmap(self.default_pixmap)
        self.constraint_name.setText('')
        self.type_label.setText('')

        self.parents_line.setText('')
        self.parents_line.setPalette(self.default_palette)

        self.children_line.setText('')
        self.children_line.setPalette(self.default_palette)

    def reload(self):
        self.clear()

        if self.constraint is None:
            return

        constraint_type = self.constraint.get_type()

        pixmap = QPixmap(f':{constraint_type}.svg')
        pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        self.type_icon.setPixmap(pixmap)
        self.constraint_name.setText(self.constraint.name)
        self.type_label.setText(constraint_type)

        parents = self.constraint.get_parents()
        if parents:
            parents_str = ', '.join(parents)
            self.parents_line.setText(parents_str)
        else:
            self.parents_line.setText('No parents found')
            self.parents_line.setPalette(self.red_palette)

        children = self.constraint.get_children()
        if children:
            children_str = ', '.join(children)
            self.children_line.setText(children_str)
        else:
            self.children_line.setText('No children found')
            self.children_line.setPalette(self.red_palette)


class ConstraintEditor(DockableWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Constraint Editor')
        self.resize(500, 700)

        self.constraint_info_widget = ConstraintInfoWidget()

        self.constraint_tree = ConstraintTree()
        self.constraint_tree.itemSelectionChanged.connect(self.reload_constraint_info_widget)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.constraint_tree)
        main_layout.addWidget(self.constraint_info_widget)

        self.reload()

    def reload(self):
        self.constraint_tree.reload()
        self.reload_constraint_info_widget()

    def reload_constraint_info_widget(self, *args, **kwargs):
        selected_constraints = self.constraint_tree.get_selected_constraints()

        if selected_constraints:
            selected_constraint = selected_constraints[-1]
        else:
            selected_constraint = None

        self.constraint_info_widget.constraint = selected_constraint
        self.constraint_info_widget.reload()


def open_constraint_editor():
    ConstraintEditor.open_in_workspace()