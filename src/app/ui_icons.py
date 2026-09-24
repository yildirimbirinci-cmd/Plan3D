from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


SVG_PATHS = {
    "close": """
        <line x1="6" y1="6" x2="18" y2="18"/>
        <line x1="18" y1="6" x2="6" y2="18"/>
    """,

    "minimize": """
        <line x1="6" y1="12" x2="18" y2="12"/>
    """,

    "refresh": """
        <path d="
            M18.2 8.1
            C16.8 5.8 14.5 4.5 11.8 4.5
            C7.6 4.5 4.2 7.9 4.2 12
            C4.2 16.1 7.6 19.5 11.8 19.5
            C15.1 19.5 17.9 17.4 19 14.4
        "/>
        <polyline points="18.2,4.8 18.2,8.4 14.6,8.4"/>
    """,
}


def _svg(kind, color):
    paths = SVG_PATHS[kind]

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg"
         width="24"
         height="24"
         viewBox="0 0 24 24">
        <g
            fill="none"
            stroke="{color}"
            stroke-width="2.3"
            stroke-linecap="round"
            stroke-linejoin="round">
            {paths}
        </g>
    </svg>
    """


def _render_svg(kind, size, color):
    renderer = QSvgRenderer(
        QByteArray(
            _svg(
                kind,
                color,
            ).encode("utf-8")
        )
    )

    # Render at 4x and downscale for cleaner antialiasing.
    scale = 4

    pixmap = QPixmap(
        size * scale,
        size * scale,
    )

    pixmap.fill(
        Qt.transparent
    )

    painter = QPainter(
        pixmap
    )

    painter.setRenderHint(
        QPainter.Antialiasing,
        True,
    )

    painter.setRenderHint(
        QPainter.SmoothPixmapTransform,
        True,
    )

    renderer.render(
        painter
    )

    painter.end()

    return pixmap.scaled(
        size,
        size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


def build_toolbar_icon(kind, size=20):
    icon = QIcon()

    normal = _render_svg(
        kind,
        size,
        "#D7D9DD",
    )

    hover = _render_svg(
        kind,
        size,
        "#78AEFF",
    )

    disabled = _render_svg(
        kind,
        size,
        "#66696E",
    )

    icon.addPixmap(
        normal,
        QIcon.Normal,
        QIcon.Off,
    )

    icon.addPixmap(
        hover,
        QIcon.Active,
        QIcon.Off,
    )

    icon.addPixmap(
        hover,
        QIcon.Selected,
        QIcon.Off,
    )

    icon.addPixmap(
        disabled,
        QIcon.Disabled,
        QIcon.Off,
    )

    return icon


def apply_window_tool_icon(
    button,
    kind,
    icon_size=None,
):
    if icon_size is None:
        icon_size = (
            20
            if kind == "refresh"
            else 18
        )

    button.setText("")

    button.setIcon(
        build_toolbar_icon(
            kind,
            icon_size,
        )
    )

    button.setIconSize(
        QSize(
            icon_size,
            icon_size,
        )
    )

    button.setFixedSize(
        28,
        28,
    )

    button.setToolButtonStyle(
        Qt.ToolButtonIconOnly
    )
