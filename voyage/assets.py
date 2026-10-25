"""Local, attributed visual assets. Photos are representative, not fleet identities."""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "assets"
NAV_ICONS = ["layout-dashboard", "bot", "ship", "container", "anchor", "anchor", "chart-no-axes-combined", "file-chart-column", "files", "settings"]


def icon_uri(name):
    return "data:image/svg+xml;base64," + base64.b64encode((ROOT / "icons" / f"{name}.svg").read_bytes()).decode("ascii")


def icon_styles():
    rules = []
    for idx, name in enumerate(NAV_ICONS, 1):
        rules.append(f'[data-testid="stSidebar"] [role="radiogroup"]>div:nth-child({idx}) [data-testid="stRadioOption"]:before{{mask-image:url("{icon_uri(name)}");}}')
    for name in ["ship", "chart-pie", "fuel", "clock", "trending-up", "bot"]:
        rules.append(f'.icon-{name}{{mask-image:url("{icon_uri(name)}");}}')
    return "\n".join(rules)


def vessel_photo(vessel_id):
    number = int(vessel_id.split("-")[-1])
    return str(ROOT / "photos" / f"bulker-{(number-1)%4+1}.jpg")
