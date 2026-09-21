"""Zepp / Amazfit Device Source Catalog."""

DEVICE_CATALOG: dict[int, str] = {
    7930112: "Amazfit GTR 4 46mm",
    7930113: "Amazfit GTR 4 46mm",
    8192257: "Amazfit T-Rex 2",
    8257793: "Amazfit GTR 4",
    8257794: "Amazfit GTS 4",
    8323329: "Amazfit Active",
    8388865: "Amazfit Balance",
    8454401: "Amazfit Cheetah Pro",
    8454402: "Amazfit Cheetah (Round)",
    8454403: "Amazfit Cheetah (Square)",
    8519936: "Amazfit Balance 46mm",
    8519937: "Amazfit T-Rex Ultra",
    8519939: "Amazfit Balance 46mm",
    8651008: "Amazfit Helio Ring",
    8651009: "Amazfit Bip 5",
    8716544: "Amazfit T-Rex 3 48mm",
    8716545: "Amazfit Active Edge",
    8716547: "Amazfit T-Rex 3 48mm",
    8782081: "Amazfit Helio Ring",
    8847617: "Amazfit T-Rex 3",
    8913155: "Amazfit Active 2 44mm",
    9568512: "Amazfit Balance 2",
    9568513: "Amazfit Balance 2",
    9568515: "Amazfit Balance 2",
    9978112: "Amazfit Cheetah 2 Ultra",
    9978113: "Amazfit Cheetah 2 Ultra",
    10092800: "Amazfit Active 2 44mm",
    10092801: "Amazfit Active 2 44mm",
    10092803: "Amazfit Active 2 44mm",
    10092807: "Amazfit Active 2 44mm",
    10158337: "Amazfit Bip 6",
    10223873: "Amazfit Active 2 Square",
    10289410: "Amazfit Helio Strap",
    10289411: "Amazfit Helio Strap",
    10486017: "Amazfit Balance 2",
    10486019: "Amazfit Balance 2 XT",
    10551552: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10551553: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10551555: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10682624: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10682625: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10682627: "Amazfit T-Rex 3 Pro 48mm/44mm",
    10813697: "Amazfit Active MAX",
    10879233: "Amazfit T-Rex Ultra 2",
    10944769: "Amazfit Active 3 Premium",
    10944771: "Amazfit Active 3 Premium",
    11141377: "Amazfit Balance 3",
    11141379: "Amazfit Balance 3",
    11145472: "Amazfit Balance 3",
    11206915: "Amazfit Bip Max",
}

def resolve_device_name(device_source: int | None, display_name: str | None = None) -> str:
    """Resolve friendly device name from deviceSource code or user display name."""
    if display_name and display_name.strip():
        return display_name.strip()
    if device_source and device_source in DEVICE_CATALOG:
        return DEVICE_CATALOG[device_source]
    return "Amazfit Watch"
