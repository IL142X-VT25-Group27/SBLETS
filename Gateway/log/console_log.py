import logging, coloredlogs


def setup_logger(debug, tofile):
    logging.getLogger("bleak").level = logging.DEBUG

    if tofile:
        pass

    else:

        level_colors = {
            "critical": {"bold": True, "color": "red"},
            "error": {"color": "red"},
            "warning": {"color": "yellow"},
            "info": {"color": "green"},
            "debug": {"color": "cyan"},
            "success": {"bold": True, "color": "green"},
        }
        field_colors = {
            "asctime": {},
            "levelname": {"color": "magenta"},
            "filename": {"color": "white", "faint": True},
        }
        coloredlogs.install(
            level=logging.DEBUG if debug else logging.INFO,
            fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(filename)s: %(message)s",
            datefmt="%H:%M:%S",
            level_styles=level_colors,
            field_styles=field_colors,
        )
