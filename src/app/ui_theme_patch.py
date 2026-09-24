from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QSizePolicy,
    QPushButton,
    QLabel,
    QToolBar,
    QToolButton,
    QWidget,
)


UI_METRICS = {
    "menu_bar_h": 30,
    "menu_button_h": 24,
    "tab_h": 24,
    "panel_header_h": 30,
    "layer_row_h": 30,
    "header_icon": 28,
    "status_bar_h": 22,
}

GLOBAL_STYLE = """
/* =========================================================
   MAP PLAN3D - UNIFIED UI SYSTEM
   ========================================================= */

QWidget {
    background-color: #121315;
    color: #E7E9EC;
    font-family: "Segoe UI";
    font-size: 10px;
    selection-background-color: #29445F;
    selection-color: #FFFFFF;
}

/* =========================================================
   MAIN WINDOW
   ========================================================= */

QMainWindow {
    background-color: #101113;
    border: none;
}

/* =========================================================
   CUSTOM TOP MENU TOOLBAR
   ========================================================= */

QToolBar#topMenuToolbar {
    background-color: #0E0F11;
    border: none;
    border-bottom: 1px solid #24262A;
    spacing: 3px;
    padding: 3px 8px;
}

QToolButton#topMenuButton {
    background-color: #1D1E20;
    color: #D8DADF;
    border: 1px solid #34363A;
    border-radius: 4px;
    padding: 0px;
    margin: 0px;
    font-family: "Segoe UI";
    font-size: 11px;
    font-weight: 500;
}

QToolButton#topMenuButton:hover {
    background-color: #192A3B;
    color: #FFFFFF;
    border: 1px solid #385F86;
}

QToolButton#topMenuButton:pressed,
QToolButton#topMenuButton:checked {
    background-color: #20364B;
    color: #FFFFFF;
    border: 1px solid #4F7EAC;
}

QToolBar#topMenuToolbar QToolButton#qt_toolbar_ext_button {
    width: 0px;
    max-width: 0px;
    min-width: 0px;
    border: none;
    padding: 0px;
    margin: 0px;
}

/* =========================================================
   MENU BAR
   ========================================================= */

QMenuBar {
    background-color: #0E0F11;
    color: #E7E9EC;
    border: none;
    border-bottom: 1px solid #24262A;
    padding: 3px 8px;
    spacing: 5px;
    min-height: 30px;
    max-height: 30px;
}

QMenuBar::item {
    background-color: #202225;
    color: #F0F1F3;
    border: 1px solid #34363A;
    border-radius: 3px;
    padding: 3px 18px;
    margin: 0px 2px;
    min-height: 18px;
    font-family: "Segoe UI";
    font-size: 11px;
    font-weight: 500;
}

QMenuBar::item:selected {
    background-color: #25272B;
    color: #FFFFFF;
    border: 1px solid #464A50;
}

QMenuBar::item:pressed {
    background-color: #26384A;
    color: #FFFFFF;
    border: 1px solid #52779A;
}

/* =========================================================
   POPUP MENUS
   ========================================================= */

QMenu {
    background-color: #18191B;
    color: #E7E9EC;
    border: 1px solid #34373B;
    border-radius: 6px;
    padding: 5px;
}

QMenu::item {
    background-color: transparent;
    color: #E3E5E8;
    padding: 6px 18px 6px 10px;
    margin: 2px;
    border-radius: 3px;
    min-width: 120px;
}

QMenu::item:selected {
    background-color: #26282C;
    color: #FFFFFF;
}

QMenu::item:pressed {
    background-color: #2A3948;
}

QMenu::item:disabled {
    color: #686C72;
}

QMenu::separator {
    height: 1px;
    background-color: #303338;
    margin: 5px 7px;
}

/* =========================================================
   TABS
   ========================================================= */

QTabWidget::pane {
    background-color: #101113;
    border: none;
}

QTabBar {
    background-color: #101113;
}

QTabBar::tab {
    background-color: #202225;
    color: #C8CDD3;
    border: 1px solid #34363A;
    border-radius: 3px;
    min-height: 24px;
    max-height: 24px;
    min-width: 100px;
    padding: 0px 14px;
    margin: 0px 3px 0px 0px;
}

QTabBar::tab:selected {
    background-color: #2A2C30;
    color: #FFFFFF;
    border: 1px solid #4A4E55;
}

QTabBar::tab:hover:!selected {
    background-color: #25272B;
    color: #ECEEF1;
    border: 1px solid #464A50;
}

/* =========================================================
   GENERIC BUTTONS
   ========================================================= */

QPushButton {
    background-color: #202225;
    color: #E5E7EA;
    border: 1px solid #383B40;
    border-radius: 4px;
    min-height: 26px;
    padding: 0px 10px;
}

QPushButton:hover {
    background-color: #25303A;
    color: #FFFFFF;
    border: 1px solid #415E7A;
}

QPushButton:pressed {
    background-color: #2A3B4C;
    border: 1px solid #52779A;
}

QPushButton:disabled {
    background-color: #17181A;
    color: #60646A;
    border: 1px solid #292B2F;
}

/* =========================================================
   START CARDS
   ========================================================= */

QPushButton#startCard {
    background-color: #191A1D;
    color: #F1F2F4;
    border: 1px solid #35383D;
    border-radius: 18px;
    min-width: 240px;
    max-width: 240px;
    min-height: 240px;
    max-height: 240px;
    padding: 0px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#startCard:hover {
    background-color: #20262C;
    border: 1px solid #405B74;
}

QPushButton#startCard:pressed {
    background-color: #26323E;
    border: 1px solid #54789A;
}

/* =========================================================
   TOOL BUTTONS
   ========================================================= */

QToolButton {
    background-color: transparent;
    color: #D8DADF;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0px;
}

QToolButton:hover {
    background-color: #192A3B;
    border: 1px solid #385F86;
}

QToolButton:pressed {
    background-color: #20364B;
    border: 1px solid #4F7EAC;
}

/* =========================================================
   INPUTS
   ========================================================= */

QLineEdit,
QSpinBox,
QDoubleSpinBox {
    background-color: #1C1E21;
    color: #E7E9EC;
    border: 1px solid #34373B;
    border-radius: 3px;
    min-height: 23px;
    padding: 0px 6px;
}

QLineEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover {
    border: 1px solid #464A50;
}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #486B8C;
}

/* =========================================================
   COMBO BOX
   ========================================================= */

QComboBox {
    background-color: #202225;
    color: #E5E7EA;
    border: 1px solid #34363A;
    border-radius: 3px;
    min-height: 22px;
    padding-left: 7px;
    padding-right: 20px;
}

QComboBox:hover {
    background-color: #25272B;
    border: 1px solid #464A50;
}

QComboBox:focus {
    border: 1px solid #486B8C;
}

QComboBox::drop-down {
    width: 18px;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #1C1D1F;
    color: #E5E7EA;
    border: 1px solid #34363A;
    selection-background-color: #26384A;
    selection-color: #FFFFFF;
    outline: none;
    padding: 3px;
}

/* =========================================================
   SCROLLBARS
   ========================================================= */

QScrollBar:vertical {
    background-color: #111214;
    width: 8px;
    margin: 2px 1px 2px 1px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #4B4E53;
    min-height: 28px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #666A70;
}

QScrollBar::handle:vertical:pressed {
    background-color: #7A7F86;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background-color: #111214;
    height: 8px;
    margin: 1px 2px 1px 2px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #4B4E53;
    min-width: 28px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #666A70;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* =========================================================
   SHARED LEFT TOOL DOCK
   ========================================================= */

QFrame#toolPanelDock {
    background-color: #111214;
    border: none;
}

QFrame#layersPanel,
QFrame#propertiesPanel {
    background-color: #18191B;
    border: 1px solid #2D3034;
    border-radius: 0px;
}

QFrame#layersHeader,
QFrame#propertiesHeader {
    background-color: #1C1D1F;
    border: none;
    border-bottom: 1px solid #34363A;
}

QLabel#layersTitle,
QLabel#propertiesTitle {
    background-color: transparent;
    color: #F0F1F3;
    border: none;
    font-size: 11px;
    font-weight: 600;
}

/* =========================================================
   HEADER ICON BUTTONS
   ========================================================= */

QToolButton#layersWindowButton,
QToolButton#propertiesWindowButton {
    background-color: #1D1E20;
    border: 1px solid #34363A;
    border-radius: 4px;
}

QToolButton#layersWindowButton:hover,
QToolButton#propertiesWindowButton:hover {
    background-color: #192A3B;
    border: 1px solid #385F86;
}

QToolButton#layersWindowButton:pressed,
QToolButton#propertiesWindowButton:pressed {
    background-color: #20364B;
    border: 1px solid #4F7EAC;
}

/* =========================================================
   LAYERS
   ========================================================= */

QScrollArea#layersScroll,
QScrollArea#propertiesScroll {
    background-color: #18191B;
    border: none;
}

QWidget#layersContent,
QWidget#propertiesBody {
    background-color: #18191B;
    border: none;
}

QFrame#layerRow {
    background-color: #18191B;
    border: 1px solid transparent;
    border-bottom: 1px solid #25272A;
    border-radius: 3px;
    min-height: 30px;
    max-height: 30px;
}

QFrame#layerRow:hover {
    background-color: #192A3B;
    border: 1px solid #385F86;
    border-radius: 3px;
}

QLabel#layerName {
    background-color: transparent;
    color: #E5E7EA;
    border: none;
    font-size: 10px;
}

QFrame#layerRow:hover QLabel#layerName {
    color: #FFFFFF;
}

/* =========================================================
   PROPERTIES
   ========================================================= */

QLabel#propKey {
    background-color: transparent;
    color: #858A92;
    border: none;
    font-size: 9px;
}

QLabel#propValue {
    background-color: transparent;
    color: #E9EAEC;
    border: none;
    font-size: 10px;
}

QPushButton#propertiesActionButton {
    background-color: #202225;
    color: #E4E6E9;
    border: 1px solid #383B40;
    border-radius: 3px;
    min-height: 27px;
}

QPushButton#propertiesActionButton:hover {
    background-color: #24303C;
    border: 1px solid #42617F;
    color: #FFFFFF;
}

/* =========================================================
   HISTORY + STATUS
   ========================================================= */

QFrame#historyPanel {
    background-color: #17181A;
    border-top: 1px solid #2C2E32;
    border-bottom: 1px solid #25272A;
}

QPushButton#historyButton {
    background-color: transparent;
    color: #BFC3C8;
    border: none;
    border-radius: 0px;
    min-height: 22px;
    max-height: 22px;
    padding: 0px 8px;
}

QPushButton#historyButton:hover {
    background-color: #202225;
    color: #FFFFFF;
}

/* =========================================================
   TOOLTIP
   ========================================================= */

QToolTip {
    background-color: #202225;
    color: #F0F1F3;
    border: 1px solid #3A3D42;
    padding: 4px 6px;
}
"""


def _style_panel(panel):
    panel.setStyleSheet(GLOBAL_STYLE)
    panel.setSizePolicy(
        QSizePolicy.Fixed,
        QSizePolicy.Expanding,
    )


def _install_custom_top_menu(window):
    if hasattr(window, "_plan3d_top_menu_toolbar"):
        return

    menu_bar = window.menuBar()

    if menu_bar is None:
        return

    source_actions = []

    for action in menu_bar.actions():
        text = action.text().replace("&", "").strip()

        if text in ("File", "Edit", "Tools"):
            source_actions.append(
                (
                    text,
                    action.menu(),
                )
            )

    if not source_actions:
        return

    toolbar = QToolBar(window)
    toolbar.setObjectName("topMenuToolbar")

    toolbar.setMovable(False)
    toolbar.setFloatable(False)

    toolbar.setAllowedAreas(
        Qt.TopToolBarArea
    )

    toolbar.setFixedHeight(
        30
    )

    toolbar.setIconSize(
        toolbar.iconSize()
    )

    for text, menu in source_actions:
        button = QToolButton(toolbar)

        button.setObjectName(
            "topMenuButton"
        )

        button.setText(
            text
        )

        button.setFixedSize(
            64,
            24,
        )

        button.setToolButtonStyle(
            Qt.ToolButtonTextOnly
        )

        if menu is not None:
            button.setMenu(
                menu
            )

            button.setPopupMode(
                QToolButton.InstantPopup
            )

        toolbar.addWidget(
            button
        )

        if text != source_actions[-1][0]:
            spacer_gap = QWidget(toolbar)
            spacer_gap.setFixedWidth(3)
            toolbar.addWidget(spacer_gap)

    spacer = QWidget(toolbar)

    spacer.setSizePolicy(
        QSizePolicy.Expanding,
        QSizePolicy.Preferred,
    )

    toolbar.addWidget(
        spacer
    )

    window.addToolBar(
        Qt.TopToolBarArea,
        toolbar,
    )

    # Old QMenuBar is no longer used visually.
    menu_bar.hide()

    window._plan3d_top_menu_toolbar = toolbar



def _install_start_card_title_hover(window):
    module = __import__("__main__")
    StartCard = getattr(module, "StartCard", None)

    if StartCard is None:
        return

    for card in window.findChildren(StartCard):
        title_label = None

        # Find only the exact Open / New title label.
        for label in card.findChildren(QLabel):
            text = label.text().strip()

            if text in ("Open", "New"):
                title_label = label
                break

        if title_label is None:
            continue

        # Keep original title appearance when not hovered.
        title_label.setProperty(
            "plan3dStartTitle",
            True
        )

        title_label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #F1F2F4;
                border: none;
            }
        """)

        original_enter = card.enterEvent
        original_leave = card.leaveEvent

        def enter_event(
            event,
            _original=original_enter,
            _label=title_label,
            _card=card
        ):
            _original(event)

            _card.setStyleSheet("""
                QPushButton {
                    background-color: #20262C;
                    border: 1px solid #405B74;
                    border-radius: 18px;
                    color: #F1F2F4;
                }
            """)

            _label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #78AEFF;
                    border: none;
                }
            """)

        def leave_event(
            event,
            _original=original_leave,
            _label=title_label,
            _card=card
        ):
            _original(event)

            _card.setStyleSheet("""
                QPushButton {
                    background-color: #191A1D;
                    border: 1px solid #35383D;
                    border-radius: 18px;
                    color: #F1F2F4;
                }
            """)

            _label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #F1F2F4;
                    border: none;
                }
            """)

        card.enterEvent = enter_event
        card.leaveEvent = leave_event


def _mark_named_widgets(window):
    for button in window.findChildren(QPushButton):
        if button.text().strip() == "History":
            button.setObjectName(
                "historyButton"
            )

    module = __import__("__main__")

    StartCard = getattr(
        module,
        "StartCard",
        None,
    )

    if StartCard is not None:
        for card in window.findChildren(
            StartCard
        ):
            card.setObjectName(
                "startCard"
            )

            card.setFixedSize(
                240,
                240,
            )


def install_plan3d_theme_patch(
    MainWindow,
    CadPage,
    LayersPanel,
    EyeToggleButton,
):
    try:
        from project_runtime import (
            PropertiesPanel,
            ToolPanelDock,
        )
    except Exception:
        PropertiesPanel = None
        ToolPanelDock = None

    # -----------------------------------------------------
    # LAYERS PANEL
    # -----------------------------------------------------

    original_layers_init = (
        LayersPanel.__init__
    )

    def layers_init(
        self,
        *args,
        **kwargs
    ):
        original_layers_init(
            self,
            *args,
            **kwargs
        )

        _style_panel(self)

        if hasattr(
            self,
            "minimize_button"
        ):
            header = (
                self.minimize_button.parentWidget()
            )

            if header is not None:
                header.setFixedHeight(
                    UI_METRICS["panel_header_h"]
                )

                layout = header.layout()

                if layout is not None:
                    layout.setContentsMargins(
                        8,
                        4,
                        5,
                        4,
                    )

                    layout.setSpacing(
                        5
                    )

        for name in (
            "refresh_button",
            "minimize_button",
            "close_button",
        ):
            button = getattr(
                self,
                name,
                None,
            )

            if button is not None:
                button.setFixedSize(
                    UI_METRICS["header_icon"],
                    UI_METRICS["header_icon"],
                )

    LayersPanel.__init__ = (
        layers_init
    )

    # -----------------------------------------------------
    # PROPERTIES PANEL
    # -----------------------------------------------------

    if PropertiesPanel is not None:
        original_properties_init = (
            PropertiesPanel.__init__
        )

        def properties_init(
            self,
            *args,
            **kwargs
        ):
            original_properties_init(
                self,
                *args,
                **kwargs
            )

            _style_panel(self)

            if hasattr(
                self,
                "close_button"
            ):
                header = (
                    self.close_button.parentWidget()
                )

                if header is not None:
                    header.setFixedHeight(
                        UI_METRICS["panel_header_h"]
                    )

                    layout = header.layout()

                    if layout is not None:
                        layout.setContentsMargins(
                            8,
                            4,
                            5,
                            4,
                        )

                        layout.setSpacing(
                            5
                        )

                self.close_button.setFixedSize(
                    UI_METRICS["header_icon"],
                    UI_METRICS["header_icon"],
                )

        PropertiesPanel.__init__ = (
            properties_init
        )

    # -----------------------------------------------------
    # SHARED DOCK
    # -----------------------------------------------------

    if ToolPanelDock is not None:
        original_dock_init = (
            ToolPanelDock.__init__
        )

        def dock_init(
            self,
            *args,
            **kwargs
        ):
            original_dock_init(
                self,
                *args,
                **kwargs
            )

            _style_panel(self)

        ToolPanelDock.__init__ = (
            dock_init
        )

    # -----------------------------------------------------
    # WHOLE APPLICATION
    # -----------------------------------------------------

    original_main_init = (
        MainWindow.__init__
    )

    def main_init(
        self,
        *args,
        **kwargs
    ):
        original_main_init(
            self,
            *args,
            **kwargs
        )

        logo_path = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "branding"
            / "plan3d_logo.ico"
        )

        if logo_path.exists():
            icon = QIcon(str(logo_path))
            self.setWindowIcon(icon)

            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)

        app = QApplication.instance()

        if app is not None:
            app.setStyleSheet(
                GLOBAL_STYLE
            )

        _mark_named_widgets(
            self
        )

        _install_start_card_title_hover(
            self
        )

        _install_custom_top_menu(
            self
        )

    MainWindow.__init__ = (
        main_init
    )

