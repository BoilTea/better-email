"""Shared Qt widget styling, scrolling, and bundled-resource helpers."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListView, QScrollArea, QStyledItemDelegate, QTextEdit,
    QWidget,
)


def resource_path(filename):
    """Resolve resources from the repository root or a PyInstaller bundle."""
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return str(base_path / filename)


def make_field_label(title, description, font):
    """Place a compact, accessible circled exclamation mark next to a label."""
    header = QWidget()
    header.setStyleSheet("background-color: transparent;")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(0, 5, 0, 0)
    layout.setSpacing(6)
    label = QLabel(title)
    label.setFont(font)
    label.setStyleSheet("color: #34495e; background-color: transparent;")
    layout.addWidget(label)

    help_icon = QLabel("!")
    help_icon.setObjectName("fieldHelpIcon")
    help_icon.setFixedSize(16, 16)
    help_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    help_icon.setCursor(Qt.CursorShape.WhatsThisCursor)
    help_icon.setToolTip(description)
    help_icon.setAccessibleName(f"Help for {title}")
    help_icon.setAccessibleDescription(description)
    help_icon.setStyleSheet("""
        QLabel {
            color: #8c83b3; background-color: #f7f5ff;
            border: 1px solid #bcb4d9; border-radius: 8px;
            font-size: 11px; font-weight: 600; padding: 0; margin: 0;
        }
        QLabel:hover { color: #5d50c6; border-color: #6d5bd0; }
    """)
    layout.addWidget(help_icon)
    layout.addStretch()
    return header


class ComboBoxItemDelegate(QStyledItemDelegate):
    """Keep combo-box popup rows comfortably spaced on every platform."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(44)
        return size



def configure_modern_combo_box(combo_box):
    """Apply a consistent modern popup and triangle indicator."""
    arrow_path = resource_path("dropdown_arrow.svg").replace("\\", "/")
    combo_box.setCursor(Qt.CursorShape.PointingHandCursor)
    combo_box.setMaxVisibleItems(8)
    combo_box.setStyleSheet(f"""
        QComboBox {{
            color: #20283a;
            background-color: #f8f9fc;
            border: 1px solid #dfe4ee;
            border-radius: 10px;
            padding: 9px 40px 9px 12px;
            min-height: 25px;
            font-size: 14px;
        }}
        QComboBox:hover, QComboBox:focus {{
            background-color: white;
            border: 2px solid #6d5bd0;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 34px;
        }}
        QComboBox::down-arrow {{
            image: url("{arrow_path}");
            width: 10px;
            height: 6px;
        }}
    """)

    popup = QListView(combo_box)
    popup.setMouseTracking(True)
    popup.setSpacing(4)
    popup.setUniformItemSizes(True)
    popup.setItemDelegate(ComboBoxItemDelegate(popup))
    popup.setStyleSheet("""
        QListView {
            color: #20283a;
            background-color: white;
            border: 1px solid #dfe4ee;
            border-radius: 10px;
            padding: 6px;
            outline: 0;
        }
        QListView::item {
            padding: 0 12px;
            border-radius: 8px;
        }
        QListView::item:hover {
            color: #4d3aaf;
            background-color: #f3f1ff;
        }
        QListView::item:selected {
            color: #4d3aaf;
            background-color: #e9e5ff;
        }
    """)
    combo_box.setView(popup)



def hide_text_edit_scrollbars(root_widget):
    """Keep multiline editors scrollable without showing scrollbar chrome."""
    for editor in root_widget.findChildren(QTextEdit):
        editor.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        editor.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )



def make_settings_scroll_page(content_widget):
    """Wrap a settings tab so compact windows can reach all of its content."""
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    scroll_area.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    scroll_area.setStyleSheet(
        "QScrollArea { border: none; background-color: white; }"
    )
    scroll_area.viewport().setStyleSheet("background-color: white;")
    scroll_area.setWidget(content_widget)
    return scroll_area

